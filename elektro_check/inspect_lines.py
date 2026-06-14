# -*- coding: utf-8 -*-
"""
Diagnostika car - hleda krizky (dve cary do X = rusene spojeni).
Projde vsechny DWG ve slozce a vypise:
 - entity podle vrstvy
 - diagonalni cary podle vrstvy a delky
 - kandidaty na X-krizek (cara '/' a cara '\\' se stredy u sebe)

Pouziti: py inspect_lines.py <slozka s DWG>
"""

import sys
import math
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf
from ezdxf.addons import odafc

ODA_EXE = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
ezdxf.options.set("odafc-addon", "win_exec_path", ODA_EXE)


def line_info(e):
    s, t = e.dxf.start, e.dxf.end
    dx, dy = t.x - s.x, t.y - s.y
    length = math.hypot(dx, dy)
    ang = math.degrees(math.atan2(abs(dy), abs(dx)))     # 0=vodorovna, 90=svisla
    if ang < 10:
        cls = "H"
    elif ang > 80:
        cls = "V"
    else:
        cls = "/" if (dx * dy) > 0 else "\\"             # diagonala
    mid = ((s.x + t.x) / 2, (s.y + t.y) / 2)
    return cls, length, mid


def find_crosses(lines, mid_tol=3.0, min_len=0.0, max_len=15.0):
    """X-krizek = '/' cara a '\\' cara s blizkymi stredy, delky v <min_len, max_len>."""
    plus = [l for l in lines if l[0] == "/" and min_len <= l[1] <= max_len]
    minus = [l for l in lines if l[0] == "\\" and min_len <= l[1] <= max_len]
    crosses = []
    for p in plus:
        for m in minus:
            d = math.hypot(p[2][0] - m[2][0], p[2][1] - m[2][1])
            if d <= mid_tol:
                crosses.append((round(p[2][0], 1), round(p[2][1], 1),
                                p[3], round(p[1], 1), round(m[1], 1)))
    return crosses


def main(folder):
    folder = Path(folder)
    dwgs = sorted(folder.glob("*.dwg"))

    for dwg in dwgs:
        try:
            doc = odafc.readfile(str(dwg))
        except Exception as ex:
            print("{}: CHYBA {}".format(dwg.name, ex))
            continue
        msp = doc.modelspace()

        # entity podle vrstvy
        ent_layer = Counter((e.dxf.layer, e.dxftype()) for e in msp)
        # cary
        lines = []
        diag_by_layer = defaultdict(list)
        for e in msp.query("LINE"):
            cls, length, mid = line_info(e)
            lines.append((cls, length, mid, e.dxf.layer))
            if cls in ("/", "\\"):
                diag_by_layer[e.dxf.layer].append(round(length, 1))

        short = find_crosses(lines, max_len=8.0)            # konektory (~5.7)
        long_ = find_crosses(lines, min_len=8.0, max_len=40.0)  # potencialni ruseni

        # histogram delek diagonal
        all_diag_len = Counter()
        for lens in diag_by_layer.values():
            for L in lens:
                all_diag_len[round(L, 1)] += 1

        print("\n=== {} ===".format(dwg.name))
        print("  diagonal delky (x pocet): {}".format(dict(sorted(all_diag_len.items()))))
        print("  krizky kratke (konektory ~5.7): {}".format(len(short)))
        if long_:
            print("  >>> DLOUHE KRIZKY (mozna RUSENI): {}".format(len(long_)))
            for x, y, lay, l1, l2 in long_[:20]:
                print("        ({:.1f},{:.1f}) vrstva={} delky={}/{}".format(x, y, lay, l1, l2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Pouziti: py inspect_lines.py <slozka s DWG>")
        sys.exit(1)
    main(sys.argv[1])
