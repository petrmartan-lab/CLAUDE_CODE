# -*- coding: utf-8 -*-
"""Ke kazdemu krizku najde zarizeni (SILS blok), pres jehoz obrys lezi = ruseni zarizeni."""
import sys
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.addons import odafc

from crosses_context import diag_lines, find_crosses

ODA_EXE = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
ezdxf.options.set("odafc-addon", "win_exec_path", ODA_EXE)


def device_boxes(msp):
    """Vrati [(tag, extmin, extmax)] pro vsechny SILS bloky."""
    out = []
    for e in msp.query("INSERT"):
        if e.dxf.layer != "SILS":
            continue
        tag = next((a.dxf.text for a in e.attribs if a.dxf.tag == "VYPSANE_OZNACENI"), "")
        try:
            ext = bbox.extents([e])
            if ext.has_data:
                out.append((tag, ext.extmin, ext.extmax))
        except Exception:
            pass
    return out


def containing_device(pt, boxes, margin=2.0):
    """Vrati tag zarizeni, jehoz obrys (s rezervou) obsahuje bod pt."""
    hits = []
    for tag, lo, hi in boxes:
        if lo.x - margin <= pt[0] <= hi.x + margin and lo.y - margin <= pt[1] <= hi.y + margin:
            area = (hi.x - lo.x) * (hi.y - lo.y)
            hits.append((area, tag))
    if not hits:
        return None
    return min(hits)[1]   # nejmensi obsahujici box = nejtesnejsi


def main(path):
    doc = odafc.readfile(path)
    msp = doc.modelspace()

    # vsechny krizky (kratke i dlouhe)
    lines = diag_lines(msp)
    all_cr = find_crosses(lines, min_len=0.0, max_len=40.0, tol=3.0)
    boxes = device_boxes(msp)

    over_dev, on_conn = [], []
    for c in all_cr:
        tag = containing_device(c, boxes)
        if tag:
            over_dev.append((c, tag))
        else:
            on_conn.append(c)

    print("\n{}".format(Path(path).name))
    print("  krizku celkem: {}".format(len(all_cr)))
    print("  PRES ZARIZENI (ruseni zarizeni): {}".format(len(over_dev)))
    for c, tag in over_dev:
        print("      ({:6.1f},{:6.1f}) -> zarizeni '{}'".format(c[0], c[1], tag))
    print("  mimo zarizeni (konektory NEBO ruseni spoje): {}".format(len(on_conn)))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
