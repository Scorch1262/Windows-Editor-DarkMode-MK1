#!/bin/bash
# Lokaler macOS-Build mit Internet (Python 3.10+ von python.org mit Tk).
# Ohne Internet: Offline-Build-Kit im Ordner offline_build_kit benutzen.
set -e
cd "$(dirname "$0")"
python3 -c "import tkinter" 2>/dev/null || {
    echo "[FEHLER] Dieses Python hat kein Tkinter. Bitte Python von python.org installieren"
    echo "         (oder bei Homebrew: brew install python-tk)."
    exit 1
}
python3 -m venv .venv_build
.venv_build/bin/python -m pip install -r requirements-build.txt
.venv_build/bin/python -m PyInstaller --noconfirm --clean Editor-Darkmode-MK1.spec
echo
echo "Fertig: dist/Editor-Darkmode-MK1.app"
