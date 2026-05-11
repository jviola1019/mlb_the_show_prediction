"""Small The Show API client used by the Python backend.

The client intentionally uses the standard library so the Docker/API path does
not depend on the legacy R Shiny runtime.
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .uuid_tools import is_uuid


DEFAULT_YEARS = (26, 25, 24)
USER_AGENT = "mlb-show-terminal/1.2 python-fastapi"


class TheShowError(RuntimeError):
    pass


def normalize_name(raw: Any) -> str:
    """Normalize user search text without stripping baseball name suffixes."""
    if raw is None:
        return ""
    name = " ".join(str(raw).strip().split())
    if not name:
        return ""
    if name.count(",") == 1:
        last, first = [part.strip() for part in name.split(",", 1)]
        if last and first:
            name = f"{first} {last}"
    name = "".join(ch for ch in name if ch.isprintable())
    name = name.lstrip(".,- ").rstrip(",- ")
    return " ".join(name.split())


def _name_key(value: Any) -> str:
    return normalize_name(value).casefold()


def search_match(query: str, candidate: str) -> dict[str, Any]:
    q = _name_key(query)
    c = _name_key(candidate)
    if not q or not c:
        score = 0.0
    elif q == c:
        score = 1.0
    elif q in c:
        score = 0.82 + min(0.12, len(q) / max(len(c), 1) * 0.12)
    else:
        score = SequenceMatcher(None, q, c).ratio() * 0.78
    return {
        "normalized_query": normalize_name(query),
        "normalized_name": normalize_name(candidate),
        "exact_name_match": bool(q and c and q == c),
        "partial_name_match": bool(q and c and q != c and q in c),
        "match_score": round(score, 4),
    }


def _get_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed public API host
        payload = resp.read().decode("utf-8")
    data = json.loads(payload)
    return data if isinstance(data, dict) else {"records": data}


def request_with_year(path: str, query: dict[str, Any], years: tuple[int, ...] = DEFAULT_YEARS) -> dict[str, Any]:
    last_error: str | None = None
    for year in years:
        host = f"https://mlb{year}.theshow.com"
        url = f"{host}/{path.lstrip('/')}?{urlencode(query)}"
        for attempt in range(3):
            try:
                body = _get_json(url)
                if isinstance(body.get("listings"), list) and not body["listings"]:
                    break
                body["_year_used"] = year
                body["_host"] = host
                body["_source_url"] = url
                return body
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = str(exc)
                if attempt < 2:
                    time.sleep(2**attempt)
        continue
    raise TheShowError(last_error or "no usable The Show response")


@lru_cache(maxsize=256)
def search_card(name: str, year: int = 26, page: int = 1) -> dict[str, Any]:
    normalized = normalize_name(name)
    if len(normalized) < 2:
        return {"listings": [], "year": None, "source_url": None}
    years = tuple(dict.fromkeys((int(year), *DEFAULT_YEARS)))
    body = request_with_year("apis/listings.json", {"type": "mlb_card", "name": normalized, "page": page}, years=years)
    listings = body.get("listings", [])
    annotated: list[dict[str, Any]] = []
    for listing in listings if isinstance(listings, list) else []:
        if not isinstance(listing, dict):
            continue
        item = listing.get("item") or {}
        candidate = item.get("name") or listing.get("listing_name") or ""
        meta = search_match(normalized, candidate)
        row = dict(listing)
        row["search"] = meta
        row["fetched_at"] = _utc_now()
        annotated.append(row)
    annotated.sort(
        key=lambda row: (
            not bool((row.get("search") or {}).get("exact_name_match")),
            -float((row.get("search") or {}).get("match_score") or 0),
            str(((row.get("item") or {}).get("name") or row.get("listing_name") or "")),
        )
    )
    return {
        "query": name,
        "normalized_query": normalized,
        "listings": annotated,
        "year": body.get("_year_used"),
        "source_url": body.get("_source_url"),
        "fetched_at": _utc_now(),
    }


@lru_cache(maxsize=512)
def get_listing(uuid: str, year: int = 26) -> dict[str, Any]:
    if not is_uuid(uuid):
        raise TheShowError("invalid uuid")
    uuid = uuid.strip().lower()
    years = tuple(dict.fromkeys((int(year), *DEFAULT_YEARS)))
    body = request_with_year("apis/listing.json", {"uuid": uuid}, years=years)
    body["source_url"] = body.get("_source_url")
    body["fetched_at"] = _utc_now()
    return body


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@lru_cache(maxsize=64)
def discover_top_listings(rarity: str = "Gold", top_n: int = 25, year: int = 26, pages: int = 20) -> dict[str, Any]:
    rarity_norm = normalize_name(rarity) or "Gold"
    target = rarity_norm.casefold()
    limit = max(1, min(int(top_n or 25), 75))
    max_pages = max(1, min(int(pages or 20), 30))
    years = tuple(dict.fromkeys((int(year), *DEFAULT_YEARS)))
    rows: list[dict[str, Any]] = []
    source_url = None
    year_used = None
    for page in range(1, max_pages + 1):
        body = request_with_year("apis/listings.json", {"type": "mlb_card", "page": page}, years=years)
        source_url = source_url or body.get("_source_url")
        year_used = year_used or body.get("_year_used")
        for listing in body.get("listings", []) if isinstance(body.get("listings"), list) else []:
            if not isinstance(listing, dict):
                continue
            item = listing.get("item") or {}
            if str(item.get("rarity") or "").casefold() != target:
                continue
            row = dict(listing)
            row["fetched_at"] = _utc_now()
            rows.append(row)
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break
    rows.sort(key=lambda row: float(row.get("best_sell_price") or 0), reverse=True)
    return {
        "rarity": rarity_norm,
        "top_n": limit,
        "listings": rows[:limit],
        "uuids": [str((row.get("item") or {}).get("uuid")).lower() for row in rows[:limit] if (row.get("item") or {}).get("uuid")],
        "year": year_used,
        "source_url": source_url,
        "fetched_at": _utc_now(),
    }
