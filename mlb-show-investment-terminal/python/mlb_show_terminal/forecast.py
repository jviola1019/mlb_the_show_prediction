"""Deterministic price-history diagnostics.

Forecast diagnostics are intentionally separate from executable flip decisions.
They can describe price-history direction and uncertainty, but never overwrite
after-tax bid/ask flip math.
"""

from __future__ import annotations

import math
import random
from statistics import mean, median, stdev
from typing import Any


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def extract_prices(listing: dict[str, Any]) -> list[float]:
    orders = listing.get("completed_orders") or []
    prices = [_num((row or {}).get("price")) for row in orders if isinstance(row, dict)]
    prices = [p for p in prices if p is not None and p > 0]
    if len(prices) >= 8:
        return list(reversed(prices))

    history = listing.get("price_history") or (listing.get("item") or {}).get("price_history") or []
    out: list[float] = []
    for row in history:
        if not isinstance(row, dict):
            continue
        ask = _num(row.get("best_sell_price"))
        bid = _num(row.get("best_buy_price"))
        vals = [x for x in (ask, bid) if x is not None and x > 0]
        if vals:
            out.append(mean(vals))
    return out


def log_returns(prices: list[float]) -> list[float]:
    return [
        math.log(prices[i] / prices[i - 1])
        for i in range(1, len(prices))
        if prices[i] > 0 and prices[i - 1] > 0
    ]


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _safe_mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def _safe_stdev(values: list[float]) -> float | None:
    return stdev(values) if len(values) >= 2 else None


def _norm_cdf(x: float, mean_: float = 0.0, sd: float = 1.0) -> float:
    if sd <= 0 or not math.isfinite(sd):
        return 0.5
    z = (x - mean_) / (sd * math.sqrt(2))
    return 0.5 * (1 + math.erf(z))


def _pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 3:
        return None
    mx, my = mean(x), mean(y)
    sx = math.sqrt(sum((v - mx) ** 2 for v in x))
    sy = math.sqrt(sum((v - my) ** 2 for v in y))
    if sx <= 0 or sy <= 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def _ols_drift(prices: list[float]) -> dict[str, float | None]:
    if len(prices) < 8:
        return {"drift_per_day": None, "drift_p_value": None}
    y = [math.log(p) for p in prices if p > 0]
    n = len(y)
    if n < 8:
        return {"drift_per_day": None, "drift_p_value": None}
    x = list(range(n))
    mx, my = mean(x), mean(y)
    sxx = sum((v - mx) ** 2 for v in x)
    if sxx <= 0:
        return {"drift_per_day": None, "drift_p_value": None}
    slope = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / sxx
    residuals = [yi - (my + slope * (xi - mx)) for xi, yi in zip(x, y)]
    if n <= 2:
        return {"drift_per_day": slope, "drift_p_value": None}
    sigma2 = sum(r * r for r in residuals) / (n - 2)
    se = math.sqrt(sigma2 / sxx) if sigma2 >= 0 else None
    if not se or se <= 0:
        return {"drift_per_day": slope, "drift_p_value": None}
    t = slope / se
    # Normal approximation is sufficient for a diagnostic label.
    p_value = 2 * (1 - _norm_cdf(abs(t)))
    return {"drift_per_day": slope, "drift_p_value": max(0.0, min(1.0, p_value))}


def _hurst_rs(prices: list[float]) -> float | None:
    rets = log_returns(prices)
    if len(rets) < 20:
        return None
    window_sizes = [w for w in (8, 12, 16, 24, 32) if w * 2 <= len(rets)]
    points: list[tuple[float, float]] = []
    for window in window_sizes:
        rs_values: list[float] = []
        for start in range(0, len(rets) - window + 1, window):
            chunk = rets[start : start + window]
            m = mean(chunk)
            cumulative: list[float] = []
            total = 0.0
            for value in chunk:
                total += value - m
                cumulative.append(total)
            r = max(cumulative) - min(cumulative)
            s = _safe_stdev(chunk)
            if s and s > 0:
                rs_values.append(r / s)
        if rs_values:
            points.append((math.log(window), math.log(mean(rs_values))))
    if len(points) < 2:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx, my = mean(xs), mean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom <= 0:
        return None
    hurst = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    return max(0.0, min(1.0, hurst))


