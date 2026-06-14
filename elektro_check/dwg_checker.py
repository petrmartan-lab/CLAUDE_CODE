# -*- coding: utf-8 -*-
"""
DWG checker - kontrola elektro vykresu primo z DWG (pres ezdxf + ODA File Converter).
Cte strukturovana data z atributu bloku (razitko, kabely, zarizeni) -> bez OCR chyb.

Pouziti: py dwg_checker.py <slozka s DWG>
"""

import sys
from pathlib import Path

import ezdxf
from ezdxf.addons import odafc
import pandas as pd

import checks

try:                                   # konzole muze byt cp1250 -> nespadni na diakritice
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ODA_EXE = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
ezdxf.options.set("odafc-addon", "win_exec_path", ODA_EXE)


# ── Extrakce z jednoho vykresu ───────────────────────────────────────────────

def extract(doc, source_file, page):
    """Vytahne razitko, kabely a zarizeni z atributu bloku v modelspace."""
    msp = doc.modelspace()
    header = {}
    cables, devices = [], []

    for e in msp.query("INSERT"):
        attrs = {a.dxf.tag: a.dxf.text for a in e.attribs}
        if not attrs:
            continue
        layer = e.dxf.layer
        try:
            ins = e.dxf.insert
            pos = (round(ins.x, 1), round(ins.y, 1))
        except Exception:
            pos = None

        if layer == "T_RAM" and "ARCH_C" in attrs:           # rohove razitko
            header.update({
                "doc_id":   attrs.get("ARCH_C", ""),
                "list":     attrs.get("LIST", ""),
                "index":    attrs.get("INDEX", ""),
                "vyprac":   attrs.get("VYPRACOVAL", ""),
                "kontrol":  attrs.get("KONTROLOVAL", ""),
                "nazev":    attrs.get("NAZEV_1", ""),    # spolecny titulek (ma byt stejny)
                "nazev_2":  attrs.get("NAZEV_2", ""),    # podtitul listu (lisi se zamerne)
                "ktd":      attrs.get("KTD", ""),
                "lokalita": attrs.get("LOKALITA", ""),
            })
        elif layer == "O_RARO" and "BALIK" in attrs:          # cislo vykresu
            header["balik"] = attrs.get("BALIK", "")
        elif layer == "CABL":                                 # stitek kabelu
            cables.append({
                "cable_id":   attrs.get("VYPSANE_OZNACENI", ""),
                "from_loc":   attrs.get("ODKUD", ""),
                "to_loc":     attrs.get("KAM", ""),
                "cable_type": attrs.get("TYP", ""),
                "typ_cislo":  attrs.get("TYP_CISLO_KAB", ""),
                "ae_name":    attrs.get("AE_NAME", ""),
                "popis":      attrs.get("POPIS", ""),
                "page": page, "source_file": source_file, "pos": pos,
            })
        elif layer == "SILS":                                 # zarizeni
            devices.append({
                "tag":       attrs.get("VYPSANE_OZNACENI", ""),
                "gtyp":      attrs.get("GTYP", ""),
                "styp":      attrs.get("STYP", ""),
                "typ":       attrs.get("TYP", ""),
                "ae_name":   attrs.get("AE_NAME", ""),
                "nazev":     attrs.get("NAZEV", ""),
                "nev_kryti": attrs.get("NEV_KRYTI", ""),
                "page": page, "source_file": source_file, "pos": pos,
            })

    return header, cables, devices


# ── Kontroly nad jednim kabelem ──────────────────────────────────────────────

def check_cable(c):
    issues = []
    err = checks.check_id_format(c["cable_id"])
    if err:
        issues.append(("Format ID", err))
    err = checks.check_from_to(c)
    if err:
        issues.append(("FROM/TO", err))
    # AE_NAME ma koncit oznacenim kabelu (napr. '2' + 'OR3-WF-1001')
    if c["ae_name"] and c["cable_id"] and not c["ae_name"].endswith(c["cable_id"]):
        issues.append(("AE_NAME", "AE_NAME '{}' neodpovida oznaceni '{}'".format(
            c["ae_name"], c["cable_id"])))
    return issues


# ── Hlavni logika ─────────────────────────────────────────────────────────────

def analyze(folder):
    folder = Path(folder)
    dwgs = sorted(folder.glob("*.dwg"))
    if not dwgs:
        print("Zadne DWG v: {}".format(folder))
        return

    all_cables, all_devices, all_headers, issues = [], [], [], []

    for page, dwg in enumerate(dwgs, 1):
        print("[{:>2}/{}] {} ...".format(page, len(dwgs), dwg.name), end=" ", flush=True)
        try:
            doc = odafc.readfile(str(dwg))
        except Exception as ex:
            print("CHYBA prevodu: {}".format(ex))
            issues.append({"strana": page, "typ": "Prevod", "detail": str(ex), "kabel": ""})
            continue

        header, cables, devices = extract(doc, dwg.name, page)
        all_headers.append({"page": page, "fields": header})
        all_cables.extend(cables)
        all_devices.extend(devices)

        for c in cables:
            for typ, det in check_cable(c):
                issues.append({"strana": page, "typ": typ, "detail": det, "kabel": c["cable_id"]})

        print("kabelu: {:2d}  zarizeni: {:2d}".format(len(cables), len(devices)))

    # ── Kontroly napric celym projektem ──
    device_tags = {d["tag"] for d in all_devices if d["tag"]}

    project_checks = [
        ("Duplicita",     checks.check_duplicates(all_cables)),
        ("Hlavicka",      checks.check_headers(all_headers)),
        ("Cislo listu",   checks.check_list_numbers(all_headers)),
        ("Napojeni",      checks.check_dangling_refs(all_cables, device_tags)),
        ("Typ kabelu",    checks.check_type_typos(all_cables)),
        ("Typ kabelu",    checks.check_value_consistency(all_cables, "cable_type", "typ_cislo", "Konzistence typu")),
        ("Typ kabelu",    checks.check_value_consistency(all_cables, "typ_cislo", "cable_type", "Konzistence cisla typu")),
        ("Zarizeni",      checks.check_value_consistency(all_devices, "tag", "typ", "Konzistence zarizeni")),
        ("Zarizeni",      checks.check_value_consistency(all_devices, "tag", "nev_kryti", "Konzistence kryti")),
    ]
    for typ, found in project_checks:
        for det in found:
            issues.append({"strana": "projekt", "typ": typ, "detail": det, "kabel": ""})

    # ── Report ──
    out = folder / "report_dwg.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        if all_cables:
            pd.DataFrame(all_cables).to_excel(w, sheet_name="Kabely", index=False)
        if all_devices:
            pd.DataFrame(all_devices).to_excel(w, sheet_name="Zarizeni", index=False)
        if issues:
            pd.DataFrame(issues).to_excel(w, sheet_name="Chyby", index=False)
        rows = [{"strana": h["page"], **h["fields"]} for h in all_headers]
        pd.DataFrame(rows).to_excel(w, sheet_name="Hlavicky", index=False)

    print("\n[OK] {} kabelu, {} zarizeni, {} problemu".format(
        len(all_cables), len(all_devices), len(issues)))
    print("[XLS] {}".format(out))
    if issues:
        print("\n[!] Problemy:")
        for i in issues:
            print("  [{}] str.{}: {}".format(i["typ"], i["strana"], i["detail"]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Pouziti: py dwg_checker.py <slozka s DWG>")
        sys.exit(1)
    analyze(sys.argv[1])
