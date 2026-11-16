#!/usr/bin/env python3
"""Fetch raw reference data for a species into data/raw/<id>.json.

    python3 tools/fetch.py "Datura stramonium" "Prunus persica"
    python3 tools/fetch.py --list tools/species.txt

Sources (all public APIs, no keys):
  * Wikipedia  - article extract (plain text) and the Commons images on the page
  * Wikidata   - Q id, common names, taxonomy properties
  * GBIF       - accepted name match, taxonomic ranks, vernacular names
  * Commons    - licence + author for each candidate image

The output is *raw material* for the data phase. Nothing here is a game fact:
the data phase reads it, writes plants/<id>.yaml, and cites it under `sources`.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
UA = "PlantCraftDataBot/0.1 (Minecraft mod data research)"


_last_call = 0.0
MIN_GAP = 1.0  # seconds between requests; the wikis rate-limit bursts


def get(url: str) -> dict:
    global _last_call
    last = None
    for attempt in range(6):
        wait = MIN_GAP - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            _last_call = time.time()
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                try:
                    delay = float(e.headers.get("Retry-After", ""))
                except ValueError:
                    delay = 0
                time.sleep(max(delay, 5 * (attempt + 1)))
                continue
            raise
        except Exception as e:  # network blip: back off and retry
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"GET failed after retries: {url}: {last}")


def qs(**kw) -> str:
    return urllib.parse.urlencode(kw)


def species_id(name: str) -> str:
    """'Olea europaea subsp. europaea' -> 'olea_europaea_europaea' (rank words dropped)."""
    words = [w for w in re.split(r"[^a-z]+", name.lower()) if w and w not in ("subsp", "ssp", "var", "subspecies")]
    return "_".join(words)


def wikipedia(name: str, title: str = None) -> dict:
    name = title or name
    wp = "https://en.wikipedia.org/w/api.php?"
    # Resolve the title (redirects handled) and get the full plain-text article.
    page = get(wp + qs(action="query", prop="extracts|pageprops|images|pageimages", explaintext=1,
                       titles=name, redirects=1, format="json", formatversion=2, imlimit=50,
                       piprop="original", ppprop="wikibase_item"))["query"]["pages"][0]
    if page.get("missing"):
        found = get(wp + qs(action="query", list="search", srsearch=f'"{name}"', srlimit=3,
                            format="json", formatversion=2))["query"]["search"]
        return {"found": False, "search_hits": [h["title"] for h in found]}
    return {
        "found": True,
        "title": page["title"],
        "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(page["title"].replace(" ", "_")),
        "wikidata_id": page.get("pageprops", {}).get("wikibase_item"),
        "extract": page.get("extract", ""),
        "lead_image": page.get("original", {}).get("source"),
        "image_files": [i["title"] for i in page.get("images", [])
                        if re.search(r"\.(jpe?g|png|webp)$", i["title"], re.I)
                        and not re.search(r"(icon|logo|commons-logo|symbol|map|range|distribution)", i["title"], re.I)],
    }


def wikidata(qid: str) -> dict:
    if not qid:
        return {"found": False}
    ent = get("https://www.wikidata.org/wiki/Special:EntityData/" + qid + ".json")["entities"][qid]
    claims = ent.get("claims", {})

    def vals(prop):
        out = []
        for c in claims.get(prop, []):
            v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if v is not None:
                out.append(v)
        return out

    names = [v["text"] for v in vals("P1843") if v.get("language") == "en"]
    return {
        "found": True,
        "id": qid,
        "url": "https://www.wikidata.org/wiki/" + qid,
        "label": ent.get("labels", {}).get("en", {}).get("value"),
        "description": ent.get("descriptions", {}).get("en", {}).get("value"),
        "english_common_names": names,
        "taxon_name": [v for v in vals("P225")],
        "taxon_rank_qid": [v.get("id") for v in vals("P105")],
        "parent_taxon_qid": [v.get("id") for v in vals("P171")],
        "image_files": [v for v in vals("P18")],
        "external_ids": {
            "gbif_taxon": vals("P846"), "powo": vals("P5037"), "ipni": vals("P961"),
            "ncbi": vals("P685"), "inaturalist": vals("P3151"), "eppo": vals("P3031"),
        },
    }


def gbif(name: str) -> dict:
    m = get("https://api.gbif.org/v1/species/match?" + qs(name=name, strict="false", verbose="false"))
    if not m.get("usageKey"):
        return {"found": False, "match": m}
    key = m.get("acceptedUsageKey") or m["usageKey"]
    vern = get(f"https://api.gbif.org/v1/species/{key}/vernacularNames?limit=100").get("results", [])
    return {
        "found": True,
        "url": f"https://www.gbif.org/species/{key}",
        "key": key,
        "match_type": m.get("matchType"),
        "status": m.get("status"),
        "scientific_name": m.get("scientificName"),
        "canonical_name": m.get("canonicalName"),
        "classification": {k: m.get(k) for k in ("kingdom", "phylum", "class", "order", "family", "genus", "species")},
        "english_vernacular_names": sorted({v["vernacularName"] for v in vern if v.get("language") == "eng"}),
    }


def commons(files: list) -> list:
    out = []
    files = list(dict.fromkeys(files))
    for i in range(0, len(files), 20):
        chunk = files[i:i + 20]
        titles = "|".join(f if f.startswith("File:") else "File:" + f for f in chunk)
        q = get("https://commons.wikimedia.org/w/api.php?" + qs(
            action="query", prop="imageinfo", iiprop="url|extmetadata|size", iiurlwidth=640,
            titles=titles, format="json", formatversion=2))
        for p in q.get("query", {}).get("pages", []):
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            if not info:
                continue
            strip = lambda s: re.sub(r"<[^>]+>", "", s or "").strip()
            out.append({
                "file": p["title"],
                "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_")),
                "thumb_640": info.get("thumburl"),
                "original": info.get("url"),
                "width": info.get("width"), "height": info.get("height"),
                "license": strip(meta.get("LicenseShortName", {}).get("value")),
                "license_url": strip(meta.get("LicenseUrl", {}).get("value")),
                "author": strip(meta.get("Artist", {}).get("value")),
                "description": strip(meta.get("ImageDescription", {}).get("value"))[:300],
            })
    return out


def fetch(name: str, title: str = None) -> dict:
    wp = wikipedia(name, title)
    qid = wp.get("wikidata_id")
    if not qid:  # fall back to a Wikidata name search
        hits = get("https://www.wikidata.org/w/api.php?" + qs(
            action="wbsearchentities", search=name, language="en", type="item", limit=3, format="json")).get("search", [])
        qid = hits[0]["id"] if hits else None
    wd = wikidata(qid)
    # Wikipedia pages pull in unrelated template images, so keep only files whose
    # name mentions the genus or species epithet. Wikidata's P18 images are trusted.
    genus, _, epithet = name.partition(" ")
    epithet = epithet.split()[-1] if epithet else epithet
    own = [f for f in wp.get("image_files", [])
           if genus.lower() in f.lower() or (epithet and epithet.lower() in f.lower())]
    files = wd.get("image_files", []) + own
    return {
        "query": name,
        "id": species_id(name),
        "fetched": time.strftime("%Y-%m-%d"),
        "wikipedia": wp,
        "wikidata": wd,
        "gbif": gbif(name),
        "commons_images": commons(files),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--list", help="file with one scientific name per line")
    ap.add_argument("--force", action="store_true", help="re-fetch species that already have a raw file")
    ap.add_argument("--wiki", help="Wikipedia article title to use instead of the species name (e.g. a subspecies covered by a species article)")
    a = ap.parse_args()
    names = list(a.names)
    if a.list:
        names += [l.strip() for l in Path(a.list).read_text().splitlines() if l.strip() and not l.startswith("#")]
    if not names:
        ap.error("give species names or --list")
    RAW.mkdir(parents=True, exist_ok=True)
    rc = 0
    for n in names:
        if (RAW / f"{species_id(n)}.json").exists() and not a.force:
            print(f"skip {n} (cached; use --force)")
            continue
        try:
            d = fetch(n, a.wiki)
            (RAW / f"{d['id']}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"ok   {n:28} wikipedia={'yes' if d['wikipedia'].get('found') else 'NO '} "
                  f"wikidata={d['wikidata'].get('id', '-')} gbif={d['gbif'].get('key', '-')} "
                  f"images={len(d['commons_images'])}")
        except Exception as e:
            rc = 1
            print(f"FAIL {n}: {e}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
