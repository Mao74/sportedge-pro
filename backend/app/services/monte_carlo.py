"""Monte Carlo bankroll simulator.

Bootstraps an empirical distribution of historical per-trade PnL with
replacement, simulates ``n_simulations`` parallel walks of ``horizon_trades``
trades each, and reports:

- **Risk of ruin** — fraction of paths whose running bankroll ever crossed
  the configured ruin threshold during the walk.
- **Percentile ending bankrolls** (P10, P50, P90).
- **Histogram** of ending bankrolls bucketed for plotting.

Performance budget: 10k simulations × 100-trade horizon must complete in
<2s on the dev machine. We achieve this with pure Python by:

- Sampling the entire ``n_sims * horizon`` draw set in one ``random.choices``
  call (the C-implemented hot path).
- Working in ``float`` for the inner loop (Decimal is ~30× slower).
- Quantising back to ``Decimal`` only at output time.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Iterable

ZERO = Decimal("0")
HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MonteCarloInputs:
    """All inputs needed to run a simulation."""

    historical_pnls: list[Decimal]
    starting_bankroll: Decimal
    n_simulations: int = 10_000
    horizon_trades: int = 100
    ruin_threshold_pct: Decimal = Decimal("50.0")  # bankroll must drop this far below start to count as ruin
    n_buckets: int = 20
    seed: int | None = None  # for deterministic tests

    def __post_init__(self) -> None:
        if self.n_simulations < 1:
            raise ValueError("n_simulations must be >= 1")
        if self.horizon_trades < 1:
            raise ValueError("horizon_trades must be >= 1")
        if self.starting_bankroll <= ZERO:
            raise ValueError("starting_bankroll must be > 0")
        if not (ZERO <= self.ruin_threshold_pct <= HUNDRED):
            raise ValueError("ruin_threshold_pct must be in [0, 100]")
        if self.n_buckets < 2:
            raise ValueError("n_buckets must be >= 2")


@dataclass(frozen=True)
class DistributionBucket:
    bucket_low: Decimal
    bucket_high: Decimal
    count: int


@dataclass(frozen=True)
class MonteCarloResults:
    risk_of_ruin_pct: Decimal       # 0..100
    p10_ending_bankroll: Decimal
    p50_ending_bankroll: Decimal
    p90_ending_bankroll: Decimal
    mean_ending_bankroll: Decimal
    min_ending_bankroll: Decimal
    max_ending_bankroll: Decimal
    distribution: list[DistributionBucket]
    n_simulations: int
    horizon_trades: int


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def run_simulation(inputs: MonteCarloInputs) -> MonteCarloResults:
    """Execute the Monte Carlo simulation and return aggregated results."""
    if not inputs.historical_pnls:
        # No history → degenerate result: every path stays at starting bankroll.
        return _degenerate_results(inputs)

    # Convert historicals to plain floats for the hot loop.
    pnl_floats = [float(p) for p in inputs.historical_pnls]
    starting = float(inputs.starting_bankroll)
    ruin_floor = starting * (1.0 - float(inputs.ruin_threshold_pct) / 100.0)

    rng = random.Random(inputs.seed) if inputs.seed is not None else random
    total_draws = inputs.n_simulations * inputs.horizon_trades
    draws = rng.choices(pnl_floats, k=total_draws)

    endings: list[float] = [0.0] * inputs.n_simulations
    ruined = 0
    horizon = inputs.horizon_trades
    for s in range(inputs.n_simulations):
        cum = starting
        was_ruined = False
        base = s * horizon
        for j in range(horizon):
            cum += draws[base + j]
            if not was_ruined and cum <= ruin_floor:
                was_ruined = True
        endings[s] = cum
        if was_ruined:
            ruined += 1

    return _aggregate(endings, ruined, inputs)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _degenerate_results(inputs: MonteCarloInputs) -> MonteCarloResults:
    """No historical data → flat-line at starting bankroll for every sim."""
    bk = _q(inputs.starting_bankroll)
    return MonteCarloResults(
        risk_of_ruin_pct=ZERO,
        p10_ending_bankroll=bk,
        p50_ending_bankroll=bk,
        p90_ending_bankroll=bk,
        mean_ending_bankroll=bk,
        min_ending_bankroll=bk,
        max_ending_bankroll=bk,
        distribution=[DistributionBucket(bk, bk, inputs.n_simulations)],
        n_simulations=inputs.n_simulations,
        horizon_trades=inputs.horizon_trades,
    )


def _aggregate(
    endings: list[float], ruined: int, inputs: MonteCarloInputs
) -> MonteCarloResults:
    n = inputs.n_simulations
    p10, p50, p90 = _percentiles(endings, (10, 50, 90))
    mean = statistics.fmean(endings)
    distribution = _histogram(endings, inputs.n_buckets)
    risk = Decimal(ruined) / Decimal(n) * HUNDRED

    return MonteCarloResults(
        risk_of_ruin_pct=_q(risk, FOUR_PLACES),
        p10_ending_bankroll=_q(Decimal(str(p10))),
        p50_ending_bankroll=_q(Decimal(str(p50))),
        p90_ending_bankroll=_q(Decimal(str(p90))),
        mean_ending_bankroll=_q(Decimal(str(mean))),
        min_ending_bankroll=_q(Decimal(str(min(endings)))),
        max_ending_bankroll=_q(Decimal(str(max(endings)))),
        distribution=distribution,
        n_simulations=inputs.n_simulations,
        horizon_trades=inputs.horizon_trades,
    )


def _percentiles(values: Iterable[float], pcts: tuple[int, ...]) -> tuple[float, ...]:
    """Linear-interpolation percentiles. statistics.quantiles needs the full
    decile/centile parameter so we just sort and lerp ourselves — predictable
    and works for tiny samples."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    out: list[float] = []
    for p in pcts:
        if n == 1:
            out.append(sorted_vals[0])
            continue
        rank = (p / 100.0) * (n - 1)
        lo = int(rank)
        frac = rank - lo
        if lo + 1 >= n:
            out.append(sorted_vals[-1])
        else:
            out.append(sorted_vals[lo] + frac * (sorted_vals[lo + 1] - sorted_vals[lo]))
    return tuple(out)


def _histogram(values: list[float], n_buckets: int) -> list[DistributionBucket]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if lo == hi:
        return [DistributionBucket(_q(Decimal(str(lo))), _q(Decimal(str(hi))), len(values))]
    width = (hi - lo) / n_buckets
    counts = [0] * n_buckets
    for v in values:
        idx = int((v - lo) / width)
        if idx >= n_buckets:  # the maximum value lands in the last bucket
            idx = n_buckets - 1
        counts[idx] += 1
    return [
        DistributionBucket(
            bucket_low=_q(Decimal(str(lo + i * width))),
            bucket_high=_q(Decimal(str(lo + (i + 1) * width))),
            count=c,
        )
        for i, c in enumerate(counts)
    ]


def _q(value: Decimal, places: Decimal = TWO_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_EVEN)


__all__ = [
    "MonteCarloInputs",
    "MonteCarloResults",
    "DistributionBucket",
    "run_simulation",
]
