#!/usr/bin/env python3
"""
monitor_btp.py

Monitora il prezzo di alcuni BTP quotati sul MOT di Borsa Italiana per
cogliere opportunità di acquisto su Fineco. Per ogni BTP confronta il prezzo
attuale (ultimo disponibile) con una soglia configurata:

  - prezzo <= soglia  -> notifica desktop "OPPORTUNITÀ BTP" + messaggio Telegram
  - prezzo >  soglia  -> scrive una riga nel file di log btp_log.txt

Le notifiche Telegram usano il bot configurato in telegram_config.json
(bot_token e chat_id nella cartella principale del progetto).

Sorgente dati:
   Borsa Italiana -> pagina "dati-completi" del BTP, campo "Prezzo di
   riferimento" (con fallback sul "Prezzo ufficiale"). Yahoo Finance / yfinance
   non quotano i singoli BTP italiani, quindi la fonte ufficiale e' Borsa
   Italiana.

Ogni riga stampata a console e' prefissata con data e ora [YYYY-MM-DD HH:MM:SS].
I colori ANSI sono applicati solo quando l'output e' un terminale.

Uso:
    python3 monitor_btp.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

# Silenzia il logging interno delle librerie di rete (urllib3 usato da requests),
# che puo' essere verboso. Cosi' il log resta pulito in console e da cron.
import logging as _logging
_logging.disable(_logging.CRITICAL)
for _logger_name in ("urllib3", "requests"):
    _logging.getLogger(_logger_name).setLevel(_logging.CRITICAL)

# --- Configurazione dei BTP da monitorare ----------------------------------
# ISIN del BTP (usato per costruire la pagina Borsa Italiana).
# soglia: prezzo (in euro) al di sotto del quale scatta l'opportunita'.
BTP_CONFIG = [
    {"nome": "Btp Tf 4,40% Mg33",  "isin": "IT0005518128", "soglia": 100.00},
    {"nome": "Btp-1ag34 5%",       "isin": "IT0003535157", "soglia": 100.00},
    {"nome": "Btp-1fb37 4%",       "isin": "IT0003934657", "soglia": 94.75},
    {"nome": "Btp-1ag39 5%",       "isin": "IT0004286966", "soglia": 100.00},
    {"nome": "Btp-1st40 5%",       "isin": "IT0004532559", "soglia": 100.00},
    {"nome": "Btp Tf 4,75% St44",  "isin": "IT0004923998", "soglia": 95.69},
]

# --- Percorsi (basati sulla posizione dello script, robusti da cron) --------
BASE_DIR = Path(__file__).resolve().parent.parent      # .../BTP_Monitor
LOG_FILE = BASE_DIR / "log" / "btp_log.txt"            # righe BTP sopra soglia
RUN_LOG = BASE_DIR / "log" / "monitor_run.log"         # diario esecuzioni/errori
TELEGRAM_CONFIG = BASE_DIR / "telegram_config.json"    # credenziali bot Telegram

# --- Costanti per l'accesso a Borsa Italiana -------------------------------
BI_URL = ("https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp/"
          "dati-completi.html?isin={isin}&lang=it&mic=MOTX")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
}
TIMEOUT = 20  # secondi

# --- Codici colore ANSI (solo su terminale) --------------------------------
ROSSO = "\033[91m"
VERDE = "\033[92m"
GRASSETTO = "\033[1m"
RESET = "\033[0m"
USA_COLORI = sys.stdout.isatty()


# --- Funzioni di servizio ---------------------------------------------------

def log(messaggio="", errore=False):
    """Stampa una riga a console prefissata con data e ora.

    - messaggio: testo da stampare
    - errore:    se True scrive su stderr
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    flusso = sys.stderr if errore else sys.stdout
    if messaggio:
        print(f"[{timestamp}] {messaggio}", file=flusso)
    else:
        print(file=flusso)


def colora(testo, codice):
    """Applica un codice colore ANSI solo se siamo su terminale."""
    return f"{codice}{testo}{RESET}" if USA_COLORI else testo


def scrivi_log_file(riga):
    """Appende una riga al file btp_log.txt (BTP sopra soglia).

    Non solleva eccezioni: un problema di scrittura non blocca il monitoraggio.
    """
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(riga + "\n")
    except Exception as exc:
        log(f"Impossibile scrivere su {LOG_FILE}: {exc}", errore=True)


