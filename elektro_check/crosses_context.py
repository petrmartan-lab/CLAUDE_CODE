# -*- coding: utf-8 -*-
"""Vypise dlouhe krizky a nejblizsi kabel/zarizeni - pro overeni i pro export."""
import sys
import math
from pathlib import Path

import ezdxf
from ezdxf.addons import odafc

ODA_EXE = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
ezdxf.options.set("odafc-addon", "win_exec_path", ODA_EXE)


def diag_lines(msp):
    out = []
    for e in msp.query("LINE"):
        s, t = e.dxf.start, e.dxf.end
        dx, dy = t.x - s.x, t.y - s.y
        L = math.hypot(dx, dy)
        ang = math.degrees(math.atan2(abs(dy), abs(dx)))
        if 10 < ang < 80:
            cls = "/" if dx * dy > 0 else "\\"
            out.append((cls, L, ((s.x + t.x) / 2, (s.y + t.y) / 2)))
    return out


def find_crosses(lines, min_len=8.0, max_len=40.0, tol=3.0):
    plus = [l for l in lines if l[0] == "/" and min_len <= l[1] <= max_len]
    minus = [l for l in lines if l[0] == "\\" and min_len <= l[1] <= max_len]
    res = []
    for p in plus:
        for m in minus:
            if math.hypot(p[2][0] - m[2][0], p[2][1] - m[2][1]) <= tol:
                res.append(((p[2][0] + m[2][0]) / 2, (p[2][1] + m[2][1]) / 2))
    uniq = []
    for c in res:
        if all(math.hypot(c[0] - u[0], c[1] - u[1]) > 2 for u in uniq):
            uniq.append((round(c[0], 1), round(c[1], 1)))
    return uniq


def blocks(msp, layer):
    out = []
    for e in msp.query("INSERT"):
        if e.dxf.layer == layer:
            a = {at.dxf.tag: at.dxf.text for at in e.attribs}
            try:
                ins = e.dxf.insert
                p = (ins.x, ins.y)
            except Exception:
                p = (None, None)
            out.append((a.get("VYPSANE_OZNACENI", ""), p))
    return out


def nearest(pt, items):
    best, bd = None, 1e9
    for name, p in items:
        if p[0] is None:
            continue
        d = math.hypot(pt[0] - p[0], pt[1] - p[1])
        if d < bd:
            bd, best = d, (name, round(d, 1))
    return best


def main(path):
    doc = odafc.readfile(path)
    msp = doc.modelspace()
    cr = find_crosses(diag_lines(msp))
    cabs = blocks(msp, "CABL")
    devs = blocks(msp, "SILS")
    print("\n{} - dlouhych krizku: {}".format(Path(path).name, len(cr)))
    for c in cr:
        print("  krizek ({:6.1f},{:6.1f})  nejbliz kabel: {}   zarizeni: {}".format(
            c[0], c[1], nearest(c, cabs), nearest(c, devs)))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
