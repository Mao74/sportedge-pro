"""Built-in strategy template registry.

This module owns the *static* metadata for each built-in strategy:
display name, color, description, and the JSON `field_schema` declaring
the dynamic form fields. The actual `auto_pnl_calculator` callables are
attached in step 3 (`services/pnl_calculator.py`); this step only needs
the metadata for the seed migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StrategyTemplate:
    template_key: str
    slug: str
    name: str
    description: str
    color_hex: str
    field_schema: dict[str, Any]


MAGIC_CS_V3_TEMPLATE = StrategyTemplate(
    template_key="magic_cs_v3",
    slug="magic-cs",
    name="Magic CS",
    description=(
        "Multi-CS portfolio strategy with optional Lay 0-0 and Over 2.5 parachute hedges. "
        "Scenario-driven PnL calculation."
    ),
    color_hex="#8B7FFF",
    field_schema={
        "fields": [
            {
                "key": "cs_selected",
                "label": "CS selected",
                "type": "chip-picker",
                "options": [
                    "0-0", "1-0", "0-1", "1-1", "2-0", "0-2", "2-1", "1-2",
                    "2-2", "3-0", "0-3", "3-1", "1-3",
                ],
                "min_picks": 1,
                "max_picks": 6,
                "required": True,
            },
            {
                "key": "tier",
                "label": "Tier",
                "type": "select",
                "options": ["1-CS", "2-CS", "3-CS", "4-CS"],
                "required": True,
            },
            {
                "key": "lay_00_placed",
                "label": "Lay 0-0 placed",
                "type": "boolean",
                "default": False,
            },
            {
                "key": "lay_00_stake",
                "label": "Lay 0-0 stake (€)",
                "type": "number",
                "depends_on": "lay_00_placed",
                "min": 0,
                "step": 0.01,
            },
            {
                "key": "o25_placed",
                "label": "O2.5 parachute placed",
                "type": "boolean",
                "default": False,
            },
            {
                "key": "o25_stake",
                "label": "O2.5 stake (€)",
                "type": "number",
                "depends_on": "o25_placed",
                "min": 0,
                "step": 0.01,
            },
            {
                "key": "o25_odds",
                "label": "O2.5 odds at entry",
                "type": "number",
                "depends_on": "o25_placed",
                "min": 1.01,
                "step": 0.01,
            },
            {
                "key": "scenario",
                "label": "Outcome scenario",
                "type": "select",
                "options": [
                    "A1_HIT", "A2_OVER25", "B1_EARLY_CS", "B2_EARLY_OVER",
                    "B3_EARLY_MISS", "C_MULTI_GOAL", "OTHER",
                ],
                "required_for_status": "CLOSED",
            },
        ]
    },
)


DRAW_HUNTER_S4_TEMPLATE = StrategyTemplate(
    template_key="draw_hunter_s4",
    slug="draw-hunter",
    name="Draw Hunter",
    description=(
        "Lay-the-draw strategy with xG-asymmetry trigger. Three exit types "
        "(WIN / LOSS / SCRATCH) plus MANUAL fallback."
    ),
    color_hex="#1DCC8C",
    field_schema={
        "fields": [
            {
                "key": "lay_stake",
                "label": "Lay stake (€)",
                "type": "number",
                "min": 0.01,
                "step": 0.01,
                "required": True,
            },
            {
                "key": "draw_odds",
                "label": "Draw odds at entry",
                "type": "number",
                "min": 1.01,
                "step": 0.01,
                "required": True,
            },
            {
                "key": "entry_minute",
                "label": "Entry minute",
                "type": "number",
                "min": 0,
                "max": 90,
                "step": 1,
            },
            {
                "key": "xg_diff",
                "label": "xG asymmetry",
                "type": "number",
                "step": 0.01,
                "min": -5,
                "max": 5,
            },
            {
                "key": "exit_type",
                "label": "Exit",
                "type": "select",
                "options": ["WIN", "LOSS", "SCRATCH", "MANUAL"],
                "required_for_status": "CLOSED",
            },
        ]
    },
)


REGISTRY: dict[str, StrategyTemplate] = {
    MAGIC_CS_V3_TEMPLATE.template_key: MAGIC_CS_V3_TEMPLATE,
    DRAW_HUNTER_S4_TEMPLATE.template_key: DRAW_HUNTER_S4_TEMPLATE,
}


def all_templates() -> list[StrategyTemplate]:
    return list(REGISTRY.values())
