# -*- coding: utf-8 -*-
"""
Liest APP_VERSION aus editor_darkmode.py, schreibt build/version_info.txt
(Dateieigenschaften der exe) und gibt die Versionsnummer aus.

Aufruf:  python tools/make_version_info.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "editor_darkmode.py")
OUT_DIR = os.path.join(ROOT, "build")


def read_version():
    with open(SRC, encoding="utf-8") as fh:
        m = re.search(r'^APP_VERSION\s*=\s*"([0-9]+(?:\.[0-9]+){1,3})"', fh.read(), re.M)
    if not m:
        sys.exit("APP_VERSION nicht gefunden")
    return m.group(1)


def main():
    version = read_version()
    parts = [int(p) for p in version.split(".")] + [0, 0, 0]
    tup = tuple(parts[:4])
    os.makedirs(OUT_DIR, exist_ok=True)
    text = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers=%(tup)s, prodvers=%(tup)s, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704B0', [
      StringStruct('FileDescription', 'Editor (Darkmode)'),
      StringStruct('FileVersion', '%(v)s'),
      StringStruct('InternalName', 'Editor-Darkmode-MK1'),
      StringStruct('OriginalFilename', 'Editor-Darkmode-MK1.exe'),
      StringStruct('ProductName', 'Editor-Darkmode-MK1'),
      StringStruct('ProductVersion', '%(v)s')])]),
    VarFileInfo([VarStruct('Translation', [0x0407, 1200])])
  ]
)
""" % {"tup": tup, "v": version}
    with open(os.path.join(OUT_DIR, "version_info.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(version)


if __name__ == "__main__":
    main()
