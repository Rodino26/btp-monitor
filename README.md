# BTP Monitor

Monitoraggio del prezzo di alcuni BTP quotati sul MOT di Borsa Italiana per
cogliere opportunità di acquisto su Fineco.

## Cosa fa

Per ognuno dei BTP configurati confronta il prezzo attuale (ultimo disponibile)
con una soglia:

- **prezzo ≤ soglia** → invia una notifica desktop
  `🎯 OPPORTUNITÀ BTP: <Nome> è sceso a <Prezzo>€ (Soglia: <Soglia>€)`
- **prezzo > soglia** → aggiunge una riga al file `log/btp_log.txt`
  con data, ora, nome del BTP e prezzo.

## Struttura

```
BTP_Monitor/
├── script/
│   └── monitor_btp.py     # lo script di monitoraggio
├── log/
│   ├── btp_log.txt        # storico BTP sopra soglia (un riga per BTP/run)
│   └── monitor_run.log    # diario delle esecuzioni (output di cron)
└── report/
    └── README.md          # questo documento
```

## BTP monitorati

| Nome BTP            | ISIN         | Soglia (€) |
|---------------------|--------------|-----------:|
| Btp Tf 4,40% Mg33   | IT0005518128 | 100.00     |
| Btp-1ag34 5%        | IT0003535157 | 100.00     |
| Btp-1fb37 4%        | IT0003934657 | 94.75      |
| Btp-1ag39 5%        | IT0004286966 | 100.00     |
| Btp-1st40 5%        | IT0004532559 | 100.00     |
| Btp Tf 4,75% St44   | IT0004923998 | 95.69      |

## Sorgente dati

I prezzi sono letti da **Borsa Italiana** (pagina "dati-completi" del MOT),
campo *Prezzo di riferimento* (equivalente all'ultimo prezzo di chiusura sul
MOT), con fallback sul *Prezzo ufficiale*. La fonte è la fonte ufficiale dei
BTP quotati sul MOT. La data del prezzo rilevata è mostrata nell'output.

> Nota: inizialmente lo script usava yfinance come richiesto, ma Yahoo Finance
> **non quota i singoli BTP italiani** nel formato `ISIN.MI` (verificato: nessun
> dato restituito). Per questo la sorgente è Borsa Italiana.

## Esecuzione manuale

```bash
python3 /home/radam/Documenti/CLINE/BTP_Monitor/script/monitor_btp.py
```

## Automazione (cron)

Due esecuzioni al giorno negli orari di borsa, alle **11:00** e alle **17:15**:

```
0  11 * * * DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000 /usr/bin/python3 .../monitor_btp.py >> .../log/monitor_run.log 2>&1
15 17 * * * DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000 /usr/bin/python3 .../monitor_btp.py >> .../log/monitor_run.log 2>&1
```

Le variabili `DISPLAY`/`DBUS_SESSION_BUS_ADDRESS`/`XDG_RUNTIME_DIR` servono a
`notify-send` per mostrare le notifiche anche quando lo script gira da cron.

Per modificare/rimuovere la pianificazione: `crontab -e`.

## Grafico settimanale interattivo

Lo script `script/genera_grafico_btp_settimanale.py` genera un grafico HTML
interattivo (Plotly) dell'andamento dei BTP negli **ultimi 7 giorni lavorativi**,
con una linea colorata per BTP, le soglie di acquisto (linee rosse tratteggiate),
griglia, zoom e hover.

- **Fonte dati:** API "grafici" di Borsa Italiana (chiusure giornaliere).
- **Output:** `report/btp_settimana.html` (autonomo, si apre anche offline).
- **Automazione:** **ogni giorno alle 18:30** (nei giorni in cui Borsa Italiana
  è aperta) il cron lo genera in silenzio (`--no-open`). L'opzione
  `--solo-se-aperta` fa saltare sabato, domenica e festività.

