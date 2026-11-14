"""Create a Macrova user data folder with an empty recipe pool (Sprint 2 BE-22).

Run from the repo root:

    python3 scripts/setup_user_data.py                 # ./user_data (gitignored)
    python3 scripts/setup_user_data.py --dir ~/macrova # any folder

Then start the API or CLI with ``MACROVA_DATA_DIR`` pointing at the folder. The
pool starts empty; import recipes from the starter pack with
``POST /api/v1/starter_recipes/import`` (list them with ``GET /api/v1/starter_recipes``).

An existing folder is never modified.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_layer import user_data  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dir",
        default=os.environ.get(user_data.ENV_VAR) or user_data.DEFAULT_USER_DATA_DIR,
        help="Folder to create (default: $MACROVA_DATA_DIR, else ./user_data).",
    )
    args = parser.parse_args(argv)
    folder = Path(args.dir).expanduser().resolve()

    if user_data.setup_user_data(folder):
        print(f"Created {folder} with an empty recipe pool.")
    else:
        print(f"{folder} already exists; left it untouched.")
    print(f"Use it with:  export {user_data.ENV_VAR}={folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
