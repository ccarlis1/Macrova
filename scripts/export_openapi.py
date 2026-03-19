#!/usr/bin/env python3
"""Export FastAPI OpenAPI schema for contract checks and client codegen."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "openapi" / "openapi.json",
        help="Path to write openapi.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if --output differs from the freshly exported schema",
    )
    args = parser.parse_args()

    # Importing the app should not require real credentials in CI.
    os.environ.setdefault("USDA_API_KEY", "test-openapi-export-key")

    from src.api.server import app  # noqa: WPS433

    schema = app.openapi()
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not args.output.is_file():
            print(f"Missing OpenAPI snapshot: {args.output}", file=sys.stderr)
            sys.exit(1)
        existing = args.output.read_text(encoding="utf-8")
        if existing != text:
            print(
                "OpenAPI schema drift: run `python scripts/export_openapi.py` "
                f"and commit {args.output}",
                file=sys.stderr,
            )
            sys.exit(1)
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
