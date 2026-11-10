@echo off
rem Lokaler Build ohne GitHub Actions (Python 3.10+ muss installiert sein)
cd /d "%~dp0"
python -m pip install -r requirements-build.txt || goto :fehler
python tools\make_version_info.py || goto :fehler
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name Editor-Darkmode-MK1 ^
  --icon assets\editor.ico ^
  --add-data "assets\editor.ico;assets" ^
  --version-file build\version_info.txt ^
  editor_darkmode.py || goto :fehler
echo.
echo Fertig: dist\Editor-Darkmode-MK1.exe
pause
exit /b 0
:fehler
echo.
echo Build fehlgeschlagen.
pause
exit /b 1
