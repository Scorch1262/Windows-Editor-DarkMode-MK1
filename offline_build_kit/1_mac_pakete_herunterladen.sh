#!/bin/bash
# ============================================================
#  Editor-Darkmode-MK1 Offline-Build-Kit v1.0.0
#  Schritt 1 von 4 - auf dem MAC mit Internetverbindung ausfuehren.
#
#  Laedt alle fuer den Build benoetigten Python-Pakete als fertige
#  .whl-Dateien herunter:
#    offline_pakete/windows  -> fuer den Win10-PC (64-Bit, Python 3.11)
#    offline_pakete/mac      -> fuer diesen Mac (Mac-App, Schritt 4)
#  Auf dem Mac selbst wird nichts installiert.
#
#  Danach: diesen ganzen Ordner (+ ggf. die Projekt-.zip) per
#  USB-Stick/AirDrop/Kabel auf den Win10-PC kopieren.
# ============================================================

set -e
cd "$(dirname "$0")"

KIT_VERSION="1.0.0"
# Python-Version des Windows-10-PCs (Major.Minor)
PY_VER="3.11"
PY_TAG="${PY_VER/./}"            # 3.11 -> 311

# Standardwerte (wie requirements-build.txt im Repo)
DEFAULT_PYINSTALLER="pyinstaller==6.16.0"
DEFAULT_TKDND="tkinterdnd2==0.7.0"

echo
echo "=== Editor-Darkmode-MK1 Offline-Build-Kit v${KIT_VERSION} ==="
echo "=== Schritt 1: Pakete fuer Windows 10 und macOS herunterladen ==="
echo

# ------------------------------------------------------------
# Python finden. Fuer den Windows-Teil ist die Version egal (nur
# Download-Werkzeug). Fuer die Mac-App (Schritt 4) muss es dasselbe
# Python sein, mit dem spaeter gebaut wird - und es braucht Tkinter.
# Anderes Python? Vor dem Start setzen:  MAC_PYTHON=/pfad/zu/python3
# ------------------------------------------------------------
PYTHON="${MAC_PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for cand in python3 python; do
        if command -v "$cand" >/dev/null 2>&1; then
            PYTHON="$(command -v "$cand")"
            break
        fi
    done
fi
if [ -z "$PYTHON" ]; then
    echo "[FEHLER] Es wurde kein Python auf diesem Mac gefunden."
    echo "Bitte einmalig installieren - am besten von"
    echo "https://www.python.org/downloads/macos/ (enthaelt Tkinter)."
    exit 1
fi
echo "Verwende: $("$PYTHON" --version) ($PYTHON)"

# ------------------------------------------------------------
# Paketversionen bestimmen: aus der requirements-build.txt des
# Projekts (Projekt-.zip hier im Ordner oder umgebendes Repo),
# sonst Standardwerte.
# ------------------------------------------------------------
REQS=""
for z in *.zip; do
    [ -f "$z" ] || continue
    SPEC_IN_ZIP=$(unzip -Z1 "$z" 2>/dev/null | grep -E '(^|/)Editor-Darkmode-MK1\.spec$' | head -n 1 || true)
    [ -n "$SPEC_IN_ZIP" ] || continue
    REQ_IN_ZIP="$(dirname "$SPEC_IN_ZIP")/requirements-build.txt"
    REQ_IN_ZIP="${REQ_IN_ZIP#./}"
    REQS=$(unzip -p "$z" "$REQ_IN_ZIP" 2>/dev/null | tr -d '\r' || true)
    [ -n "$REQS" ] && echo "Projekt-Archiv gefunden: $z  -> nutze dessen requirements-build.txt"
    break
done
if [ -z "$REQS" ] && [ -f "../requirements-build.txt" ]; then
    REQS=$(tr -d '\r' < ../requirements-build.txt)
    echo "Kit liegt im Projekt-Repo -> nutze ../requirements-build.txt"
fi

PYI_LINE=$(printf '%s\n' "$REQS" | sed 's/#.*//' | grep -iE '^[[:space:]]*pyinstaller' | head -n 1 | tr -d ' ' || true)
TKDND_LINE=$(printf '%s\n' "$REQS" | sed 's/#.*//; s/;.*//' | grep -iE '^[[:space:]]*tkinterdnd2' | head -n 1 | tr -d ' ' || true)
[ -n "$PYI_LINE" ] || PYI_LINE="$DEFAULT_PYINSTALLER"
[ -n "$TKDND_LINE" ] || TKDND_LINE="$DEFAULT_TKDND"

# Paketlisten fuer Schritt 2 (Windows) und Schritt 4 (Mac)
printf '%s\n' "$PYI_LINE" > paketliste_windows.txt
printf '%s\n%s\n' "$PYI_LINE" "$TKDND_LINE" > paketliste_mac.txt
echo "Paketliste Windows (paketliste_windows.txt):"
sed 's/^/   /' paketliste_windows.txt
echo "Paketliste Mac (paketliste_mac.txt):"
sed 's/^/   /' paketliste_mac.txt

