#!/usr/bin/env bash
#
# aggiorna_grafico_se_necessario.sh
#
# Rete di sicurezza per il grafico BTP. Lo rigenera SOLO se:
#   - oggi la Borsa Italiana è aperta (--solo-se-aperta: salta weekend/festivi), E
#   - il report non è già stato aggiornato oggi (--max-eta 1).
#
# Serve quando il PC era spento all'ora del job principale (18:30): appena il
# PC è acceso (cron serale o login), la giornata di borsa saltata viene messa
# in pari. Nei giorni di chiusura non fa nulla.
#
# Non apre il browser (--no-open): il grafico si apre poi con doppio clic su
# vedi_grafico_btp.sh. Va bene anche in ambiente headless (cron).

set -u

CARTELLA="$(cd "$(dirname "$0")/.." && pwd)"
GENERATORE="$CARTELLA/script/genera_grafico_btp_settimanale.py"
LOG="$CARTELLA/log/grafico_run.log"
MAX_ETA=1   # rigenera se il report ha più di 1 giorno (giornata di borsa saltata)

mkdir -p "$CARTELLA/log"
ts="$(date '+%Y-%m-%d %H:%M:%S')"

if [ ! -f "$GENERATORE" ]; then
    echo "[$ts] ERRORE: generatore non trovato ($GENERATORE)" | tee -a "$LOG"
    exit 1
fi

# --solo-se-aperta: salta se borsa chiusa. --max-eta 1: salta se già fatto oggi.
# --no-open: genera in silenzio.
python3 "$GENERATORE" --no-open --solo-se-aperta --max-eta "$MAX_ETA" >> "$LOG" 2>&1
esito=$?
echo "[$ts] catch-up completato (exit=$esito)" >> "$LOG"
exit $esito

