# -*- coding: utf-8 -*-
"""
Detekce zrusenych prvku z rusicich krizku (✕).
Pravidlo (potvrzeno): ✕ = vzdy zruseni. Konektory jsou obloucky, nikdy krizky.
  - ✕ pres nazev HUBu/zarizeni  -> zruseny HUB/zarizeni
  - ✕ na care / na portu        -> zruseny spoj (propojeni)
"""
import math

from crosses_context import diag_lines, find_crosses


def all_texts(msp):
    """Vsechny texty (atributy bloku + TEXT/MTEXT) s pozici a vyskou."""
    out = []
    for e in msp.query("INSERT"):
        for a in e.attribs:
            t = a.dxf.text.strip()
            if t:
                try:
                    p = a.dxf.insert
                    out.append((t, p.x, p.y, a.dxf.height or 2.5))
                except Exception:
                    pass
    for e in msp.query("TEXT MTEXT"):
        t = (e.dxf.text if e.dxftype() == "TEXT" else e.text).strip()
        if t:
            try:
                p = e.dxf.insert
                out.append((t, p.x, p.y, getattr(e.dxf, "height", 2.5) or 2.5))
            except Exception:
                pass
    return out


def sils_tags(msp):
    """Mnozina oznaceni zarizeni (SILS bloky)."""
    s = set()
    for e in msp.query("INSERT"):
        if e.dxf.layer == "SILS":
            for a in e.attribs:
                if a.dxf.tag == "VYPSANE_OZNACENI" and a.dxf.text.strip():
                    s.add(a.dxf.text.strip())
    return s


def cable_positions(msp):
    """Pozice kabelu = pozice atributu VYPSANE_OZNACENI (insert bloku je sablonovy 36,-20!)."""
    out = []
    for e in msp.query("INSERT"):
        if e.dxf.layer == "CABL":
            tag, pos = "", None
            for a in e.attribs:
                if a.dxf.tag == "VYPSANE_OZNACENI" and a.dxf.text.strip():
                    tag = a.dxf.text.strip()
                    p = a.dxf.insert
                    pos = (p.x, p.y)
            if tag and pos:
                out.append((tag, pos[0], pos[1]))
    return out


def text_under(c, texts):
    """Text, jehoz obdelnik (i pri krizku uprostred) pokryva bod c."""
    best, bd = None, 1e9
    for t, x, y, h in texts:
        w = len(t) * h * 0.8
        if x - h <= c[0] <= x + w + h and y - h <= c[1] <= y + 2 * h:
            d = abs(c[1] - (y + h / 2))
            if d < bd:
                bd, best = d, t
    return best


def reserve_cables(msp):
    """Kabely oznacene textem 'KABEL V REZERVE' = kabel v rezerve (vsechny spoje zrusene).
    Vraci mnozinu oznaceni kabelu."""
    texts = all_texts(msp)
    res_pts = [(x, y) for t, x, y, h in texts if "REZERV" in t.upper()]
    cabs = cable_positions(msp)
    flagged = set()
    for rx, ry in res_pts:
        best, bd = None, 20.0
        for tag, cx, cy in cabs:
            d = math.hypot(rx - cx, ry - cy)
            if d < bd:
                bd, best = d, tag
        if best:
            flagged.add(best)
    return flagged


def associate_cable(c, cabs, col_tol=16.0):
    """Kabel ve stejnem sloupci (|dx|<col_tol), nejblizsi -> zruseny spoj patri jemu.
    (Trasovat po dratech nelze - zruseny drat je z vykresu smazany.)"""
    best, bd = None, 1e9
    for tag, x, y in cabs:
        if abs(x - c[0]) <= col_tol:
            d = math.hypot(c[0] - x, c[1] - y)
            if d < bd:
                bd, best = d, tag
    return best


def nearest_device(c, devs, rng=14.0):
    """Nejblizsi zarizeni/port ke krizku = stary cil zruseneho spoje."""
    best, bd = None, rng
    for t, x, y in devs:
        d = math.hypot(c[0] - x, c[1] - y)
        if d < bd:
            bd, best = d, t
    return best


def detect(msp):
    """Vrati seznam zruseni: [{typ, prvek, kabel, x, y}]."""
    crosses = find_crosses(diag_lines(msp), 0.0, 40.0, 3.0)
    texts = all_texts(msp)
    tags = sils_tags(msp)
    cabs = cable_positions(msp)
    devs = [(t, x, y) for t, x, y, h in texts if "HUB" in t.upper() or t in tags]

    res = []
    for c in crosses:
        t = text_under(c, texts)
        is_device = bool(t) and ("HUB" in t.upper() or t in tags)
        if is_device:
            res.append({"typ": "zruseny HUB/zarizeni", "prvek": t, "kabel": "-",
                        "x": round(c[0], 1), "y": round(c[1], 1)})
        else:
            res.append({"typ": "zruseny spoj",
                        "prvek": nearest_device(c, devs) or "(na care)",
                        "kabel": associate_cable(c, cabs) or "-",
                        "x": round(c[0], 1), "y": round(c[1], 1)})
    return res


if __name__ == "__main__":
    import sys
    from pathlib import Path
    import ezdxf
    from ezdxf.addons import odafc
    ezdxf.options.set("odafc-addon", "win_exec_path",
                      r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe")
    for p in sys.argv[1:]:
        doc = odafc.readfile(p)
        from collections import defaultdict
        items = detect(doc.modelspace())
        devs = sorted({i["prvek"] for i in items if i["typ"].startswith("zruseny HUB")})
        spoj = [i for i in items if i["typ"] == "zruseny spoj"]
        print("\n{}".format(Path(p).name))
        print("  zrusene HUBy/zarizeni: {}".format(devs if devs else "-"))
        print("  zrusene spoje (kabel -> stary cil), pocet: {}".format(len(spoj)))
        agg = defaultdict(set)
        for i in spoj:
            agg[i["kabel"]].add(i["prvek"])
        for kab in sorted(agg):
            print("      kabel {:16s} -> stary cil: {}".format(kab, sorted(agg[kab])))
