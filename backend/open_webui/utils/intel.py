"""
Offline intelligence helpers for the built-in "Intel" workspace.

This module is intentionally dependency free (besides ``httpx`` which Open WebUI
already ships with). It talks to Elasticsearch over its REST API, auto-detects the
schema of the flight dataset, normalises trajectories and offers a lightweight
retrieval layer that the frontend turns into an LLM prompt.

Everything is configured through environment variables so the workspace can run
completely offline behind a firewall:

    INTEL_ENABLE=true                     # kill switch for the whole workspace
    INTEL_ELASTICSEARCH_URL=...           # preferred; falls back to ELASTICSEARCH_URL
    INTEL_ELASTICSEARCH_INDEX=flights     # falls back to ELASTICSEARCH_INDEX
    INTEL_ELASTICSEARCH_API_KEY / _USERNAME / _PASSWORD
    INTEL_ELASTICSEARCH_VERIFY_CERTS=true
    INTEL_ELASTICSEARCH_CA_CERTS=/path/ca.pem
    INTEL_DEMO_MODE=auto                  # auto | on | off  (auto == demo when no URL)
    INTEL_TIME_FIELD / INTEL_ID_FIELD / INTEL_TRAJECTORY_FIELD ...  # manual overrides
    INTEL_DEFAULT_LOOKBACK_HOURS=24
    INTEL_MAX_ROWS=500
    INTEL_RAG_TOP_K=8
    INTEL_MAP_TILE_URL=                   # leave empty for the fully offline vector map
    INTEL_TOPIC_NAME / INTEL_TOPIC_PROMPT  # optional server-side override of the topic tab

The implementation is defensive on purpose: unknown schemas are common in
Elasticsearch deployments, so fields are detected from the index mapping and every
query has a fallback path.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional
from urllib.parse import quote

import httpx

# ---------------------------------------------------------------------------
# Optional imports (kept lazy so the module can be imported in unit tests)
# ---------------------------------------------------------------------------

try:  # pragma: no cover - loguru is a hard dependency in production
    from open_webui.utils.logger import log
except Exception:  # pragma: no cover
    import logging

    log = logging.getLogger(__name__)


class IntelError(Exception):
    """Base error for the intelligence workspace."""


class IntelUnavailable(IntelError):
    """Raised when Elasticsearch cannot be reached or returns an unusable answer."""


class IntelDisabled(IntelError):
    """Raised when the workspace has been disabled by the operator."""


# ---------------------------------------------------------------------------
# Small env helpers
# ---------------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class IntelConfig:
    enabled: bool = True
    es_url: str = ""
    es_index: str = "flights"
    es_api_key: str = ""
    es_username: str = ""
    es_password: str = ""
    es_verify_certs: bool = True
    es_ca_certs: str = ""
    es_timeout: float = 20.0

    demo_mode: str = "auto"

    time_field: str = ""
    id_field: str = ""
    callsign_field: str = ""
    trajectory_field: str = ""
    lat_field: str = ""
    lon_field: str = ""
    alt_field: str = ""
    speed_field: str = ""
    heading_field: str = ""
    status_field: str = ""

    query_fields: list[str] = field(default_factory=list)

    default_lookback_hours: float = 24.0
    max_rows: int = 500
    max_trajectory_docs: int = 2000
    max_trajectory_points: int = 1200
    rag_top_k: int = 8
    rag_max_snippet: int = 4000

    map_tile_url: str = ""

    topic_name: str = ""
    topic_prompt: str = ""
    topic_suggestions: list[str] = field(default_factory=list)

    @property
    def configured(self) -> bool:
        return bool(self.es_url)

    @property
    def demo(self) -> bool:
        """Whether the workspace should serve synthetic demo data."""
        mode = (self.demo_mode or "auto").lower()
        if mode in {"on", "true", "yes", "1"}:
            return True
        if mode in {"off", "false", "no", "0"}:
            return False
        return not self.configured

    def public(self) -> dict[str, Any]:
        """Configuration safe to expose to the browser (never includes secrets)."""
        return {
            "enabled": self.enabled,
            "demo": self.demo,
            "demo_mode": self.demo_mode,
            "elasticsearch": {
                "configured": self.configured,
                "url": _redact_url(self.es_url),
                "index": self.es_index,
                "verify_certs": self.es_verify_certs,
            },
            "fields": {
                "time": self.time_field or None,
                "id": self.id_field or None,
                "callsign": self.callsign_field or None,
                "trajectory": self.trajectory_field or None,
                "lat": self.lat_field or None,
                "lon": self.lon_field or None,
                "altitude": self.alt_field or None,
                "speed": self.speed_field or None,
                "heading": self.heading_field or None,
                "status": self.status_field or None,
            },
            "query_fields": self.query_fields,
            "default_lookback_hours": self.default_lookback_hours,
            "max_rows": self.max_rows,
            "rag_top_k": self.rag_top_k,
            "map_tile_url": self.map_tile_url,
            "topic": {
                "name": self.topic_name,
                "prompt": self.topic_prompt,
                "suggestions": self.topic_suggestions,
            },
        }


def _redact_url(url: str) -> str:
    """Hide credentials embedded in a URL."""
    if not url:
        return ""
    return re.sub(r"//([^/@\s]+)@", "//***@", url)


def get_config() -> IntelConfig:
    """Build the runtime configuration from the environment (cheap, stateless)."""
    es_url = _env("INTEL_ELASTICSEARCH_URL") or _env("ELASTICSEARCH_URL")
    return IntelConfig(
        enabled=_env_bool("INTEL_ENABLE", True),
        es_url=es_url.rstrip("/"),
        es_index=_env("INTEL_ELASTICSEARCH_INDEX") or _env("ELASTICSEARCH_INDEX") or "flights",
        es_api_key=_env("INTEL_ELASTICSEARCH_API_KEY") or _env("ELASTICSEARCH_API_KEY"),
        es_username=_env("INTEL_ELASTICSEARCH_USERNAME") or _env("ELASTICSEARCH_USERNAME"),
        es_password=_env("INTEL_ELASTICSEARCH_PASSWORD") or _env("ELASTICSEARCH_PASSWORD"),
        es_verify_certs=_env_bool("INTEL_ELASTICSEARCH_VERIFY_CERTS", True),
        es_ca_certs=_env("INTEL_ELASTICSEARCH_CA_CERTS") or _env("ELASTICSEARCH_CA_CERTS"),
        es_timeout=_env_float("INTEL_ELASTICSEARCH_TIMEOUT", 20.0),
        demo_mode=(_env("INTEL_DEMO_MODE", "auto") or "auto").lower(),
        time_field=_env("INTEL_TIME_FIELD"),
        id_field=_env("INTEL_ID_FIELD"),
        callsign_field=_env("INTEL_CALLSIGN_FIELD"),
        trajectory_field=_env("INTEL_TRAJECTORY_FIELD"),
        lat_field=_env("INTEL_LAT_FIELD"),
        lon_field=_env("INTEL_LON_FIELD"),
        alt_field=_env("INTEL_ALT_FIELD"),
        speed_field=_env("INTEL_SPEED_FIELD"),
        heading_field=_env("INTEL_HEADING_FIELD"),
        status_field=_env("INTEL_STATUS_FIELD"),
        query_fields=_split_csv(_env("INTEL_QUERY_FIELDS")),
        default_lookback_hours=_env_float("INTEL_DEFAULT_LOOKBACK_HOURS", 24.0),
        max_rows=_env_int("INTEL_MAX_ROWS", 500),
        max_trajectory_docs=_env_int("INTEL_MAX_TRAJECTORY_DOCS", 2000),
        max_trajectory_points=_env_int("INTEL_MAX_TRAJECTORY_POINTS", 1200),
        rag_top_k=_env_int("INTEL_RAG_TOP_K", 8),
        rag_max_snippet=_env_int("INTEL_RAG_MAX_SNIPPET", 4000),
        map_tile_url=_env("INTEL_MAP_TILE_URL"),
        topic_name=_env("INTEL_TOPIC_NAME"),
        topic_prompt=_env("INTEL_TOPIC_PROMPT"),
        topic_suggestions=_split_csv(_env("INTEL_TOPIC_SUGGESTIONS")),
    )


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def parse_datetime(value: Any) -> Optional[datetime]:
    """Parse ISO-8601 strings, epoch seconds/milliseconds and datetime objects."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            return None
        seconds = value / 1000.0 if value > 1e11 else float(value)
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return parse_datetime(int(text))
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_time_range(
    start: Any = None, end: Any = None, hours: Any = None, default_hours: float = 24.0
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    parsed_end = parse_datetime(end) or now
    parsed_start = parse_datetime(start)
    if parsed_start is None:
        lookback = default_hours
        try:
            if hours not in (None, ""):
                lookback = float(hours)
        except (TypeError, ValueError):
            lookback = default_hours
        lookback = _clamp(lookback, 0.05, 24 * 365)
        parsed_start = parsed_end - timedelta(hours=lookback)
    if parsed_start > parsed_end:
        parsed_start, parsed_end = parsed_end, parsed_start
    return parsed_start, parsed_end


# ---------------------------------------------------------------------------
# Elasticsearch REST client
# ---------------------------------------------------------------------------


class ElasticsearchClient:
    """Tiny async Elasticsearch client built on top of httpx."""

    def __init__(self, config: IntelConfig):
        self.config = config
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if config.es_api_key:
            headers["Authorization"] = f"ApiKey {config.es_api_key}"
        elif config.es_username:
            import base64

            token = base64.b64encode(f"{config.es_username}:{config.es_password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"

        verify: bool | str = config.es_verify_certs
        if config.es_ca_certs:
            verify = config.es_ca_certs

        self._client = httpx.AsyncClient(
            base_url=config.es_url,
            headers=headers,
            verify=verify,
            timeout=httpx.Timeout(config.es_timeout, connect=min(5.0, config.es_timeout)),
        )

    async def __aenter__(self) -> "ElasticsearchClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        try:
            await self._client.aclose()
        except Exception:  # pragma: no cover - best effort
            pass

    async def request(
        self, method: str, path: str, *, json_body: Any = None, params: dict | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, json=json_body, params=params)
        except httpx.HTTPError as exc:
            raise IntelUnavailable(f"Elasticsearch is unreachable: {exc}") from exc

        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
                detail = payload.get("error", {}).get("reason") or payload.get("error")
            except Exception:
                detail = response.text[:400]
            raise IntelUnavailable(
                f"Elasticsearch returned HTTP {response.status_code}: {detail or 'unknown error'}"
            )

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise IntelUnavailable("Elasticsearch returned a non JSON response") from exc

    async def ping(self) -> dict[str, Any]:
        return await self.request("GET", "/")

    async def get_mapping(self, index: str) -> dict[str, Any]:
        return await self.request("GET", f"/{quote(index, safe='*,-_.')}/_mapping")

    async def count(self, index: str) -> int:
        payload = await self.request("GET", f"/{quote(index, safe='*,-_.')}/_count")
        return int(payload.get("count") or 0)

    async def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self.request(
            "POST",
            f"/{quote(index, safe='*,-_.')}/_search",
            json_body=body,
            params={"ignore_unavailable": "true", "allow_no_indices": "true"},
        )


# ---------------------------------------------------------------------------
# Schema detection
# ---------------------------------------------------------------------------

_FIELD_CANDIDATES: dict[str, list[str]] = {
    "time": [
        "@timestamp",
        "timestamp",
        "time",
        "event_time",
        "eventtime",
        "datetime",
        "date",
        "created_at",
        "recorded_at",
        "position_time",
    ],
    "id": [
        "flight_id",
        "flightid",
        "flightId",
        "icao24",
        "icao_24",
        "icao",
        "hex",
        "aircraft_id",
        "aircraftid",
        "tail_number",
        "tail",
        "registration",
        "reg",
        "callsign",
        "ident",
        "flight",
        "id",
    ],
    "callsign": [
        "callsign",
        "call_sign",
        "flight_number",
        "flight_no",
        "flightnumber",
        "ident",
        "flight",
        "name",
        "aircraft",
    ],
    "lat": [
        "lat",
        "latitude",
        "position.lat",
        "position.latitude",
        "location.lat",
        "location.latitude",
        "last_position.lat",
        "coordinates.lat",
        "coords.lat",
        "geo.lat",
        "y",
    ],
    "lon": [
        "lon",
        "lng",
        "long",
        "longitude",
        "position.lon",
        "position.lng",
        "position.longitude",
        "location.lon",
        "location.lng",
        "location.longitude",
        "last_position.lon",
        "last_position.lng",
        "coordinates.lon",
        "coordinates.lng",
        "coords.lon",
        "coords.lng",
        "geo.lon",
        "x",
    ],
    "altitude": [
        "altitude",
        "alt",
        "alt_baro",
        "baro_altitude",
        "geo_altitude",
        "altitude_ft",
        "altitude_m",
        "elevation",
        "height",
        "z",
    ],
    "speed": ["ground_speed", "speed", "gs", "velocity", "speed_kt", "groundspeed", "tas", "ias"],
    "heading": ["heading", "track", "course", "true_track", "bearing", "direction"],
    "status": ["status", "flight_status", "state", "phase"],
}

_IGNORED_QUERY_TYPES = {"geo_point", "geo_shape", "dense_vector", "sparse_vector", "binary", "object", "nested"}


@dataclass
class Schema:
    time_field: str = ""
    id_field: str = ""
    callsign_field: str = ""
    trajectory_field: str = ""
    lat_field: str = ""
    lon_field: str = ""
    alt_field: str = ""
    speed_field: str = ""
    heading_field: str = ""
    status_field: str = ""
    query_fields: list[str] = field(default_factory=list)
    date_fields: list[str] = field(default_factory=list)
    id_agg_field: str = "_id"


def flatten_mapping(properties: dict[str, Any], prefix: str = "") -> dict[str, dict[str, Any]]:
    """Flatten an ES ``_mapping.properties`` dict into dotted paths."""
    flat: dict[str, dict[str, Any]] = {}
    for name, spec in (properties or {}).items():
        if not isinstance(spec, dict):
            continue
        path = f"{prefix}{name}"
        field_type = spec.get("type")
        if field_type in {"nested", "object"} or "properties" in spec:
            flat[path] = {"type": field_type or "object", "aggable": False}
            flat.update(flatten_mapping(spec.get("properties") or {}, f"{path}."))
            # ``nested``/``object`` without a type can still hold scalar leaf data,
            # so make the container itself available for existence checks.
        else:
            flat[path] = {
                "type": field_type or "keyword",
                "aggable": (field_type in {None, "keyword", "boolean", "integer", "long", "short", "byte"})
                or bool(spec.get("fields", {}).get("keyword")),
                "keyword_subfield": "keyword" in (spec.get("fields") or {}),
            }
    return flat


def pick_field(flat: dict[str, dict[str, Any]], candidates: Iterable[str]) -> str:
    lowered = {path.lower(): path for path in flat}
    for candidate in candidates:
        match = lowered.get(candidate.lower())
        if match:
            return match
    return ""


def detect_schema(mapping: dict[str, Any], config: IntelConfig) -> Schema:
    """Detect the relevant fields for the flight dataset.

    ``mapping`` is the raw response of ``GET /<index>/_mapping``. Manual overrides
    from the configuration always win.
    """
    flat: dict[str, dict[str, Any]] = {}
    for index_meta in (mapping or {}).values():
        mappings = (index_meta or {}).get("mappings") or {}
        flat.update(flatten_mapping(mappings.get("properties") or {}))
        flat.update(flatten_mapping((mappings.get("_doc") or {}).get("properties") or {}))

    schema = Schema()
    schema.date_fields = [path for path, spec in flat.items() if spec.get("type") == "date"]

    schema.time_field = config.time_field or pick_field(flat, _FIELD_CANDIDATES["time"])
    if not schema.time_field and schema.date_fields:
        schema.time_field = sorted(schema.date_fields)[0]

    schema.id_field = config.id_field or pick_field(flat, _FIELD_CANDIDATES["id"])
    schema.callsign_field = config.callsign_field or pick_field(flat, _FIELD_CANDIDATES["callsign"])
    schema.lat_field = config.lat_field or pick_field(flat, _FIELD_CANDIDATES["lat"])
    schema.lon_field = config.lon_field or pick_field(flat, _FIELD_CANDIDATES["lon"])
    schema.alt_field = config.alt_field or pick_field(flat, _FIELD_CANDIDATES["altitude"])
    schema.speed_field = config.speed_field or pick_field(flat, _FIELD_CANDIDATES["speed"])
    schema.heading_field = config.heading_field or pick_field(flat, _FIELD_CANDIDATES["heading"])
    schema.status_field = config.status_field or pick_field(flat, _FIELD_CANDIDATES["status"])

    if config.trajectory_field:
        schema.trajectory_field = config.trajectory_field
    else:
        trajectory_candidates = [
            "trajectory",
            "trajectories",
            "track",
            "path",
            "route",
            "positions",
            "flight_path",
            "trail",
        ]
        schema.trajectory_field = pick_field(flat, trajectory_candidates)
        if not schema.trajectory_field:
            for path in flat:
                if "trajector" in path.lower() or path.lower().endswith(".track"):
                    schema.trajectory_field = path
                    break

    # The id field is used inside a terms aggregation; text fields without a
    # keyword sub-field cannot be aggregated directly.
    if schema.id_field and schema.id_field in flat:
        spec = flat[schema.id_field]
        if spec.get("aggable"):
            schema.id_agg_field = schema.id_field
        elif spec.get("keyword_subfield"):
            schema.id_agg_field = f"{schema.id_field}.keyword"
        else:
            schema.id_agg_field = "_id"
    elif schema.id_field and schema.id_field != "_id":
        schema.id_agg_field = schema.id_field

    if config.query_fields:
        schema.query_fields = list(config.query_fields)
    else:
        candidates = []
        for path, spec in flat.items():
            if path.startswith("_") or spec.get("type") in _IGNORED_QUERY_TYPES:
                continue
            if spec.get("type") in {"text", "keyword", "match_only_text"}:
                candidates.append(path)
        # Prefer human readable text fields first.
        priority = ["callsign", "flight", "description", "notes", "message", "content", "text", "name"]
        candidates.sort(key=lambda path: next((i for i, p in enumerate(priority) if p in path.lower()), len(priority)))
        schema.query_fields = candidates[:40]

    return schema


_SCHEMA_CACHE: dict[str, tuple[float, Schema]] = {}
_SCHEMA_LOCK = asyncio.Lock()
_SCHEMA_TTL = 120.0


async def get_schema(client: ElasticsearchClient, config: IntelConfig) -> Schema:
    key = f"{config.es_url}|{config.es_index}|{config.time_field}|{config.trajectory_field}"
    now = time.monotonic()
    cached = _SCHEMA_CACHE.get(key)
    if cached and now - cached[0] < _SCHEMA_TTL:
        return cached[1]
    async with _SCHEMA_LOCK:
        cached = _SCHEMA_CACHE.get(key)
        if cached and time.monotonic() - cached[0] < _SCHEMA_TTL:
            return cached[1]
        mapping = await client.get_mapping(config.es_index)
        schema = detect_schema(mapping, config)
        if not schema.id_field:
            schema.id_field = "_id"
        _SCHEMA_CACHE[key] = (time.monotonic(), schema)
        return schema


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------


def get_path(source: Any, path: str) -> Any:
    if not path or not isinstance(source, dict):
        return None
    if path in source:
        return source[path]
    current: Any = source
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list):
            return None
        else:
            return None
    return current


_LAT_KEYS = ("lat", "latitude", "Lat", "LAT", "y")
_LON_KEYS = ("lon", "lng", "long", "longitude", "Lon", "LON", "x")
_ALT_KEYS = ("alt", "altitude", "altitude_ft", "altitude_m", "baro_alt", "height", "elevation", "z")
_TIME_KEYS = (
    "timestamp",
    "time",
    "ts",
    "t",
    "datetime",
    "date",
    "@timestamp",
    "recorded_at",
    "updated_at",
)


def _first_key(mapping: dict, keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        text = value.strip().replace("°", "")
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _looks_like_geojson(value: Any) -> bool:
    return isinstance(value, dict) and str(value.get("type") or "").lower() == "linestring"


def normalize_trajectory(value: Any, config: IntelConfig | None = None) -> list[dict[str, Any]]:
    """Normalise the many possible trajectory encodings into ``[{lat, lon, alt, ts}]``.

    Supported shapes::

        [{"lat": .., "lon": .., "alt": .., "timestamp": ..}, ...]
        [[lat, lon], [lat, lon, alt], ...]          # common in telemetry dumps
        [[lon, lat], ...]  / GeoJSON LineString     # detected via coordinate ranges
        {"points": [...]} / {"type": "LineString", "coordinates": [...]}
        "[{...}]"                                   # JSON encoded string
    """
    points: list[dict[str, Any]] = []

    def push(lat: Optional[float], lon: Optional[float], alt: Any, ts: Any):
        if lat is None or lon is None:
            return
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return
        point = {"lat": round(lat, 6), "lon": round(lon, 6)}
        altitude = _to_float(alt)
        if altitude is not None:
            point["alt"] = round(altitude, 1)
        parsed_ts = parse_datetime(ts)
        if parsed_ts is not None:
            point["ts"] = iso(parsed_ts)
        points.append(point)

    def from_pair(item: list | tuple):
        numbers = [_to_float(entry) for entry in item]
        numbers = [entry for entry in numbers if entry is not None]
        if len(numbers) < 2:
            return
        first, second = numbers[0], numbers[1]
        # [lon, lat] is the GeoJSON order; infer it when the ranges make it obvious.
        if abs(first) > 90 and abs(second) <= 90:
            lat, lon = second, first
        elif abs(second) > 90 and abs(first) <= 90:
            lat, lon = first, second
        else:
            lat, lon = first, second
        alt = numbers[2] if len(numbers) > 2 else None
        push(lat, lon, alt, None)

    def walk(node: Any, depth: int = 0):
        if node is None or depth > 6:
            return
        if isinstance(node, str):
            text = node.strip()
            if text[:1] in "[{" and len(text) < 5_000_000:
                try:
                    walk(json.loads(text), depth + 1)
                except (ValueError, TypeError):
                    return
            return
        if isinstance(node, dict):
            node_type = str(node.get("type") or "").lower()
            if node_type in {"linestring", "multilinestring", "geometrycollection"}:
                coordinates = node.get("coordinates")
                if node_type == "linestring":
                    for item in coordinates or []:
                        if isinstance(item, (list, tuple)):
                            from_pair(item)
                elif node_type == "multilinestring":
                    for line in coordinates or []:
                        for item in line or []:
                            if isinstance(item, (list, tuple)):
                                from_pair(item)
                else:
                    for geometry in node.get("geometries") or []:
                        walk(geometry, depth + 1)
                return
            if str(node.get("type") or "").lower() == "feature":
                walk(node.get("geometry"), depth + 1)
                return
            for key in ("points", "coordinates", "path", "trajectory", "positions", "track", "trail", "data"):
                if key in node:
                    walk(node[key], depth + 1)
                    if points:
                        return
            lat = _to_float(_first_key(node, _LAT_KEYS))
            lon = _to_float(_first_key(node, _LON_KEYS))
            alt = _first_key(node, _ALT_KEYS)
            ts = _first_key(node, _TIME_KEYS)
            if lat is None and lon is None:
                # Nested ``{"position": {"lat": ..}}`` style documents.
                for nested_key in ("position", "location", "last_position", "current_position", "coords"):
                    nested = node.get(nested_key)
                    if isinstance(nested, dict):
                        lat = _to_float(_first_key(nested, _LAT_KEYS))
                        lon = _to_float(_first_key(nested, _LON_KEYS))
                        alt = alt if alt is not None else _first_key(nested, _ALT_KEYS)
                        ts = ts if ts is not None else _first_key(nested, _TIME_KEYS)
                        if lat is not None and lon is not None:
                            break
            push(lat, lon, alt, ts)
            return
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and all(_to_float(item) is not None for item in node[:4]):
                from_pair(node)
                return
            for item in node:
                if isinstance(item, (dict, str, list, tuple)):
                    walk(item, depth + 1)
            return

    walk(value)
    if points:
        # Sort by timestamp when available, keeping the original order otherwise.
        if all(point.get("ts") for point in points):
            points.sort(key=lambda point: point["ts"])
        deduped: list[dict[str, Any]] = []
        seen: set[tuple] = set()
        for point in points:
            key = (point["lat"], point["lon"], point.get("ts"), point.get("alt"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(point)
        return deduped
    return points


def extract_position(
    source: dict[str, Any], schema: Schema, config: IntelConfig | None = None
) -> tuple[Optional[float], Optional[float], Optional[float], list[dict[str, Any]]]:
    """Return ``(lat, lon, altitude, trajectory_points)`` for one document."""
    trajectory: list[dict[str, Any]] = []
    if schema.trajectory_field:
        trajectory = normalize_trajectory(get_path(source, schema.trajectory_field), config)

    lat = _to_float(get_path(source, schema.lat_field)) if schema.lat_field else None
    lon = _to_float(get_path(source, schema.lon_field)) if schema.lon_field else None

    if lat is None or lon is None:
        for nested_key in ("position", "location", "last_position", "current_position", "coordinates"):
            nested = source.get(nested_key)
            if isinstance(nested, dict):
                nested_lat = _to_float(_first_key(nested, _LAT_KEYS))
                nested_lon = _to_float(_first_key(nested, _LON_KEYS))
                if nested_lat is not None and nested_lon is not None:
                    lat, lon = nested_lat, nested_lon
                    break
            elif isinstance(nested, (list, tuple)) and len(nested) >= 2:
                first, second = _to_float(nested[0]), _to_float(nested[1])
                if first is not None and second is not None:
                    if abs(first) > 90:  # GeoJSON [lon, lat]
                        first, second = second, first
                    lat, lon = first, second
                    break

    altitude = _to_float(get_path(source, schema.alt_field)) if schema.alt_field else None
    if (lat is None or lon is None) and trajectory:
        last = trajectory[-1]
        lat = lat if lat is not None else last.get("lat")
        lon = lon if lon is not None else last.get("lon")

    if trajectory and lat is not None and lon is not None:
        last = trajectory[-1]
        if (last.get("lat"), last.get("lon")) != (round(lat, 6), round(lon, 6)):
            trajectory.append({"lat": round(lat, 6), "lon": round(lon, 6)})

    return lat, lon, altitude, trajectory


def _string(value: Any, limit: int = 120) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            value = str(value)
    return str(value)[:limit]


def flight_from_hit(hit: dict[str, Any], schema: Schema, config: IntelConfig) -> dict[str, Any]:
    """Convert an Elasticsearch hit into the row shape used by the UI."""
    source = hit.get("_source") or {}
    hit_id = hit.get("_id") or ""
    lat, lon, altitude, trajectory = extract_position(source, schema, config)

    def field_value(name: str) -> Any:
        return get_path(source, name) if name else None

    identifier = _string(field_value(schema.id_field) or hit_id)
    callsign = _string(field_value(schema.callsign_field)) or identifier
    timestamp = iso(parse_datetime(field_value(schema.time_field))) if schema.time_field else None

    row = {
        "id": identifier,
        "doc_id": hit_id,
        "callsign": callsign,
        "time": timestamp,
        "lat": round(lat, 6) if lat is not None else None,
        "lon": round(lon, 6) if lon is not None else None,
        "altitude": altitude,
        "speed": _to_float(field_value(schema.speed_field)),
        "heading": _to_float(field_value(schema.heading_field)),
        "status": _string(field_value(schema.status_field)) or None,
        "points": len(trajectory),
        "source": "elasticsearch",
    }
    # A couple of widely used extras, when present.
    for key, candidate in (
        ("origin", ("origin", "origin_airport", "departure", "departure_airport", "from")),
        ("destination", ("destination", "destination_airport", "arrival", "arrival_airport", "to")),
        ("registration", ("registration", "reg", "tail", "tail_number")),
        ("aircraft_type", ("aircraft_type", "type", "model", "ac_type")),
    ):
        for name in candidate:
            if name in source:
                value = _string(source[name], 80)
                if value:
                    row[key] = value
                    break
    return row


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------


def build_time_filter(schema: Schema, start: datetime, end: datetime) -> list[dict[str, Any]]:
    if not schema.time_field:
        return []
    return [
        {
            "range": {
                schema.time_field: {
                    "gte": iso(start),
                    "lte": iso(end),
                    "format": "strict_date_optional_time",
                }
            }
        }
    ]


def build_text_query(query: str, schema: Schema) -> Optional[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return None
    fields = schema.query_fields or ["*"]
    return {
        "bool": {
            "should": [
                {
                    "multi_match": {
                        "query": query,
                        "fields": fields,
                        "type": "best_fields",
                        "lenient": True,
                        "fuzziness": "AUTO",
                    }
                },
                {"multi_match": {"query": query, "fields": fields, "type": "phrase", "lenient": True}},
            ],
            "minimum_should_match": 1,
        }
    }


def _aggregatable_field(schema: Schema) -> str:
    """The id field may be a ``text`` field without a keyword sub-field."""
    return schema.id_agg_field or "_id"


def build_latest_flights_body(
    schema: Schema,
    start: datetime,
    end: datetime,
    query: str,
    size: int,
    extra_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregation based latest-state-per-aircraft query.

    Using ``top_hits`` gives us the most recent document per aircraft, which keeps
    the table correct even for per-second telemetry indexes.
    """
    filters = build_time_filter(schema, start, end)
    for field_name, value in (extra_filters or {}).items():
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            filters.append({"terms": {field_name: value}})
        else:
            filters.append({"term": {field_name: value}})

    text_query = build_text_query(query, schema)
    query_block: dict[str, Any] = {"bool": {"filter": filters}}
    if text_query:
        query_block["bool"]["must"] = [text_query]

    latest_sub_agg: dict[str, Any] = {"max": {"field": schema.time_field}} if schema.time_field else {"value_count": {"field": "_index"}}
    orders: list[dict[str, Any]] = [{"latest": "desc"}, {"_count": "desc"}]

    return {
        "size": 0,
        "track_total_hits": True,
        "query": query_block,
        "aggs": {
            "aircraft_count": {"cardinality": {"field": _aggregatable_field(schema), "precision_threshold": 40000}},
            "latest": {
                "terms": {
                    "field": _aggregatable_field(schema),
                    "size": size,
                    "order": orders,
                },
                "aggs": {
                    "latest": latest_sub_agg,
                    "doc": {
                        "top_hits": {
                            "size": 1,
                            "sort": [{schema.time_field: {"order": "desc", "unmapped_type": "date"}}]
                            if schema.time_field
                            else [{"_doc": {"order": "desc"}}],
                            "_source": {"excludes": [schema.trajectory_field] if schema.trajectory_field else []},
                        }
                    },
                },
            },
        },
    }


def build_scan_body(
    schema: Schema,
    start: datetime,
    end: datetime,
    query: str,
    size: int,
    extra_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fallback plain search used when the id field is not aggregatable."""
    filters = build_time_filter(schema, start, end)
    for field_name, value in (extra_filters or {}).items():
        if value in (None, "", []):
            continue
        filters.append({"terms": {field_name: value}} if isinstance(value, list) else {"term": {field_name: value}})

    text_query = build_text_query(query, schema)
    query_block: dict[str, Any] = {"bool": {"filter": filters}}
    if text_query:
        query_block["bool"]["must"] = [text_query]

    body: dict[str, Any] = {
        "size": size,
        "track_total_hits": True,
        "query": query_block,
        "_source": {"excludes": [schema.trajectory_field] if schema.trajectory_field else []},
    }
    if schema.time_field:
        body["sort"] = [{schema.time_field: {"order": "desc", "unmapped_type": "date"}}, {"_doc": "desc"}]
    return body


def build_trajectory_body(
    schema: Schema, identifier: str, start: datetime, end: datetime, max_docs: int
) -> dict[str, Any]:
    filters = build_time_filter(schema, start, end)
    id_field = schema.id_field if schema.id_field and schema.id_field != "_id" else None
    if id_field:
        base = id_field[:-8] if id_field.endswith(".keyword") else id_field
        id_clauses: list[dict[str, Any]] = [
            {"term": {schema.id_agg_field: identifier}},
            {"term": {base: identifier}},
            {"match_phrase": {base: identifier}},
        ]
        filters.append({"bool": {"should": id_clauses, "minimum_should_match": 1}})
    query_block: dict[str, Any] = {"bool": {"filter": filters}}
    body: dict[str, Any] = {"size": max_docs, "query": query_block, "track_total_hits": False}
    if schema.time_field:
        body["sort"] = [{schema.time_field: {"order": "asc", "unmapped_type": "date"}}]
    return body


def trajectory_from_hits(
    hits: list[dict[str, Any]], schema: Schema, config: IntelConfig, identifier: str
) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for hit in hits:
        source = hit.get("_source") or {}
        lat, lon, altitude, inline = extract_position(source, schema, config)
        points.extend(inline)
        doc_time = get_path(source, schema.time_field) if schema.time_field else None
        if lat is not None and lon is not None:
            point: dict[str, Any] = {"lat": round(lat, 6), "lon": round(lon, 6)}
            if altitude is not None:
                point["alt"] = round(altitude, 1)
            parsed = parse_datetime(doc_time)
            if parsed is not None:
                point["ts"] = iso(parsed)
            points.append(point)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for point in points:
        key = (point["lat"], point["lon"], point.get("ts"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(point)

    if all(point.get("ts") for point in deduped):
        deduped.sort(key=lambda point: point["ts"])

    limit = max(10, config.max_trajectory_points)
    if len(deduped) > limit:
        step = len(deduped) / limit
        deduped = [deduped[min(len(deduped) - 1, int(index * step))] for index in range(limit)]

    return {
        "id": identifier,
        "points": deduped,
        "count": len(deduped),
        "source": "elasticsearch",
        "start": deduped[0].get("ts") if deduped else None,
        "end": deduped[-1].get("ts") if deduped else None,
    }


# ---------------------------------------------------------------------------
# Demo dataset (used when Elasticsearch is not configured)
# ---------------------------------------------------------------------------

_DEMO_ROUTES: list[dict[str, Any]] = [
    {
        "callsign": "IRB101",
        "origin": "IKA",
        "destination": "FRA",
        "aircraft": "A330-243",
        "reg": "EP-IJA",
        "waypoints": [(35.42, 51.15), (37.2, 47.5), (39.6, 42.0), (41.0, 36.0), (42.5, 29.0), (45.0, 20.0), (48.2, 12.0), (50.03, 8.57)],
    },
    {
        "callsign": "IRA721",
        "origin": "IKA",
        "destination": "LHR",
        "aircraft": "A330-343",
        "reg": "EP-IJB",
        "waypoints": [(35.42, 51.15), (37.6, 46.0), (40.2, 39.0), (42.8, 31.0), (45.6, 22.0), (48.0, 15.0), (50.1, 8.0), (51.47, -0.45)],
    },
    {
        "callsign": "THY5",
        "origin": "IST",
        "destination": "JFK",
        "aircraft": "B777-300ER",
        "reg": "TC-JJV",
        "waypoints": [(40.97, 28.81), (44.0, 20.0), (47.5, 8.0), (52.0, -4.0), (56.0, -18.0), (58.0, -35.0), (54.0, -55.0), (40.64, -73.78)],
    },
    {
        "callsign": "EK3",
        "origin": "DXB",
        "destination": "LHR",
        "aircraft": "A380-861",
        "reg": "A6-EUA",
        "waypoints": [(25.25, 55.36), (27.0, 50.0), (30.0, 44.0), (33.5, 38.0), (37.0, 30.0), (41.0, 22.0), (45.0, 14.0), (48.5, 6.0), (51.47, -0.45)],
    },
    {
        "callsign": "QTR7",
        "origin": "DOH",
        "destination": "CDG",
        "aircraft": "B787-9",
        "reg": "A7-BHA",
        "waypoints": [(25.27, 51.61), (27.5, 47.0), (31.0, 40.0), (35.0, 33.0), (39.0, 25.0), (43.0, 17.0), (47.0, 9.0), (49.0, 2.55)],
    },
    {
        "callsign": "SVA21",
        "origin": "JED",
        "destination": "IAD",
        "aircraft": "B777-368",
        "reg": "HZ-AK21",
        "waypoints": [(21.68, 39.16), (25.0, 33.0), (31.0, 24.0), (38.0, 14.0), (44.0, 2.0), (50.0, -12.0), (52.0, -30.0), (45.0, -55.0), (38.95, -77.46)],
    },
    {
        "callsign": "DLH400",
        "origin": "FRA",
        "destination": "JFK",
        "aircraft": "A340-313",
        "reg": "D-AIGT",
        "waypoints": [(50.03, 8.57), (53.0, 4.0), (57.0, -5.0), (60.0, -20.0), (61.0, -35.0), (56.0, -52.0), (45.0, -68.0), (40.64, -73.78)],
    },
    {
        "callsign": "BA117",
        "origin": "LHR",
        "destination": "DXB",
        "aircraft": "B787-8",
        "reg": "G-ZBJB",
        "waypoints": [(51.47, -0.45), (49.0, 6.0), (45.5, 14.0), (41.5, 22.0), (37.0, 30.0), (32.0, 39.0), (28.0, 47.0), (25.25, 55.36)],
    },
    {
        "callsign": "AFR6",
        "origin": "CDG",
        "destination": "JFK",
        "aircraft": "B777-328",
        "reg": "F-GSQJ",
        "waypoints": [(49.0, 2.55), (52.0, -2.0), (55.0, -12.0), (57.0, -25.0), (55.0, -40.0), (47.0, -60.0), (40.64, -73.78)],
    },
    {
        "callsign": "UAE201",
        "origin": "DXB",
        "destination": "JFK",
        "aircraft": "A380-861",
        "reg": "A6-EOA",
        "waypoints": [(25.25, 55.36), (30.0, 45.0), (36.0, 32.0), (42.0, 20.0), (48.0, 5.0), (55.0, -12.0), (59.0, -30.0), (55.0, -55.0), (40.64, -73.78)],
    },
    {
        "callsign": "PIA785",
        "origin": "KHI",
        "destination": "IST",
        "aircraft": "A320-214",
        "reg": "AP-BLW",
        "waypoints": [(24.9, 67.16), (26.5, 60.0), (28.5, 53.0), (31.0, 47.0), (34.0, 41.0), (37.5, 35.0), (40.97, 28.81)],
    },
    {
        "callsign": "MEA205",
        "origin": "BEY",
        "destination": "LHR",
        "aircraft": "A321-231",
        "reg": "T7-ME3",
        "waypoints": [(33.82, 35.49), (35.5, 30.0), (38.0, 24.0), (42.0, 17.0), (46.0, 9.0), (50.0, 2.0), (51.47, -0.45)],
    },
]

_DEMO_STATUSES = ["cruising", "cruising", "descending", "climbing", "cruising"]

# Small offline airport directory so free-text questions such as
# "flights to London" also match the demo dataset.
_AIRPORT_INFO: dict[str, tuple[str, str]] = {
    "IKA": ("Tehran", "Imam Khomeini International"),
    "FRA": ("Frankfurt", "Frankfurt Airport"),
    "LHR": ("London", "Heathrow"),
    "IST": ("Istanbul", "Istanbul Airport"),
    "JFK": ("New York", "John F. Kennedy"),
    "DXB": ("Dubai", "Dubai International"),
    "DOH": ("Doha", "Hamad International"),
    "CDG": ("Paris", "Charles de Gaulle"),
    "JED": ("Jeddah", "King Abdulaziz"),
    "IAD": ("Washington", "Dulles"),
    "KHI": ("Karachi", "Jinnah International"),
    "BEY": ("Beirut", "Rafic Hariri International"),
}


def _interpolate_route(waypoints: list[tuple[float, float]], step_degrees: float = 0.45):
    """Yield lat/lon pairs along the great-circle-ish polyline."""
    for start, end in zip(waypoints, waypoints[1:]):
        lat1, lon1 = start
        lat2, lon2 = end
        segments = max(6, int(max(abs(lat2 - lat1), abs(lon2 - lon1)) / step_degrees))
        for index in range(segments):
            fraction = index / segments
            yield (lat1 + (lat2 - lat1) * fraction, lon1 + (lon2 - lon1) * fraction)
    yield waypoints[-1]


def demo_dataset(now: Optional[datetime] = None) -> list[dict[str, Any]]:
    """Build a deterministic, realistic looking flight dataset for the last 24h."""
    now = now or datetime.now(timezone.utc)
    flights: list[dict[str, Any]] = []
    for index, route in enumerate(_DEMO_ROUTES):
        path = list(_interpolate_route(route["waypoints"]))
        # Each aircraft is somewhere between 15% and 85% of its route.
        progress = 0.15 + ((index * 37) % 70) / 100.0
        visible = max(4, int(len(path) * progress))
        visible_path = path[:visible]
        total_minutes = 180 + (index % 5) * 45
        # Stagger "last seen" so the table looks like a live feed rather than all
        # aircraft reporting at the same instant. The 45s guard keeps every row
        # strictly inside a window whose `end` was computed a moment before the
        # dataset was generated.
        end_time = now - timedelta(seconds=45, minutes=(index * 13) % 150)
        start_time = end_time - timedelta(minutes=total_minutes)
        step = timedelta(minutes=total_minutes / max(1, len(visible_path) - 1))
        trajectory = []
        for point_index, (lat, lon) in enumerate(visible_path):
            ts = start_time + step * point_index
            altitude = 24000 + min(12000, point_index * 260) if point_index < visible_path.__len__() - 1 else 31000
            trajectory.append(
                {
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "alt": altitude,
                    "ts": iso(ts),
                }
            )
        # Aircraft still en route are "live"; a few already landed.
        status = "landed" if index % 7 == 6 else _DEMO_STATUSES[index % len(_DEMO_STATUSES)]
        last = trajectory[-1]
        heading = 0.0
        if len(trajectory) > 1:
            prev = trajectory[-2]
            heading = (math.degrees(math.atan2(last["lon"] - prev["lon"], last["lat"] - prev["lat"])) + 360) % 360
        origin_city, origin_name = _AIRPORT_INFO.get(route["origin"], ("", route["origin"]))
        destination_city, destination_name = _AIRPORT_INFO.get(route["destination"], ("", route["destination"]))
        flight = {
            "flight_id": f"demo-{route['callsign'].lower()}",
            "callsign": route["callsign"],
            "icao24": f"DEMO{index:02d}",
            "registration": route["reg"],
            "aircraft_type": route["aircraft"],
            "origin": route["origin"],
            "origin_city": origin_city,
            "origin_airport": origin_name,
            "destination": route["destination"],
            "destination_city": destination_city,
            "destination_airport": destination_name,
            "status": status,
            "@timestamp": last["ts"],
            "lat": last["lat"],
            "lon": last["lon"],
            "altitude": last.get("alt"),
            "speed": 420 + (index * 13) % 90,
            "heading": round(heading, 1),
            "vertical_rate": 0 if status == "cruising" else (-800 if status == "descending" else 1200),
            "trajectory": trajectory,
        }
        flight["description"] = (
            f"{route['callsign']} ({route['aircraft']}, registration {route['reg']}) operating "
            f"{origin_city} {route['origin']} to {destination_city} {route['destination']}. "
            f"Status: {status}. Last reported position {last['lat']}, {last['lon']} at "
            f"{int(last.get('alt') or 0)} ft, ground speed {flight['speed']} kt, heading {flight['heading']} deg. "
            f"Trajectory contains {len(trajectory)} recorded points."
        )
        flights.append(flight)
    return flights


def demo_rows(
    start: datetime,
    end: datetime,
    query: str,
    size: int,
    now: Optional[datetime] = None,
) -> tuple[list[dict[str, Any]], int]:
    dataset = demo_dataset(now)
    query_lower = (query or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for doc in dataset:
        timestamp = parse_datetime(doc["@timestamp"])
        if timestamp is None or not (start <= timestamp <= end):
            continue
        if query_lower:
            haystack = " ".join(
                str(doc.get(key, ""))
                for key in (
                    "callsign",
                    "registration",
                    "origin",
                    "origin_city",
                    "destination",
                    "destination_city",
                    "aircraft_type",
                    "status",
                    "icao24",
                )
            ).lower()
            if query_lower not in haystack:
                continue
        trajectory = doc.get("trajectory") or []
        rows.append(
            {
                "id": doc["flight_id"],
                "doc_id": doc["flight_id"],
                "callsign": doc["callsign"],
                "time": doc["@timestamp"],
                "lat": doc["lat"],
                "lon": doc["lon"],
                "altitude": doc.get("altitude"),
                "speed": doc.get("speed"),
                "heading": doc.get("heading"),
                "status": doc.get("status"),
                "origin": doc.get("origin"),
                "destination": doc.get("destination"),
                "registration": doc.get("registration"),
                "aircraft_type": doc.get("aircraft_type"),
                "points": len(trajectory),
                "source": "demo",
            }
        )
    rows.sort(key=lambda row: row.get("time") or "", reverse=True)
    return rows[:size], len(rows)


def demo_trajectory(
    identifier: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    dataset = demo_dataset(now)
    empty = {"id": identifier, "points": [], "count": 0, "source": "demo", "start": None, "end": None}
    for doc in dataset:
        if doc["flight_id"] != identifier and doc["callsign"].lower() != str(identifier).lower():
            continue
        last_seen = parse_datetime(doc.get("@timestamp"))
        # Mirror Elasticsearch: an aircraft that did not report inside the window
        # has no trajectory for that window.
        if last_seen is None:
            return empty
        if start is not None and last_seen < start:
            return empty
        if end is not None and last_seen > end:
            return empty
        points = doc.get("trajectory") or []
        if start is not None or end is not None:
            points = [
                point
                for point in points
                if (timestamp := parse_datetime(point.get("ts"))) is not None
                and (start is None or timestamp >= start)
                and (end is None or timestamp <= end)
            ]
        return {
            "id": identifier,
            "points": points,
            "count": len(points),
            "source": "demo",
            "start": points[0]["ts"] if points else None,
            "end": points[-1]["ts"] if points else None,
        }
    return empty


def demo_search(query: str, top_k: int) -> list[dict[str, Any]]:
    dataset = demo_dataset()
    query_tokens = [token for token in re.split(r"\W+", query.lower()) if len(token) > 1]
    if not query_tokens:
        hits = dataset[:top_k]
        scores = [1.0] * len(hits)
    else:
        scored: list[tuple[float, dict[str, Any]]] = []
        for doc in dataset:
            trajectory = doc.get("trajectory") or []
            text = json.dumps(
                {
                    "callsign": doc.get("callsign"),
                    "origin": doc.get("origin"),
                    "origin_city": doc.get("origin_city"),
                    "destination": doc.get("destination"),
                    "destination_city": doc.get("destination_city"),
                    "status": doc.get("status"),
                    "aircraft_type": doc.get("aircraft_type"),
                    "registration": doc.get("registration"),
                    "description": doc.get("description"),
                    "route_summary": f"{doc.get('origin')} to {doc.get('destination')}",
                    "last_position": {"lat": doc.get("lat"), "lon": doc.get("lon"), "altitude": doc.get("altitude")},
                    "trajectory_points": len(trajectory),
                },
                ensure_ascii=False,
            ).lower()
            score = sum(1.0 for token in query_tokens if token in text)
            if score:
                scored.append((score / len(query_tokens), doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        hits = [doc for _, doc in scored[:top_k]]
        scores = [score for score, _ in scored[:top_k]]

    results = []
    for doc, score in zip(hits, scores):
        document = {key: value for key, value in doc.items() if key != "trajectory"}
        document["trajectory_points"] = len(doc.get("trajectory") or [])
        results.append(
            {
                "id": doc["flight_id"],
                "score": round(score, 4),
                "source": "demo",
                "index": "demo-flights",
                "document": document,
                "snippet": json.dumps(document, ensure_ascii=False)[:600],
                "highlights": [],
            }
        )
    return results


# ---------------------------------------------------------------------------
# High level service used by the router
# ---------------------------------------------------------------------------

_META_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_META_TTL = 30.0


def _trim_source(source: Any, exclude: Iterable[str], max_string: int = 4000) -> Any:
    if isinstance(source, dict):
        return {
            key: _trim_source(value, exclude, max_string)
            for key, value in source.items()
            if key not in exclude
        }
    if isinstance(source, list):
        trimmed = [_trim_source(item, exclude, max_string) for item in source[:50]]
        if len(source) > 50:
            trimmed.append(f"... ({len(source) - 50} more items omitted)")
        return trimmed
    if isinstance(source, str) and len(source) > max_string:
        return source[:max_string] + " ..."
    return source


def _snippet_from_source(source: Any, max_length: int = 600) -> str:
    if isinstance(source, dict):
        preferred = ["description", "notes", "message", "content", "text", "summary", "callsign"]
        for key in preferred:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:max_length]
        try:
            return json.dumps(source, ensure_ascii=False, default=str)[:max_length]
        except (TypeError, ValueError):
            return str(source)[:max_length]
    return str(source)[:max_length]


class IntelService:
    """Facade combining Elasticsearch, schema detection and the demo dataset."""

    def __init__(self, config: Optional[IntelConfig] = None):
        self.config = config or get_config()
        if not self.config.enabled:
            raise IntelDisabled("The Intel workspace is disabled (INTEL_ENABLE=false)")

    @property
    def demo(self) -> bool:
        return self.config.demo

    async def _with_client(self) -> ElasticsearchClient:
        if not self.config.configured:
            raise IntelUnavailable("Elasticsearch is not configured")
        return ElasticsearchClient(self.config)

    async def meta(self, force: bool = False) -> dict[str, Any]:
        """Return capability information for the UI (cached briefly)."""
        cache_key = f"{self.config.es_url}|{self.config.es_index}|{self.demo}"
        now = time.monotonic()
        if not force:
            cached = _META_CACHE.get(cache_key)
            if cached and now - cached[0] < _META_TTL:
                return cached[1]

        payload: dict[str, Any] = {
            **self.config.public(),
            "ok": True,
            "elasticsearch": {
                **self.config.public()["elasticsearch"],
                "connected": False,
                "doc_count": None,
                "error": None,
                "schema_detected": False,
            },
        }

        if self.demo:
            payload["fields"] = {
                "time": "@timestamp",
                "id": "flight_id",
                "callsign": "callsign",
                "trajectory": "trajectory",
                "lat": "lat",
                "lon": "lon",
                "altitude": "altitude",
                "speed": "speed",
                "heading": "heading",
                "status": "status",
            }
            payload["query_fields"] = ["callsign", "origin", "destination", "status", "aircraft_type"]
            payload["demo_aircraft"] = len(_DEMO_ROUTES)
            _META_CACHE[cache_key] = (now, payload)
            return payload

        try:
            async with await self._with_client() as client:
                info = await client.ping()
                cluster_name = info.get("cluster_name")
                version = (info.get("version") or {}).get("number")
                doc_count = await client.count(self.config.es_index)
                schema = await get_schema(client, self.config)
            payload["elasticsearch"].update(
                {
                    "connected": True,
                    "cluster": cluster_name,
                    "version": version,
                    "doc_count": doc_count,
                    "schema_detected": True,
                    "error": None,
                }
            )
            payload["fields"] = {
                "time": schema.time_field or None,
                "id": schema.id_field or None,
                "callsign": schema.callsign_field or None,
                "trajectory": schema.trajectory_field or None,
                "lat": schema.lat_field or None,
                "lon": schema.lon_field or None,
                "altitude": schema.alt_field or None,
                "speed": schema.speed_field or None,
                "heading": schema.heading_field or None,
                "status": schema.status_field or None,
            }
            payload["query_fields"] = schema.query_fields
            if not schema.trajectory_field:
                payload["warnings"] = [
                    "No trajectory field was detected in the index mapping. "
                    "Set INTEL_TRAJECTORY_FIELD to enable route drawing."
                ]
        except IntelUnavailable as exc:
            payload["elasticsearch"]["error"] = str(exc)
            log.warning(f"Intel: Elasticsearch unavailable: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            payload["elasticsearch"]["error"] = str(exc)
            log.exception("Intel: failed to build meta payload")

        _META_CACHE[cache_key] = (now, payload)
        return payload

    async def flights(
        self,
        *,
        start: Any = None,
        end: Any = None,
        hours: Any = None,
        query: str = "",
        size: Optional[int] = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = self.config
        start_dt, end_dt = resolve_time_range(start, end, hours, cfg.default_lookback_hours)
        size = int(_clamp(size or cfg.max_rows, 1, cfg.max_rows))
        started = time.perf_counter()

        if self.demo:
            # Demo timestamps are anchored to the real "now" so custom ranges that
            # do not overlap the last day correctly return nothing.
            rows, matched = demo_rows(start_dt, end_dt, query, size)
            return {
                "items": rows,
                "total": matched,
                "aircraft": matched,
                "returned": len(rows),
                "source": "demo",
                "range": {"start": iso(start_dt), "end": iso(end_dt)},
                "time_field": "@timestamp",
                "took_ms": round((time.perf_counter() - started) * 1000, 1),
            }

        async with await self._with_client() as client:
            schema = await get_schema(client, cfg)
            body = build_latest_flights_body(schema, start_dt, end_dt, query, size, filters)
            try:
                response = await client.search(cfg.es_index, body)
                items: list[dict[str, Any]] = []
                for bucket in ((response.get("aggregations") or {}).get("latest") or {}).get("buckets") or []:
                    hits = ((bucket.get("doc") or {}).get("hits") or {}).get("hits") or []
                    if not hits:
                        continue
                    items.append(flight_from_hit(hits[0], schema, cfg))
                if ((response.get("aggregations") or {}).get("latest") or {}).get("buckets") is None:
                    raise IntelUnavailable("aggregation did not return the expected buckets")
                total_docs = (response.get("hits") or {}).get("total")
                total_docs = total_docs.get("value") if isinstance(total_docs, dict) else total_docs
                aircraft = ((response.get("aggregations") or {}).get("aircraft_count") or {}).get("value")
            except IntelUnavailable:
                # Fallback: plain search + de-duplication in Python.
                body = build_scan_body(schema, start_dt, end_dt, query, min(size * 4, 4000), filters)
                response = await client.search(cfg.es_index, body)
                hits = ((response.get("hits") or {}).get("hits")) or []
                seen: set[str] = set()
                items = []
                for hit in hits:
                    row = flight_from_hit(hit, schema, cfg)
                    if row["id"] in seen:
                        continue
                    seen.add(row["id"])
                    items.append(row)
                    if len(items) >= size:
                        break
                total_docs = ((response.get("hits") or {}).get("total") or {}).get("value")
                aircraft = len(items)

        return {
            "items": items,
            "total": total_docs,
            "aircraft": aircraft if aircraft is not None else len(items),
            "returned": len(items),
            "source": "elasticsearch",
            "range": {"start": iso(start_dt), "end": iso(end_dt)},
            "time_field": schema.time_field or None,
            "took_ms": round((time.perf_counter() - started) * 1000, 1),
        }

    async def trajectory(
        self, identifier: str, *, start: Any = None, end: Any = None, hours: Any = None
    ) -> dict[str, Any]:
        cfg = self.config
        start_dt, end_dt = resolve_time_range(start, end, hours, cfg.default_lookback_hours)
        if self.demo:
            return demo_trajectory(identifier, start_dt, end_dt)

        async with await self._with_client() as client:
            schema = await get_schema(client, cfg)
            body = build_trajectory_body(schema, identifier, start_dt, end_dt, cfg.max_trajectory_docs)
            response = await client.search(cfg.es_index, body)
            hits = ((response.get("hits") or {}).get("hits")) or []
        return trajectory_from_hits(hits, schema, cfg, identifier)

    async def search(
        self,
        query: str,
        *,
        top_k: Optional[int] = None,
        start: Any = None,
        end: Any = None,
        hours: Any = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = self.config
        top_k = int(_clamp(top_k or cfg.rag_top_k, 1, 25))
        started = time.perf_counter()

        if self.demo:
            hits = demo_search(query, top_k)
            return {
                "hits": hits,
                "total": len(hits),
                "source": "demo",
                "took_ms": round((time.perf_counter() - started) * 1000, 1),
            }

        start_dt, end_dt = resolve_time_range(start, end, hours, cfg.default_lookback_hours)
        async with await self._with_client() as client:
            schema = await get_schema(client, cfg)
            time_filters = build_time_filter(schema, start_dt, end_dt)
            for field_name, value in (filters or {}).items():
                if value in (None, "", []):
                    continue
                time_filters.append(
                    {"terms": {field_name: value}} if isinstance(value, list) else {"term": {field_name: value}}
                )
            text_query = build_text_query(query, schema)
            query_block: dict[str, Any] = (
                {"bool": {"must": [text_query], "filter": time_filters}}
                if text_query
                else {"bool": {"must": [{"match_all": {}}], "filter": time_filters}}
            )
            body: dict[str, Any] = {
                "size": top_k,
                "query": query_block,
                "_source": {"excludes": [schema.trajectory_field] if schema.trajectory_field else []},
                "highlight": {
                    "fields": {field: {} for field in (schema.query_fields or [])[:20]},
                    "pre_tags": [""],
                    "post_tags": [""],
                    "number_of_fragments": 2,
                    "fragment_size": 240,
                }
                if schema.query_fields
                else {},
            }
            if text_query:
                body["sort"] = ["_score"]
            elif schema.time_field:
                body["sort"] = [{schema.time_field: {"order": "desc", "unmapped_type": "date"}}]
            response = await client.search(cfg.es_index, body)

        hits = []
        for hit in ((response.get("hits") or {}).get("hits")) or []:
            source = hit.get("_source") or {}
            document = _trim_source(source, exclude=[schema.trajectory_field] if schema.trajectory_field else [], max_string=cfg.rag_max_snippet)
            highlights = [
                fragment
                for fragments in ((hit.get("highlight") or {}).values())
                for fragment in fragments
                if isinstance(fragment, str)
            ]
            hits.append(
                {
                    "id": hit.get("_id"),
                    "score": hit.get("_score"),
                    "source": "elasticsearch",
                    "index": hit.get("_index"),
                    "document": document,
                    "snippet": (highlights[0] if highlights else _snippet_from_source(document)),
                    "highlights": highlights[:4],
                    "callsign": _string(
                        get_path(source, schema.callsign_field) if schema.callsign_field else None, 60
                    )
                    or None,
                    "time": iso(parse_datetime(get_path(source, schema.time_field)))
                    if schema.time_field
                    else None,
                }
            )

        total = ((response.get("hits") or {}).get("total") or {})
        total = total.get("value") if isinstance(total, dict) else total
        return {
            "hits": hits,
            "total": total,
            "source": "elasticsearch",
            "took_ms": round((time.perf_counter() - started) * 1000, 1),
        }


