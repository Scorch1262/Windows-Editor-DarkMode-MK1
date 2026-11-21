@echo off
rem Lokaler Windows-Build mit Internet (Python 3.10+ muss installiert sein).
rem Ohne Internet: Offline-Build-Kit im Ordner offline_build_kit benutzen.
cd /d "%~dp0"
python -m pip install -r requirements-build.txt || goto :fehler
python -m PyInstaller --noconfirm --clean Editor-Darkmode-MK1.spec || goto :fehler
echo.
echo Fertig: dist\Editor-Darkmode-MK1.exe
pause
exit /b 0
:fehler
echo.
echo Build fehlgeschlagen.
pause
exit /b 1
