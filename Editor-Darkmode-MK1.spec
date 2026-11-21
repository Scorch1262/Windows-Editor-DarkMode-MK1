# -*- mode: python ; coding: utf-8 -*-
#
# Gemeinsame PyInstaller-Bauvorschrift für
#   * Windows:  dist/Editor-Darkmode-MK1.exe   (eine Datei, ohne Konsole)
#   * macOS:    dist/Editor-Darkmode-MK1.app   (App-Bundle)
#
# Benutzt von GitHub Actions, build_local.bat / build_local_mac.sh und dem
# Offline-Build-Kit – damit sind alle Builds identisch.
#
#   pyinstaller --noconfirm --clean Editor-Darkmode-MK1.spec

import os
import sys

ROOT = os.path.abspath(SPECPATH)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_version_info  # noqa: E402

APP = "Editor-Darkmode-MK1"
VERSION = make_version_info.read_version(os.path.join(ROOT, "editor_darkmode.py"))
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

ICO = os.path.join(ROOT, "assets", "editor.ico")
ICNS = os.path.join(ROOT, "assets", "editor.icns")

hiddenimports = []
if IS_MAC:
    # Drag & Drop aufs Fenster (tkdnd); die passende .dylib sammelt der
    # tkinterdnd2-Hook aus pyinstaller-hooks-contrib ein.
    hiddenimports.append("tkinterdnd2")

a = Analysis(
    [os.path.join(ROOT, "editor_darkmode.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(ICO, "assets")],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

if IS_MAC:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP,
        debug=False,
        strip=False,
        upx=False,
        console=False,
        argv_emulation=False,
        icon=ICNS,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP)
    app = BUNDLE(
        coll,
        name=APP + ".app",
        icon=ICNS,
        bundle_identifier="de.editor-darkmode.mk1",
        version=VERSION,
        info_plist={
            "CFBundleName": APP,
            "CFBundleDisplayName": "Editor",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            # Dunkle Fensterrahmen auch bei hellem System-Erscheinungsbild erlauben
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "11.0",
            # Im Finder unter "Öffnen mit" für Textdateien anbieten
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Textdokument",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": [
                    "public.plain-text", "public.text", "public.source-code",
                    "public.script", "public.log", "public.comma-separated-values-text",
                    "public.json", "public.xml",
                ],
            }],
        },
    )
else:
    version_file = None
    if IS_WIN:
        version_file = make_version_info.write_version_file(workpath)
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP,
        debug=False,
        strip=False,
        upx=False,
        console=False,
        icon=ICO if IS_WIN else None,
        version=version_file,
    )
