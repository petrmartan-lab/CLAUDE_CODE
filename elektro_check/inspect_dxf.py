# -*- coding: utf-8 -*-
"""
Faze A - diagnostika struktury DWG/DXF.
Prevede jeden DWG -> DXF pres ODA File Converter a vypise strukturu,
abychom vedeli jak jsou stitky a razitko zakodovane.

Pouziti: py inspect_dxf.py <soubor.dwg>
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf
from ezdxf.addons import odafc

ODA_EXE = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
ezdxf.options.set("odafc-addon", "win_exec_path", ODA_EXE)


def load(path):
    path = Path(path)
    if path.suffix.lower() == ".dwg":
        print("[..] Prevadim DWG -> DXF pres ODA...")
        return odafc.readfile(str(path))
    return ezdxf.readfile(str(path))


def main(path):
    doc = load(path)
    msp = doc.modelspace()

    print("\n=== VRSTVY (layers) ===")
    for layer in sorted(doc.layers, key=lambda l: l.dxf.name):
        print("  {}".format(layer.dxf.name))

    print("\n=== POCTY ENTIT (modelspace) ===")
    counts = Counter(e.dxftype() for e in msp)
    for typ, n in counts.most_common():
        print("  {:12s} {}".format(typ, n))

    print("\n=== UKAZKY TEXT / MTEXT (prvnich 40) ===")
    n = 0
    for e in msp:
        if e.dxftype() in ("TEXT", "MTEXT"):
            txt = e.dxf.text if e.dxftype() == "TEXT" else e.text
            txt = txt.replace("\n", "\\n")[:40]
            try:
                ins = e.dxf.insert
                pos = "({:.0f},{:.0f})".format(ins.x, ins.y)
            except Exception:
                pos = "(?)"
            print("  [{}] layer={:14s} {} {!r}".format(
                e.dxftype()[:5], e.dxf.layer, pos, txt))
            n += 1
            if n >= 40:
                break

    print("\n=== INSERT BLOKY + ATRIBUTY (prvnich 25) ===")
    block_names = Counter()
    n = 0
    for e in msp:
        if e.dxftype() == "INSERT":
            block_names[e.dxf.name] += 1
            if n < 25:
                attribs = [(a.dxf.tag, a.dxf.text) for a in e.attribs]
                if attribs:
                    print("  blok '{}' layer={}".format(e.dxf.name, e.dxf.layer))
                    for tag, val in attribs:
                        print("       {} = {!r}".format(tag, val))
                    n += 1
    print("\n  -- prehled nazvu bloku --")
    for name, c in block_names.most_common(30):
        print("  {:20s} x{}".format(name, c))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Pouziti: py inspect_dxf.py <soubor.dwg>")
        sys.exit(1)
    main(sys.argv[1])
