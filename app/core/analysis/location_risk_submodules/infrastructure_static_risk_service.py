"""
Infrastructure Static Risk Service
=====================================
Derives district-level infrastructure disruption risk from:
  - Climate Static Risk  (weight 0.6)
  - Political Static Risk (weight 0.4)

Formula:
    Infrastructure Risk = 0.6 * climate_disruption_score
                        + 0.4 * political_security_disruption_score

Climate disruption uses infra-relevant hazard weights only:
    River flood=18, Urban flood=15, Coastal flood=10, Cyclone=18,
    Landslide=12, Earthquake=10, Extreme heat=8, Water scarcity=6, Wildfire=3

Political security disruption = Political Relative Score (from ACLED).

No database, no LLM — derived entirely from static file-based services.
"""

import logging

from app.core.analysis.location_risk_submodules.climate_static_risk_service import (
    _load_data as _load_climate,
    _compute_score,
    _parse_severity,
    resolve_from_list,
)
from app.core.analysis.location_risk_submodules.political_static_risk_service import (
    _load_data as _load_political,
)
from app.core.utils.risk_utils import score_to_level, to_gauge_score

logger = logging.getLogger(__name__)

# Infra-relevant hazard weights (subset of climate hazards)
INFRA_HAZARD_WEIGHTS: dict[str, int] = {
    "River flood":    18,
    "Urban flood":    15,
    "Coastal flood":  10,
    "Cyclone":        18,
    "Landslide":      12,
    "Earthquake":     10,
    "Extreme heat":    8,
    "Water scarcity":  6,
    "Wildfire":        3,
}

_CLIMATE_WEIGHT  = 0.6
_POLITICAL_WEIGHT = 0.4


def _compute_infra_climate_score(location: str) -> tuple[float | None, list[dict], str | None, str | None]:
    """
    Compute climate disruption score using infra-relevant hazard weights.

    Returns (score, top_drivers, district_name, state_name).
    Returns (None, [], None, None) if location cannot be resolved.
    """
    df = _load_climate()
    division_to_state = {r["division"]: r["region_l2"] for _, r in df.iterrows()}
    divisions = list(division_to_state.keys())

    resolution = resolve_from_list(location, divisions, fuzzy_cutoff=0.5)
    if resolution["matched"] is None:
        return None, [], None, None

    district_name = resolution["matched"]
    state_name    = division_to_state[district_name]
    row = df[df["division"] == district_name].iloc[0]

    weighted_sum = 0.0
    weight_sum   = 0
    drivers: list[dict] = []

    for hazard, weight in INFRA_HAZARD_WEIGHTS.items():
        raw   = row.get(hazard)
        score = _parse_severity(raw)
        if score is not None:
            weighted_sum += score * weight
            weight_sum   += weight
            drivers.append({
                "hazard":       hazard,
                "score":        score,
                "weight":       weight,
                "contribution": round(score * weight * _CLIMATE_WEIGHT, 4),
                "level":        score_to_level(score),
            })

    if weight_sum == 0:
        return None, [], district_name, state_name

    final = weighted_sum / weight_sum
    top_drivers = sorted(drivers, key=lambda d: d["contribution"], reverse=True)[:5]
    return final, top_drivers, district_name, state_name


def _compute_infra_political_score(location: str) -> tuple[float | None, str | None]:
    """
    Returns (political_relative_score, district_name) or (None, None).
    """
    districts, _ = _load_political()
    labels = districts["Row Labels"].tolist()
    resolution = resolve_from_list(location, labels)
    if resolution["matched"] is None:
        return None, None

    district_name = resolution["matched"]
    row = districts[districts["Row Labels"] == district_name].iloc[0]
    score = float(row.get("Relative Score", 0) or 0)
    return score, district_name


