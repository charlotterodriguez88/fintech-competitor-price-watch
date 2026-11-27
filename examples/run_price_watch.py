import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.price_watch import CatalogCheck, build_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one competitor catalog check.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--reference", required=True, type=float)
    parser.add_argument("--schedule", default="0 * * * *")
    args = parser.parse_args()
    report = build_service().run(CatalogCheck(args.url, args.reference, args.schedule))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
