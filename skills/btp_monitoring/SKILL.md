---
name: btp_monitoring
description: Istruzioni specializzate per il monitoraggio dei BTP su Borsa Italiana, gestione degli alert Telegram, delle soglie di acquisto e del logging sicuro. Usa questa skill quando l'utente chiede di controllare i BTP, modificare le soglie o aggiornare la logica di monitoraggio.
version: "1.0"
---

ISTRUZIONI OPERATIVE PER IL MONITORAGGIO BTP:
FONTE DATI: Usa sempre la libreria requests con un User-Agent realistico per scaricare i dati da Borsa Italiana. Non usare yfinance per i BTP italiani poiché i dati sono spesso incompleti o ritardati.
CONFIGURAZIONE SICURA: Leggi sempre i ticker dei BTP e le soglie di prezzo dal file di configurazione esistente. Non inserire mai valori fissi direttamente nel codice dello script.
NOTIFICHE TELEGRAM: Quando il prezzo scende sotto la soglia, invia un alert Telegram usando il file telegram_config.json. Il messaggio deve essere in formato HTML e contenere: nome del BTP, prezzo attuale, soglia di acquisto e orario. Gestisci gli eventuali errori di rete senza bloccare l'esecuzione dello script.
LOGGING: Registra ogni controllo nel file log/btp_log.txt con timestamp, nome del BTP e prezzo rilevato. Questo file è uno storico permanente e non deve essere soggetto a rotazione o cancellazione automatica.
SICUREZZA: Il file telegram_config.json contiene credenziali sensibili. Non mostrarne mai il contenuto in chat, non includerlo in eventuali repository Git e non condividerlo
