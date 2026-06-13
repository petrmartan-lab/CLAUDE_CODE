import sys
import re
from pathlib import Path
from collections import defaultdict

import pytesseract
from pdf2image import convert_from_path
import pandas as pd

import checks
from checks import CABLE_ID_RE

TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER   = (r"C:\Users\petrm\AppData\Local\Microsoft\WinGet\Packages"
             r"\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe"
             r"\poppler-25.07.0\Library\bin")

pytesseract.pytesseract.tesseract_cmd = TESSERACT

OCR_DPI     = 350
LINE_TOL    = 12
LABEL_GAP   = 60


def normalize(s):
    s = re.sub(r'[^\x00-\x7F]', '-', s)
    s = re.sub(r'-{2,}', '-', s)
    return s.strip()


def ocr_words(img):
    data = pytesseract.image_to_data(
        img, lang="ces+eng",
        config="--psm 11 --oem 3",
        output_type=pytesseract.Output.DICT
    )
    words = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if text and int(data["conf"][i]) > 20:
            words.append({
                "text": text,
                "x0":   data["left"][i],
                "top":  data["top"][i],
                "cx":   data["left"][i] + data["width"][i] // 2,
            })
    return words


def group_lines(words):
    by_line = defaultdict(list)
    for w in words:
        key = round(w["top"] / LINE_TOL) * LINE_TOL
        by_line[key].append(w)
    result = []
    for top in sorted(by_line.keys()):
        for w in sorted(by_line[top], key=lambda w: w["x0"]):
            result.append({"top": top, "cx": w["cx"], "x0": w["x0"], "text": w["text"]})
    return result


def is_cable_id(text):
    norm = normalize(text)
    return CABLE_ID_RE.match(norm), norm


def extract_cables(lines):
    id_items = []
    for item in lines:
        m, norm = is_cable_id(item["text"])
        if m:
            id_items.append(dict(item, cable_id=norm))

    cables = []
    used = set()

    def find_near(cx, target_top):
        cands = [l for l in lines
                 if abs(l["cx"] - cx) < 80
                 and 5 < abs(l["top"] - target_top) < LABEL_GAP * 1.5]
        if not cands:
            return None
        return min(cands, key=lambda l: abs(l["top"] - target_top))

    for item in id_items:
        if item["top"] in used:
            continue
        cx, top = item["cx"], item["top"]
        from_item = find_near(cx, top - LABEL_GAP)
        type_item = find_near(cx, top + LABEL_GAP)
        to_item   = find_near(cx, top + LABEL_GAP * 2) if type_item else None

        if from_item and type_item and to_item:
            cables.append({
                "from_loc":   normalize(from_item["text"]),
                "cable_id":   item["cable_id"],
                "cable_type": type_item["text"],
                "to_loc":     normalize(to_item["text"]),
            })
            used.add(top)

    return cables


def parse_header(lines, img_height):
    h_lines = [l for l in lines if l["top"] > img_height * 0.88]
    text = " ".join(l["text"] for l in h_lines)
    f = {}
    for pat, key in [
        (r'\bList\s+(\S+)', "list"),
        (r'\bIndex\s+(\S+)', "index"),
        (r'\b(T\d{3}-\d{2}[A-Z0-9\-]+)\b', "doc_id"),
        (r'Vyprac[\.\s]+([A-Z][a-z]+\.?\s+[A-Z]+)', "vyprac"),
        (r'Kontrol[\.\s]+([A-Z][a-z]+\.?\s+[A-Z]+)', "kontrol"),
        (r'(\d+\+t\d{3}[\w\+\.\-]+\.dwg)', "soubor"),
    ]:
        m = re.search(pat, text, re.I)
        f[key] = m.group(1).strip() if m else ""
    return f


def analyze_pdf(pdf_path):
    print("\n[PDF] {}".format(pdf_path.name))
    images = convert_from_path(str(pdf_path), dpi=OCR_DPI, poppler_path=POPPLER)
    all_cables, all_headers, issues = [], [], []

    for pn, img in enumerate(images, 1):
        print("  str.{}/{}...".format(pn, len(images)), end=" ", flush=True)
        words = ocr_words(img)
        lines = group_lines(words)

        fields = parse_header(lines, img.height)
        all_headers.append({"page": pn, "fields": fields})

        body = [l for l in lines if l["top"] < img.height * 0.88]
        cables = extract_cables(body)
        print("kabelu: {}".format(len(cables)))

        for c in cables:
            c["page"] = pn
            c["source_file"] = pdf_path.name
            for err, typ in [(checks.check_type(c["cable_type"]), "Typ"), (checks.check_from_to(c), "FROM/TO")]:
                if err:
                    issues.append({"strana": pn, "typ": typ, "detail": err, "kabel": c["cable_id"]})

        all_cables.extend(cables)

    for e in checks.check_headers(all_headers):
        issues.append({"strana": "vice", "typ": "Hlavicka", "detail": e, "kabel": ""})

    print("  => {} kabelu, {} problemu".format(len(all_cables), len(issues)))
    return all_cables, all_headers, issues


def run(folder):
    folder = Path(folder)
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print("Zadne PDF v: {}".format(folder))
        return

    all_cables, all_issues, all_headers = [], [], []
    for pdf in pdfs:
        c, h, i = analyze_pdf(pdf)
        all_cables.extend(c)
        all_issues.extend(i)
        all_headers.extend(h)

    for e in checks.check_duplicates(all_cables):
        all_issues.append({"strana": "vice souboru", "typ": "Duplicita", "detail": e, "kabel": ""})

    out = folder / "report.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        if all_cables: pd.DataFrame(all_cables).to_excel(w, sheet_name="Kabely", index=False)
        if all_issues: pd.DataFrame(all_issues).to_excel(w, sheet_name="Chyby", index=False)
        rows = [{"strana": h["page"], **h["fields"]} for h in all_headers]
        pd.DataFrame(rows).to_excel(w, sheet_name="Hlavicky", index=False)

    print("\n[OK] {} kabelu, {} problemu".format(len(all_cables), len(all_issues)))
    print("[XLS] {}".format(out))
    if all_issues:
        print("\n[!] Problemy:")
        for i in all_issues:
            print("  [{}] str.{}: {}".format(i["typ"], i["strana"], i["detail"]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Pouziti: py checker.py <slozka s PDF>")
        sys.exit(1)
    run(sys.argv[1])