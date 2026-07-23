"""
Climate Static Risk Service
============================
District-level climate/hazard risk scoring from thinkhzrd.csv (ThinkHazard data).
No database, no LLM — pure file-based, deterministic.

Formula:
    weighted_score = sum(hazard_score * weight) / sum(weights of available hazards)
    NaN / "No Data" hazards are excluded from both numerator and denominator.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from app.core.utils.text_utils import resolve_from_list
from app.core.utils.risk_utils import score_to_level, to_gauge_score

logger = logging.getLogger(__name__)

_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "thinkhzrd.csv"

HAZARD_WEIGHTS: dict[str, int] = {
    "River flood":    15,
    "Urban flood":    10,
    "Coastal flood":   8,
    "Earthquake":     10,
    "Landslide":       8,
    "Tsunami":         5,
    "Volcano":         2,
    "Cyclone":        15,
    "Water scarcity": 10,
    "Extreme heat":   12,
    "Wildfire":        5,
}

HAZARD_COLS: list[str] = list(HAZARD_WEIGHTS.keys())

SEVERITY_SCORES: dict[str, int] = {
    "high":     10,
    "medium":    6,
    "low":       3,
    "very low":  1,
}

_REQUIRED_COLS: frozenset[str] = frozenset({"region_l2", "division"} | set(HAZARD_COLS))
_ADMIN_NOT_AVAILABLE = "administrative unit not available"


# Simple mtime-aware cache: re-parses thinkhzrd.csv only when its file
# modification time changes, instead of caching forever for the life of
# the process (the old @lru_cache(maxsize=1) behavior). This means
# updating the CSV with new districts is picked up automatically on the
# next request — no service restart needed — while still avoiding a
# full re-parse on every single call.
_cache: dict = {"df": None, "mtime": None}


def _load_data() -> pd.DataFrame:
    if not _CSV_PATH.exists():
        raise FileNotFoundError(
            f"ThinkHazard data file not found: {_CSV_PATH}. "
            "Place thinkhzrd.csv in data/."
        )

    mtime = _CSV_PATH.stat().st_mtime
    if _cache["df"] is not None and _cache["mtime"] == mtime:
        return _cache["df"]

    valid = _parse_data()
    _cache["df"] = valid
    _cache["mtime"] = mtime
    return valid


def _parse_data() -> pd.DataFrame:
    logger.info("Loading ThinkHazard climate risk data from %s", _CSV_PATH.name)
    df = pd.read_csv(_CSV_PATH)
    df.columns = [str(c).strip() for c in df.columns]

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"thinkhzrd.csv is missing required columns: {sorted(missing)}. "
            f"Found: {sorted(df.columns.tolist())}"
        )

    df["region_l2"] = df["region_l2"].astype(str).str.strip()
    df["division"]  = df["division"].astype(str).str.strip()

    valid = df[
        (df["region_l2"].str.lower() != _ADMIN_NOT_AVAILABLE)
        & (df["division"].str.lower() != _ADMIN_NOT_AVAILABLE)
    ].copy()

    for col in HAZARD_COLS:
        if col in valid.columns:
            valid[col] = valid[col].apply(
                lambda v: str(v).strip() if pd.notna(v) else None
            )

    logger.info("ThinkHazard loaded: %d districts across %d states", len(valid), valid["region_l2"].nunique())
    return valid


def _parse_severity(raw: Optional[str]) -> Optional[int]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    return SEVERITY_SCORES.get(str(raw).strip().lower())


def _compute_score(row: pd.Series) -> tuple[float, list[dict], list[dict]]:
    included: list[dict] = []
    excluded: list[dict] = []
    weighted_sum = 0.0
    weight_sum   = 0

    for hazard in HAZARD_COLS:
        raw    = row.get(hazard)
        score  = _parse_severity(raw)
        weight = HAZARD_WEIGHTS[hazard]
        sev    = str(raw).strip() if raw is not None and not (isinstance(raw, float) and pd.isna(raw)) else None

        if score is not None:
            weighted_sum += score * weight
            weight_sum   += weight
            included.append({
                "hazard":   hazard,
                "severity": sev,
                "score":    score,
                "weight":   weight,
                "level":    score_to_level(score),
            })
        else:
            excluded.append({
                "hazard":   hazard,
                "severity": "No Data",
                "score":    None,
                "weight":   weight,
                "reason":   "No data / not applicable",
            })

    if weight_sum == 0:
        raise ValueError("No available hazard data for this district.")

    return weighted_sum / weight_sum, included, excluded


def get_climate_static_risk(location: str) -> dict:
    """
    Return the full climate static risk payload for a given location string.

    Raises
    ------
    FileNotFoundError  — CSV file missing
    ValueError         — required columns missing, location not found,
                         or no available hazard data for the district
    """
    df = _load_data()

    # Build district → state lookup; resolve against division names
    division_to_state: dict[str, str] = {}
    for _, r in df.iterrows():
        division_to_state[r["division"]] = r["region_l2"]

    divisions = list(division_to_state.keys())
    resolution = resolve_from_list(location, divisions, fuzzy_cutoff=0.5)

    if resolution["matched"] is None:
        sample = ", ".join(sorted(divisions)[:8])
        raise ValueError(
            f"Location '{location}' could not be resolved to any district in thinkhzrd.csv. "
            f"Sample districts: {sample}…"
        )

    district_name: str = resolution["matched"]
    state_name:    str = division_to_state[district_name]

    row = df[df["division"] == district_name].iloc[0]

    actual_score, included, excluded = _compute_score(row)
    gauge_score = to_gauge_score(actual_score)
    level       = score_to_level(actual_score)

    top_drivers = sorted(
        included,
        key=lambda h: (h["score"], h["weight"]),
        reverse=True,
    )[:5]

    # ── Visualization ──────────────────────────────────────────────────────────
    hazard_cards = [
        {"hazard": h["hazard"], "severity": h["severity"], "score": h["score"],
         "weight": h["weight"], "level": h["level"]}
        for h in sorted(included, key=lambda x: x["score"], reverse=True)
    ]

    hazard_bar_chart = [
        {"label": h["hazard"], "value": h["score"]}
        for h in sorted(included, key=lambda x: x["score"], reverse=True)
    ]

    hazard_radar_chart = [
        {"axis": h["hazard"], "value": h["score"]}
        for h in included
    ]

    sev_counts: dict[str, int] = {"High": 0, "Medium": 0, "Low": 0, "Very low": 0}
    for h in included:
        if h["severity"] in sev_counts:
            sev_counts[h["severity"]] += 1
    severity_distribution_donut = [
        {"label": sev, "value": cnt}
        for sev, cnt in sev_counts.items()
        if cnt > 0
    ]

    hazard_table = [
        {"hazard": h["hazard"], "severity": h["severity"], "score": h["score"],
         "weight": h["weight"], "level": h["level"], "available": True}
        for h in sorted(included, key=lambda x: x["score"], reverse=True)
    ] + [
        {"hazard": h["hazard"], "severity": "No Data", "score": None,
         "weight": h["weight"], "level": None, "available": False}
        for h in excluded
    ]

    # ── Reasoning ──────────────────────────────────────────────────────────────
    top_names = [d["hazard"] for d in top_drivers[:3]]
    drivers_str = ", ".join(top_names[:-1]) + (" and " + top_names[-1] if len(top_names) > 1 else (top_names[0] if top_names else ""))
    excl_count = len(excluded)
    excl_note  = f" {excl_count} hazard(s) had no data and were excluded." if excl_count else ""

    reasoning = {
        "summary": (
            f"{district_name}, {state_name} shows {level} climate/environmental risk "
            f"based on ThinkHazard static district-level hazard data "
            f"(weighted score: {actual_score:.2f}).{excl_note}"
        ),
        "drivers": [
            f"Top hazards: {drivers_str} "
            f"(scores: {', '.join(str(d['score']) for d in top_drivers[:3])})."
        ] + (
            [f"Excluded (No Data): {', '.join(e['hazard'] for e in excluded[:4])}"]
            if excl_count else []
        ),
        "methodology_note": (
            "Static baseline environmental risk from ThinkHazard district-level hazard "
            "classifications. Severity (High=10, Medium=6, Low=3, Very low=1) is "
            "multiplied by hazard weight; No Data hazards excluded from both numerator "
            "and denominator. Does not include real-time climate monitoring."
        ),
    }

    return {
        "input_location": location,
        "resolved_location": {
            "district":   district_name,
            "state":      state_name,
            "confidence": resolution["confidence"],
            "method":     resolution["method"],
        },
        "climate_static_risk": {
            "score":        round(actual_score, 4),
            "actual_score": round(actual_score, 4),
            "gauge_score":  round(gauge_score, 4),
            "level":        level,
            "method":       "Weighted average of ThinkHazard district-level hazard scores",
            "source":       "thinkhzrd.csv",
        },
        "hazard_metrics":     included,
        "excluded_metrics":   excluded,
        "top_hazard_drivers": top_drivers,
        "visualization": {
            "overall_gauge": {
                "label":        "Climate / Environmental Risk",
                "actual_score": round(actual_score, 4),
                "gauge_score":  round(gauge_score, 4),
                "level":        level,
            },
            "hazard_cards":               hazard_cards,
            "hazard_bar_chart":           hazard_bar_chart,
            "hazard_radar_chart":         hazard_radar_chart,
            "severity_distribution_donut":severity_distribution_donut,
            "hazard_table":               hazard_table,
        },
        "reasoning": reasoning,
    }
