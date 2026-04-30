#!/usr/bin/env python3
"""Ingest `session_result` and `starting_grid` for all meetings/sessions in given years.

Usage:
    python scripts/ingest_scrapers.py --years 2026

This calls the scrapers in `openf1.services.f1_scraping` programmatically and
logs errors (continues on failure).
"""
import argparse
import logging
from typing import Iterable, List

from openf1.services.f1_scraping import session_result as sr_mod
from openf1.services.f1_scraping import starting_grid as sg_mod
from openf1.util.schedule import get_meeting_keys, get_session_keys


DEFAULT_COLLS = ["session_result", "starting_grid"]


def ingest_meeting_scrapers(year: int, meeting_key: int, collections: List[str]):
    session_keys = get_session_keys(year=year, meeting_key=meeting_key)
    logging.info(f"Meeting {meeting_key}: found sessions {session_keys}")
    for sk in session_keys:
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


def ingest_year(year: int, collections: List[str]):
    meeting_keys = get_meeting_keys(year)
    logging.info(f"Year {year}: found meetings {meeting_keys}")
    for mk in meeting_keys:
        ingest_meeting_scrapers(year, mk, collections)


def main(argv: Iterable[str] | None = None):
    parser = argparse.ArgumentParser(description="Ingest scrapers for years")
    parser.add_argument("--years", nargs="+", type=int, required=True, help="Years to ingest, e.g. 2024 2025 2026")
    parser.add_argument("--collections", nargs="*", default=DEFAULT_COLLS, help="Which scrapers to run")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    for y in args.years:
        logging.info(f"Starting ingestion for year {y}")
        ingest_year(y, args.collections)


if __name__ == "__main__":
    main()
