#!/usr/bin/env python3
"""Validate every plants/*.yaml against schema/plant.schema.json.

Run:  python3 tools/validate.py
Exits non-zero if any file is invalid, if the id does not match the
filename, or if a growth stage id is repeated.
"""
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    schema = json.loads((ROOT / "schema" / "plant.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    failures = 0
    files = sorted((ROOT / "plants").glob("*.yaml"))
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        problems = [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in validator.iter_errors(data)]
        if isinstance(data, dict):
            if data.get("id") != path.stem:
                problems.append(f"id {data.get('id')!r} does not match filename {path.stem!r}")
            ids = [s.get("id") for s in data.get("growth_stages", [])]
            if len(ids) != len(set(ids)):
                problems.append("duplicate growth stage ids")
        if problems:
            failures += 1
            print(f"FAIL {path.name}")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"ok   {path.name}")
    print(f"\n{len(files) - failures}/{len(files)} valid")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
