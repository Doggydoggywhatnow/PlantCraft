"""Shared helpers: paths, config, a thread-safe HTTP client with per-host rate limits, JSONL I/O."""
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

sys.dont_write_bytecode = True  # tools/__pycache__ is tracked in git; keep pipeline runs from dirtying it

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))

WORK = ROOT / CONFIG["paths"]["work"]          # resolved.jsonl, failures.jsonl, extracted/, drafts/
RAW = ROOT / CONFIG["paths"]["raw"]            # same raw files tools/fetch.py writes
PLANTS = ROOT / "plants"


def species_id(name: str) -> str:
    """'Olea europaea subsp. europaea' -> 'olea_europaea_europaea' (same rule as tools/fetch.py)."""
    words = [w for w in re.split(r"[^a-z]+", name.lower())
             if w and w not in ("subsp", "ssp", "var", "subspecies")]
    return "_".join(words)


def read_names(path: Path) -> list:
    """One scientific name per line; '#' comments and blank lines ignored; duplicates dropped."""
    out, seen = [], set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line and line.lower() not in seen:
            seen.add(line.lower())
            out.append(line)
    return out


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


_jl_lock = threading.Lock()


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _jl_lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class RateLimiter:
    """Allows at most `rps` requests per second for one host, across all threads."""

    def __init__(self, rps: float):
        self.gap = 1.0 / rps
        self.lock = threading.Lock()
        self.next_ok = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            slot = max(now, self.next_ok)
            self.next_ok = slot + self.gap
        if slot > now:
            time.sleep(slot - now)


_limiters = {}
_limiters_lock = threading.Lock()


def _limiter(host: str) -> RateLimiter:
    with _limiters_lock:
        if host not in _limiters:
            rps = CONFIG["rate_limits_rps"].get(host, CONFIG["rate_limits_rps"]["default"])
            _limiters[host] = RateLimiter(rps)
        return _limiters[host]


def get_json(url: str) -> dict:
    """GET JSON with per-host rate limiting and retry/backoff on 429/5xx and network errors."""
    host = re.match(r"https?://([^/]+)/", url).group(1)
    last = None
    for attempt in range(CONFIG["http"]["retries"]):
        _limiter(host).wait()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": CONFIG["http"]["user_agent"],
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=CONFIG["http"]["timeout_s"]) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                try:
                    delay = float(e.headers.get("Retry-After", ""))
                except ValueError:
                    delay = 0
                time.sleep(min(max(delay, 4 * (attempt + 1)), 60))   # never obey an hours-long Retry-After
                continue
            raise
        except Exception as e:  # network blip
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"GET failed after retries: {url}: {last}")


def load_raw(path: Path) -> dict:
    """Read a data/raw file; the filename is the id (older raw files may not store it)."""
    d = json.loads(path.read_text(encoding="utf-8"))
    d.setdefault("id", path.stem)
    d.setdefault("query", d["id"].replace("_", " ").capitalize())
    return d


def batch_raws(only=None, everything=False) -> list:
    """Raw files for the current batch: species that resolve.py marked ok (or every file with everything=True).

    data/raw/ may also hold files from tools/fetch.py or non-species notes; those are skipped unless
    they are in the resolved batch, so a pipeline run never touches work it did not start.
    """
    if everything:
        ids = None
    else:
        ids = {r["id"] for r in read_jsonl(WORK / "resolved.jsonl") if r["status"] == "ok"}
    out = []
    for p in sorted(RAW.glob("*.json")):
        if ids is not None and p.stem not in ids:
            continue
        if only and p.stem not in only:
            continue
        out.append(load_raw(p))
    return out


def get_bytes(url: str, deadline_s: float = 45.0, attempts: int = 3) -> bytes:
    """GET a binary file (a photo) with the per-host rate limit, a hard overall deadline per attempt (a server that
    trickles bytes would otherwise hang a worker forever) and a few retries on 429/5xx/timeouts."""
    host = re.match(r"https?://([^/]+)/", url).group(1)
    last = None
    for attempt in range(attempts):
        _limiter(host).wait()
        end = time.monotonic() + deadline_s
        try:
            req = urllib.request.Request(url, headers={"User-Agent": CONFIG["http"]["user_agent"]})
            with urllib.request.urlopen(req, timeout=20) as r:
                chunks = []
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
                    if time.monotonic() > end:
                        raise TimeoutError(f"download exceeded {deadline_s:.0f}s")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                try:
                    delay = float(e.headers.get("Retry-After", ""))
                except ValueError:
                    delay = 0
                time.sleep(min(max(delay, 4 * (attempt + 1)), 15))
                continue
            raise
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed after {attempts} attempts: {url}: {last}")
