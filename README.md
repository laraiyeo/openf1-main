# OpenF1 API

**OpenF1** is a free and open-source API that offers real-time and historical Formula 1 data.<br />
Whether you're a developer, data analyst, or F1 enthusiast, OpenF1 provides comprehensive
access to lap timings, car telemetry, driver information, race control messages, and more.

Explore the data through JSON or CSV formats to build dashboards, analyze races, or
integrate F1 data into your projects.

For full API documentation, visit [openf1.org](https://openf1.org).

## Key Features

- **Real-Time Data**: Stay updated with live lap times, speeds, and driver positioning.
- **Historical Data**: Analyze past races, compare performance over seasons, and dive deep into race strategy.
- **Car Telemetry**: Access in-depth car data, including throttle, brake, DRS, and gear information.
- **Driver Information**: Get details on F1 drivers, including team affiliations and performance metrics.

## Example Usage

Here’s a quick example of how to fetch lap data for a specific driver using the API:

```bash
curl "https://api.openf1.org/v1/laps?session_key=9161&driver_number=63&lap_number=8"
```

For more detailed examples and documentation, visit the [API Documentation](https://openf1.org).

## Running the project locally

1. Install and start [MongoDB Community Server](https://www.mongodb.com/try/download/community) v7 or v8

2. Install pip>=23 and python>=3.10

3. Install the OpenF1 python package

```bash
git clone git@github.com:br-g/openf1.git
pip install -e openf1
```

4. Configure the MongoDB connection

Set the **MONGO_CONNECTION_STRING** environment variable to connect to your local MongoDB instance:

```bash
export MONGO_CONNECTION_STRING="mongodb://localhost:27017"
```

5. Run the project

- Fetch and ingest scraped data: [services/f1_scraping/](src/openf1/services/f1_scraping/README.md)
- Fetch and ingest live timing data: [services/ingestor_livetiming/](src/openf1/services/ingestor_livetiming/README.md)
- Start and query the API: [services/query_api/](src/openf1/services/query_api/README.md)

### Running without an F1TV token

You can run the API and most live-timing endpoints without an `F1_TOKEN`. The project fetches a number of public live-timing resources (lap times, positions, session results, intervals, start grids) directly from Formula 1 timing endpoints and stores them in MongoDB. These endpoints generally work without an `F1_TOKEN`.

- What works without `F1_TOKEN`: session results, lap times, intervals, positions, basic live timing feeds collected from `livetiming.formula1.com`.
- What requires `F1_TOKEN`: detailed F1TV telemetry (high-frequency car telemetry like throttle, brake, gear, per-sample streams). `F1_TOKEN` is obtained from an F1TV subscription and typically expires frequently.

Be aware that scraping or high-rate polling of F1 endpoints may trigger blocks or violate terms of service. Use sensible caching and respect rate limits.

### Configurable limits and caching

The API includes a lightweight, in-memory rate limiter and a cache with sensible defaults. You can configure behaviour with environment variables:

- `OPENF1_RATE_LIMIT_COUNT` (default `30`) — number of allowed requests
- `OPENF1_RATE_LIMIT_WINDOW` (default `10`) — window in seconds for the count above
- `OPENF1_TRUSTED_API_KEYS` (default empty) — comma-separated keys that can be trusted clients
- `OPENF1_BYPASS_LIMIT_FOR_TRUSTED` (default `false`) — when `true`, trusted keys bypass rate limiting
- `OPENF1_TRUSTED_RATE_LIMIT_COUNT` and `OPENF1_TRUSTED_RATE_LIMIT_WINDOW` — alternate limits for trusted keys
- `OPENF1_CACHE_TTL` (default `3`) — cache TTL (seconds) used by the query API cache

To raise the default throughput locally, increase `OPENF1_RATE_LIMIT_COUNT` and/or `OPENF1_RATE_LIMIT_WINDOW`, or provide a trusted API key and set `OPENF1_BYPASS_LIMIT_FOR_TRUSTED=true`.

### Railway / hosted deployment notes

- Use the included `Dockerfile` and point Railway to this repository for Docker deployment. Alternatively, build the image locally and push it to a container registry.
- Provision a MongoDB instance (Railway add-on or MongoDB Atlas) and set `MONGO_CONNECTION_STRING`.
- Expose one service with `ROLE=api` for the query API. If you want ingestion of live telemetry, create a service with `ROLE=ingest-realtime` and set `F1_TOKEN` in environment variables (note token expiry and license considerations).

Example minimal env for the API service on Railway:

```
MONGO_CONNECTION_STRING=mongodb://<host>:<port>
ROLE=api
OPENF1_RATE_LIMIT_COUNT=300
OPENF1_RATE_LIMIT_WINDOW=60
OPENF1_CACHE_TTL=5
```

## Supporting OpenF1

If you find this project useful, consider supporting its long-term sustainability:

<div>
  <a href="https://www.buymeacoffee.com/openf1" target="_blank" style="text-decoration:none; border:none;">
    <img src="https://storage.googleapis.com/openf1-public/images/bmec_button.png" alt="Buy Me A Coffee" height="32" style="border:none; vertical-align:middle;">
  </a>
  &nbsp;
  <a href="https://github.com/sponsors/br-g" style="text-decoration:none; border:none;">
    <img src="https://img.shields.io/badge/Sponsor-%E2%9D%A4-brightgreen" alt="Sponsor me" height="32" style="border:none; vertical-align:middle;">
  </a>
</div>

## Disclaimer

OpenF1 is an unofficial project and is not affiliated with Formula 1 companies.
All F1-related trademarks are owned by Formula One Licensing B.V.
