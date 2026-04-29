import os
import re
import time
import threading
import traceback

import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from loguru import logger

from openf1.services.query_api.cache import get_from_cache, save_to_cache
from openf1.services.query_api.csv import generate_csv_response
from openf1.services.query_api.query_params import (
    parse_query_params,
    query_params_raw_items_to_raw_dict,
    query_params_to_mongo_filters,
)
from openf1.util.db import get_documents

# Simple in-process rate limiter (configurable via env vars).
# Defaults mirror the previous decorator: 30 requests per 10 seconds.
try:
    RATE_LIMIT_COUNT = int(os.getenv("OPENF1_RATE_LIMIT_COUNT", "30"))
except Exception:
    RATE_LIMIT_COUNT = 30

try:
    RATE_LIMIT_WINDOW = int(os.getenv("OPENF1_RATE_LIMIT_WINDOW", "10"))
except Exception:
    RATE_LIMIT_WINDOW = 10

# Trusted API keys (comma separated) can optionally bypass limits when
# OPENF1_BYPASS_LIMIT_FOR_TRUSTED is set to "true".
TRUSTED_KEYS = [k.strip() for k in os.getenv("OPENF1_TRUSTED_API_KEYS", "").split(",") if k.strip()]
BYPASS_FOR_TRUSTED = os.getenv("OPENF1_BYPASS_LIMIT_FOR_TRUSTED", "false").lower() in ("1", "true", "yes")

# Optional higher limits for trusted keys
try:
    TRUSTED_RATE_LIMIT_COUNT = int(os.getenv("OPENF1_TRUSTED_RATE_LIMIT_COUNT", str(RATE_LIMIT_COUNT)))
except Exception:
    TRUSTED_RATE_LIMIT_COUNT = RATE_LIMIT_COUNT

try:
    TRUSTED_RATE_LIMIT_WINDOW = int(os.getenv("OPENF1_TRUSTED_RATE_LIMIT_WINDOW", str(RATE_LIMIT_WINDOW)))
except Exception:
    TRUSTED_RATE_LIMIT_WINDOW = RATE_LIMIT_WINDOW

# Window store: key -> (window_start_ts, count)
_rate_lock = threading.Lock()
_rate_windows: dict[str, tuple[float, int]] = {}

app = FastAPI()


def _get_request_key(request: Request) -> tuple[str, int, int]:
    """Return a tuple (identity_key, allowed_count, window_seconds).

    Identity is API key (if provided) or remote IP address.
    Trusted API keys may receive higher limits or bypass depending on env vars.
    """
    api_key = None
    # headers are case-insensitive; FastAPI provides a dict-like object
    if "x-api-key" in request.headers:
        api_key = request.headers.get("x-api-key")

    if api_key and api_key in TRUSTED_KEYS:
        if BYPASS_FOR_TRUSTED:
            return (f"api_key:{api_key}", 0, 0)  # special: bypass
        return (f"api_key:{api_key}", TRUSTED_RATE_LIMIT_COUNT, TRUSTED_RATE_LIMIT_WINDOW)

    # fallback to client IP
    client_host = "unknown"
    if request.client is not None:
        client_host = request.client.host

    return (f"ip:{client_host}", RATE_LIMIT_COUNT, RATE_LIMIT_WINDOW)


def check_rate_limit(request: Request) -> None:
    """Raise HTTPException(429) if rate limit exceeded for the request key."""
    key, allowed, window = _get_request_key(request)
    # allowed==0 and window==0 indicates bypass
    if allowed == 0 and window == 0:
        return

    now = time.time()
    with _rate_lock:
        window_start, count = _rate_windows.get(key, (now, 0))
        if now - window_start >= window:
            # reset window
            window_start = now
            count = 1
        else:
            count += 1

        _rate_windows[key] = (window_start, count)

        if count > allowed:
            logger.warning("Rate limit exceeded", key=key, count=count, allowed=allowed, window=window)
            raise HTTPException(status_code=429, detail="Too Many Requests")

# CORS middleware settings
# There are pretty much no security risks here as the app read-only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


_favicon = None


async def _get_favicon() -> Response:
    global _favicon

    if _favicon is not None:
        return Response(content=_favicon, media_type="image/png")

    favicon_url = "https://storage.googleapis.com/openf1-public/images/favicon.png"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(favicon_url) as resp:
                if resp.status == 200:
                    _favicon = await resp.read()
                    return Response(content=_favicon, media_type="image/png")
                raise HTTPException(status_code=404, detail="Favicon not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching favicon: {str(e)}")


def _parse_path(path: str) -> str:
    """
    Extracts the MongoDB collection name from an API path.
    The path is expected to be in the format "v1/{collection}".
    """
    path = path.lower()

    pattern = r"^v1/(\w+)$"
    match = re.match(pattern, path)

    if match:
        collection = match.group(1)
        return collection
    else:
        raise ValueError("Invalid route")


async def _process_request(request: Request, path: str) -> list[dict] | Response:
    if not path and not request.query_params.multi_items():
        return Response(content="Welcome to OpenF1!", media_type="text/plain")
    query_params = parse_query_params(
        query_params_raw_items_to_raw_dict(request.query_params.multi_items())
    )
    collection = _parse_path(path)
    use_csv = "csv" in query_params and query_params.pop("csv")[0].value

    results = get_from_cache(path=path, query_params=query_params)

    if results is None:
        mongodb_filter = query_params_to_mongo_filters(query_params)
        results = await get_documents(
            collection_name=collection, filters=mongodb_filter
        )
        save_to_cache(path=path, query_params=query_params, results=results)

    return (
        generate_csv_response(results, filename=f"{collection}.csv")
        if use_csv
        else results
    )


@app.api_route("/{path:path}", methods=["GET", "POST"])
async def endpoint(request: Request, path: str):
    try:
        # Enforce configurable in-process rate limit (may raise HTTPException(429))
        check_rate_limit(request)
        if path == "favicon.ico":
            return await _get_favicon()
        return await _process_request(request, path)
    except Exception as e:
        stack_trace = traceback.format_exc()
        error_msg = f"<h1>An error occurred</h1><pre>{stack_trace}</pre>"
        logger.error(
            f"Path: {path} | Headers: {dict(request.headers)}"
            f" | Query Parameters: {dict(request.query_params)}"
            f" | Exception: {e}"
        )
        return HTMLResponse(content=error_msg, status_code=500)
