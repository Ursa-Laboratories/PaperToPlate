"""Normalize the full Crossref snapshot and retain transparent retrieval evidence."""

import csv
import gzip
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote, urlparse


ROOT = Path(__file__).resolve().parent
RULES = {
    "Pipetting / liquid handling": r"\b(?:pipett(?:e|es|ed|ing|ors?)|pipet(?:s|ting)?|liquid[- ]handl\w*|serial[- ]dilutions?|aliquots?|dispens(?:e|ed|ing|ers?)|aspirat(?:e|ed|ing|ion))\b",
    "Plate assays / readers": r"\b(?:microplates?|microwells?|multiwell|microtit(?:er|re)|well[- ]plates?|(?:96|384|1536)[- ]well|plate[- ]readers?)\b",
    "Assays / bioassays": r"\b(?:assays?|bioassays?|immunoassays?|enzyme[- ]activity|cell[- ]viability|protein[- ]quantification|antioxidant[- ]activity)\b",
    "Named assays": r"\b(?:bradford|bicinchoninic|elisa|mtt|resazurin|alamar[- ]?blue|luciferase|dpph|abts|western[- ]blot|enzyme[- ]linked[- ]immunosorbent)\b",
    "Screening / experimental workflows": r"\b(?:high[- ]throughput[- ]screen\w*|high[- ]throughput[- ]experiment\w*|sample[- ]preparation|automated[- ]synthesis|reaction[- ]screen\w*|reaction[- ]optimi[sz]ation|design[- ]of[- ]experiments)\b",
    "Readout / assay context": r"\b(?:colorimetric|fluorometric|fluorogenic|spectrophotometric|chemiluminescen\w*|absorbance|dose[- ]response|ic50|ec50|radical[- ]scaveng\w*)\b",
}
COMPILED = {k: re.compile(v, re.I) for k, v in RULES.items()}
METHOD = re.compile(r"\b(?:protocols?|workflows?|incubat\w*|reagents?|dilut\w*|calibrat\w*|detect\w*|quantif\w*|measur\w*)\b", re.I)
VERSION = re.compile(r"(?:[./-]v)(\d+)$", re.I)


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def date(item):
    parts = (item.get("posted") or item.get("published") or {}).get("date-parts", [[]])[0]
    return "-".join(str(n).zfill(2) if i else str(n) for i, n in enumerate(parts))


def match(title, abstract):
    text = title + " " + abstract
    hits = {name: sorted({m.group(0).lower() for m in pattern.finditer(text)})
            for name, pattern in COMPILED.items()}
    hits = {name: terms for name, terms in hits.items() if terms}
    direct = any(k in hits for k in ("Pipetting / liquid handling", "Plate assays / readers", "Assays / bioassays", "Named assays"))
    broad = "Screening / experimental workflows" in hits or ("Readout / assay context" in hits and METHOD.search(text))
    band = "Assay / liquid-handling metadata match" if direct else "Broader experimental-method candidate" if broad else "No metadata match"
    # Short evidence excerpt: at most 20 words. It is not a methods extraction.
    found = [m for p in COMPILED.values() for m in p.finditer(text)]
    if found:
        m = min(found, key=lambda m: m.start())
        before = text[:m.start()].split()[-5:]
        after = text[m.start():].split()[:15]
        excerpt = " ".join(before + after)
    else:
        excerpt = ""
    return band, hits, excerpt


def dump_jsonl(name, rows):
    with (ROOT / name).open("w") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")


def dump_csv(name, rows):
    fields = ["title", "screening_band", "categories", "matched_terms", "published_date", "doi", "version", "authors", "pdf_url", "pdf_link_source", "landing_url", "evidence_excerpt", "versions_in_family", "family_id", "abstract_available", "possible_same_title_families", "family_match_categories", "review_or_analysis_title", "protocol_readiness", "grouped_family_ids", "all_version_dois", "all_version_pdf_urls", "crossref_record_url"]
    with (ROOT / name).open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            for key, value in flat.items():
                if isinstance(value, list):
                    flat[key] = "; ".join(str(x) for x in value)
                # Protect spreadsheet consumers from formula injection in source metadata.
                if isinstance(flat[key], str) and flat[key].startswith(("=", "+", "-", "@")):
                    flat[key] = "'" + flat[key]
            writer.writerow(flat)


