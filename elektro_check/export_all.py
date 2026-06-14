# -*- coding: utf-8 -*-
"""
Kompletni export vsech dat z DWG vykresu do XLSX + CSV.
Vytahne KAZDY blok s atributy (kabely, zarizeni, razitko, ostatni),
vsechny jeho atributy, pozici, vrstvu a list - a propojeni (kam kabel vede).

Pouziti: py export_all.py <slozka s DWG>
Vystup:  export_full.xlsx  +  slozka export_csv\
"""

import re
import sys
from collections import Counter
from pathlib import Path

import ezdxf
from ezdxf.addons import odafc
import pandas as pd

import cancellations

try:                                   # konzole muze byt cp1250 -> nespadni na diakritice
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ODA_EXE = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
ezdxf.options.set("odafc-addon", "win_exec_path", ODA_EXE)

# Preferovane poradi sloupcu (zbytek se prida za ne)
CABLE_COLS = ["vykres", "list", "VYPSANE_OZNACENI", "ODKUD", "KAM", "TYP",
              "TYP_CISLO_KAB", "AE_NAME", "NAPETI", "POPIS", "SO_DPS",
              "SKRYTE_OZNACENI", "x", "y"]
DEVICE_COLS = ["vykres", "list", "VYPSANE_OZNACENI", "GTYP", "STYP", "TYP",
               "NAZEV", "NEV_KRYTI", "NEV_POCET_KONTAKTU", "AE_NAME",
               "NAPETI", "SKRYTE_OZNACENI", "SO_DPS", "x", "y"]

# Zname nazvy atributu razitka, ktere prevod zkomoli (non-ASCII -> '?').
_KNOWN_GARBLED = {"?ISLO_AKCE": "CISLO_AKCE", "STUPE?_PD": "STUPEN_PD", "PO?_?.": "POR_C"}


def clean_columns(df):
    """Prejmenuje sloupce s rozbitou diakritikou na citelne ASCII nazvy."""
    mapping = {}
    for c in df.columns:
        if isinstance(c, str) and any(ord(ch) > 127 for ch in c):
            skel = re.sub(r'[^\x00-\x7F]', '?', c)
            mapping[c] = _KNOWN_GARBLED.get(skel, re.sub(r'[^\x00-\x7F]', '_', c))
    return df.rename(columns=mapping) if mapping else df


def ordered(df, preferred):
    """Seradi sloupce: nejdriv preferovane (co existuji), pak zbytek."""
    cols = [c for c in preferred if c in df.columns]
    cols += [c for c in df.columns if c not in cols]
    return df[cols]


def list_no_of(doc):
    """Najde cislo listu z razitka (blok na vrstve T_RAM)."""
    for e in doc.modelspace().query("INSERT"):
        if e.dxf.layer == "T_RAM":
            for a in e.attribs:
                if a.dxf.tag == "LIST":
                    return a.dxf.text
    return ""


def extract_blocks(doc, drawing, list_no):
    """Vrati seznam radku - jeden za kazdy blok, ktery ma atributy."""
    rows = []
    for e in doc.modelspace().query("INSERT"):
        attrs = {a.dxf.tag: a.dxf.text for a in e.attribs}
        if not attrs:
            continue
        try:
            ins = e.dxf.insert
            x, y = round(ins.x, 1), round(ins.y, 1)
        except Exception:
            x = y = None
        row = {"vykres": drawing, "list": list_no, "vrstva": e.dxf.layer,
               "blok": e.dxf.name, "x": x, "y": y}
        row.update(attrs)
        rows.append(row)
    return rows


