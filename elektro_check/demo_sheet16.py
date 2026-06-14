# -*- coding: utf-8 -*-
"""
DEMO (ne finalni nastroj): ukaze, jak chapu rusici krizky na jednom listu.
Pro kazdy krizek zjisti, PRES CO lezi (text nazvu / cara) a zaradi ho.
Vykresli list s ocislovanymi krizky a vypise tabulku.

Pouziti: py demo_sheet16.py <soubor.dwg>
"""
import sys
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ezdxf
from ezdxf.addons import odafc
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

from crosses_context import diag_lines, find_crosses

ODA_EXE = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
ezdxf.options.set("odafc-addon", "win_exec_path", ODA_EXE)


def texts(msp):
    """Vsechny texty (atributy bloku + samostatne TEXT/MTEXT) s pozici."""
    out = []
    for e in msp.query("INSERT"):
        for a in e.attribs:
            t = a.dxf.text.strip()
            if t:
                try:
                    p = a.dxf.insert
                    out.append((t, (p.x, p.y)))
                except Exception:
                    pass
    for e in msp.query("TEXT MTEXT"):
        t = (e.dxf.text if e.dxftype() == "TEXT" else e.text).strip()
        if t:
            try:
                p = e.dxf.insert
                out.append((t, (p.x, p.y)))
            except Exception:
                pass
    return out


def wires(msp):
    """Vodorovne/svisle cary delsi nez 8 = realne spoje (ne konektorove pahyly)."""
    out = []
    for e in msp.query("LINE"):
        s, t = e.dxf.start, e.dxf.end
        dx, dy = t.x - s.x, t.y - s.y
        L = math.hypot(dx, dy)
        ang = math.degrees(math.atan2(abs(dy), abs(dx)))
        if L > 8 and (ang < 10 or ang > 80):
            out.append(((s.x, s.y), (t.x, t.y)))
    return out


def pt_seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def nearest_text(pt, txts, rng=7.0):
    best, bd = None, rng
    for t, p in txts:
        d = math.hypot(pt[0] - p[0], pt[1] - p[1])
        if d < bd:
            bd, best = d, t
    return best


def classify(cross, txts, wrs):
    t = nearest_text(cross, txts)
    on_wire = any(pt_seg_dist(cross, a, b) < 1.5 for a, b in wrs)
    if t:
        up = t.upper()
        if up.startswith("HUB") and "_PORT" not in up:
            return "HUB zrušen", t
        if "_PORT" in up or up in ("X1", "X2", "X7", "X8"):
            return "PORT", t
        # jine zarizeni (ORx, I207x, 1Pxx ...)
        if any(c.isalpha() for c in t) and any(c.isdigit() for c in t) and len(t) <= 8:
            return "ZARIZENI zrušeno", t
    if on_wire:
        return "SPOJ zrušen", "(na čáře)"
    return "konektor", ""


COLORS = {"HUB zrušen": "red", "ZARIZENI zrušeno": "red",
          "SPOJ zrušen": "orange", "PORT": "deepskyblue", "konektor": "0.6"}


def main(path):
    doc = odafc.readfile(path)
    msp = doc.modelspace()
    crosses = find_crosses(diag_lines(msp), min_len=0.0, max_len=40.0, tol=3.0)
    txts, wrs = texts(msp), wires(msp)

    rows = []
    for i, c in enumerate(crosses, 1):
        kind, what = classify(c, txts, wrs)
        rows.append((i, c, kind, what))

    print("\n{} - krizku: {}".format(Path(path).name, len(crosses)))
    for i, c, kind, what in rows:
        if kind != "konektor":
            print("  #{:<2} ({:6.1f},{:6.1f})  {:18s} {}".format(i, c[0], c[1], kind, what))
    nconn = sum(1 for r in rows if r[2] == "konektor")
    print("  ... + {} konektoru (ignorovano)".format(nconn))

    # render
    fig = plt.figure(figsize=(24, 16))
    ax = fig.add_axes([0, 0, 1, 1])
    try:
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
    except Exception as ex:
        print("  varovani render: {}".format(ex))
    for i, c, kind, what in rows:
        col = COLORS.get(kind, "0.6")
        if kind == "konektor":
            continue
        ax.add_patch(plt.Circle(c, 10, fill=False, color=col, lw=2.5))
        ax.text(c[0] + 11, c[1] + 6, "#{} {}".format(i, kind), color=col, fontsize=9, weight="bold")
    out = Path(__file__).parent / (Path(path).stem + "_DEMO.png")
    fig.savefig(str(out), dpi=120)
    plt.close(fig)
    print("[PNG] {}".format(out))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