def price_history_summary(prices: list[float]) -> dict[str, Any]:
    return {
        "n": len(prices),
        "last": prices[-1] if prices else None,
        "min": min(prices) if prices else None,
        "max": max(prices) if prices else None,
        "median": median(prices) if prices else None,
    }


def _simulate_paths(
    current: float,
    rets: list[float],
    *,
    horizon: int,
    n_sims: int,
    seed: int,
) -> list[list[float]]:
    rng = random.Random(seed)
    block_len = max(3, int(len(rets) ** 0.4))
    paths: list[list[float]] = []
    for _ in range(max(50, int(n_sims))):
        log_p = math.log(current)
        steps = 0
        path: list[float] = []
        while steps < horizon:
            start = rng.randrange(0, max(1, len(rets) - block_len + 1))
            for r in rets[start : start + block_len]:
                log_p += r
                path.append(math.exp(log_p))
                steps += 1
                if steps >= horizon:
                    break
        paths.append(path)
    return paths


def _path_returns(
    paths: list[list[float]],
    *,
    current: float,
    spread_ratio: float,
) -> list[float]:
    return [((path[-1] * spread_ratio * 0.90) - current) / current for path in paths if path]


def _horizon_summary(paths: list[list[float]], *, current: float, spread_ratio: float, horizon: int) -> dict[str, Any]:
    returns = _path_returns(paths, current=current, spread_ratio=spread_ratio)
    if not returns:
        return {"horizon": horizon, "status": "unavailable"}
    expected_ret = mean(returns)
    p_profit = sum(1 for r in returns if r > 0) / len(returns)
    variance = sum((r - expected_ret) ** 2 for r in returns) / max(1, len(returns) - 1)
    half_kelly = 0.5 * expected_ret / variance if variance > 0 and expected_ret > 0 else 0.0
    return {
        "horizon": horizon,
        "status": "ok",
        "expected_ret": expected_ret,
        "p_profit": p_profit,
        "p5_ret": _quantile(returns, 0.05),
        "p50_ret": median(returns),
        "p95_ret": _quantile(returns, 0.95),
        "breakeven_ret": 0.0,
        "half_kelly": max(0.0, min(1.0, half_kelly)),
    }


def forecast_cone(paths: list[list[float]]) -> list[dict[str, Any]]:
    if not paths:
        return []
    horizon = max(len(path) for path in paths)
    out: list[dict[str, Any]] = []
    for idx in range(horizon):
        values = [path[idx] for path in paths if len(path) > idx]
        if values:
            out.append({
                "step": idx + 1,
                "p5": _quantile(values, 0.05),
                "p50": median(values),
                "p95": _quantile(values, 0.95),
            })
    return out


def quant_diagnostics(prices: list[float], *, ask: float | None, bid: float | None) -> dict[str, Any]:
    rets = log_returns(prices)
    recent = prices[-30:] if len(prices) >= 30 else prices
    z30 = None
    if len(recent) >= 3:
        sd = _safe_stdev(recent)
        if sd and sd > 0:
            z30 = (recent[-1] - mean(recent)) / sd
    drift = _ols_drift(prices)
    spread_pct = (ask - bid) / ask if ask and bid and ask > 0 and bid > 0 else None
    ret_sd = _safe_stdev(rets)
    return {
        "z30": z30,
        "drift_per_day": drift["drift_per_day"],
        "drift_p_value": drift["drift_p_value"],
        "hurst": _hurst_rs(prices),
        "annualized_vol": ret_sd * math.sqrt(365) if ret_sd is not None else None,
        "n_steps": len(rets),
        "spread_pct": spread_pct,
    }


