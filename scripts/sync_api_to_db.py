"""Sync missing meetings/sessions from api.openf1.org into MongoDB.

Usage:
  python scripts/sync_api_to_db.py --year 2026 --kind meetings --dry-run
  railway run -- python scripts/sync_api_to_db.py --year 2026 --kind both

Options:
  --year    Year to fetch (optional)
  --kind    meetings|sessions|both (default: both)
  --dry-run If set, do not perform any DB writes; only report what would be written.
"""

import argparse
from datetime import datetime
from pprint import pprint

import requests

from openf1.util.db import upsert_data_sync, _get_mongo_db_sync

BASE_URL = "https://api.openf1.org/v1"
HEADERS = {"Accept": "application/json"}


def fetch_api(kind: str, year: int | None = None) -> list[dict]:
    params = {"year": year} if year else {}
    url = f"{BASE_URL}/{kind}"
    resp = requests.get(url, params=params, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    for key in (kind, "data", "results"):
        if key in data:
            return data[key]
    return []


def get_db_keys(collection: str, key_field: str) -> set:
    db = _get_mongo_db_sync()
    coll = db.get_collection(collection)
    docs = coll.find({}, projection={key_field: 1, "_id": 0})
    return set(d.get(key_field) for d in docs if d.get(key_field) is not None)


def _parse_date_fields(doc: dict) -> dict:
    for fld in ("date_start", "date_end"):
        if fld in doc and isinstance(doc[fld], str):
            try:
                doc[fld] = datetime.fromisoformat(doc[fld])
            except Exception:
                pass
    return doc


def sync(kind: str, year: int | None, dry_run: bool):
    api_items = fetch_api(kind, year)
    if kind == "meetings":
        key_field = "meeting_key"
        coll = "meetings"
    else:
        key_field = "session_key"
        coll = "sessions"

    api_keys = set()
    for it in api_items:
        if key_field in it:
            api_keys.add(it[key_field])
        else:
            # try common alternatives
            for alt in ("meetingKey", "meeting_key", "meetingKey", "sessionKey", "meetingSessionKey"):
                if alt in it:
                    api_keys.add(int(it[alt]))
                    it[key_field] = int(it[alt])
                    break

    db_keys = get_db_keys(coll, key_field)
    missing = sorted(api_keys - db_keys)

    print(f"{kind}: API count={len(api_keys)} DB count={len(db_keys)} missing={len(missing)}")
    if not missing:
        return

    # Prepare docs to upsert
    docs_to_upsert = []
    for it in api_items:
        key = it.get(key_field)
        if key in missing:
            doc = dict(it)
            doc = _parse_date_fields(doc)
            doc["_key"] = key
            doc["_id"] = key
            docs_to_upsert.append(doc)

    print("Examples of docs to upsert:")
    pprint(docs_to_upsert[:3])

    if dry_run:
        print("Dry run; no writes performed.")
        return

    print(f"Upserting {len(docs_to_upsert)} documents into '{coll}'")
    upsert_data_sync(collection_name=coll, docs=docs_to_upsert)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=False)
    parser.add_argument("--kind", choices=["meetings", "sessions", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    kinds = [args.kind] if args.kind != "both" else ["meetings", "sessions"]
    for k in kinds:
        sync(k, args.year, args.dry_run)


if __name__ == "__main__":
    main()
