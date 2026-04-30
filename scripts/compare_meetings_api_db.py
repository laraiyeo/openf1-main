"""Compare meetings returned by the public F1 API with meetings in MongoDB.

Usage:
  # Local (uses MONGO_CONNECTION_STRING env or default in code)
  python scripts/compare_meetings_api_db.py --year 2026

  # Via Railway (pulls env from selected service)
  railway run -- python scripts/compare_meetings_api_db.py --year 2026

The script prints counts and lists meeting keys present only in the API,
only in the DB, and common to both.
"""

import argparse
from pprint import pprint

import requests

from openf1.util.db import _get_mongo_db_sync

BASE_URL = "https://api.openf1.org/v1"
HEADERS = {"Accept": "application/json"}


def fetch_api(kind: str, year: int | None = None) -> list[dict]:
    """Fetch `meetings` or `sessions` from api.openf1.org.

    Meetings endpoint: GET /v1/meetings?year=YYYY
    Sessions endpoint: GET /v1/sessions?year=YYYY
    """
    params = {"year": year} if year else {}
    if kind == "meetings":
        url = f"{BASE_URL}/meetings"
    elif kind == "sessions":
        url = f"{BASE_URL}/sessions"
    else:
        raise ValueError("kind must be 'meetings' or 'sessions'")

    resp = requests.get(url, params=params, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    # OpenF1 returns a list at top-level for these endpoints
    if isinstance(data, list):
        return data
    # If wrapped in an object, try common keys
    for key in ("meetings", "sessions", "data", "results"):
        if key in data:
            return data[key]
    return []


def get_db_items(collection: str, key_field: str) -> list[dict]:
    db = _get_mongo_db_sync()
    coll = db.get_collection(collection)
    docs = list(coll.find({}, projection={key_field: 1, "_id": 0}))
    return docs


def _detect_key(api_items: list[dict], candidates: list[str]) -> str | None:
    if not api_items:
        return None
    first = api_items[0]
    for cand in candidates:
        if cand in first:
            return cand
    # fallback: try to find any numeric-like key on items
    for k, v in first.items():
        if isinstance(v, (int, str)) and str(v).isdigit():
            return k
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=False)
    parser.add_argument(
    "--kind",
    choices=["meetings", "sessions", "both"],
    default="both",
    help="What to compare"
    )
    args = parser.parse_args()

    kinds = [args.kind] if args.kind != "both" else ["meetings", "sessions"]

    for kind in kinds:
        api_items = fetch_api(kind, args.year)

        if kind == "meetings":
            api_key_candidates = ["meetingKey", "meeting_key", "meetingKey"]
            db_collection = "meetings"
            db_key = "meeting_key"
        else:
            api_key_candidates = ["sessionKey", "session_key", "meetingSessionKey", "sessionKey"]
            db_collection = "sessions"
            db_key = "session_key"

        api_key_field = _detect_key(api_items, api_key_candidates)
        api_keys = []
        if api_key_field:
            for m in api_items:
                val = m.get(api_key_field)
                if val is not None:
                    try:
                        api_keys.append(int(val))
                    except Exception:
                        # non-numeric keys kept as-is
                        api_keys.append(val)

        db_items = get_db_items(db_collection, db_key)
        db_keys = [d.get(db_key) for d in db_items if d.get(db_key) is not None]

        api_set = set(api_keys)
        db_set = set(db_keys)

        print(f"\n=== Comparison for {kind} ===")
        print(f"API {kind} count: {len(api_keys)}")
        print(f"DB {kind} count:  {len(db_keys)}")

        only_in_api = sorted(api_set - db_set)
        only_in_db = sorted(db_set - api_set)
        in_both = sorted(api_set & db_set)

        print("Only in API (keys):")
        pprint(only_in_api)
        print("\nOnly in DB (keys):")
        pprint(only_in_db)
        print("\nIn both (keys):")
        pprint(in_both)


if __name__ == "__main__":
    main()