rm -rf offline_pakete
mkdir -p offline_pakete/windows offline_pakete/mac
echo "$PY_VER" > offline_pakete/windows/python_version.txt

echo
echo "Aktualisiere pip (falls moeglich)..."
"$PYTHON" -m pip install --upgrade pip --quiet 2>/dev/null \
    || echo "   (pip-Aktualisierung uebersprungen - kein Problem)"

# ------------------------------------------------------------
# Windows-Pakete
# WICHTIG: "pip download --platform win_amd64" waehlt zwar korrekt
# Windows-Wheels aus, wertet bedingte Abhaengigkeiten (z. B.
# "sys_platform == 'win32'") aber anhand DIESES Macs aus.
# PyInstaller braucht unter Windows "pefile" und "pywin32-ctypes" -
# deshalb werden beide hier explizit ergaenzt.
# ------------------------------------------------------------
cp paketliste_windows.txt offline_reqs_win_tmp.txt
{
    echo "pefile>=2022.5.30"
    echo "pywin32-ctypes>=0.2.0"
} >> offline_reqs_win_tmp.txt

echo
echo "[1/2] Lade Wheels fuer Windows 64-Bit, Python ${PY_VER}..."
"$PYTHON" -m pip download -r offline_reqs_win_tmp.txt -d offline_pakete/windows \
    --platform win_amd64 --python-version "$PY_TAG" --implementation cp --abi "cp$PY_TAG" \
    --only-binary=:all:
rm -f offline_reqs_win_tmp.txt
# Wheels nur fuer macOS werden unter Windows nicht gebraucht
rm -f offline_pakete/windows/macholib-*.whl

for pkg in pyinstaller pefile pywin32_ctypes; do
    if ! ls offline_pakete/windows/${pkg}-*.whl >/dev/null 2>&1; then
        echo "[FEHLER] Kein Wheel fuer '${pkg}' (Windows) heruntergeladen."
        exit 1
    fi
done

# ------------------------------------------------------------
# Mac-Pakete (fuer genau dieses Python auf diesem Mac)
# ------------------------------------------------------------
echo
echo "[2/2] Lade Wheels fuer diesen Mac ($("$PYTHON" --version))..."
MAC_OK=1
if "$PYTHON" -m pip download -r paketliste_mac.txt -d offline_pakete/mac --only-binary=:all:; then
    for pkg in pyinstaller tkinterdnd2; do
        if ! ls offline_pakete/mac/${pkg}-*.whl >/dev/null 2>&1; then
            echo "[WARNUNG] Kein Wheel fuer '${pkg}' (Mac) heruntergeladen."
            MAC_OK=0
        fi
    done
else
    echo "[WARNUNG] Download der Mac-Pakete fehlgeschlagen."
    MAC_OK=0
fi
"$PYTHON" -c "import sys;print(sys.executable)" > offline_pakete/mac/mac_python.txt
"$PYTHON" -c "import sys;print('%d.%d' % sys.version_info[:2])" > offline_pakete/mac/python_version.txt
if ! "$PYTHON" -c "import tkinter" >/dev/null 2>&1; then
    echo "[WARNUNG] Dieses Python hat kein Tkinter - Schritt 4 (Mac-App) wird so nicht"
    echo "          funktionieren. Python von python.org installieren (oder bei Homebrew"
    echo "          'brew install python-tk@<Version>') und Schritt 1 wiederholen."
    MAC_OK=0
fi

# Pruefsummen fuer die Kontrolle auf dem Windows-PC / Mac
for d in windows mac; do
    ( cd "offline_pakete/$d" && { shasum -a 256 *.whl > SHA256SUMS.txt 2>/dev/null \
        || sha256sum *.whl > SHA256SUMS.txt; } ) || true
done

echo
echo "Heruntergeladen (Windows):"
ls -1 offline_pakete/windows | sed 's/^/   /'
echo "Heruntergeladen (Mac):"
ls -1 offline_pakete/mac | sed 's/^/   /'

echo
echo "============================================================"
echo " FERTIG."
echo
echo " Windows-exe: kopiere den kompletten Ordner"
echo "   $(pwd)"
echo " (inkl. offline_pakete/, paketliste_windows.txt und der .bat-Skripte)"
echo " auf den Windows-10-PC, z. B. per USB-Stick. Liegt das Kit nicht"
echo " im Projekt-Repo, die Projekt-.zip in denselben Ordner legen."
echo
if [ "$MAC_OK" = "1" ]; then
    echo " Mac-App: auf DIESEM Mac jetzt ./4_mac_app_aus_zip_bauen.sh starten"
    echo " (geht auch ohne Internet)."
else
    echo " Mac-App: siehe Warnungen oben - Schritt 4 ist so noch nicht moeglich."
fi
echo "============================================================"
echo
