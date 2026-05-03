#!/usr/bin/env python3
"""Ingest all meetings/sessions for given years but omit `car_data` collection.

Usage:
    python scripts/ingest_all_no_cardata.py --years 2024 2025 2026

This script imports and calls the ingestor functions directly so you don't have
to specify meeting/session keys manually.
"""
import argparse
import logging
from typing import Iterable, List

from openf1.services.ingestor_livetiming.historical import main as hist_main
from openf1.util.schedule import get_meeting_keys, get_session_keys
from openf1.util.db import _get_mongo_db_sync


DEFAULT_COLLS = [
    "championship_drivers",
    "championship_teams",
    "drivers",
    "intervals",
    "laps",
    "location",
    "overtakes",
    "pit",
    "position",
    "race_control",
    "stints",
    "team_radio",
    "weather",
]


def ingest_meeting_no_cardata(year: int, meeting_key: int, collections: List[str], verbose: bool = True, skip_existing: bool = True):
    session_keys = get_session_keys(year=year, meeting_key=meeting_key)
    logging.info(f"Meeting {meeting_key}: found sessions {session_keys}")
    for sk in session_keys:
        logging.info(f"Ingesting year={year} meeting={meeting_key} session={sk}")
        if skip_existing:
            missing = []
            for c in collections:
                try:
                    if not _collection_has_data(c, sk, meeting_key):
                        missing.append(c)
                except Exception:
                    # If any issue checking collection, fall back to attempting ingest
                    missing.append(c)

            if not missing:
                logging.info(f"All collections present for session {sk}; skipping")
                continue

            logging.info(f"Collections missing for session {sk}: {missing}")
            try:
                hist_main.ingest_collections(
                    year=year,
                    meeting_key=meeting_key,
                    session_key=sk,
                    collection_names=missing,
                    verbose=verbose,
                )
            except Exception as exc:
                # Continue with next session instead of aborting the whole year.
                logging.exception(
                    f"Failed ingest for year={year} meeting={meeting_key} session={sk}: {exc}"
                )
                continue
        else:
            try:
                hist_main.ingest_collections(
                    year=year,
                    meeting_key=meeting_key,
                    session_key=sk,
                    collection_names=collections,
                    verbose=verbose,
                )
            except Exception as exc:
                logging.exception(
                    f"Failed ingest for year={year} meeting={meeting_key} session={sk}: {exc}"
                )
                continue


def _collection_has_data(collection: str, session_key: int, meeting_key: int) -> bool:
    """Return True if DB contains docs for this specific session.

    Important: checks are session-scoped by default to avoid false positives where
    one session's data makes another session look complete.
    """
    db = _get_mongo_db_sync()
    coll = db.get_collection(collection)
    # Primary check: strict per-session presence.
    query = {"session_key": session_key}

    # Fallback for legacy/edge docs that may be missing session_key.
    # Prefer meeting_key only for collections that are clearly meeting-scoped.
    meeting_scoped = {"meetings"}
    if collection in meeting_scoped:
        query = {"meeting_key": meeting_key}

    doc = coll.find_one(query)
    return doc is not None


def ingest_year(year: int, collections: List[str], verbose: bool = True, skip_existing: bool = True):
    meeting_keys = get_meeting_keys(year)
    logging.info(f"Year {year}: found meetings {meeting_keys}")
    for mk in meeting_keys:
        ingest_meeting_no_cardata(year, mk, collections, verbose=verbose, skip_existing=skip_existing)


def main(argv: Iterable[str] | None = None):
    parser = argparse.ArgumentParser(description="Ingest all meetings/sessions for years, omitting car_data")
    parser.add_argument("--years", nargs="+", type=int, required=True, help="Years to ingest, e.g. 2024 2025 2026")
    parser.add_argument("--collections", nargs="*", default=DEFAULT_COLLS, help="Collections to ingest (omit car_data)")
    parser.add_argument("--no-verbose", dest="verbose", action="store_false", help="Disable verbose logging inside ingestor calls")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", help="Skip collections already present in DB (default: true)")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false", help="Do not skip existing collections")
    parser.set_defaults(skip_existing=True)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    for y in args.years:
        logging.info(f"Starting ingestion for year {y}")
        ingest_year(y, args.collections, verbose=args.verbose, skip_existing=args.skip_existing)


if __name__ == "__main__":
    main()