def run(folder):
    folder = Path(folder)
    dwgs = sorted(folder.glob("*.dwg"))
    if not dwgs:
        print("Zadne DWG v: {}".format(folder))
        return

    all_rows = []
    overview = []
    cancel_rows = []
    reserve_map = {}            # (vykres, kabel) -> True pokud "KABEL V REZERVE"

    for i, dwg in enumerate(dwgs, 1):
        print("[{:>2}/{}] {} ...".format(i, len(dwgs), dwg.name), end=" ", flush=True)
        try:
            doc = odafc.readfile(str(dwg))
        except Exception as ex:
            print("CHYBA: {}".format(ex))
            continue
        list_no = list_no_of(doc)
        rows = extract_blocks(doc, dwg.name, list_no)
        all_rows.extend(rows)

        msp = doc.modelspace()
        # rusici krizky (X = zruseni)
        cancels = cancellations.detect(msp)
        cancel_devs = sorted({c["prvek"] for c in cancels if c["typ"].startswith("zruseny HUB")})
        n_spoj = sum(1 for c in cancels if c["typ"] == "zruseny spoj")
        for c in cancels:
            cancel_rows.append({"vykres": dwg.name, "list": list_no,
                                "typ": c["typ"], "zarizeni_nebo_cil": c["prvek"],
                                "kabel": c.get("kabel", "-"), "x": c["x"], "y": c["y"]})

        # kabely v rezerve (vsechny spoje zrusene) - oznacene textem v vykresu
        reserve = cancellations.reserve_cables(msp)
        for tag in reserve:
            reserve_map[(dwg.name, tag)] = True

        layer_counts = Counter(r["vrstva"] for r in rows)
        overview.append({
            "vykres": dwg.name,
            "list": list_no,
            "prvku_celkem": len(rows),
            "kabely_CABL": layer_counts.get("CABL", 0),
            "zarizeni_SILS": layer_counts.get("SILS", 0),
            "ostatni": len(rows) - layer_counts.get("CABL", 0) - layer_counts.get("SILS", 0),
            "ruseno_zarizeni": len(cancel_devs),
            "ruseno_spoju": n_spoj,
            "kabelu_rezerva": len(reserve),
        })
        print("prvku: {}  ruseni: {} zar / {} spoj".format(len(rows), len(cancel_devs), n_spoj))

    df_all = clean_columns(pd.DataFrame(all_rows))

    # Rozdeleni podle vrstvy
    df_cab = ordered(df_all[df_all["vrstva"] == "CABL"].dropna(axis=1, how="all"), CABLE_COLS)
    df_dev = ordered(df_all[df_all["vrstva"] == "SILS"].dropna(axis=1, how="all"), DEVICE_COLS)
    df_oth = df_all[~df_all["vrstva"].isin(["CABL", "SILS"])].dropna(axis=1, how="all")

    # Propojeni - kam kabel vede (FROM -> TO)
    df_conn = df_cab[[c for c in ["vykres", "list", "VYPSANE_OZNACENI", "ODKUD", "KAM", "TYP"]
                      if c in df_cab.columns]].copy()
    df_conn.columns = ["vykres", "list", "kabel", "odkud_FROM", "kam_TO", "typ"][:len(df_conn.columns)]
    # priznak rezervy (kabel v rezerve = vsechny spoje zrusene)
    if "vykres" in df_conn.columns and "kabel" in df_conn.columns:
        df_conn["rezerva"] = ["REZERVA" if (v, k) in reserve_map else ""
                              for v, k in zip(df_conn["vykres"], df_conn["kabel"])]

    # Razitko / hlavicky
    df_hdr = df_all[df_all["vrstva"] == "T_RAM"].dropna(axis=1, how="all")

    df_over = pd.DataFrame(overview)
    df_cancel = pd.DataFrame(cancel_rows) if cancel_rows else pd.DataFrame(
        columns=["vykres", "list", "typ", "zarizeni_nebo_cil", "kabel", "x", "y"])

    # ── XLSX ──
    xlsx = folder / "export_full.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        df_over.to_excel(w, sheet_name="Prehled", index=False)
        df_cab.to_excel(w, sheet_name="Kabely", index=False)
        df_dev.to_excel(w, sheet_name="Zarizeni", index=False)
        df_conn.to_excel(w, sheet_name="Propojeni", index=False)
        df_cancel.to_excel(w, sheet_name="Ruseni", index=False)
        df_hdr.to_excel(w, sheet_name="Hlavicky", index=False)
        df_oth.to_excel(w, sheet_name="Ostatni_prvky", index=False)
        df_all.to_excel(w, sheet_name="VSE_prvky", index=False)

    # ── CSV (utf-8-sig kvuli Excelu a diakritice) ──
    csv_dir = folder / "export_csv"
    csv_dir.mkdir(exist_ok=True)
    locked = []
    for name, df in [("prehled", df_over), ("kabely", df_cab), ("zarizeni", df_dev),
                     ("propojeni", df_conn), ("ruseni", df_cancel), ("hlavicky", df_hdr),
                     ("ostatni_prvky", df_oth), ("vse_prvky", df_all)]:
        try:
            df.to_csv(csv_dir / (name + ".csv"), index=False, encoding="utf-8-sig", sep=";")
        except PermissionError:
            locked.append(name + ".csv")
    if locked:
        print("[!] Preskoceno (zamcene, zavri v Excelu): {}".format(", ".join(locked)))

    print("\n[OK] {} prvku z {} vykresu, zruseni: {}".format(
        len(df_all), len(df_over), len(df_cancel)))
    print("[XLS] {}".format(xlsx))
    print("[CSV] {}\\ (8 souboru, oddelovac ';')".format(csv_dir))
    print("\nListy: Prehled | Kabely | Zarizeni | Propojeni | Ruseni | Hlavicky | Ostatni_prvky | VSE_prvky")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Pouziti: py export_all.py <slozka s DWG>")
        sys.exit(1)
    run(sys.argv[1])