def get_infrastructure_static_risk(location: str) -> dict:
    """
    Return the full infrastructure static risk payload for a given location string.

    Raises
    ------
    FileNotFoundError  — data files missing
    ValueError         — location cannot be resolved in either dataset
    """
    climate_score,   climate_drivers,  climate_district,   climate_state   = _compute_infra_climate_score(location)
    political_score, political_district                                     = _compute_infra_political_score(location)

    if climate_score is None and political_score is None:
        raise ValueError(
            f"Location '{location}' could not be resolved in either the climate "
            "or political dataset."
        )

    # Resolve best district/state name
    resolved_district = climate_district or political_district
    resolved_state    = climate_state

    # ── Compute infrastructure score ──────────────────────────────────────────
    if climate_score is not None and political_score is not None:
        infra_score = _CLIMATE_WEIGHT * climate_score + _POLITICAL_WEIGHT * political_score
        availability = "full"
    elif climate_score is not None:
        infra_score = climate_score
        availability = "climate_only"
    else:
        infra_score = political_score
        availability = "political_only"

    gauge_score = to_gauge_score(infra_score)
    level       = score_to_level(infra_score)

    # ── Components ─────────────────────────────────────────────────────────────
    components = {}
    if climate_score is not None:
        components["climate_disruption"] = {
            "score":       round(climate_score, 4),
            "weight":      _CLIMATE_WEIGHT,
            "contribution":round(_CLIMATE_WEIGHT * climate_score, 4),
            "level":       score_to_level(climate_score),
            "source":      "thinkhzrd.csv (infra-relevant hazards)",
        }
    if political_score is not None:
        components["political_disruption"] = {
            "score":       round(political_score, 4),
            "weight":      _POLITICAL_WEIGHT,
            "contribution":round(_POLITICAL_WEIGHT * political_score, 4),
            "level":       score_to_level(political_score),
            "source":      "ACLED_updated.xlsx (Relative Score)",
        }

    # ── Top infrastructure drivers ─────────────────────────────────────────────
    top_infra_drivers: list[dict] = []
    for d in climate_drivers:
        top_infra_drivers.append({
            "driver":      d["hazard"],
            "type":        "climate",
            "score":       d["score"],
            "contribution":d["contribution"],
            "level":       d["level"],
        })
    if political_score is not None:
        top_infra_drivers.append({
            "driver":      "Political/Security Risk",
            "type":        "political",
            "score":       round(political_score, 4),
            "contribution":round(_POLITICAL_WEIGHT * political_score, 4),
            "level":       score_to_level(political_score),
        })
    top_infra_drivers.sort(key=lambda d: d["contribution"], reverse=True)

    # ── Visualization ──────────────────────────────────────────────────────────
    component_bar_chart = [
        {
            "label": "Climate Disruption",
            "value": round(_CLIMATE_WEIGHT * climate_score, 4) if climate_score is not None else 0,
            "weight": _CLIMATE_WEIGHT,
        },
        {
            "label": "Political/Security Disruption",
            "value": round(_POLITICAL_WEIGHT * political_score, 4) if political_score is not None else 0,
            "weight": _POLITICAL_WEIGHT,
        },
    ]

    top_driver_bar_chart = [
        {"label": d["driver"], "value": d["contribution"], "type": d["type"]}
        for d in top_infra_drivers[:8]
    ]

    impact_cards = [
        {
            "label":  "Infrastructure Disruption Risk",
            "score":  round(infra_score, 4),
            "level":  level,
            "note":   "Combined climate and political disruption",
        },
        {
            "label":  "Climate Disruption Component",
            "score":  round(climate_score, 4) if climate_score is not None else None,
            "level":  score_to_level(climate_score) if climate_score is not None else "N/A",
            "note":   "Infra-relevant natural hazard exposure",
        },
        {
            "label":  "Political/Security Component",
            "score":  round(political_score, 4) if political_score is not None else None,
            "level":  score_to_level(political_score) if political_score is not None else "N/A",
            "note":   "ACLED relative political/security risk",
        },
    ]

    # ── Reasoning ──────────────────────────────────────────────────────────────
    parts = []
    if climate_score is not None and political_score is not None:
        parts.append(
            f"Infrastructure disruption risk is computed as "
            f"0.6 × climate ({climate_score:.2f}) + 0.4 × political ({political_score:.2f}) = {infra_score:.2f}."
        )
    elif climate_score is not None:
        parts.append(
            f"Only climate data available; infrastructure score equals climate disruption score ({infra_score:.2f})."
        )
    else:
        parts.append(
            f"Only political data available; infrastructure score equals political disruption score ({infra_score:.2f})."
        )

    top_names = [d["driver"] for d in top_infra_drivers[:3]]
    if top_names:
        parts.append(f"Top infrastructure risk drivers: {', '.join(top_names)}.")

    reasoning = {
        "summary": " ".join(parts),
        "methodology_note": (
            "Infrastructure risk is a derived score — it reflects potential disruption "
            "to infrastructure from environmental hazards and political/security events. "
            "It does not directly measure infrastructure quality, age, or maintenance. "
            "Climate component uses infra-relevant hazard weights: River flood, Urban flood, "
            "Coastal flood, Cyclone, Landslide, Earthquake, Extreme heat, Water scarcity, Wildfire. "
            "Political component uses the ACLED Relative Score."
        ),
        "availability": availability,
    }

    return {
        "input_location": location,
        "resolved_location": {
            "district": resolved_district,
            "state":    resolved_state,
        },
        "infrastructure_static_risk": {
            "score":        round(infra_score, 4),
            "actual_score": round(infra_score, 4),
            "gauge_score":  round(gauge_score, 4),
            "level":        level,
            "availability": availability,
        },
        "components":             components,
        "top_infrastructure_drivers": top_infra_drivers,
        "visualization": {
            "overall_gauge": {
                "label":        "Infrastructure Disruption Risk",
                "actual_score": round(infra_score, 4),
                "gauge_score":  round(gauge_score, 4),
                "level":        level,
            },
            "component_bar_chart":   component_bar_chart,
            "top_driver_bar_chart":  top_driver_bar_chart,
            "impact_cards":          impact_cards,
        },
        "reasoning": reasoning,
    }
