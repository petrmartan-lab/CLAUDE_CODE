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

## Detekce zrušených prvků (rušící křížky ✕)

Revizní křížky `✕` (dvě křížící se čáry) = **zrušení**. Konektory se kreslí jako
obloučky, nikdy jako křížky — proto se nepletou. Podle toho, **přes co křížek leží**:

| Křížek leží přes… | Význam |
|---|---|
| název `HUBxxx` / zařízení | **zrušený HUB / zařízení** |
| čáru spoje nebo port (X1/X2) | **zrušený spoj** |

Detekce je v `cancellations.py`, výsledek je v exportu na listu **`Ruseni`**
(`typ`, `zarizeni_nebo_cil`, `kabel`, `x`, `y`) a souhrnně v `Prehled`
(sloupce `ruseno_zarizeni`, `ruseno_spoju`).

U zrušeného spoje se navíc dopočítává **kterého kabelu se týká** a jaký byl
**starý cíl** (zařízení/port). Příklad z listu 16: `OR5-WF-1003 → HUB6_PORT4`
(spoj zrušen, kabel přesměrován jinam).

Vizuální ověření libovolného listu (🔴 zařízení, 🟠 spoj):
```
py render_cancel.py "cesta\k\vykresu.dwg"
```

**Jak se kabel přiřazuje:** trasovat po drátech NELZE — zrušený drát je z výkresu
smazaný (zůstane jen ✕). Proto se kabel určuje podle **sloupce** (kabel leží pod svým
spojem ve stejném `x`). Je to spolehlivý odhad, ne 100 % jistota — u nejasných případů
doporučen spot-check přes `render_cancel.py`.

### Kabely v rezervě (úplně zrušené)

Kabel, který má **všechny spoje zrušené**, je ve výkresu označen červeným textem
**„KABEL V REZERVĚ"**. Tento text se detekuje (`cancellations.reserve_cables`) a přiřadí
k nejbližšímu kabelu. V exportu:
- list **`Propojeni`** (a `propojeni.csv`) má sloupec **`rezerva`** = `REZERVA` u takových kabelů
- `Prehled` má počet `kabelu_rezerva` na list

Toto je spolehlivější než počítat křížky — vychází z explicitního údaje projektanta.

## Porovnání se zadáním (`Input.xlsx`)

`compare_input.py` porovná data z DWG (`export_full.xlsx`) se zadáním (`Input.xlsx`,
list `FO` — viz struktura níže). Spuštění:
```
py compare_input.py "<složka s Input.xlsx a export_full.xlsx>"
```
Výstup `porovnani.xlsx` (listy: Detail, Jen_v_zadani, Jen_v_DWG, Porty_chybi, OR_nesedi).

Kontroly:
- **Rušení**: kabel zrušený v zadání (vlákna červeně) ↔ kabel `REZERVA` v DWG
- **FROM/TO**: nové `Cab From/To` vs DWG `ODKUD/KAM` — rozliší `DWG=NEW` (aktualizováno),
  `DWG=OLD` (drží původní), nebo nesedí
- **Inventura**: kabely jen v zadání / jen v DWG
- **Porty**: HUB porty z `Connect From/To` existují v DWG zařízeních
- **Kabel→OR**: přiřazení OR z listu `FO in OR` vs DWG `ODKUD/KAM`

`Input.xlsx` list `FO`: sloupce **A–O = původní** (červená výplň = rušený), **S–Z = nové
údaje** u kabelů co zůstávají. Každý kabel má řádky po vláknech (X1/X2). Barvu výplně
čte jen openpyxl. Plnou legendu ostatních listů zná projektant.

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