def walk_forward_cv(prices: list[float], *, lookback: int = 20, boot_b: int = 300, seed: int = 1702) -> dict[str, Any]:
    rets = log_returns(prices)
    if len(rets) < lookback + 8:
        return {
            "status": "unavailable",
            "reason": "need more price history for walk-forward CV",
            "n_trades": 0,
            "ci_method": "unavailable",
            "boot_b": boot_b,
            "trades": [],
        }
    trades: list[dict[str, Any]] = []
    for idx in range(lookback, len(rets)):
        hist = rets[idx - lookback : idx]
        mu = mean(hist)
        sd = _safe_stdev(hist) or 1e-9
        p_up = 1 - _norm_cdf(0, mean_=mu, sd=sd)
        realized_up = 1 if rets[idx] > 0 else 0
        trades.append({
            "index": idx,
            "p_up": max(0.0, min(1.0, p_up)),
            "realized_up": realized_up,
            "brier_t": (p_up - realized_up) ** 2,
        })
    p = [float(t["p_up"]) for t in trades]
    y = [float(t["realized_up"]) for t in trades]
    brier = mean([(pi - yi) ** 2 for pi, yi in zip(p, y)])
    ic = _pearson(p, y)
    hit_rate = mean([1.0 if (pi >= 0.5) == bool(yi) else 0.0 for pi, yi in zip(p, y)])
    rng = random.Random(seed)
    brier_samples: list[float] = []
    ic_samples: list[float] = []
    for _ in range(max(50, boot_b)):
        sample = [rng.randrange(0, len(trades)) for _ in trades]
        ps = [p[i] for i in sample]
        ys = [y[i] for i in sample]
        brier_samples.append(mean([(pi - yi) ** 2 for pi, yi in zip(ps, ys)]))
        corr = _pearson(ps, ys)
        if corr is not None:
            ic_samples.append(corr)
    return {
        "status": "ok",
        "n_trades": len(trades),
        "brier_point": brier,
        "brier_ci": [_quantile(brier_samples, 0.05), _quantile(brier_samples, 0.95)],
        "ic_point": ic,
        "ic_ci": [_quantile(ic_samples, 0.05), _quantile(ic_samples, 0.95)] if ic_samples else [None, None],
        "hit_rate": hit_rate,
        "ci_method": "block-bootstrap",
        "boot_b": boot_b,
        "trades": trades[-80:],
    }


def reliability_bins(trades: list[dict[str, Any]], *, n_bins: int = 5) -> dict[str, Any]:
    if len(trades) < n_bins:
        return {"status": "unavailable", "reason": "not enough trades for reliability bins", "bins": []}
    bins: list[dict[str, Any]] = []
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        bucket = [
            t for t in trades
            if lo <= float(t.get("p_up", -1)) <= hi if i == n_bins - 1
        ]
        if i != n_bins - 1:
            bucket = [t for t in trades if lo <= float(t.get("p_up", -1)) < hi]
        observed = mean([float(t["realized_up"]) for t in bucket]) if bucket else None
        predicted = mean([float(t["p_up"]) for t in bucket]) if bucket else None
        bins.append({
            "bin_lo": lo,
            "bin_hi": hi,
            "bin_mid": (lo + hi) / 2,
            "n": len(bucket),
            "mean_pred": predicted,
            "observed_rate": observed,
        })
    return {"status": "ok", "bins": bins}


