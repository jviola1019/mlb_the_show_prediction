"""Small MLB Stats API client for upgrade-model inputs."""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from math import isfinite
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .theshow import normalize_name


USER_AGENT = "mlb-show-terminal/1.2 python-fastapi"
BASE_URL = "https://statsapi.mlb.com"


class MLBStatsError(RuntimeError):
    pass


def _get_json(path: str, query: dict[str, Any] | None = None, timeout: float = 15.0) -> dict[str, Any]:
    qs = f"?{urlencode(query or {})}" if query else ""
    req = Request(f"{BASE_URL}{path}{qs}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed public API host
        data = json.loads(resp.read().decode("utf-8"))
    return data if isinstance(data, dict) else {"records": data}


def _num(value: Any) -> float | int | str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value if isfinite(float(value)) else None
    if isinstance(value, str):
        cleaned = value.replace(",", "")
        try:
            out = float(cleaned)
        except ValueError:
            return value
        return out if isfinite(out) else None
    return value


def _stats(stat: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(stat, dict):
        return {}
    return {key: _num(value) for key, value in stat.items()}


@lru_cache(maxsize=256)
def search_player(name: str) -> dict[str, Any] | None:
    query = normalize_name(name)
    if not query:
        return None
    body = _get_json("/api/v1/people/search", {"names": query})
    people = body.get("people")
    if not isinstance(people, list) or not people:
        return None
    person = people[0]
    position = person.get("primaryPosition") or {}
    return {
        "id": person.get("id"),
        "full_name": person.get("fullName") or person.get("nameFirstLast"),
        "primary_position": position.get("name"),
        "primary_position_code": position.get("code"),
    }


@lru_cache(maxsize=512)
def player_stats(player_id: int, start_date: str, end_date: str, group: str) -> dict[str, Any]:
    group = "pitching" if group == "pitching" else "hitting"
    body = _get_json(
        f"/api/v1/people/{int(player_id)}/stats",
        {"stats": "byDateRange", "startDate": start_date, "endDate": end_date, "group": group},
    )
    stats = body.get("stats")
    if not isinstance(stats, list) or not stats:
        return {}
    splits = stats[0].get("splits") if isinstance(stats[0], dict) else None
    if not isinstance(splits, list) or not splits:
        return {}
    return _stats(splits[0].get("stat") if isinstance(splits[0], dict) else None)


def recent_vs_season(name: str, role: str | None = None, today: date | None = None, days: int = 14) -> dict[str, Any]:
    today = today or date.today()
    days = max(1, min(int(days or 14), 60))
    player = search_player(name)
    if player is None:
        resolved_role = role if role in {"hitter", "pitcher"} else "hitter"
        return {"recent": {}, "season": {}, "role": resolved_role, "player": None}

    if role not in {"hitter", "pitcher"}:
        role = "pitcher" if "pitcher" in str(player.get("primary_position") or "").lower() else "hitter"
    group = "pitching" if role == "pitcher" else "hitting"
    end = today.isoformat()
    recent_start = (today - timedelta(days=days)).isoformat()
    season_start = date(today.year, 3, 1).isoformat()
    return {
        "recent": player_stats(int(player["id"]), recent_start, end, group) if player.get("id") else {},
        "season": player_stats(int(player["id"]), season_start, end, group) if player.get("id") else {},
        "role": role,
        "player": player,
        "recent_start": recent_start,
        "season_start": season_start,
        "end": end,
        "source": "statsapi.mlb.com",
    }
