#!/bin/bash
# ============================================================
#  Editor-Darkmode-MK1 Offline-Build-Kit v1.0.0
#  Schritt 4 von 4 - auf dem MAC ausfuehren, NACHDEM Schritt 1
#  einmal erfolgreich lief. Braucht KEIN Internet.
#
#  Projektquelle (in dieser Reihenfolge):
#    1. genau eine Editor-Darkmode-MK1-.zip in diesem Ordner
#       -> wird nach "projekt" entpackt
#    2. keine .zip, aber das Kit liegt im Projekt-Repo
#       (Ordner offline_build_kit) -> baut direkt aus dem Repo
#
#  Installiert PyInstaller + tkinterdnd2 offline aus
#  "offline_pakete/mac" in die venv "venv_mac" und baut mit
#  Editor-Darkmode-MK1.spec die Mac-App - wie GitHub Actions.
# ============================================================

set -e
cd "$(dirname "$0")"
KITDIR="$(pwd)"

echo
echo "=== Editor-Darkmode-MK1 Offline-Build-Kit v1.0.0 ==="
echo "=== Schritt 4: macOS-App bauen ==="
echo

fehler() { echo; echo "[FEHLER] $*"; exit 1; }

[ -f offline_pakete/mac/mac_python.txt ] && [ -f paketliste_mac.txt ] \
    || fehler "Ordner 'offline_pakete/mac' fehlt. Bitte zuerst ./1_mac_pakete_herunterladen.sh ausfuehren."

# --- dasselbe Python wie beim Download (die Wheels passen genau dazu) ---
PYTHON="$(tr -d '\r\n' < offline_pakete/mac/mac_python.txt)"
[ -x "$PYTHON" ] || fehler "Python '$PYTHON' aus Schritt 1 existiert nicht mehr. Schritt 1 wiederholen."
echo "Verwende: $("$PYTHON" --version) ($PYTHON)"
"$PYTHON" -c "import tkinter" >/dev/null 2>&1 \
    || fehler "Diesem Python fehlt Tkinter. Python von python.org installieren und Schritt 1 wiederholen."

# --- Pakete pruefen (SHA256) ---
echo
echo "[1/4] Pruefe die Pakete auf Vollstaendigkeit (SHA256)..."
if [ -f offline_pakete/mac/SHA256SUMS.txt ]; then
    ( cd offline_pakete/mac && shasum -a 256 -c SHA256SUMS.txt >/dev/null ) \
        || fehler "Mindestens ein Paket in offline_pakete/mac ist beschaedigt. Schritt 1 wiederholen."
    echo "   alle Pakete in Ordnung"
else
    echo "   (keine Pruefsummen-Datei vorhanden, ueberspringe)"
fi

# --- venv anlegen und offline installieren ---
echo
echo "[2/4] Installiere Pakete offline in 'venv_mac'..."
if [ ! -x venv_mac/bin/python ]; then
    "$PYTHON" -m venv venv_mac
fi
venv_mac/bin/python -m pip install --no-index --find-links=offline_pakete/mac -r paketliste_mac.txt \
    || fehler "Installation fehlgeschlagen. Ordner 'venv_mac' loeschen und erneut starten."
venv_mac/bin/python -c "import PyInstaller, tkinter, tkinterdnd2" \
    || fehler "PyInstaller, Tkinter oder tkinterdnd2 fehlt in venv_mac."

# --- Projektquelle bestimmen ---
echo
echo "[3/4] Suche die Projektquelle..."
shopt -s nullglob
ZIPS=( *.zip )
shopt -u nullglob
SPEC=""
if [ ${#ZIPS[@]} -gt 1 ]; then
    printf '   - %s\n' "${ZIPS[@]}"
    fehler "Es liegen mehrere .zip-Dateien in diesem Ordner. Bitte nur die Projekt-.zip ablegen."
elif [ ${#ZIPS[@]} -eq 1 ]; then
    echo "Gefundenes Archiv: ${ZIPS[0]}"
    rm -rf projekt
    mkdir projekt
    unzip -q "${ZIPS[0]}" -d projekt || fehler "Entpacken fehlgeschlagen."
    SPEC="$(find projekt -name 'Editor-Darkmode-MK1.spec' -type f | head -n 1)"
    [ -n "$SPEC" ] || fehler "In der .zip wurde keine Editor-Darkmode-MK1.spec gefunden (ab Version 1.4.0)."
elif [ -f ../Editor-Darkmode-MK1.spec ]; then
    echo "Keine .zip gefunden - Kit liegt im Projekt-Repo, baue direkt daraus."
    SPEC="../Editor-Darkmode-MK1.spec"
else
    fehler "Keine Projektquelle gefunden. Bitte die Editor-Darkmode-MK1-.zip in diesen Ordner legen."
fi
PROJDIR="$(cd "$(dirname "$SPEC")" && pwd)"
SPEC="$PROJDIR/Editor-Darkmode-MK1.spec"
SRC="$PROJDIR/editor_darkmode.py"
[ -f "$SRC" ] && grep -q "Editor-Darkmode-MK1" "$SRC" \
    || fehler "editor_darkmode.py des Editor-Darkmode-MK1 fehlt in $PROJDIR"
APPVER="$(sed -n 's/^APP_VERSION *= *"\([^"]*\)".*/\1/p' "$SRC" | head -n 1)"
[ -n "$APPVER" ] || APPVER="0.0.0"
echo "Projektordner: $PROJDIR"
echo "Version: $APPVER"

# --- Bauen ---
echo
echo "[4/4] Baue Editor-Darkmode-MK1.app ..."
rm -rf build_tmp
( cd "$PROJDIR" && "$KITDIR/venv_mac/bin/python" -m PyInstaller --noconfirm --clean \
    --distpath "$KITDIR/build_tmp/dist" --workpath "$KITDIR/build_tmp/work" "$SPEC" ) \
    || fehler "Build der Mac-App fehlgeschlagen."
APP="build_tmp/dist/Editor-Darkmode-MK1.app"
[ -d "$APP" ] || fehler "PyInstaller lief durch, aber die App fehlt."

mkdir -p fertige_app
ZIPNAME="Editor-Darkmode-MK1-v${APPVER}-macos.zip"
rm -rf "fertige_app/Editor-Darkmode-MK1.app" "fertige_app/$ZIPNAME"
# ditto erhaelt Symlinks und Signatur des App-Bundles (wie im GitHub-Workflow)
ditto -c -k --sequesterRsrc --keepParent "$APP" "fertige_app/$ZIPNAME"
ditto "$APP" "fertige_app/Editor-Darkmode-MK1.app"
rm -rf build_tmp

echo
echo "============================================================"
echo " FERTIG!"
echo
echo " Im Ordner"
echo "   $KITDIR/fertige_app"
echo " liegt jetzt:"
ls -1 fertige_app | sed 's/^/   /'
echo
echo " Die App z. B. in den Ordner 'Programme' ziehen und starten."
echo " Die .zip ist zum Weitergeben gedacht (wie das GitHub-Release)."
echo "============================================================"
echo