### Come aprire il grafico

- **Doppio clic** su `vedi_grafico_btp.sh` (nella cartella principale del
  progetto): apre `report/btp_settimana.html` in Brave.
- Oppure da terminale: `./vedi_grafico_btp.sh`
- Oppure apri a mano il file `report/btp_settimana.html` con un browser.

> Il calendario segue **Borsa Italiana** (non i festivi civili): la borsa è
> aperta il 6 gen, 2 giu, 1 nov, 8 dic, mentre chiude il 24 e 31 dic e per
> Pasqua (Venerdì Santo e Pasquetta). Nei giorni di chiusura il grafico non
> viene rigenerato (i prezzi non cambierebbero).

### Reti di sicurezza (se il PC è spento all'ora del job)

| Quando | Cosa fa | Configurato in |
|---|---|---|
| Ogni giorno 18:30 | genera il report (solo se borsa aperta, `--solo-se-aperta`) | cron |
| Ogni giorno 19:05 | rigenera **solo se** borsa aperta e il report non è di oggi (`--solo-se-aperta --max-eta 1`) | cron (`aggiorna_grafico_se_necessario.sh`) |
| Al login grafico | idem, con 10s di ritardo dall'avvio | `~/.config/autostart/btp-monitor-aggiorna-report.desktop` |
| Doppio clic / manuale | genera al volo | `vedi_grafico_btp.sh` |

Il cuore sono due opzioni: `--solo-se-aperta` (salta weekend/festività di borsa)
e `--max-eta N` (non riscarica nulla se il report è più recente di N giorni).
Così, se il PC era spento alle 18:30, appena viene acceso la giornata di borsa
saltata viene messa in pari automaticamente, senza chiamate di rete inutili.

### Rotazione dei log

I log `log/grafico_run.log` e `log/monitor_run.log` sono ruotati ogni giorno
alle **19:00** con logrotate (config: `log/logrotate_btp.conf`), mantenendo
gli **ultimi 30 giorni** di archivi compressi. Stesso approccio del progetto
Euribor. Grazie a `copytruncate` non è mai necessario riavviare i processi.


## Dipendenze

- `requests` (già presente nel sistema, usata per leggere Borsa Italiana e per le notifiche Telegram)
- `notify-send` (pacchetto `libnotify-bin`) per le notifiche desktop

> `yfinance` è stata rimossa: Yahoo Finance non quota i singoli BTP, quindi la
> sorgente è esclusivamente Borsa Italiana.

## Notifiche Telegram

Oltre alla notifica desktop (`notify-send`), quando un BTP scende a/sotto la
soglia lo script invia anche un messaggio **Telegram** con lo stesso alert,
formattato così:

```
🚨 OPPORTUNITÀ BTP
📉 <nome BTP> è sceso a <prezzo>€
🎯 Soglia di acquisto: <soglia>€
🕐 Rilevato alle: <ora>
```

### Configurazione
Le credenziali del bot stanno in `telegram_config.json` (cartella principale
del progetto):

```json
{
  "bot_token": "<token del bot>",
  "chat_id": "<id della chat>"
}
```

- Crea il bot con [@BotFather](https://t.me/BotFather) per ottenere il `bot_token`.
- Il `chat_id` è l'id della chat/destinatario (per un chat privato, avvia il bot
  e recupera l'id, es. con `@userinfobot`).
- `telegram_config.json` è nel `.gitignore` (contiene un segreto: non va versionato).

### Se il bot non riesce a inviare
L'invio è **best-effort e non bloccante**: se manca il file, il token è errato
(HTTP 401) o la rete è assente, lo script stampa un warning nel log di run
(`log/monitor_run.log`) e **prosegue normalmente**. Il monitoraggio prezzi e le
notifiche desktop non vengono mai interrotti da un problema Telegram. Telegram
non richiede Display/DBUS, quindi funziona anche quando lo script gira da cron.
