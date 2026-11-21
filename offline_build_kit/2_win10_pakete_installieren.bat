@echo off
REM ============================================================
REM  Editor-Darkmode-MK1 Offline-Build-Kit v1.0.0
REM  Schritt 2 von 4 - auf dem Windows-10-PC ausfuehren.
REM  Python 3.11 (64-Bit) muss auf diesem PC bereits installiert sein.
REM
REM  Installiert PyInstaller komplett OFFLINE aus dem Ordner
REM  "offline_pakete\windows" (vom Mac-Skript) in eine neue
REM  virtuelle Umgebung "venv". Kein Internetzugriff noetig.
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo === Editor-Darkmode-MK1 Offline-Build-Kit v1.0.0 ===
echo === Schritt 2: Pakete offline installieren ===
echo.

if not exist "offline_pakete\windows\python_version.txt" (
    echo [FEHLER] Ordner "offline_pakete\windows" fehlt oder ist unvollstaendig.
    echo Bitte zuerst auf dem Mac "1_mac_pakete_herunterladen.sh"
    echo ausfuehren und den kompletten Ordner hierher kopieren.
    pause
    exit /b 1
)
if not exist "paketliste_windows.txt" (
    echo [FEHLER] "paketliste_windows.txt" fehlt - sie entsteht in Schritt 1 auf dem Mac.
    pause
    exit /b 1
)

set /p PYVER=<"offline_pakete\windows\python_version.txt"
echo Benoetigte Python-Version: %PYVER% ^(64-Bit^)

REM --- passendes Python suchen: erst "python", dann Python-Launcher "py" ---
set "PYCMD="
set "PYCHECK=import sys,struct;v=sys.argv[1].split('.');sys.exit(0 if list(sys.version_info[:2])==[int(v[0]),int(v[1])] and struct.calcsize('P')==8 else 1)"

where python >nul 2>nul
if not errorlevel 1 (
    python -c "%PYCHECK%" %PYVER% >nul 2>nul
    if not errorlevel 1 set "PYCMD=python"
)
if not defined PYCMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -%PYVER% -c "%PYCHECK%" %PYVER% >nul 2>nul
        if not errorlevel 1 set "PYCMD=py -%PYVER%"
    )
)
if not defined PYCMD (
    echo [FEHLER] Kein passendes Python %PYVER% ^(64-Bit^) gefunden.
    echo Gefunden wurde:
    python --version 2>nul
    py --list 2>nul
    echo Die Pakete aus Schritt 1 passen nur zu Python %PYVER% 64-Bit.
    pause
    exit /b 1
)
echo Verwende: %PYCMD%
%PYCMD% --version

REM --- Tkinter ist Teil von Python, muss aber bei der Installation angehakt sein ---
%PYCMD% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] Diesem Python fehlt "tcl/tk and IDLE" ^(Tkinter^).
    echo Python-Installer erneut starten, "Modify" waehlen und
    echo "tcl/tk and IDLE" anhaken.
    pause
    exit /b 1
)

echo.
echo [1/3] Pruefe die Pakete auf Vollstaendigkeit ^(SHA256^)...
if exist "offline_pakete\windows\SHA256SUMS.txt" (
    powershell -NoProfile -Command "$bad=0; Get-Content 'offline_pakete\windows\SHA256SUMS.txt' | Where-Object { $_.Trim() } | ForEach-Object { $h,$n = $_.Trim() -split '\s+',2; $n=$n.TrimStart('*'); try { if ((Get-FileHash -Algorithm SHA256 -LiteralPath ('offline_pakete\windows\'+$n) -ErrorAction Stop).Hash -ne $h) { Write-Host ('   DEFEKT: '+$n); $bad=1 } } catch { Write-Host ('   FEHLT: '+$n); $bad=1 } }; exit $bad"
    if errorlevel 1 (
        echo [FEHLER] Mindestens ein Paket ist beim Kopieren beschaedigt worden
        echo oder fehlt. Bitte den Ordner "offline_pakete" erneut kopieren.
        pause
        exit /b 1
    )
    echo    alle Pakete in Ordnung
) else (
    echo    ^(keine Pruefsummen-Datei vorhanden, ueberspringe^)
)

echo.
echo [2/3] Lege virtuelle Umgebung "venv" an ^(falls noch nicht vorhanden^)...
if not exist "venv\Scripts\python.exe" (
    %PYCMD% -m venv venv
    if errorlevel 1 (
        echo [FEHLER] Anlegen der virtuellen Umgebung fehlgeschlagen.
        pause
        exit /b 1
    )
) else (
    echo    ^(existiert bereits, ueberspringe^)
)

echo.
echo [3/3] Installiere Pakete rein aus "offline_pakete\windows"
echo       ^(--no-index = es wird NICHTS aus dem Internet geladen^)...
venv\Scripts\python.exe -m pip install --no-index --find-links="offline_pakete\windows" -r "paketliste_windows.txt"
if errorlevel 1 (
    echo.
    echo [FEHLER] Installation fehlgeschlagen.
    echo Haeufigste Ursache: die .whl-Dateien in "offline_pakete\windows" passen
    echo nicht zur Python-Version der venv. Dann den Ordner "venv" loeschen
    echo und dieses Skript erneut starten.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  FERTIG. PyInstaller steckt jetzt in der virtuellen
echo  Umgebung "venv" in diesem Ordner.
echo.
echo  Naechster Schritt: "3_win10_exe_aus_zip_bauen.bat" ausfuehren
echo  ^(liegt das Kit nicht im Projekt-Repo, vorher die
echo   Editor-Darkmode-MK1-.zip in diesen Ordner legen^).
echo ============================================================
echo.
pause
