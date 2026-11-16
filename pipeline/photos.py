"""Stage 2b - PHOTOS: download reference photos of each species, covering flowering, fruiting and more.

    python3 pipeline/photos.py            # every "ok" species in data/pipeline/resolved.jsonl
    python3 pipeline/photos.py --force    # redo species that already have a manifest
    python3 pipeline/photos.py --only salvia_rosmarinus

Output per species: data/photos/<id>/<role>_<n>_<slug>.jpg and data/photos/<id>/manifest.json.

Where candidates come from (Wikimedia Commons only, so licences are known):
  * the images already found by the fetch stage (Wikidata image + the Wikipedia article's images)
  * the species' Commons category, and its subcategories whose names mention flowers, fruit, seeds, leaves, bark ...

Each candidate is tagged with a role from its title, description and categories:
    flower, fruit, seed, leaf, bark, branches (twigs, limbs, crown, tillers), illustration (botanical plates), habit (whole plant, the fallback).
Only freely reusable licences are kept (CC0, public domain, CC BY, CC BY-SA); NC/ND, unknown and non-photo files
(maps, diagrams, pests, herbarium sheets) are dropped. The best few per role are downloaded, preferring large
images and different authors. Roles listed under `must_have` in config.yaml (flowers and fruit by default) are
reported as missing if nothing suitable exists. Authors and licences are saved in manifest.json: keep them with the photos.
"""
import argparse
import html
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from common import CONFIG, ROOT, WORK, append_jsonl, batch_raws, get_bytes, get_json, write_json

PHOTOS = ROOT / CONFIG["paths"]["photos"]
CFG = CONFIG["photos"]
API = "https://commons.wikimedia.org/w/api.php?"

ROLES = ["flower", "fruit", "seed", "leaf", "bark", "branches", "illustration", "habit"]   # also the tie-break priority
ROLE_WORDS = {
    "flower": ["flower", "flowers", "flowering", "bloom", "blooms", "blossom", "blossoms", "inflorescence", "raceme", "panicle",
               "catkin", "bud", "buds", "petal", "petals", "anther", "spikelet", "spikelets", "floret", "corolla"],
    "fruit": ["fruit", "fruits", "berry", "berries", "drupe", "drupes", "capsule", "capsules", "pod", "pods", "cone", "cones", "nut",
              "nuts", "ripe", "unripe", "ripening", "grain", "grains", "seedhead", "infructescence", "olive", "olives", "peach", "peaches"],
    "seed": ["seed", "seeds", "stone", "pit", "kernel", "kernels", "oospore"],
    "leaf": ["leaf", "leaves", "foliage", "leaflet", "needle", "needles"],
    "bark": ["bark", "trunk", "stem", "stems", "bole"],
    "branches": ["branch", "branches", "branching", "twig", "twigs", "crown", "canopy", "silhouette", "limb", "limbs", "shoot", "shoots", "tillers", "tiller"],
    "illustration": ["illustration", "plate", "drawing", "engraving", "lithograph", "botanical", "köhler", "kohler", "flora"],
}
EXCLUDE = re.compile(r"\b(map|maps|distribution|logo|icon|diagram|chart|graph|larva|larvae|caterpillar|aphid|beetle|weevil|mite|gall|"
                     r"blight|disease|fungus|herbarium|specimen sheet|stamp|coin|banknote)\b|mhnt\.bot|herbier|pressed", re.I)
GOOD_MIME = ("image/jpeg", "image/png", "image/webp")


def license_ok(short: str) -> bool:
    s = (short or "").lower().replace("_", " ")
    if not s or re.search(r"\b(nc|nd)\b|non-?commercial|no derivatives|fair use|all rights", s):
        return False
    return any(s.startswith(ok) or re.search(rf"\b{re.escape(ok)}\b", s) for ok in CFG["licenses_ok"])


