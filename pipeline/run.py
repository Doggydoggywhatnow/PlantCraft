#!/usr/bin/env python3
"""Run the whole pipeline (or parts of it) for a list of species.

    python3 pipeline/run.py pipeline/lists/example.txt                 # resolve -> fetch -> photos -> extract -> assemble -> report
    python3 pipeline/run.py my.txt --stages resolve fetch              # just the free, no-API-key stages
    python3 pipeline/run.py my.txt --stages assemble report            # re-assemble after editing defaults.yaml
    python3 pipeline/run.py my.txt --export-prompts                    # extract by hand/other tool instead of the API

Every stage is resumable: finished work is cached on disk and skipped, so after a crash or a
rate-limit pause just run the same command again.
"""
import argparse
import subprocess
import sys

import assemble
import fetch
import photos
import report
import resolve
from common import HERE, read_names
from pathlib import Path

STAGES = ["resolve", "fetch", "photos", "extract", "assemble", "report"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("list", help="species list file (names, genus:X, family:X)")
    ap.add_argument("--stages", nargs="+", choices=STAGES, default=STAGES)
    ap.add_argument("--accept-fuzzy", action="store_true", help="fetch fuzzy GBIF matches instead of flagging them")
    ap.add_argument("--limit", type=int, default=500, help="max species per genus:/family: line")
    ap.add_argument("--force", action="store_true", help="redo cached work in the chosen stages")
    ap.add_argument("--export-prompts", action="store_true", help="extract stage writes prompts instead of calling the API")
    ap.add_argument("--write", action="store_true", help="assemble stage publishes drafts into plants/ (never overwrites)")
    a = ap.parse_args()

    names = read_names(Path(a.list))
    if "resolve" in a.stages:
        resolve.run(names, a.accept_fuzzy, a.limit, force=a.force)
    if "fetch" in a.stages:
        fetch.run(force=a.force)
    if "photos" in a.stages:
        photos.run(force=a.force)
    if "extract" in a.stages:
        cmd = [sys.executable, str(HERE / "extract.py")] + (["--export"] if a.export_prompts else []) + (["--force"] if a.force else [])
        if subprocess.call(cmd) != 0:
            return 1
    if "assemble" in a.stages:
        assemble.assemble_all(write=a.write)
    if "report" in a.stages:
        report.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