def invia_notifica(titolo, messaggio):
    """Mostra una notifica desktop con notify-send.

    Restituisce True se la notifica e' stata inviata, False altrimenti.
    Non solleva mai eccezioni: se notify-send non e' disponibile o fallisce
    (es. sessione grafica assente quando gira da cron), registra l'evento nel
    log di run e prosegue. Ricostruisce l'ambiente grafico (DISPLAY/DBUS)
    partendo da XDG_RUNTIME_DIR / UID corrente.
    """
    percorso = shutil.which("notify-send")
    if percorso is None:
        log("notify-send non disponibile: notifica saltata.", errore=True)
        return False

    env = os.environ.copy()
    runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    env.setdefault("DISPLAY", ":0")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={runtime}/bus")
    env.setdefault("XDG_RUNTIME_DIR", runtime)

    try:
        subprocess.run(
            [percorso, "-a", "BTP Monitor", titolo, messaggio],
            env=env, check=True, timeout=15,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        log(f"Notifica desktop inviata: {titolo}")
        return True
    except Exception as exc:
        log(f"Invio notifica non riuscito: {exc}", errore=True)
        return False


def carica_config_telegram():
    """Legge bot_token e chat_id da telegram_config.json.

    Restituisce il dict della config, oppure None se il file manca o non e'
    valido (registrando un warning, senza interrompere).
    """
    try:
        with open(TELEGRAM_CONFIG, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        log(f"{TELEGRAM_CONFIG.name} non trovato: notifiche Telegram saltate.",
            errore=True)
        return None
    except (json.JSONDecodeError, OSError) as exc:
        log(f"Errore lettura {TELEGRAM_CONFIG.name}: {exc}", errore=True)
        return None

    token = config.get("bot_token")
    chat_id = config.get("chat_id")
    if not token or not chat_id:
        log(f"Config Telegram incompleta in {TELEGRAM_CONFIG.name} "
            f"(servono 'bot_token' e 'chat_id').", errore=True)
        return None
    return config


def invia_telegram(messaggio):
    """Invia un messaggio Telegram via Bot API (parse_mode HTML).

    Legge token e chat_id da telegram_config.json e chiama:
        https://api.telegram.org/bot<TOKEN>/sendMessage
    con payload {"chat_id", "text", "parse_mode": "HTML"}.

    Restituisce True se l'invio riesce, False altrimenti. NON solleva mai
    eccezioni: in caso di errore (rete, token non valido, file mancante)
    stampa un warning nel log ma NON blocca l'esecuzione dello script, così il
    monitoraggio e le notifiche desktop proseguono comunque.
    """
    config = carica_config_telegram()
    if config is None:
        return False

    token = config["bot_token"]
    chat_id = config["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": messaggio, "parse_mode": "HTML"}

    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        # Telegram risponde 200 con {"ok": true, ...} anche sui messaggi ok.
        if resp.status_code == 200 and resp.json().get("ok"):
            log("Notifica Telegram inviata.")
            return True
        log(f"Telegram ha rifiutato il messaggio (HTTP {resp.status_code}): "
            f"{resp.text[:200]}", errore=True)
        return False
    except requests.RequestException as exc:
        log(f"Invio Telegram non riuscito (errore di rete): {exc}", errore=True)
        return False


# --- Sorgente dati: Borsa Italiana -----------------------------------------

def _numero_it(testo):
    """Converte un numero in formato italiano ('101,26') in float."""
    if testo is None:
        return None
    pulito = testo.replace(".", "").replace(",", ".").strip()
    try:
        return float(pulito)
    except ValueError:
        return None


def _estrai_campo(flat, etichetta):
    """Estrae il valore numerico accanto a un'etichetta nella tabella BI.

    Cerca il pattern: <strong>Etichetta</strong> ... <span ...>VALORE</span>
    """
    pattern = (re.escape(etichetta) + r"\s*</strong>\s*</span>\s*</td>\s*<td>\s*"
               r'<span class="t-text -right">\s*([0-9.,]+)')
    m = re.search(pattern, flat, re.IGNORECASE)
    return _numero_it(m.group(1)) if m else None


def prezzo_da_borsa_italiana(isin):
    """Legge il prezzo del BTP dalla pagina 'dati-completi' di Borsa Italiana.

    Usa 'Prezzo di riferimento' (equivalente all'ultimo prezzo di chiusura sul
    MOT) con fallback sul 'Prezzo ufficiale'. Restituisce (prezzo, etichetta,
    data_prezzo) oppure (None, motivo, None).
    """
    url = BI_URL.format(isin=isin)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        return None, f"Borsa Italiana errore HTTP ({exc})", None

    testo = resp.text
    flat = re.sub(r"\s+", " ", testo)

    prezzo = _estrai_campo(flat, "Prezzo di riferimento")
    etichetta = "Prezzo di riferimento"
    if prezzo is None or prezzo <= 0:
        prezzo = _estrai_campo(flat, "Prezzo ufficiale")
        etichetta = "Prezzo ufficiale"

    if prezzo is None or prezzo <= 0:
        titolo = re.search(r"<title>(.*?)</title>", testo, re.S | re.I)
        nome = titolo.group(1).strip() if titolo else isin
        return None, f"prezzo non trovato su Borsa Italiana ({nome})", None

    m_data = re.search(
        r"Data Pr Ufficiale\s*</strong>\s*</span>\s*</td>\s*<td>\s*"
        r'<span class="t-text -right">\s*([0-9/]+)', flat, re.IGNORECASE)
    data_prezzo = m_data.group(1) if m_data else "n/d"
    return prezzo, etichetta, data_prezzo


def ottieni_prezzo(btp):
    """Ottiene il prezzo di un BTP da Borsa Italiana.

    Restituisce un dict con: prezzo (float|None), fonte, dettaglio, data.
    """
    isin = btp["isin"]
    prezzo, etichetta, data = prezzo_da_borsa_italiana(isin)
    return {"prezzo": prezzo, "fonte": "Borsa Italiana",
            "dettaglio": etichetta, "data": data}


# --- Valutazione e notifica -------------------------------------------------

def valuta(btp, dati):
    """Confronta il prezzo con la soglia e applica la logica richiesta.

    - errore nel reperire il prezzo -> solo log di run
    - prezzo <= soglia -> notifica desktop OPPORTUNITÀ
    - prezzo >  soglia -> riga nel file btp_log.txt
    """
    nome = btp["nome"]
    soglia = btp["soglia"]
    prezzo = dati["prezzo"]

    if prezzo is None:
        log(colora(f"{nome}: ERRORE - {dati['dettaglio']}", ROSSO))
        return

    data_txt = f" del {dati['data']}" if dati["data"] not in (None, "n/d") else ""
    log(f"{nome}: {prezzo:.2f}€ (soglia {soglia:.2f}€) "
        f"[fonte: {dati['fonte']}{data_txt}]")

    if prezzo <= soglia:
        titolo = "🎯 OPPORTUNITÀ BTP"
        messaggio = f"{nome} è sceso a {prezzo:.2f}€ (Soglia: {soglia:.2f}€)"
        log(colora(f"  -> {messaggio}", ROSSO + GRASSETTO))
        invia_notifica(titolo, messaggio)

        # Notifica Telegram (formato HTML) in aggiunta a quella desktop.
        ora = datetime.now().strftime("%H:%M:%S")
        msg_tg = (
            "🚨 <b>OPPORTUNITÀ BTP</b>\n"
            f"📉 <b>{nome}</b> è sceso a <b>{prezzo:.2f}€</b>\n"
            f"🎯 Soglia di acquisto: {soglia:.2f}€\n"
            f"🕐 Rilevato alle: {ora}"
        )
        invia_telegram(msg_tg)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        riga = f"[{timestamp}] {nome} - {prezzo:.2f}€ (soglia {soglia:.2f}€)"
        scrivi_log_file(riga)


def main():
    log(colora("=== Monitoraggio BTP avviato ===", GRASSETTO))
    for btp in BTP_CONFIG:
        try:
            dati = ottieni_prezzo(btp)
        except Exception as exc:
            log(f"{btp['nome']}: errore imprevisto ({exc})", errore=True)
            continue
        valuta(btp, dati)
    log(colora("=== Monitoraggio BTP completato ===", GRASSETTO))


if __name__ == "__main__":
    main()

