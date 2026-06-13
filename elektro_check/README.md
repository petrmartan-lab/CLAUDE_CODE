# Elektro výkres checker

Kontrola elektro schémat (zapojovací výkresy) — čte DWG a hlásí nekonzistence
v hlavičce, štítcích kabelů, typech a propojení.

## Dvě varianty

| Skript | Vstup | Přesnost | Kdy použít |
|--------|-------|----------|------------|
| **`dwg_checker.py`** | DWG | vysoká (čte atributy bloků) | **hlavní** — když máš DWG |
| `checker.py` | PDF (OCR) | nižší (OCR chyby) | fallback — jen když není DWG |

DWG varianta čte strukturovaná data přímo z atributů bloků, takže nemá OCR chyby
(žádné `OR3`→`ORS`). Vždy preferuj ji.

## Instalace

### Python knihovny
```
py -m pip install -r requirements.txt
```

### Externí nástroje
- **ODA File Converter** (zdarma) — převod DWG→DXF pro `dwg_checker.py`
  https://www.opendesign.com/guestfiles/oda_file_converter
- *(jen pro OCR fallback)* **Tesseract OCR** + **Poppler**

Cesty k nástrojům jsou nahoře v `dwg_checker.py` (`ODA_EXE`) a `checker.py`
(`TESSERACT`, `POPPLER`) — uprav podle své instalace.

## Použití

```
py dwg_checker.py "C:\cesta\ke\slozce_s_dwg"
```
Projde všechny `*.dwg` ve složce (každý = jeden list) a vytvoří `report_dwg.xlsx`
s listy: **Kabely**, **Zarizeni**, **Chyby**, **Hlavicky**.

## Jaké kontroly dělá

Na úrovni kabelu:
- formát ID (`OR3-WF-1001`)
- FROM/TO vs prefix ID
- `AE_NAME` odpovídá označení kabelu

Na úrovni projektu (napříč listy):
- duplicitní ID kabelů
- konzistence hlavičky (doc ID, vyprac., kontrol., název, KTD, lokalita)
- unikátnost čísel listů
- **překlepy typů kabelů** — data-driven: hledá podezřele podobné typy
  (např. `...0599168-7` vs `...0599169-7`), ne podle whitelistu
- konzistence typové číslo ↔ typ kabelu
- konzistence zařízení napříč listy (typ, krytí)
- **napojení** — ODKUD/KAM kabelu musí odkazovat na existující zařízení

## Mapování dat (zjištěno z DWG)

| Prvek | Vrstva | Blok | Klíčové atributy |
|-------|--------|------|------------------|
| Razítko | `T_RAM` | `Pole-2` | `ARCH_C`, `LIST`, `INDEX`, `VYPRACOVAL`, `KONTROLOVAL`, `NAZEV_1/2`, `KTD` |
| Kabel | `CABL` | `*_CABL` | `VYPSANE_OZNACENI`, `ODKUD`, `KAM`, `TYP`, `TYP_CISLO_KAB`, `AE_NAME` |
| Zařízení | `SILS` | `*_SILS` | `VYPSANE_OZNACENI`, `TYP`, `GTYP`, `STYP`, `NEV_KRYTI` |

## Ladění

- Práh detekce překlepů: `check_type_typos(..., threshold=90)` v `checks.py`
- Nové kontroly přidávej do `checks.py` (sdílí je obě varianty)
- Diagnostika struktury nového typu výkresu: `py inspect_dxf.py soubor.dwg`
