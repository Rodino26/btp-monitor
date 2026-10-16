#!/usr/bin/env bash
#
# vedi_grafico_btp.sh
#
# Apre il grafico settimanale report/btp_settimana.html nel browser Brave.
# Pensato per il doppio clic dal file manager: funziona sia da terminale sia
# da ambiente grafico. Se il file non esiste ancora, avvisa e propone di
# generarlo.
#
# Nota: Brave è spesso un'app Flatpak (sandbox) che NON può leggere /home,
# quindi il grafico viene copiato in /tmp e aperto da lì. Questo è il metodo
# collaudato (stesso approccio del progetto Euribor).

set -u

CARTELLA="$(cd "$(dirname "$0")" && pwd)"
FILE_HTML="$CARTELLA/report/btp_settimana.html"
GENERATORE="$CARTELLA/script/genera_grafico_btp_settimanale.py"

# --- Ambiente grafico (utile se lanciato in contesti minimi) ----------------
export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"

# --- Se il grafico non esiste, lo genero al volo ----------------------------
if [ ! -f "$FILE_HTML" ]; then
    echo "Grafico non ancora presente: lo genero..."
    if [ -f "$GENERATORE" ]; then
        python3 "$GENERATORE" --no-open || {
            echo "ERRORE: generazione del grafico non riuscita."
            exit 1
        }
    else
        echo "ERRORE: generatore non trovato ($GENERATORE)."
        exit 1
    fi
fi

# --- Apertura in Brave ------------------------------------------------------
# Caso 1: Brave nativo
if command -v brave-browser >/dev/null 2>&1; then
    nohup brave-browser --new-window "file://$FILE_HTML" >/dev/null 2>&1 &
    disown 2>/dev/null || true
    echo "Grafico aperto in Brave: $FILE_HTML"
    exit 0
fi

# Caso 2: Brave Flatpak (sandbox -> copio in /tmp)
if command -v flatpak >/dev/null 2>&1 && \
   flatpak list --app 2>/dev/null | grep -q 'com.brave.Browser'; then
    TMP_HTML="/tmp/btp_settimana.html"
    if cp "$FILE_HTML" "$TMP_HTML" 2>/dev/null && chmod 644 "$TMP_HTML" 2>/dev/null; then
        nohup flatpak run com.brave.Browser --new-window "file://$TMP_HTML" \
            >/dev/null 2>&1 &
        disown 2>/dev/null || true
        echo "Grafico aperto in Brave (via /tmp): $TMP_HTML"
        exit 0
    fi
fi

echo "ERRORE: Brave non trovato (né 'brave-browser' né Flatpak)."
echo "Apri manualmente questo file nel browser:"
echo "  $FILE_HTML"
exit 1
