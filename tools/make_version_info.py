# -*- coding: utf-8 -*-
"""
Liest APP_VERSION aus editor_darkmode.py und schreibt die Windows-Dateieigenschaften
der exe (version_info.txt). Wird von Editor-Darkmode-MK1.spec benutzt.

Aufruf von Hand:  python tools/make_version_info.py
  -> gibt nur die Versionsnummer aus (für Skripte / GitHub Actions)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "editor_darkmode.py")


def read_version(src=SRC):
    with open(src, encoding="utf-8") as fh:
        m = re.search(r'^APP_VERSION\s*=\s*"([0-9]+(?:\.[0-9]+){1,3})"', fh.read(), re.M)
    if not m:
        sys.exit("APP_VERSION nicht gefunden")
    return m.group(1)


def write_version_file(out_dir, src=SRC):
    """Schreibt <out_dir>/version_info.txt und gibt den Pfad zurück."""
    version = read_version(src)
    parts = [int(p) for p in version.split(".")] + [0, 0, 0]
    tup = tuple(parts[:4])
    os.makedirs(out_dir, exist_ok=True)
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
    path = os.path.join(out_dir, "version_info.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


if __name__ == "__main__":
    print(read_version())
