@echo off
REM ============================================================
REM  Editor-Darkmode-MK1 Offline-Build-Kit v1.0.0
REM  Schritt 3 von 4 - auf dem Windows-10-PC ausfuehren, NACHDEM
REM  Schritt 2 (Pakete installieren) einmal erfolgreich lief.
REM
REM  Projektquelle (in dieser Reihenfolge):
REM    1. genau eine Editor-Darkmode-MK1-.zip in diesem Ordner
REM       -> wird nach "projekt" entpackt
REM    2. keine .zip, aber das Kit liegt im Projekt-Repo
REM       (Ordner offline_build_kit) -> baut direkt aus dem Repo
REM
REM  Gebaut wird mit Editor-Darkmode-MK1.spec aus dem Projekt -
REM  genau wie der GitHub-Actions-Workflow. Komplett offline.
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"
set "KITDIR=%~dp0"

echo.
echo === Editor-Darkmode-MK1 Offline-Build-Kit v1.0.0 ===
echo === Schritt 3: Windows-exe bauen ===
echo.

if not exist "venv\Scripts\pyinstaller.exe" (
    echo [FEHLER] venv mit PyInstaller wurde nicht gefunden.
    echo Bitte zuerst "2_win10_pakete_installieren.bat" erfolgreich
    echo ausfuehren ^(im selben Ordner wie dieses Skript^).
    pause
    exit /b 1
)

REM --- .zip-Datei in diesem Ordner suchen ---
set "ZIPFILE="
set /a ZIPCOUNT=0
for %%f in ("*.zip") do (
    set "ZIPFILE=%%f"
    set /a ZIPCOUNT+=1
)
if %ZIPCOUNT% GTR 1 (
    echo [FEHLER] Es liegen mehrere .zip-Dateien in diesem Ordner:
    for %%f in ("*.zip") do echo    - %%f
    echo Bitte nur die gewuenschte Projekt-.zip-Datei hier ablegen.
    pause
    exit /b 1
)

set "SPEC="
if %ZIPCOUNT%==1 (
    echo Gefundenes Archiv: !ZIPFILE!
    echo.
    echo [1/3] Entpacke !ZIPFILE! nach "projekt" ...
    if exist "projekt" rmdir /s /q "projekt"
    mkdir "projekt"
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '!ZIPFILE!' -DestinationPath 'projekt' -Force"
    if errorlevel 1 (
        echo [FEHLER] Entpacken fehlgeschlagen.
        pause
        exit /b 1
    )
    REM --- Bauvorschrift des Projekts suchen (egal wie tief im Archiv) ---
    for /f "delims=" %%f in ('dir /s /b "projekt\Editor-Darkmode-MK1.spec" 2^>nul') do (
        if not defined SPEC set "SPEC=%%f"
    )
    if not defined SPEC (
        echo.
        echo [FEHLER] In der .zip-Datei wurde keine Editor-Darkmode-MK1.spec gefunden.
        echo Ist das wirklich Editor-Darkmode-MK1 ^(ab Version 1.4.0^)? Gefundener Inhalt:
        dir /b "projekt"
        pause
        exit /b 1
    )
) else (
    if exist "..\Editor-Darkmode-MK1.spec" (
        echo Keine .zip gefunden - Kit liegt im Projekt-Repo, baue direkt daraus.
        for %%x in ("..\Editor-Darkmode-MK1.spec") do set "SPEC=%%~fx"
        echo.
        echo [1/3] Projektquelle: Repo-Ordner
    ) else (
        echo [FEHLER] Keine Projektquelle gefunden.
        echo Bitte die Editor-Darkmode-MK1-.zip in diesen Ordner legen
        echo ^(neben dieses Skript^) und erneut ausfuehren.
        pause
        exit /b 1
    )
)
for %%y in ("!SPEC!") do set "PROJDIR=%%~dpy"
set "SRC=!PROJDIR!editor_darkmode.py"
if not exist "!SRC!" (
    echo [FEHLER] editor_darkmode.py fehlt neben der Bauvorschrift: !PROJDIR!
    pause
    exit /b 1
)
findstr /c:"Editor-Darkmode-MK1" "!SRC!" >nul 2>nul || (
    echo [FEHLER] !SRC! ist nicht der Editor-Darkmode-MK1.
    pause
    exit /b 1
)
echo Projektordner: !PROJDIR!

REM --- Versionsnummer aus APP_VERSION lesen ---
set "APPVER="
for /f "usebackq delims=" %%v in (`venv\Scripts\python.exe -c "import re,sys;m=re.search(r'^APP_VERSION\s*=\s*[\x22\x27]([0-9A-Za-z.\-]+)',open(sys.argv[1],encoding='utf-8').read(),re.M);print(m.group(1) if m else '')" "!SRC!"`) do set "APPVER=%%v"
if not defined APPVER (
    echo [WARNUNG] Keine APP_VERSION gefunden - nutze "0.0.0".
    set "APPVER=0.0.0"
)
set "EXEBASE=Editor-Darkmode-MK1"
set "EXENAME=!EXEBASE!-v!APPVER!-windows"
echo Version: !APPVER!

echo.
echo [2/3] Pruefe PyInstaller und Tkinter in der venv ...
venv\Scripts\python.exe -c "import PyInstaller, tkinter" >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] PyInstaller oder Tkinter fehlt in der venv. Bitte Schritt 2 erneut ausfuehren.
    pause
    exit /b 1
)
echo    PyInstaller + Tkinter ok

if not exist "fertige_exe" mkdir "fertige_exe"
if exist "fertige_exe\!EXENAME!.exe" del /q "fertige_exe\!EXENAME!.exe"
if exist "build_tmp" rmdir /s /q "build_tmp"

echo.
echo [3/3] Baue !EXENAME!.exe ...
REM Gebaut wird im Projektordner mit dessen .spec (wie im GitHub-Workflow),
REM Ausgabe und Zwischendateien landen im Kit-Ordner.
pushd "!PROJDIR!"
"!KITDIR!venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean ^
    --distpath "!KITDIR!build_tmp\dist" --workpath "!KITDIR!build_tmp\work" ^
    "!SPEC!"
set "PYIERR=!errorlevel!"
popd
if not "!PYIERR!"=="0" (
    echo [FEHLER] Build von !EXENAME!.exe fehlgeschlagen.
    pause
    exit /b 1
)
if not exist "build_tmp\dist\!EXEBASE!.exe" (
    echo [FEHLER] PyInstaller lief durch, aber die exe fehlt.
    pause
    exit /b 1
)
move /y "build_tmp\dist\!EXEBASE!.exe" "fertige_exe\!EXENAME!.exe" >nul

REM Aufraeumen der PyInstaller-Zwischendateien
if exist "build_tmp" rmdir /s /q "build_tmp"

echo.
echo ============================================================
echo  FERTIG!
echo.
echo  Im Ordner
echo    %~dp0fertige_exe
echo  liegt jetzt:
dir /b "fertige_exe"
echo.
echo  Die exe kann ueberall abgelegt und gestartet werden. Daneben
echo  entsteht beim Beenden die Einstellungsdatei
echo  Editor-Darkmode-MK1.ini.
echo ============================================================
echo.
pause
