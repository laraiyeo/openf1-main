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


def ingest_meeting_no_cardata(year: int, meeting_key: int, collections: List[str], verbose: bool = True):
    session_keys = get_session_keys(year=year, meeting_key=meeting_key)
    logging.info(f"Meeting {meeting_key}: found sessions {session_keys}")
    for sk in session_keys:
        logging.info(f"Ingesting year={year} meeting={meeting_key} session={sk}")
        hist_main.ingest_collections(year=year, meeting_key=meeting_key, session_key=sk, collection_names=collections, verbose=verbose)


def ingest_year(year: int, collections: List[str], verbose: bool = True):
    meeting_keys = get_meeting_keys(year)
    logging.info(f"Year {year}: found meetings {meeting_keys}")
    for mk in meeting_keys:
        ingest_meeting_no_cardata(year, mk, collections, verbose=verbose)


def main(argv: Iterable[str] | None = None):
    parser = argparse.ArgumentParser(description="Ingest all meetings/sessions for years, omitting car_data")
    parser.add_argument("--years", nargs="+", type=int, required=True, help="Years to ingest, e.g. 2024 2025 2026")
    parser.add_argument("--collections", nargs="*", default=DEFAULT_COLLS, help="Collections to ingest (omit car_data)")
    parser.add_argument("--no-verbose", dest="verbose", action="store_false", help="Disable verbose logging inside ingestor calls")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    for y in args.years:
        logging.info(f"Starting ingestion for year {y}")
        ingest_year(y, args.collections, verbose=args.verbose)


if __name__ == "__main__":
    main()