def tag_roles(title: str, description: str, cats: list, hints: set) -> dict:
    """Score every role from title (x3), description (x1) and category names (x2); subcategory hints add 4."""
    def words(t):
        return re.findall(r"[a-zäöüéèë]+", (t or "").lower())
    score = {r: 0 for r in ROLES}
    for role, vocab in ROLE_WORDS.items():
        for w in words(title):
            score[role] += 3 * (w in vocab)
        for w in words(description):
            score[role] += 1 * (w in vocab)
        for c in cats:
            score[role] += 2 * sum(w in vocab for w in words(c))
    for h in hints:
        score[h] += 4
    return score


def best_role(score: dict) -> str:
    top = max(score.values())
    if top <= 0:
        return "habit"
    return next(r for r in ROLES if score[r] == top)


def strip_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def category_members(cat: str, kind: str, limit: int) -> list:
    q = get_json(API + urllib.parse.urlencode({"action": "query", "list": "categorymembers", "cmtitle": cat, "cmtype": kind,
                                               "cmlimit": limit, "format": "json", "formatversion": 2}))
    return [m["title"] for m in q.get("query", {}).get("categorymembers", [])]


def candidate_titles(canonical: str, raw: dict) -> dict:
    """title -> set of role hints, from the fetch stage's images plus the Commons category tree."""
    cands = {}
    for im in raw.get("commons_images", []):
        cands.setdefault(im["file"], set())
    parts = canonical.split()
    cats = [f"Category:{canonical}"] + ([f"Category:{' '.join(parts[:2])}"] if len(parts) > 2 else [])
    for cat in cats:
        try:
            for t in category_members(cat, "file", 60):
                cands.setdefault(t, set())
            for sub in category_members(cat, "subcat", 200):
                hit = [r for r, vocab in ROLE_WORDS.items() if r != "illustration"
                       and any(w in vocab for w in re.findall(r"[a-z]+", sub.lower()))]
                if hit and len([1 for _ in cands]) < CFG["max_candidates"] * 3:
                    for t in category_members(sub, "file", CFG["subcategory_files"]):
                        cands.setdefault(t, set()).add(hit[0])
        except Exception as e:  # a missing category is normal
            append_jsonl(WORK / "failures.jsonl", {"stage": "photos", "id": canonical, "error": f"category {cat}: {e}"})
    return dict(list(cands.items())[: CFG["max_candidates"] * 2])


def image_info(titles: list) -> dict:
    out = {}
    for i in range(0, len(titles), 20):
        chunk = titles[i:i + 20]
        q = get_json(API + urllib.parse.urlencode({
            "action": "query", "prop": "imageinfo|categories", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": CFG["thumb_width"],
            "cllimit": "max", "titles": "|".join(chunk), "format": "json", "formatversion": 2}))
        for p in q.get("query", {}).get("pages", []):
            info = (p.get("imageinfo") or [{}])[0]
            if not info:
                continue
            meta = info.get("extmetadata", {})
            out[p["title"]] = {
                "title": p["title"], "mime": info.get("mime"), "width": info.get("width"), "height": info.get("height"),
                "thumb": info.get("thumburl"), "original": info.get("url"),
                "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_")),
                "license": strip_html(meta.get("LicenseShortName", {}).get("value")),
                "license_url": strip_html(meta.get("LicenseUrl", {}).get("value")),
                "author": strip_html(meta.get("Artist", {}).get("value")) or "unknown",
                "description": strip_html(meta.get("ImageDescription", {}).get("value"))[:400],
                "categories": [c["title"].replace("Category:", "") for c in p.get("categories", [])]}
    return out


def rank(infos: dict, hints: dict) -> dict:
    """Tag and filter candidates, then order each role's photos best-first: large images, different authors first."""
    pool = {r: [] for r in ROLES}
    for title, im in infos.items():
        if im["mime"] not in GOOD_MIME or not license_ok(im["license"]) or not im["thumb"]:
            continue
        if EXCLUDE.search(title + " " + im["description"] + " " + " ".join(im["categories"])):
            continue
        score = tag_roles(title, im["description"], im["categories"], hints.get(title, set()))
        role = best_role(score)
        im = dict(im, role=role, role_score=score[role],
                  hints=sorted({w for w in re.findall(r"[a-zäöüéèë]+", (title + " " + im["description"]).lower())
                                if w in ROLE_WORDS.get(role, [])}))
        pool[role].append(im)
    ranked = {}
    for role in ROLES:
        items = sorted(pool[role], key=lambda i: (-i["role_score"], -((i["width"] or 0) * (i["height"] or 0))))
        first, seen, rest = [], set(), []
        for im in items:                     # one photo per author first, then the rest
            if im["author"] not in seen:
                seen.add(im["author"]); first.append(im)
            else:
                rest.append(im)
        ranked[role] = first + rest
    return ranked


