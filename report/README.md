# Report BTP Monitor

Questa cartella è destinata ad accogliere i **report** generati dal
monitoraggio dei BTP (es. riepiloghi periodici, export in CSV/HTML dello
storico dei prezzi, grafici di andamento rispetto alle soglie).

Lo script `script/monitor_btp.py` non scrive qui durante il normale
funzionamento: i dati di esecuzione finiscono in:

- `../log/btp_log.txt` → storico dei BTP **sopra** soglia (una riga per BTP);
- `../log/monitor_run.log` → output completo delle esecuzioni via cron.

Per consultare la documentazione generale del progetto vedi `../README.md`.
