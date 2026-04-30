"""Create recommended MongoDB indexes for OpenF1 collections.

Usage:
  # Create default recommended indexes
  python scripts/create_indexes.py

  # Create indexes for a single collection
  python scripts/create_indexes.py --collection location --keys session_key date
"""

import argparse
from pprint import pprint

from openf1.util.db import _get_mongo_db_sync


RECOMMENDED = {
    # Each entry is a list of index specifications; each spec is a list of (field, direction)
    "location": [[("session_key", 1), ("date", 1)]],
    "meetings": [[("meeting_key", 1)]],
    "sessions": [[("session_key", 1)], [("meeting_key", 1)]],
}


def create_index(collection: str, specs: list[list[tuple[str, int]]]):
    db = _get_mongo_db_sync()
    coll = db.get_collection(collection)
    created = []
    for spec in specs:
        name = coll.create_index(spec)
        created.append(name)
    return created


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", type=str, help="Collection name (optional)")
    parser.add_argument("--keys", nargs="*", help="Keys for a single-field index, e.g. session_key date")
    args = parser.parse_args()

    if args.collection and args.keys:
        keys = [[(k, 1)] for k in args.keys]
        created = create_index(args.collection, keys)
        print(f"Created indexes on {args.collection}:")
        pprint(created)
        return

    # Create recommended set
    for coll, keys in RECOMMENDED.items():
        print(f"Creating indexes for {coll}: {keys}")
        created = create_index(coll, keys)
        pprint(created)


if __name__ == "__main__":
    main()
