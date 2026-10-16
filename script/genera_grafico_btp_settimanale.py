#!/usr/bin/env python3
"""
genera_grafico_btp_settimanale.py

Genera un grafico interattivo HTML (Plotly) con l'andamento settimanale dei
prezzi dei BTP monitorati, per cogliere a colpo d'occhio le opportunità di
acquisto su Fineco.

Fonte dati:
   Borsa Italiana - API "grafici" (grafici.borsaitaliana.it). Si scarica lo
   storico OHLCV dell'ultimo mese e si tengono le chiusure degli ultimi 7
   giorni lavorativi. L'API è protetta da WAF Imperva + token JWT anonimo:
   il token viene estratto dalla pagina "interactive-chart" e riutilizzato.

Il grafico contiene:
   - una linea colorata per ogni BTP (blu, verde, arancione, rosso, viola, marrone)
   - asse X: date degli ultimi 7 giorni lavorativi
   - asse Y: prezzo in euro
   - legenda interattiva con i nomi dei BTP
   - titolo "Andamento Settimanale BTP - Portafoglio Fineco"
   - griglia attiva
   - linea rossa orizzontale tratteggiata per la soglia di acquisto di ogni BTP
   - zoom e hover sui punti con i valori esatti

Output:
   report/btp_settimana.html  (sovrascritto ad ogni esecuzione)

Argomenti:
   --no-open   genera solo il file HTML senza aprirlo nel browser.

Uso:
   python3 genera_grafico_btp_settimanale.py            # genera e apre
   python3 genera_grafico_btp_settimanale.py --no-open  # solo genera
"""

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

try:
    import plotly.graph_objects as go
except Exception as exc:  # pragma: no cover
    print(f"ERRORE: plotly non disponibile ({exc}). Installa con: pip install plotly")
    sys.exit(1)

# --- Percorsi (basati sulla posizione dello script, robusti da cron) --------
BASE_DIR = Path(__file__).resolve().parent.parent          # .../BTP_Monitor
CARTELLA_REPORT = BASE_DIR / "report"
FILE_OUTPUT = CARTELLA_REPORT / "btp_settimana.html"

# --- Costanti Borsa Italiana (API grafici) ----------------------------------
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
URL_WARMUP = ("https://grafici.borsaitaliana.it/interactive-chart/"
              "IT0003128367-XMIL?lang=it")
RE_TOKEN = re.compile(r'token="([^"]+)"')
URL_STORICO = ("https://grafici.borsaitaliana.it/api/instruments/"
               "{isin},XMIL,ISIN/history/period")
PERIODO = "1M"             # finestra scaricata; poi filtriamo gli ultimi 7 gg
GIORNI = 7                 # quanti giorni lavorativi mostrare
TIMEOUT = 30               # secondi
PAUSA = 0.4                # pausa tra una chiamata storia e l'altra

# Colori distinti per le linee dei BTP (richiesta: blu, verde, arancione, rosso...)
COLORI = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd", "#8c564b"]


# --- Lettura della configurazione BTP da monitor_btp.py --------------------
def carica_config_btp():
    """Importa BTP_CONFIG (nome, isin, soglia) da monitor_btp.py.

    Cosi' nomi e soglie restano allineate al monitor senza duplicarli.
    In caso di problemi, usa una configurazione di ripiego.
    """
    percorso = Path(__file__).resolve().parent / "monitor_btp.py"
    try:
        spec = importlib.util.spec_from_file_location("monitor_btp", percorso)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        config = getattr(modulo, "BTP_CONFIG", None)
        if config:
            return config
    except Exception as exc:
        print(f"ATTENZIONE: impossibile leggere la config da monitor_btp.py "
              f"({exc}); uso la configurazione di ripiego.")
    # Ripiego (coerente con monitor_btp.py)
    return [
        {"nome": "Btp Tf 4,40% Mg33", "isin": "IT0005518128", "soglia": 100.00},
        {"nome": "Btp-1ag34 5%",      "isin": "IT0003535157", "soglia": 100.00},
        {"nome": "Btp-1fb37 4%",      "isin": "IT0003934657", "soglia": 94.75},
        {"nome": "Btp-1ag39 5%",      "isin": "IT0004286966", "soglia": 100.00},
        {"nome": "Btp-1st40 5%",      "isin": "IT0004532559", "soglia": 100.00},
        {"nome": "Btp Tf 4,75% St44", "isin": "IT0004923998", "soglia": 95.69},
    ]


