#!/usr/bin/env python3
"""Drop the `car_data` collection from the configured MongoDB.

Usage:
  python scripts/drop_car_data.py

You can run this via Railway one-off as:
  railway run -- python scripts/drop_car_data.py
"""
from openf1.util.db import _get_mongo_client_sync, _MONGO_DATABASE


def main():
    client = _get_mongo_client_sync()
    db_name = __import__('os').getenv('OPENF1_DB_NAME') or _MONGO_DATABASE
    db = client.get_database(db_name)
    print('Using database:', db_name)
    cols = db.list_collection_names()
    print('Collections before:', cols)
    if 'car_data' in cols:
        db.car_data.drop()
        print('Dropped collection: car_data')
    else:
        print('No car_data collection found')
    print('Collections after:', db.list_collection_names())


if __name__ == '__main__':
    main()
