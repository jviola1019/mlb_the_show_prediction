"""Roster upgrade threshold model.

This is a deterministic feature/scoring engine. Historical calibration is
handled separately in historical.py when real labels are available.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import erf, isfinite, sqrt
from typing import Any


OVR_STDS = {
    "ops": 0.110,
    "avg": 0.045,
    "era": 1.20,
    "whip": 0.20,
}


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if isfinite(out) else None


def _clamp01(value: float | None) -> float | None:
    if value is None or not isfinite(value):
        return None
    return min(1.0, max(0.0, value))


def _norm_cdf(x: float, mean: float = 0.0, sd: float = 1.0) -> float:
    z = (x - mean) / (sd * sqrt(2))
    return 0.5 * (1 + erf(z))


def _norm_sf(x: float, mean: float = 0.0, sd: float = 1.0) -> float:
    return 1 - _norm_cdf(x, mean, sd)


def _csv(values: list[str]) -> str:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return ",".join(seen)


def next_ovr_threshold(current_ovr: Any, rarity: Any = None) -> float | None:
    ovr = _num(current_ovr)
    if ovr is None:
        return None
    rarity_l = str(rarity or "").lower()
    if "common" in rarity_l or ovr < 65:
        return 65
    if "bronze" in rarity_l or 65 <= ovr < 75:
        return 75
    if "silver" in rarity_l or 75 <= ovr < 80:
        return 80
    if "gold" in rarity_l or 80 <= ovr < 85:
        return 85
    if "diamond" in rarity_l or ovr >= 85:
        if ovr < 90:
            return 90
        if ovr < 95:
            return 95
    return None


def distance_to_threshold(current_ovr: Any, rarity: Any = None) -> float | None:
    ovr = _num(current_ovr)
    threshold = next_ovr_threshold(ovr, rarity)
    if ovr is None or threshold is None:
        return None
    return max(0.0, threshold - ovr)


def distance_to_ovr(current_ovr: Any, threshold: float) -> float | None:
    ovr = _num(current_ovr)
    if ovr is None:
        return None
    return max(0.0, threshold - ovr)


def ovr_z_score(recent: dict[str, Any], season: dict[str, Any], role: str) -> tuple[float, dict[str, float]]:
    components: dict[str, float] = {}
    if role == "pitcher":
        era_r, era_s = _num(recent.get("era")), _num(season.get("era"))
        whip_r, whip_s = _num(recent.get("whip")), _num(season.get("whip"))
        if era_r is not None and era_s is not None:
            components["era"] = (era_s - era_r) / OVR_STDS["era"]
        if whip_r is not None and whip_s is not None:
            components["whip"] = (whip_s - whip_r) / OVR_STDS["whip"]
    else:
        ops_r, ops_s = _num(recent.get("ops")), _num(season.get("ops"))
        avg_r, avg_s = _num(recent.get("avg")), _num(season.get("avg"))
        if ops_r is not None and ops_s is not None:
            components["ops"] = (ops_r - ops_s) / OVR_STDS["ops"]
        if avg_r is not None and avg_s is not None:
            components["avg"] = (avg_r - avg_s) / OVR_STDS["avg"]
    if not components:
        return 0.0, {}
    return sum(components.values()) / len(components), components


def z_to_delta_ovr(z: float | None) -> int:
    if z is None or not isfinite(z):
        return 0
    if z > 2:
        return 3
    if z > 1.2:
        return 2
    if z > 0.5:
        return 1
    if z < -2:
        return -3
    if z < -1.2:
        return -2
    if z < -0.5:
        return -1
    return 0


def _required_z(delta_required: float | None) -> float | None:
    if delta_required is None or delta_required <= 0:
        return None
    if delta_required <= 1:
        return 0.5
    if delta_required <= 2:
        return 1.2
    if delta_required <= 3:
        return 2.0
    return None


def _prob_delta_at_least(z: float, delta_required: float | None, z_sd: float) -> float | None:
    z_req = _required_z(delta_required)
    if z_req is None:
        return None
    return _norm_sf(z_req, mean=z, sd=z_sd)


def _playing_time_score(recent: dict[str, Any], season: dict[str, Any], role: str) -> tuple[float, str]:
    if role == "pitcher":
        recent_v = _num(recent.get("inningsPitched") or recent.get("ip")) or 0
        season_v = _num(season.get("inningsPitched") or season.get("ip")) or 0
        if recent_v == 0 and season_v == 0:
            return 0.0, "PLAYING_TIME_UNAVAILABLE"
        score = min(1.0, (recent_v / 5) * 0.6 + (season_v / 25) * 0.4)
    else:
        recent_v = _num(recent.get("plateAppearances") or recent.get("pa") or recent.get("atBats")) or 0
        season_v = _num(season.get("plateAppearances") or season.get("pa") or season.get("atBats")) or 0
        if recent_v == 0 and season_v == 0:
            return 0.0, "PLAYING_TIME_UNAVAILABLE"
        score = min(1.0, (recent_v / 20) * 0.6 + (season_v / 80) * 0.4)
    return score, "PLAYING_TIME_OK" if score >= 0.5 else "PLAYING_TIME_LOW"


def _recent_delta_text(recent: dict[str, Any], season: dict[str, Any], role: str) -> str:
    if role == "pitcher":
        era_r, era_s = _num(recent.get("era")), _num(season.get("era"))
        whip_r, whip_s = _num(recent.get("whip")), _num(season.get("whip"))
        era_d = era_r - era_s if era_r is not None and era_s is not None else None
        whip_d = whip_r - whip_s if whip_r is not None and whip_s is not None else None
        era_txt = f"{era_d:+.2f}" if era_d is not None else "NA"
        whip_txt = f"{whip_d:+.2f}" if whip_d is not None else "NA"
        return f"ERA {era_txt}; WHIP {whip_txt}"
    ops_r, ops_s = _num(recent.get("ops")), _num(season.get("ops"))
    avg_r, avg_s = _num(recent.get("avg")), _num(season.get("avg"))
    ops_d = ops_r - ops_s if ops_r is not None and ops_s is not None else None
    avg_d = avg_r - avg_s if avg_r is not None and avg_s is not None else None
    ops_txt = f"{ops_d:+.3f}" if ops_d is not None else "NA"
    avg_txt = f"{avg_d:+.3f}" if avg_d is not None else "NA"
    return f"OPS {ops_txt}; AVG {avg_txt}"


@dataclass(frozen=True)
class UpgradeResult:
    current_ovr: float | None
    rarity: str | None
    new_rank: float | None
    next_threshold: float | None
    distance_to_threshold: float | None
    distance_to_85: float | None
    distance_to_90: float | None
    p_upgrade: float | None
    p_downgrade: float | None
    p_cross_next_threshold: float | None
    p_cross_85: float | None
    p_cross_90: float | None
    confidence: float
    confidence_label: str
    exact_delta_ovr: int
    recent_vs_season_delta: str
    z: float
    components: dict[str, float]
    upgrade_score: float
    action: str
    model_status: str
    probability_kind: str
    probability_note: str
    reason_codes: list[str]
    reason_codes_csv: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_upgrade(
    *,
    recent: dict[str, Any] | None,
    season: dict[str, Any] | None,
    role: str,
    current_ovr: Any,
    rarity: Any,
    new_rank: Any = None,
) -> UpgradeResult:
    recent = recent or {}
    season = season or {}
    role = role if role in {"hitter", "pitcher"} else "hitter"
    ovr = _num(current_ovr)
    nr = _num(new_rank)
    threshold = next_ovr_threshold(ovr, rarity)
    distance = distance_to_threshold(ovr, rarity)
    dist85 = distance_to_ovr(ovr, 85)
    dist90 = distance_to_ovr(ovr, 90)

    model_status = "uncalibrated_threshold_model"
    probability_kind = "scenario"
    probability_note = (
        "Scenario probabilities from deterministic thresholds and recent-vs-season features; "
        "not historically calibrated."
    )
    reasons = ["PYTHON_BACKEND", "UNCALIBRATED_THRESHOLD_MODEL", "SCENARIO_PROBABILITY"]
    z, components = ovr_z_score(recent, season, role)
    has_stats = bool(components)
    pt_score, pt_reason = _playing_time_score(recent, season, role)
    reasons.append(pt_reason)
    if not has_stats:
        reasons.append("RECENT_STATS_UNAVAILABLE")

    z_sd = 0.85 if pt_score >= 0.5 else 1.10
    p_upgrade = _prob_delta_at_least(z, 1, z_sd) if has_stats else None
    p_downgrade = _norm_cdf(-0.5, mean=z, sd=z_sd) if has_stats else None
    if has_stats and distance is not None and distance == 0:
        p_cross_next = 1.0
    elif has_stats and distance is not None:
        p_cross_next = _prob_delta_at_least(z, distance, z_sd)
    else:
        p_cross_next = None
    if distance is not None and distance > 3:
        p_cross_next = 0.0
        reasons.append("THRESHOLD_BEYOND_ONE_UPDATE_MODEL")

    p_cross_85 = _prob_delta_at_least(z, 85 - ovr, z_sd) if has_stats and ovr is not None and ovr < 85 else None
    p_cross_90 = _prob_delta_at_least(z, 90 - ovr, z_sd) if has_stats and ovr is not None and ovr < 90 else None

    nr_up = nr is not None and ovr is not None and nr > ovr
    nr_down = nr is not None and ovr is not None and nr < ovr
    nr_flat = nr is not None and ovr is not None and nr == ovr
    nr_crosses = nr_up and threshold is not None and ovr < threshold <= nr
    if nr is None:
        reasons.append("NEW_RANK_UNAVAILABLE")
    else:
        reasons.append("NEW_RANK_AVAILABLE")
        if nr_up:
            reasons.append("NEW_RANK_UP")
        if nr_down:
            reasons.append("NEW_RANK_DOWN")
            reasons.append("RANK_DOWN_BLOCKS_BUY")
        if nr_flat:
            reasons.append("NEW_RANK_FLAT")
        if nr_crosses:
            reasons.append("NEW_RANK_CROSSES_THRESHOLD")
        elif has_stats:
            reasons.append("STATS_ONLY_SCENARIO")

    if nr_up:
        p_upgrade = max(p_upgrade or 0, 0.70)
    if nr_down:
        p_downgrade = max(p_downgrade or 0, 0.70)
    if nr_crosses:
        p_cross_next = max(p_cross_next or 0, 0.85)
        if threshold == 85:
            p_cross_85 = max(p_cross_85 or 0, 0.85)
        if threshold == 90:
            p_cross_90 = max(p_cross_90 or 0, 0.85)

    component_bonus = min(len(components), 2) / 2
    confidence = min(
        100.0,
        max(
            0.0,
            25 + 25 * min(1.0, abs(z) / 2) + 20 * pt_score + 15 * component_bonus + (15 if nr is not None else 0),
        ),
    )
    if nr_crosses:
        confidence = max(confidence, 65.0)
    if not has_stats and nr is None:
        confidence = 0.0
    proximity_bonus = 0.0
    if distance is not None:
        proximity_bonus = 20 if distance <= 1 else 12 if distance == 2 else 5 if distance == 3 else 0
    upgrade_score = min(
        100.0,
        max(
            0.0,
            45 * (p_cross_next or 0)
            + 20 * (p_upgrade or 0)
            + 0.15 * confidence
            + proximity_bonus
            - 20 * (p_downgrade or 0),
        ),
    )

    if not has_stats and nr is None:
        action = "AVOID"
    elif nr_down:
        action = "SELL"
    elif p_downgrade is not None and p_downgrade >= 0.60 and (p_upgrade is None or p_upgrade < 0.40):
        action = "SELL"
    elif nr_crosses and confidence >= 50:
        action = "BUY SPECULATIVE"
    elif (p_upgrade is not None and p_upgrade >= 0.55) or (p_cross_next is not None and p_cross_next >= 0.25):
        action = "WATCH"
    else:
        action = "HOLD"

    if action == "BUY SPECULATIVE":
        reasons.append("UPGRADE_EDGE")
    elif action == "WATCH":
        reasons.append("UPGRADE_WATCH")
    elif action == "SELL":
        reasons.append("DOWNGRADE_RISK")

    unique_reasons = list(dict.fromkeys(reasons))
    label = "high" if confidence >= 70 else "medium" if confidence >= 45 else "low"
    return UpgradeResult(
        current_ovr=ovr,
        rarity=str(rarity) if rarity is not None else None,
        new_rank=nr,
        next_threshold=threshold,
        distance_to_threshold=distance,
        distance_to_85=dist85,
        distance_to_90=dist90,
        p_upgrade=_clamp01(p_upgrade),
        p_downgrade=_clamp01(p_downgrade),
        p_cross_next_threshold=_clamp01(p_cross_next),
        p_cross_85=_clamp01(p_cross_85),
        p_cross_90=_clamp01(p_cross_90),
        confidence=confidence,
        confidence_label=label,
        exact_delta_ovr=z_to_delta_ovr(z),
        recent_vs_season_delta=_recent_delta_text(recent, season, role),
        z=z,
        components=components,
        upgrade_score=upgrade_score,
        action=action,
        model_status=model_status,
        probability_kind=probability_kind,
        probability_note=probability_note,
        reason_codes=unique_reasons,
        reason_codes_csv=_csv(unique_reasons),
    )