def validation_gates(wfcv: dict[str, Any], diagnostics: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    if wfcv.get("status") != "ok":
        failed.append("cv_available")
    if wfcv.get("ic_point") is not None and wfcv.get("ic_point") < -0.05:
        failed.append("cv_skill_not_negative")
    if wfcv.get("n_trades", 0) and wfcv.get("n_trades", 0) < 25:
        failed.append("history_sufficient")
    if diagnostics.get("spread_pct") is None:
        failed.append("spread_available")
    return {
        "status": "pass" if not failed else "diagnostic_warning",
        "failed": failed,
        "failed_csv": ",".join(failed),
        "note": "Forecast gates do not block executable flip or upgrade signals.",
    }


def tier_from_diagnostics(wfcv: dict[str, Any], gates: dict[str, Any]) -> str:
    if gates.get("failed"):
        return "BRONZE"
    n = int(wfcv.get("n_trades") or 0)
    ic = wfcv.get("ic_point")
    brier = wfcv.get("brier_point")
    if n >= 50 and ic is not None and ic >= 0.05 and brier is not None and brier <= 0.24:
        return "GOLD"
    if n >= 25:
        return "SILVER"
    return "BRONZE"


def forecast_diagnostics(
    listing: dict[str, Any],
    *,
    horizon: int = 7,
    n_sims: int = 600,
    seed: int = 1701,
) -> dict[str, Any]:
    prices = extract_prices(listing)
    item = listing.get("item") or {}
    ask = _num(listing.get("best_sell_price"))
    bid = _num(listing.get("best_buy_price"))
    current = ask or (prices[-1] if prices else None)
    rets = log_returns(prices)
    if current is None or current <= 0 or len(rets) < 8:
        return {
            "status": "unavailable",
            "reason": "need at least 8 valid price returns",
            "diagnostic_only": True,
            "n_prices": len(prices),
            "horizon": horizon,
            "price_history": price_history_summary(prices),
            "cone": [],
            "horizons": [],
            "diagnostics": quant_diagnostics(prices, ask=ask, bid=bid),
            "walk_forward": {
                "status": "unavailable",
                "reason": "need at least 8 valid price returns",
                "n_trades": 0,
            },
            "calibration": {"status": "unavailable", "bins": []},
            "gates": {
                "status": "diagnostic_warning",
                "failed": ["history_sufficient", "cv_available"],
                "failed_csv": "history_sufficient,cv_available",
                "note": "Forecast gates do not block executable flip or upgrade signals.",
            },
            "tier": "UNRATED",
            "verdict": {
                "status": "OBSERVATIONAL ONLY",
                "reason": "forecast diagnostics unavailable",
            },
        }

    block_len = max(3, int(len(rets) ** 0.4))
    spread_ratio = (bid / ask) if ask and bid and ask > 0 and bid > 0 else 0.9
    paths = _simulate_paths(current, rets, horizon=horizon, n_sims=n_sims, seed=seed)
    returns = _path_returns(paths, current=current, spread_ratio=spread_ratio)
    expected_ret = mean(returns)
    p_profit = sum(1 for r in returns if r > 0) / len(returns)
    direction = "FORECAST FLAT"
    if expected_ret >= 0.01:
        direction = "FORECAST BULLISH"
    elif expected_ret <= -0.01:
        direction = "FORECAST BEARISH"
    diagnostics = quant_diagnostics(prices, ask=ask, bid=bid)
    wfcv = walk_forward_cv(prices)
    calibration = reliability_bins(wfcv.get("trades", []))
    gates = validation_gates(wfcv, diagnostics)
    tier = tier_from_diagnostics(wfcv, gates)
    horizons = [
        _horizon_summary(
            _simulate_paths(current, rets, horizon=h, n_sims=max(120, n_sims // 2), seed=seed + h),
            current=current,
            spread_ratio=spread_ratio,
            horizon=h,
        )
        for h in (1, 3, 7)
    ]

    return {
        "status": "ok",
        "diagnostic_only": True,
        "reason": "forecast EV is not executable flip EV",
        "uuid": item.get("uuid"),
        "horizon": horizon,
        "n_prices": len(prices),
        "block_length": block_len,
        "expected_ret": expected_ret,
        "p_profit": p_profit,
        "p5_ret": _quantile(returns, 0.05),
        "p50_ret": median(returns),
        "p95_ret": _quantile(returns, 0.95),
        "direction": direction,
        "price_history": price_history_summary(prices),
        "cone": forecast_cone(paths),
        "horizons": horizons,
        "diagnostics": diagnostics,
        "walk_forward": wfcv,
        "calibration": calibration,
        "gates": gates,
        "tier": tier,
        "verdict": {
            "status": "OBSERVATIONAL ONLY",
            "reason": "forecast diagnostics are not executable trade signals",
        },
    }