def select(infos: dict, hints: dict) -> list:
    """The best photos per role, up to the configured quota (no downloading)."""
    ranked = rank(infos, hints)
    return [im for role in ROLES for im in ranked[role][: CFG["per_role"].get(role, 0)]]


def slug(title: str) -> str:
    s = re.sub(r"^File:|\.\w+$", "", title)
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "photo"


def run_one(raw: dict, force=False) -> dict:
    d = PHOTOS / raw["id"]
    if (d / "manifest.json").exists() and not force:
        return {"cached": True}
    canonical = raw.get("gbif", {}).get("canonical_name") or raw["query"]
    hints = candidate_titles(canonical, raw)
    infos = image_info(list(hints))
    ranked = rank(infos, hints)
    d.mkdir(parents=True, exist_ok=True)
    photos, counts = [], {r: 0 for r in ROLES}
    for role in ROLES:
        for im in ranked[role]:              # a throttled or failing file is skipped; the next candidate takes its place
            if counts[role] >= CFG["per_role"].get(role, 0):
                break
            ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[im["mime"]]
            fname = f"{role}_{counts[role] + 1:02d}_{slug(im['title'])}.{ext}"
            try:
                (d / fname).write_bytes(get_bytes(im["thumb"], deadline_s=40, attempts=2))
            except Exception as e:
                append_jsonl(WORK / "failures.jsonl", {"stage": "photos", "id": raw["id"], "error": f"{im['title']}: {str(e)[:120]}"})
                continue
            counts[role] += 1
            photos.append({"file": f"{CONFIG['paths']['photos']}/{raw['id']}/{fname}", "role": role, "hints": im["hints"],
                           "title": im["title"], "page": im["page"], "original": im["original"], "width": im["width"], "height": im["height"],
                           "license": im["license"], "license_url": im["license_url"], "author": im["author"],
                           "description": im["description"], "categories": im["categories"][:12]})
    missing = [r for r in CFG["must_have"] if counts[r] == 0]
    manifest = {"id": raw["id"], "species": canonical, "fetched": time.strftime("%Y-%m-%d"),
                "note": "Photos are reference material only. Keep authors and licences with them.",
                "candidates_examined": len(infos), "coverage": counts, "missing_roles": missing, "photos": photos}
    write_json(d / "manifest.json", manifest)
    return manifest


def run(force=False, workers=None, only=None) -> int:
    if not CFG.get("enabled", True):
        print("photos: disabled in config")
        return 0
    raws = [r for r in batch_raws(only) if not only or r["id"] in only]
    print(f"photos: {len(raws)} species")
    PHOTOS.mkdir(parents=True, exist_ok=True)
    fails = 0

    def work(raw):
        try:
            return raw, run_one(raw, force), None
        except Exception as e:
            append_jsonl(WORK / "failures.jsonl", {"stage": "photos", "id": raw["id"], "error": str(e)})
            return raw, None, e

    with ThreadPoolExecutor(min(workers or CONFIG["workers"], 2)) as ex:
        for raw, m, err in ex.map(work, raws):
            if err:
                fails += 1
                print(f"  FAIL {raw['id']}: {err}")
            elif m.get("cached"):
                print(f"  skip {raw['id']} (cached)")
            else:
                cov = " ".join(f"{r}={n}" for r, n in m["coverage"].items() if n)
                print(f"  ok   {raw['id']:30} {len(m['photos']):2} photos ({cov})" + (f"  MISSING: {', '.join(m['missing_roles'])}" if m["missing_roles"] else ""))
    return fails


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    return 1 if run(a.force, only=set(a.only) if a.only else None) else 0


if __name__ == "__main__":
    sys.exit(main())