# --- Accesso all'API Borsa Italiana -----------------------------------------
def ottieni_token(sessione):
    """Estrae il token JWT anonimo dalla pagina interactive-chart."""
    risposta = sessione.get(URL_WARMUP, timeout=TIMEOUT)
    risposta.raise_for_status()
    match = RE_TOKEN.search(risposta.text)
    if not match:
        raise RuntimeError("Token JWT non trovato nella pagina interactive-chart")
    return match.group(1)


def scarica_storico(sessione, token, isin):
    """Scarica lo storico per un ISIN. None se non disponibile.

    Restituisce una lista di punti ordinati per data:
        [{"data": date, "chiusura": float}, ...]
    """
    url = URL_STORICO.format(isin=isin)
    try:
        risposta = sessione.get(
            url, params={"period": PERIODO},
            headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        print(f"  {isin}: errore di rete ({exc})")
        return None

    if risposta.status_code == 429:  # rate limit: attendo e riprovo una volta
        print(f"  {isin}: rate limit (429), attendo...")
        time.sleep(4)
        risposta = sessione.get(
            url, params={"period": PERIODO},
            headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)

    if risposta.status_code != 200:
        print(f"  {isin}: HTTP {risposta.status_code} ({risposta.text[:80]})")
        return None

    try:
        dati = risposta.json()
    except ValueError:
        print(f"  {isin}: risposta non JSON")
        return None

    punti_raw = ((dati.get("history") or {}).get("historyDt")) or []
    punti = []
    for p in punti_raw:
        dt = p.get("dt")
        prezzo = p.get("closePx")
        if prezzo is None:
            prezzo = p.get("lastPx")
        if dt is None or prezzo is None:
            continue
        try:
            data = datetime.strptime(dt, "%Y%m%d").date()
        except ValueError:
            continue
        punti.append({"data": data, "chiusura": float(prezzo)})

    punti.sort(key=lambda x: x["data"])
    return punti


# --- Costruzione del grafico -------------------------------------------------
def costruisci_grafico(serie):
    """Crea la figura Plotly.

    serie: lista di dict {nome, colore, soglia, punti:[{data, chiusura}, ...]}
    """
    fig = go.Figure()

    for s in serie:
        date = [p["data"] for p in s["punti"]]
        prezzi = [p["chiusura"] for p in s["punti"]]

        # Linea del BTP + marcatori
        fig.add_trace(go.Scatter(
            x=date,
            y=prezzi,
            mode="lines+markers",
            name=s["nome"],
            line=dict(color=s["colore"], width=2),
            marker=dict(size=7),
            hovertemplate=(f"<b>{s['nome']}</b><br>%{{x|%d %b %Y}}<br>"
                           f"%{{y:.2f}} €<extra></extra>"),
        ))

        # Soglia di acquisto: linea rossa orizzontale tratteggiata
        fig.add_hline(
            y=s["soglia"],
            line=dict(color="red", width=1.5, dash="dash"),
            annotation_text=f"Soglia {s['nome']} ({s['soglia']:.2f} €)",
            annotation_position="right",
            annotation_font=dict(color="red", size=10),
        )

    fig.update_layout(
        title="Andamento Settimanale BTP - Portafoglio Fineco",
        xaxis_title="Data",
        yaxis_title="Prezzo (€)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        margin=dict(l=50, r=60, t=90, b=40),
    )
    # Griglia attiva su entrambi gli assi per facilitare la lettura
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="lightgray")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="lightgray")
    return fig


