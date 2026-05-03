#!/usr/bin/env python3
"""Ingest `session_result` and `starting_grid` for all meetings/sessions in given years.

Usage:
    python scripts/ingest_scrapers.py --years 2026
    python scripts/ingest_scrapers.py --years 2026 --skip-existing

This calls the scrapers in `openf1.services.f1_scraping` programmatically and
logs errors (continues on failure).
"""
import argparse
import logging
from typing import Iterable, List

from openf1.services.f1_scraping import session_result as sr_mod
from openf1.services.f1_scraping import starting_grid as sg_mod
from openf1.util.schedule import get_meeting_keys, get_session_keys
from openf1.util.db import _get_mongo_db_sync


DEFAULT_COLLS = ["session_result", "starting_grid"]


def _collection_has_data(collection: str, session_key: int) -> bool:
    """Return True if DB contains docs for this specific session."""
    db = _get_mongo_db_sync()
    coll = db.get_collection(collection)
    doc = coll.find_one({"session_key": session_key})
    return doc is not None


def ingest_meeting_scrapers(year: int, meeting_key: int, collections: List[str], skip_existing: bool = False):
    session_keys = get_session_keys(year=year, meeting_key=meeting_key)
    logging.info(f"Meeting {meeting_key}: found sessions {session_keys}")
    for sk in session_keys:
        if skip_existing:
            missing = []
            for c in collections:
                try:
                    if not _collection_has_data(c, sk):
                        missing.append(c)
                except Exception:
                    # If any issue checking collection, fall back to attempting ingest
                    missing.append(c)

            if not missing:
                logging.info(f"All scraper collections present for session {sk}; skipping")
                continue

            logging.info(f"Scraper collections missing for session {sk}: {missing}")
            collections = missing

        if "session_result" in collections:
            try:
                logging.info(f"Ingesting session_result for year={year} meeting={meeting_key} session={sk}")
                sr_mod.ingest_session_result(meeting_key=meeting_key, session_key=sk)
            except Exception:
                logging.exception(f"session_result ingestion failed for session {sk}")

        if "starting_grid" in collections:
            try:
                logging.info(f"Ingesting starting_grid for year={year} meeting={meeting_key} session={sk}")
                sg_mod.ingest_starting_grid(meeting_key=meeting_key, session_key=sk)
            except Exception:
                logging.exception(f"starting_grid ingestion failed for session {sk}")


def ingest_year(year: int, collections: List[str], skip_existing: bool = False):
    meeting_keys = get_meeting_keys(year)
    logging.info(f"Year {year}: found meetings {meeting_keys}")
    for mk in meeting_keys:
        ingest_meeting_scrapers(year, mk, collections, skip_existing=skip_existing)


def main(argv: Iterable[str] | None = None):
    parser = argparse.ArgumentParser(description="Ingest scrapers for years or latest session")
    parser.add_argument("--years", nargs="*", type=int, help="Years to ingest, e.g. 2024 2025 2026. Omit to ingest latest session only.")
    parser.add_argument("--collections", nargs="*", default=DEFAULT_COLLS, help="Which scrapers to run")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", help="Skip collections already present in DB")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # When no years provided, ingest the latest session (or session in progress)
    if not args.years:
        logging.info("No years provided; ingesting latest session only")
        try:
            # Determine latest meeting/session from schedule utils
            from openf1.util.schedule import get_latest_meeting_key, get_latest_session_key

            mk = get_latest_meeting_key()
            sk = get_latest_session_key()
            logging.info(f"Ingesting latest session: meeting={mk}, session={sk}")
            
            # Check for skip-existing when doing latest session
            if args.skip_existing:
                missing = []
                for c in args.collections:
                    try:
                        if not _collection_has_data(c, sk):
                            missing.append(c)
                    except Exception:
                        missing.append(c)
                if not missing:
                    logging.info(f"All scraper collections present for latest session {sk}; skipping")
                    return
                args.collections = missing
            
            # run session_result and starting_grid scrapers for the latest session
            if "session_result" in args.collections:
                logging.info(f"Ingesting session_result for meeting={mk} session={sk}")
                sr_mod.ingest_session_result(meeting_key=mk, session_key=sk)
            if "starting_grid" in args.collections:
                logging.info(f"Ingesting starting_grid for meeting={mk} session={sk}")
                sg_mod.ingest_starting_grid(meeting_key=mk, session_key=sk)
        except Exception:
            logging.exception("Failed to ingest latest session")
        return

    for y in args.years:
        logging.info(f"Starting ingestion for year {y}")
        ingest_year(y, args.collections, skip_existing=args.skip_existing)


if __name__ == "__main__":
    main()
