# Editor-Darkmode-MK1 — exe und Mac-App ohne GitHub bauen

**Offline-Build-Kit v1.0.0** (für Editor-Darkmode-MK1 ab Version 1.4.0)

Der Mac lädt einmal alle Pakete herunter. Danach baut der Windows-10-PC die
**exe** und der Mac die **Mac-App**, beide ohne Internet. Gebaut wird mit
derselben Bauvorschrift (`Editor-Darkmode-MK1.spec`) und denselben
Paketversionen wie bei GitHub Actions. Das Ergebnis ist also identisch:

- `Editor-Darkmode-MK1-v<Version>-windows.exe`
- `Editor-Darkmode-MK1-v<Version>-macos.zip` (enthält `Editor-Darkmode-MK1.app`)

```
offline_build_kit/
├── 1_mac_pakete_herunterladen.sh      <- Mac, mit Internet
├── 2_win10_pakete_installieren.bat    <- Windows-10-PC
├── 3_win10_exe_aus_zip_bauen.bat      <- Windows-10-PC
├── 4_mac_app_aus_zip_bauen.sh         <- Mac, ohne Internet
└── ANLEITUNG.md                       <- diese Datei
```

**Woher kommt der Quellcode?** Die Skripte 3 und 4 nehmen

1. eine **Editor-Darkmode-MK1-`.zip`** (Projekt-Zip oder „Download ZIP“ von
   GitHub), die neben den Skripten liegt, oder
2. falls dort keine `.zip` liegt: das **Repo selbst**, wenn das Kit wie
   ausgeliefert im Ordner `offline_build_kit` des Projekts liegt.

---

## Voraussetzungen

| Rechner | benötigt |
|---|---|
| Mac | Python 3 von [python.org](https://www.python.org/downloads/macos/) (enthält Tkinter). Homebrew-Python geht auch, dann zusätzlich `brew install python-tk@<Version>`. |
| Windows-10-PC | Python **3.11 (64-Bit)**, bei der Installation „tcl/tk and IDLE“ angehakt (Standard). |

---

## Schritt 1 — auf dem Mac: Pakete herunterladen

```bash
cd <Pfad>/offline_build_kit
chmod +x *.sh
./1_mac_pakete_herunterladen.sh
```

Es entstehen

- `offline_pakete/windows`: `.whl`-Dateien für **Windows 64-Bit / Python 3.11**
  (PyInstaller samt Abhängigkeiten, inkl. `pefile` und `pywin32-ctypes`),
- `offline_pakete/mac`: `.whl`-Dateien für **genau dieses Python auf diesem Mac**
  (PyInstaller und `tkinterdnd2` für Drag & Drop),
- je eine Prüfsummen-Datei `SHA256SUMS.txt`,
- `paketliste_windows.txt` und `paketliste_mac.txt`.

Die Paketversionen kommen aus der `requirements-build.txt` des Projekts
(Projekt-`.zip` im Ordner oder umgebendes Repo), sonst gelten
`pyinstaller==6.16.0` und `tkinterdnd2==0.7.0`.

> Soll später mit einem anderen Python auf dem Mac gebaut werden:
> `MAC_PYTHON=/pfad/zu/python3 ./1_mac_pakete_herunterladen.sh`

**Danach auf den Windows-10-PC kopieren** (USB-Stick, Kabel, egal wie): den
kompletten Ordner `offline_build_kit` mit `offline_pakete`. Liegt das Kit nicht
mehr im Projekt-Repo, die Projekt-`.zip` **in denselben Ordner** legen.

---

## Schritt 2 — Windows-10-PC: Pakete installieren

1. Doppelklick auf **`2_win10_pakete_installieren.bat`**.
2. Das Skript
   - sucht ein passendes Python 3.11 (64-Bit): erst `python`, sonst `py -3.11`,
   - prüft, ob Tkinter vorhanden ist,
   - prüft per SHA256, dass beim Kopieren keine Paketdatei beschädigt wurde,
   - legt die virtuelle Umgebung `venv` an und installiert alles
     **ausschließlich** aus `offline_pakete\windows` (`--no-index`, kein Internet).
3. Am Ende erscheint `FERTIG.`

---

## Schritt 3 — Windows-10-PC: exe bauen

1. Doppelklick auf **`3_win10_exe_aus_zip_bauen.bat`**.
2. Das Skript
   - entpackt eine daneben liegende `.zip` nach `projekt` (höchstens **eine**
     `.zip` im Ordner) oder nimmt das umgebende Repo,
   - sucht `Editor-Darkmode-MK1.spec` und `editor_darkmode.py`,
   - liest die Versionsnummer aus `APP_VERSION`,
   - baut mit PyInstaller und der `.spec` des Projekts, genau wie GitHub Actions.
3. Ergebnis in **`fertige_exe`**:
   ```
   fertige_exe/
   └── Editor-Darkmode-MK1-v1.4.0-windows.exe
   ```

---

## Schritt 4 — auf dem Mac: Mac-App bauen

```bash
./4_mac_app_aus_zip_bauen.sh
```

Das Skript prüft die Pakete, legt `venv_mac` an, installiert alles offline aus
`offline_pakete/mac`, sucht die Projektquelle wie Schritt 3 und baut die App.
Ergebnis in **`fertige_app`**:

```
fertige_app/
├── Editor-Darkmode-MK1.app                  <- in "Programme" ziehen und starten
└── Editor-Darkmode-MK1-v1.4.0-macos.zip     <- zum Weitergeben
```

Die App wird für die Architektur des Macs gebaut, auf dem das Skript läuft
(Apple Silicon → arm64, Intel → x86_64).

---

## Neue Projektversion bauen

Neue `.zip` gegen die alte austauschen (bzw. das Repo aktualisieren) und
Schritt 3 bzw. 4 erneut starten. Schritt 1 und 2 müssen nur wiederholt werden,
wenn sich die `requirements-build.txt` des Projekts ändert.

---

## Fehlerbehebung

- **„Kein passendes Python 3.11 (64-Bit) gefunden“** (Schritt 2) →
  `python --version` bzw. `py --list` prüfen. Ein anderes Python? Dann im
  Mac-Skript oben `PY_VER="3.11"` anpassen und Schritt 1 wiederholen.
- **„Diesem Python fehlt tcl/tk“** (Schritt 2) → Python-Installer starten,
  „Modify“, „tcl/tk and IDLE“ anhaken.
- **„DEFEKT“ / „FEHLT“ bei der Paketprüfung** → Kopiervorgang unvollständig;
  `offline_pakete` erneut kopieren.
- **„venv mit PyInstaller wurde nicht gefunden“** (Schritt 3) → erst Schritt 2
  im selben Ordner erfolgreich durchlaufen lassen.
- **„mehrere .zip-Dateien“** → genau eine `.zip` neben die Skripte legen.
- **„keine Editor-Darkmode-MK1.spec gefunden“** → falsches Archiv oder
  Projektversion älter als 1.4.0.
- **„Diesem Python fehlt Tkinter“** (Mac) → Python von python.org installieren,
  Schritt 1 wiederholen.
- **Windows Defender meldet die neue exe** → normal bei frisch gebauten,
  unsignierten PyInstaller-Dateien: „Trotzdem ausführen“ bzw. Ausnahme eintragen.
- **macOS: „App kann nicht geöffnet werden“** (nur bei weitergegebener `.zip`)
  → einmal Rechtsklick auf die App › „Öffnen“ › „Öffnen“. Alternativ im
  Terminal: `xattr -cr /Applications/Editor-Darkmode-MK1.app`
