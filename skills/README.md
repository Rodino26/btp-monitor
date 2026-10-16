# Skills — BTP_Monitor

Questo progetto espone **skill specializzate**: istruzioni operative pronte
all'uso che guidano l'AI nelle attività di monitoraggio, alert e manutenzione
del codice. Ogni skill vive nella propria cartella con un file `SKILL.md`.

## Indice delle skill

| Skill | Scopo principale |
|-------|------------------|
| [`btp_monitoring`](btp_monitoring/SKILL.md) | Monitoraggio dei BTP su Borsa Italiana: recupero prezzi, alert Telegram sotto soglia e logging sicuro. |

## btp_monitoring

**Scopo:** standardizzare il monitoraggio dei BTP — fonte dati Borsa Italiana
via `requests`, configurazione sicura di ticker e soglie, alert Telegram in
formato HTML e scrittura nello storico `log/btp_log.txt`.

**Quando usarla:** per controllare i BTP, modificare le soglie di acquisto o
aggiornare la logica di monitoraggio.

### Esempi di come richiederla in chat

> Usa la skill btp_monitoring per aggiungere un nuovo BTP con ISIN IT0005444507 e soglia a 90 euro.

Altri esempi:

> Usa la skill btp_monitoring per modificare la soglia di acquisto del Btp Tf 4,40% Mg33.

> Usa la skill btp_monitoring per spiegare come vengono inviati gli alert Telegram quando un prezzo scende sotto soglia.
