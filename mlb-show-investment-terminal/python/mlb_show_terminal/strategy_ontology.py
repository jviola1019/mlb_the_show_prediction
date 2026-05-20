"""Typed strategy ontology for card-market decisions.

These dataclasses are the API contract used by scan/card analysis responses.
They keep spread flips, directional holds, inventory quality, and the final
action separated so a bearish forecast can never be mislabeled as investable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return str(self.value)


class FlipVerdict(StrEnum):
    FLIP_PASS = "FLIP PASS"
    FLIP_MARGINAL = "FLIP MARGINAL"
    NO_FLIP_EDGE = "NO FLIP EDGE"
    DO_NOT_FLIP = "DO NOT FLIP"


class DirectionalVerdict(StrEnum):
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    INSUFFICIENT_DATA = "INSUFFICIENT DATA"


class InventoryVerdict(StrEnum):
    HIGH_LIQUIDITY = "HIGH LIQUIDITY"
    MEDIUM_LIQUIDITY = "MEDIUM LIQUIDITY"
    THIN = "THIN"
    DEAD_INVENTORY = "DEAD INVENTORY"


class FinalAction(StrEnum):
    INSTANT_FLIP_ONLY = "INSTANT FLIP ONLY"
    FLIP_OR_SHORT_HOLD = "FLIP OR SHORT HOLD"
    SPREAD_CAPTURE_ONLY = "SPREAD CAPTURE ONLY"
    SPECULATIVE_HOLD = "SPECULATIVE HOLD"
    WATCHLIST_NO_MODEL_TRADE = "WATCHLIST / NO MODEL TRADE"
    AVOID = "AVOID"
    AVOID_MANUAL_REVIEW = "AVOID / MANUAL REVIEW"
    MANUAL_REVIEW = "MANUAL REVIEW"


class ValidationTier(StrEnum):
    UNVALIDATED = "UNVALIDATED"
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"
    PLATINUM = "PLATINUM"


class HoldingHorizon(StrEnum):
    ONE_DAY = "1d"
    THREE_DAY = "3d"
    SEVEN_DAY = "7d"
    MANUAL_REVIEW = "manual review"


@dataclass(frozen=True)
class FlipStrategy:
    verdict: FlipVerdict
    raw_ask: float | None
    raw_bid: float | None
    after_tax_resale_value: float | None
    expected_net_stubs: float | None
    expected_roi_after_tax_and_friction: float | None
    p_successful_exit: float | None
    expected_holding_time_hours: float | None
    worst_case_liquidation_value: float | None
    action: str
    reason_codes: list[str] = field(default_factory=list)
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    slippage_estimate: float | None = None
    undercut_risk: float | None = None
    spread_compression_risk: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return _clean(asdict(self))


@dataclass(frozen=True)
class DirectionalStrategy:
    verdict: DirectionalVerdict
    investable_label: str | None
    expected_return_by_horizon: dict[str, float | None]
    p_up: float | None
    p_down: float | None
    p_profit: float | None
    prediction_interval: dict[str, float | None]
    quantile_forecasts: dict[str, float | None]
    forecast_cone: list[dict[str, Any]]
    model_confidence: float | None
    validation_tier: ValidationTier
    recommended_holding_horizon: HoldingHorizon
    holding_instruction: str
    source_verdict: str | None
    reason_codes: list[str] = field(default_factory=list)
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    data_coverage_tier: ValidationTier = ValidationTier.UNVALIDATED
    performance_validation_tier: ValidationTier = ValidationTier.UNVALIDATED

    def to_dict(self) -> dict[str, Any]:
        return _clean(asdict(self))


@dataclass(frozen=True)
class InventoryStrategy:
    verdict: InventoryVerdict
    inventory_risk_score: float
    expected_exit_time_hours: float | None
    liquidity_score: float | None
    liquidity_recent: int | None
    dead_inventory_warning: str | None
    position_size_recommendation: str
    max_position_stubs: int
    reason_codes: list[str] = field(default_factory=list)
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _clean(asdict(self))


@dataclass(frozen=True)
class CompositeStrategy:
    final_action: FinalAction
    strategy_type: str
    investable_label: str | None
    hold_duration: HoldingHorizon
    holding_instruction: str
    explanation: str
    gates_passed: list[str]
    gates_failed: list[str]
    reason_codes: list[str]
    confidence: float | None

    def to_dict(self) -> dict[str, Any]:
        return _clean(asdict(self))


def _clean(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value