# --- Apertura nel browser (Brave) -------------------------------------------
def apri_in_brave(percorso_html):
    """Apre il file HTML in Brave, se disponibile.

    Brave è spesso un'app Flatpak: in sandbox non può leggere /home, quindi il
    file viene copiato in /tmp e aperto da lì (metodo collaudato nel progetto
    Euribor). Non solleva eccezioni.
    """
    try:
        # Caso 1: Brave nativo (comando brave-browser)
        brave = shutil.which("brave-browser")
        if brave:
            subprocess.Popen([brave, "--new-window", f"file://{percorso_html}"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Grafico aperto in Brave: {percorso_html}")
            return True

        # Caso 2: Brave Flatpak (sandbox: copia in /tmp)
        if shutil.which("flatpak"):
            elenco = subprocess.run(["flatpak", "list", "--app"],
                                    capture_output=True, text=True).stdout
            if "com.brave.Browser" in elenco:
                tmp_html = "/tmp/btp_settimana.html"
                shutil.copy(percorso_html, tmp_html)
                subprocess.Popen(
                    ["flatpak", "run", "com.brave.Browser", "--new-window",
                     f"file://{tmp_html}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Grafico aperto in Brave (via /tmp): {tmp_html}")
                return True

        print("Brave non trovato (né 'brave-browser' né Flatpak). "
              f"Apri manualmente: {percorso_html}")
        return False
    except Exception as exc:
        print(f"Errore nell'apertura del browser: {exc}")
        return False


# --- Calendario di Borsa Italiana (giorni di chiusura) ---------------------
# Giorni in cui il MOT è CHIUSO. Non coincide esatto coi festivi civili: la
# borsa è aperta il 6 gen, 2 giu, 1 nov, 8 dic; chiude invece il 24 e 31 dic e
# il Venerdì Santo. Per i BTP conta il calendario di borsa (senza dati nuovi,
# il grafico sarebbe identico al giorno prima).
CHIUSURE_FISSE = {
    (1, 1),    # Capodanno
    (4, 25),   # Festa della Liberazione
    (5, 1),    # Festa del Lavoro
    (8, 15),   # Ferragosto / Assunzione
    (12, 24),  # Vigilia di Natale
    (12, 25),  # Natale
    (12, 26),  # Santo Stefano
    (12, 31),  # Ultimo dell'anno
}


def pasqua(anno):
    """Domenica di Pasqua con l'algoritmo di Butcher (Gregoriano anonimo)."""
    a = anno % 19
    b = anno // 100
    c = anno % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = ((h + l - 7 * m + 114) % 31) + 1
    return date(anno, mese, giorno)


def e_giorno_di_borsa(giorno=None):
    """True se 'giorno' è un giorno in cui il MOT è aperto (lun-ven, non festivo).

    Esclude sabato/domenica e i giorni di chiusura di Borsa Italiana, inclusi
    Venerdì Santo (Pasqua - 2) e Lunedì dell'Angelo/Pasquetta (Pasqua + 1).
    """
    if giorno is None:
        giorno = date.today()
    if giorno.weekday() >= 5:               # 5=sabato, 6=domenica
        return False
    if (giorno.month, giorno.day) in CHIUSURE_FISSE:
        return False
    p = pasqua(giorno.year)
    if giorno in (p - timedelta(days=2), p + timedelta(days=1)):
        return False
    return True


# --- Catch-up: controllo età del report -------------------------------------
def report_troppo_recente(max_eta_giorni):
    """True se il report HTML esiste ed è stato modificato meno di N giorni fa.

    Usato con --max-eta per rigenerare solo se il report è assente o vecchio.
    Così i job automatici (cron giornaliero / login) non riscaricano dati
    quando il grafico settimanale è già fresco.
    """
    if not FILE_OUTPUT.exists():
        return False
    eta = datetime.now().timestamp() - FILE_OUTPUT.stat().st_mtime
    return eta < max_eta_giorni * 86400


# --- Main --------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Genera il grafico settimanale interattivo dei BTP.")
    parser.add_argument("--no-open", action="store_true",
                        help="Genera solo il file HTML senza aprirlo nel browser.")
    parser.add_argument("--max-eta", type=int, default=None, metavar="GIORNI",
                        help="Rigenera solo se il file HTML non esiste oppure ha "
                             "più di GIORNI giorni. Utile per il catch-up "
                             "automatico (es. --max-eta 6).")
    parser.add_argument("--solo-se-aperta", action="store_true",
                        help="Non genera nulla se oggi la Borsa Italiana è "
                             "chiusa (weekend o festività). Pensato per "
                             "l'esecuzione automatica quotidiana da cron.")
    args = parser.parse_args()

    # Se richiesto, salta l'esecuzione nei giorni di chiusura della borsa.
    if args.solo_se_aperta and not e_giorno_di_borsa():
        oggi = date.today()
        print(f"Borsa Italiana chiusa oggi ({oggi:%d/%m/%Y}): grafico non generato.")
        return

    # Catch-up: se richiesto, salta la generazione quando il report è recente.
    if args.max_eta is not None and report_troppo_recente(args.max_eta):
        print(f"Report già aggiornato (età < {args.max_eta} giorni): "
              f"nessuna rigenerazione.")
        return

    config = carica_config_btp()
    print(f"Scarico lo storico degli ultimi {GIORNI} giorni lavorativi per "
          f"{len(config)} BTP da Borsa Italiana...")

    sessione = requests.Session()
    sessione.headers.update({"User-Agent": UA,
                             "Accept-Language": "it-IT,it;q=0.9"})

    try:
        token = ottieni_token(sessione)
    except Exception as exc:
        print(f"ERRORE: impossibile ottenere il token da Borsa Italiana ({exc}).")
        sys.exit(1)

    # Finestra: torno indietro di qualche giorno extra per garantire 7 giorni
    # lavorativi anche con weekend/festività.
    limite = datetime.now().date() - timedelta(days=GIORNI + 3)

    serie = []
    for indice, btp in enumerate(config):
        isin = btp["isin"]
        punti = scarica_storico(sessione, token, isin)
        time.sleep(PAUSA)
        if not punti:
            print(f"  {btp['nome']} ({isin}): nessun dato storico, escluso.")
            continue

        # Tieni solo gli ultimi GIORNI giorni lavorativi più recenti
        punti_recenti = [p for p in punti if p["data"] >= limite][-GIORNI:]
        if not punti_recenti:
            print(f"  {btp['nome']} ({isin}): dati troppo vecchi, escluso.")
            continue

        print(f"  {btp['nome']} ({isin}): {len(punti_recenti)} giorni "
              f"({punti_recenti[0]['data']:%d/%m} → "
              f"{punti_recenti[-1]['data']:%d/%m})")
        serie.append({
            "nome": btp["nome"],
            "soglia": float(btp["soglia"]),
            "colore": COLORI[indice % len(COLORI)],
            "punti": punti_recenti,
        })

    if not serie:
        print("Nessun dato disponibile: grafico non generato.")
        sys.exit(1)

    CARTELLA_REPORT.mkdir(parents=True, exist_ok=True)
    fig = costruisci_grafico(serie)

    # include_plotlyjs=True incorpora Plotly nel file: grafico autonomo e
    # apribile anche OFFLINE (nessuna connessione richiesta per la resa).
    fig.write_html(FILE_OUTPUT, include_plotlyjs=True)
    print(f"\nGrafico salvato in: {FILE_OUTPUT}")

    if args.no_open:
        print("Modalità --no-open: file non aperto nel browser.")
    else:
        apri_in_brave(str(FILE_OUTPUT))


if __name__ == "__main__":
    main()