def main():
    manifest = json.loads((ROOT / "harvest_manifest.json").read_text())
    if not manifest["complete"]:
        raise RuntimeError("Harvest is not complete")
    records = []
    raw_count = 0
    for page in sorted((ROOT / "raw_crossref").glob("*.json.gz")):
        payload = json.load(gzip.open(page, "rt"))
        for item in payload["message"]["items"]:
            raw_count += 1
            doi = item["DOI"].lower()
            if not doi.startswith("10.26434/chemrxiv"):
                continue
            title = clean(" ".join(item.get("title", [])))
            abstract = clean(item.get("abstract", ""))
            band, hits, excerpt = match(title, abstract)
            links = list(dict.fromkeys(x["URL"] for x in item.get("link", []) if x.get("URL")))
            pdfs = [url for url in links if any(s in url.lower() for s in ("/pdf/", ".pdf", "ndownloader.figshare.com", "api.figshare.com/v2/file/download"))]
            # Never construct a PDF URL for a missing deposit.
            version = VERSION.search(doi)
            records.append({
                "doi": doi, "family_id": VERSION.sub("", doi),
                "version": int(version.group(1)) if version else 0,
                "title": title, "published_date": date(item),
                "authors": [clean(" ".join(filter(None, (a.get("given"), a.get("family"), a.get("name"))))) for a in item.get("author", [])],
                "screening_band": band, "categories": list(hits),
                "matched_terms": sorted({t for terms in hits.values() for t in terms}),
                "evidence_excerpt": excerpt, "evidence_level": "title_and_abstract_only",
                "abstract_available": bool(abstract),
                "pdf_url": pdfs[0] if pdfs else "", "pdf_urls": pdfs,
                "pdf_link_source": "Crossref deposited link" if pdfs else "Missing deposited PDF link",
                "other_deposited_links": links,
                "landing_url": item.get("resource", {}).get("primary", {}).get("URL") or "https://doi.org/" + doi,
                "crossref_record_url": "https://api.crossref.org/works/" + quote(doi, safe=""),
                "license_urls": list(dict.fromkeys(x.get("URL", "") for x in item.get("license", []) if x.get("URL"))),
                "raw_page": str(page.relative_to(ROOT)),
            })
    assert raw_count == manifest["retrieved_records"] == manifest["reported_total_latest_page"]
    doi_count = Counter(x["doi"] for x in records)
    if any(n != 1 for n in doi_count.values()):
        raise RuntimeError("Duplicate DOI returned by pagination; inspect before claiming completeness")
    families = defaultdict(list)
    for row in records:
        families[row["family_id"]].append(row)
    latest = []
    for key, versions in families.items():
        selected = dict(max(versions, key=lambda x: (x["version"], x["published_date"])))
        selected["versions_in_family"] = len(versions)
        selected["all_version_dois"] = [x["doi"] for x in sorted(versions, key=lambda x: x["version"])]
        selected["all_version_pdf_urls"] = list(dict.fromkeys(u for x in versions for u in x["pdf_urls"]))
        # Older versions can contain relevant metadata omitted from the latest.
        candidates = [x for x in versions if x["screening_band"] != "No metadata match"]
        selected["any_version_matches"] = bool(candidates)
        selected["matching_version_dois"] = [x["doi"] for x in candidates]
        selected["family_match_categories"] = sorted({k for x in candidates for k in x["categories"]})
        if selected["screening_band"] == "No metadata match" and candidates:
            selected["screening_band"] = "Earlier-version metadata match"
        latest.append(selected)
    titlegroups = Counter(re.sub(r"\W+", "", x["title"]).lower() for x in latest)
    for row in latest:
        row["possible_same_title_families"] = titlegroups[re.sub(r"\W+", "", row["title"]).lower()]
    order = {"Assay / liquid-handling metadata match": 0, "Earlier-version metadata match": 1, "Broader experimental-method candidate": 2, "No metadata match": 3}
    latest.sort(key=lambda x: (order[x["screening_band"]], -len(x["categories"]), x["title"].lower()))
    candidates = [x for x in latest if x["any_version_matches"]]
    direct = [x for x in candidates if any(k in x["family_match_categories"] for k in ("Pipetting / liquid handling", "Plate assays / readers", "Assays / bioassays", "Named assays"))]
    # Conservative migration-alias grouping: exact normalized title AND complete
    # ordered author list. Keep every underlying DOI and PDF in the grouped row.
    alias_groups = defaultdict(list)
    for row in candidates:
        normalize = lambda s: re.sub(r"\W+", "", s).casefold()
        key = (normalize(row["title"]), tuple(normalize(a) for a in row["authors"]))
        if not row["authors"]:
            key = (row["family_id"], ())
        alias_groups[key].append(row)
    deduplicated = []
    for group in alias_groups.values():
        selected = dict(max(group, key=lambda x: (x["published_date"], bool(x["pdf_url"]), x["version"])))
        selected["grouped_family_ids"] = sorted(x["family_id"] for x in group)
        selected["all_version_dois"] = sorted({doi for x in group for doi in x["all_version_dois"]})
        selected["all_version_pdf_urls"] = sorted({u for x in group for u in x["all_version_pdf_urls"]})
        selected["family_match_categories"] = sorted({k for x in group for k in x["family_match_categories"]})
        selected["review_or_analysis_title"] = bool(re.search(r"\breview\b|life[- ]cycle|\bperspective\b|\bsurvey\b|bibliometric|meta[- ]analysis", selected["title"], re.I))
        selected["protocol_readiness"] = "Unverified: inspect full methods and supporting information"
        deduplicated.append(selected)
    deduplicated.sort(key=lambda x: (order[x["screening_band"]], x["review_or_analysis_title"], -len(x["categories"]), x["title"].lower()))
    candidate_families = {x["family_id"] for x in candidates}
    all_urls = sorted({u for x in records for u in x["pdf_urls"]})
    candidate_urls = sorted({u for x in records if x["family_id"] in candidate_families for u in x["pdf_urls"]})
    dump_jsonl("all_doi_records.jsonl", records)
    dump_jsonl("missing_pdf_links.jsonl", [x for x in records if not x["pdf_url"]])
    dump_jsonl("all_paper_families.jsonl", latest)
    dump_jsonl("workflow_candidates.jsonl", candidates)
    dump_jsonl("workflow_candidates_deduplicated.jsonl", deduplicated)
    dump_jsonl("assay_liquid_handling_matches.jsonl", direct)
    dump_csv("all_paper_families.csv", latest)
    dump_csv("workflow_candidates.csv", candidates)
    dump_csv("workflow_candidates_deduplicated.csv", deduplicated)
    dump_csv("assay_liquid_handling_matches.csv", direct)
    (ROOT / "all_pdf_links.txt").write_text("\n".join(all_urls) + "\n")
    (ROOT / "workflow_pdf_links.txt").write_text("\n".join(candidate_urls) + "\n")
    (ROOT / "workflow_latest_pdf_links.txt").write_text("\n".join(sorted({x["pdf_url"] for x in candidates if x["pdf_url"]})) + "\n")
    stats = {
        "snapshot_date": manifest["snapshot_date"], "raw_records": raw_count,
        "chemrxiv_doi_records": len(records), "doi_families": len(latest),
        "workflow_candidate_families": len(candidates), "direct_assay_or_liquid_handling_families": len(direct),
        "deduplicated_workflow_candidates": len(deduplicated),
        "exact_title_author_alias_families_grouped": len(candidates) - len(deduplicated),
        "all_pdf_urls": len(all_urls), "workflow_pdf_urls_all_versions": len(candidate_urls),
        "workflow_latest_pdf_urls": sum(bool(x["pdf_url"]) for x in candidates),
        "records_missing_pdf_url": sum(not x["pdf_url"] for x in records),
        "records_missing_abstract": sum(not x["abstract_available"] for x in records),
        "families_with_duplicate_title": sum(x["possible_same_title_families"] > 1 for x in latest),
        "candidate_categories": dict(Counter(k for x in candidates for k in x["family_match_categories"])),
        "screening_rules_regex": RULES,
        "readout_context_rule": METHOD.pattern,
        "full_text_protocol_verification": "Not performed; metadata screening only",
    }
    (ROOT / "catalogue_manifest.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps({k: v for k, v in stats.items() if not isinstance(v, dict)}, indent=2))


if __name__ == "__main__":
    main()
