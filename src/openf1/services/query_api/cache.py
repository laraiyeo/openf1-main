import threading
import os

from cachetools import TTLCache

from openf1.services.query_api.query_params import QueryParam

_lock = threading.Lock()
# Allow cache TTL to be configured via env var `OPENF1_CACHE_TTL` (seconds).
# Default to 3 seconds to preserve previous behavior.
try:
    _ttl = int(os.getenv("OPENF1_CACHE_TTL", "3"))
except Exception:
    _ttl = 3

_cache = TTLCache(maxsize=1024, ttl=_ttl)


def _request_to_string(path: str, query_params: dict[str, list[QueryParam]]) -> str:
    # Sort params by value to ensure consistent hashes
    params_str = [
        str(sorted(params, key=lambda param: param.value))
        for params in query_params.values()
    ]
    return f"{path},{','.join(sorted(params_str))}"


def save_to_cache(path: str, query_params: list[str], results: list[dict]):
    request_key = _request_to_string(path, query_params)

    with _lock:
        _cache[request_key] = results


def get_from_cache(
    path: str, query_params: dict[str, list[QueryParam]]
) -> list[dict] | None:
    request_key = _request_to_string(path, query_params)
    with _lock:
        results = _cache.get(request_key)
    return results
