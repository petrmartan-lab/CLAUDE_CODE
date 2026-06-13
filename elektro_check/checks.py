# -*- coding: utf-8 -*-
"""
Sdilene kontroly a konstanty pro OCR (checker.py) i DWG (dwg_checker.py) checker.
Tisknute retezce drzime v ASCII kvuli Windows konzoli (cp1250).
"""

import re
from collections import defaultdict

from rapidfuzz import fuzz

# Format ID kabelu, napr. OR3-WF-1001, 1P80-WF-1018
CABLE_ID_RE = re.compile(r'^[A-Z0-9]{2,5}-[A-Z]{1,3}-\d{3,}$')

# Zname typy kabelu (rozsiruje se podle realnych dat)
KNOWN_TYPES = ["AMP X-0599142-7", "AMP X-0599169-7"]

# Prah fuzzy shody pro detekci preklepu v typu kabelu
TYPO_THRESHOLD = 75


def check_id_format(cable_id):
    """Vrati popis chyby pokud ID neodpovida ocekavanemu formatu, jinak None."""
    if not CABLE_ID_RE.match(cable_id):
        return "Neplatny format ID: '{}'".format(cable_id)
    return None


def check_type(cable_type):
    """Fuzzy porovnani typu kabelu vuci znamym typum -> detekce preklepu."""
    if not cable_type:
        return "Chybi typ kabelu"
    best, match = 0, None
    for known in KNOWN_TYPES:
        score = fuzz.ratio(cable_type, known)
        if score > best:
            best, match = score, known
    if best == 100:
        return None
    if best >= TYPO_THRESHOLD:
        return "Preklep? '{}' -> '{}' ({}%)".format(cable_type, match, round(best))
    return "Neznamy typ: '{}'".format(cable_type)


def check_from_to(cable):
    """Prefix ID kabelu musi odpovidat FROM nebo TO lokaci."""
    prefix = cable["cable_id"].split("-")[0]
    if prefix not in (cable.get("from_loc"), cable.get("to_loc")):
        return "FROM/TO nesedi: '{}' prefix={} FROM={} TO={}".format(
            cable["cable_id"], prefix, cable.get("from_loc"), cable.get("to_loc"))
    return None


def check_duplicates(cables):
    """Najde duplicitni ID kabelu napric vsemi listy."""
    seen = defaultdict(list)
    for c in cables:
        seen[c["cable_id"]].append(c)
    issues = []
    for cid, entries in seen.items():
        if len(entries) > 1:
            locs = ", ".join("str.{} ({})".format(e.get("page"), e.get("source_file"))
                             for e in entries)
            issues.append("Duplicita '{}': {}".format(cid, locs))
    return issues


def check_headers(headers, fields=("vyprac", "kontrol", "doc_id", "nazev", "ktd", "lokalita")):
    """
    Konzistence klicovych poli razitka napric listy. headers: [{'page','fields'}].
    Vystup je seskupeny podle hodnoty (jedna radka na pole misto N parovych).
    """
    if len(headers) < 2:
        return []
    issues = []
    for field in fields:
        groups = defaultdict(list)
        for h in headers:
            val = h["fields"].get(field, "")
            if val:
                groups[val].append(h["page"])
        if len(groups) > 1:
            parts = ["'{}' (str.{})".format(v, ",".join(str(p) for p in pages))
                     for v, pages in sorted(groups.items(), key=lambda kv: -len(kv[1]))]
            issues.append("Hlavicka '{}' nekonzistentni: {}".format(field, "; ".join(parts)))
    return issues


def check_list_numbers(headers):
    """Cisla listu (LIST) maji byt unikatni napric soubory."""
    seen = defaultdict(list)
    for h in headers:
        lst = h["fields"].get("list", "")
        if lst:
            seen[lst].append(h["page"])
    issues = []
    for lst, pages in seen.items():
        if len(pages) > 1:
            issues.append("Cislo listu '{}' se opakuje na stranach: {}".format(
                lst, ", ".join(str(p) for p in pages)))
    return issues


def check_value_consistency(items, key_field, value_field, label):
    """
    Seskupi prvky podle key_field a overi, ze value_field je v ramci skupiny stejny.
    Napr. stejny TYP kabelu musi mit stejne TYP_CISLO_KAB.
    """
    groups = defaultdict(set)
    locs = defaultdict(set)
    for it in items:
        k = it.get(key_field)
        v = it.get(value_field)
        if k and v:
            groups[k].add(v)
            locs[k].add("str.{}".format(it.get("page")))
    issues = []
    for k, vals in groups.items():
        if len(vals) > 1:
            issues.append("{}: '{}' ma ruzne '{}' = {} ({})".format(
                label, k, value_field, sorted(vals), ", ".join(sorted(locs[k]))))
    return issues


def check_type_typos(cables, threshold=90):
    """
    Detekce preklepu v typu kabelu z dat (bez whitelistu):
    najde dvojice ruznych typu, ktere jsou si velmi podobne (>= threshold %),
    a oznaci ten mene casty jako pravdepodobny preklep toho castejsiho.
    """
    from collections import Counter
    types = Counter(c["cable_type"] for c in cables if c.get("cable_type"))
    distinct = list(types)
    issues = []
    for i, t1 in enumerate(distinct):
        for t2 in distinct[i + 1:]:
            score = fuzz.ratio(t1, t2)
            if score >= threshold:
                if types[t1] <= types[t2]:
                    suspect, ref = t1, t2
                else:
                    suspect, ref = t2, t1
                issues.append("Mozny preklep typu: '{}' (x{}) podobny '{}' (x{}), shoda {}%".format(
                    suspect, types[suspect], ref, types[ref], round(score)))
    return issues


def check_dangling_refs(cables, device_tags):
    """ODKUD/KAM kabelu musi odkazovat na existujici zarizeni v projektu."""
    issues = []
    for c in cables:
        for role, tag in (("FROM", c.get("from_loc")), ("TO", c.get("to_loc"))):
            if tag and tag not in device_tags:
                issues.append("Kabel '{}' (str.{}): {} odkazuje na nezname zarizeni '{}'".format(
                    c["cable_id"], c.get("page"), role, tag))
    return issues
