"""
Political Static Risk Service
==============================
District-level ACLED political/security risk scoring from ACLED_updated.xlsx.
No database, no LLM — pure file-based, deterministic.
"""

import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.core.utils.text_utils import resolve_from_list
from app.core.utils.risk_utils import score_to_level, to_gauge_score

logger = logging.getLogger(__name__)

_EXCEL_PATH = Path(__file__).resolve().parents[2] / "data" / "ACLED_updated.xlsx"

_NON_EVENT_COLS: frozenset[str] = frozenset({
    "Row Labels", "Grand Total", "Score", "Relative Score",
    "Terrorism", "Political", "Crime",
    "Terrorism Relative Score", "Political Relative Score", "Crime Relative Score",
})

_REQUIRED_COLS: frozenset[str] = frozenset({
    "Row Labels", "Grand Total", "Score", "Relative Score",
    "Terrorism", "Political", "Crime",
    "Terrorism Relative Score", "Political Relative Score", "Crime Relative Score",
})


@lru_cache(maxsize=1)
def _load_data() -> tuple[pd.DataFrame, pd.Series]:
    if not _EXCEL_PATH.exists():
        raise FileNotFoundError(
            f"ACLED data file not found: {_EXCEL_PATH}. "
            "Place ACLED_updated.xlsx in data/."
        )

    logger.info("Loading ACLED political risk data from %s", _EXCEL_PATH.name)
    df = pd.read_excel(_EXCEL_PATH, header=1)
    df.columns = [str(c).strip() for c in df.columns]

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"ACLED file is missing required columns: {sorted(missing)}. "
            f"Available: {sorted(df.columns.tolist())}"
        )

    df["Row Labels"] = df["Row Labels"].astype(str).str.strip()
    gt_mask = df["Row Labels"].str.lower() == "grand total"
    grand_total_df = df[gt_mask]
    districts = df[~gt_mask].copy()

    _invalid = {"nan", "", "(blank)", "none"}
    districts = districts[
        districts["Row Labels"].notna()
        & ~districts["Row Labels"].str.lower().isin(_invalid)
    ]

    num_cols = [c for c in districts.columns if c != "Row Labels"]
    for col in num_cols:
        districts[col] = pd.to_numeric(districts[col], errors="coerce").fillna(0)

    grand_total = (
        grand_total_df.iloc[0] if not grand_total_df.empty else pd.Series(dtype=float)
    )

    logger.info("ACLED loaded: %d districts", len(districts))
    return districts, grand_total


def get_political_static_risk(location: str) -> dict:
    """
    Return the full political static risk payload for a given location string.

    Raises
    ------
    FileNotFoundError  — ACLED file missing
    ValueError         — location not found or required columns absent
    """
    districts, _ = _load_data()
    labels: list[str] = districts["Row Labels"].tolist()

    resolution = resolve_from_list(location, labels)
    if resolution["matched"] is None:
        sample = ", ".join(sorted(labels)[:8])
        raise ValueError(
            f"Location '{location}' not found in ACLED dataset. "
            f"Sample districts: {sample}…"
        )

    district_name: str = resolution["matched"]
    row = districts[districts["Row Labels"] == district_name].iloc[0]

    relative_score = float(row.get("Relative Score", 0) or 0)
    terrorism_rs   = float(row.get("Terrorism Relative Score", 0) or 0)
    political_rs   = float(row.get("Political Relative Score", 0) or 0)
    crime_rs       = float(row.get("Crime Relative Score", 0) or 0)
    raw_score      = float(row.get("Score", 0) or 0)
    terrorism_raw  = float(row.get("Terrorism", 0) or 0)
    political_raw  = float(row.get("Political", 0) or 0)
    crime_raw      = float(row.get("Crime", 0) or 0)
    total_events   = int(row.get("Grand Total", 0) or 0)

    overall_level   = score_to_level(relative_score)
    terrorism_level = score_to_level(terrorism_rs)
    political_level = score_to_level(political_rs)
    crime_level     = score_to_level(crime_rs)
    gauge_score     = to_gauge_score(relative_score)

    event_cols = [c for c in districts.columns if c not in _NON_EVENT_COLS]
    event_counts = {col: int(row.get(col, 0) or 0) for col in event_cols}
    top_drivers = sorted(
        [{"event_type": k, "count": v} for k, v in event_counts.items() if v > 0],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    # ── Visualization ──────────────────────────────────────────────────────────
    risk_cards = [
        {"label": "Overall Security Risk",  "score": round(relative_score, 4), "level": overall_level},
        {"label": "Terrorism Risk",          "score": round(terrorism_rs, 4),   "level": terrorism_level},
        {"label": "Political/Unrest Risk",   "score": round(political_rs, 4),   "level": political_level},
        {"label": "Crime/Security Risk",     "score": round(crime_rs, 4),       "level": crime_level},
    ]

    top_event_bar_chart = [
        {"event_type": d["event_type"], "count": d["count"]}
        for d in top_drivers
    ]

    sub_total = terrorism_raw + political_raw + crime_raw
    risk_composition_donut = [
        {"label": "Terrorism",       "value": round(terrorism_raw / sub_total * 100, 1) if sub_total else 0},
        {"label": "Political Unrest","value": round(political_raw / sub_total * 100, 1) if sub_total else 0},
        {"label": "Crime/Security",  "value": round(crime_raw     / sub_total * 100, 1) if sub_total else 0},
    ]

    event_table = [
        {
            "event_type": d["event_type"],
            "count": d["count"],
            "percentage": round(d["count"] / total_events * 100, 1) if total_events else 0,
        }
        for d in top_drivers
    ]

    driver_parts = [f"{d['event_type']} ({d['count']} events)" for d in top_drivers[:2]]
    driver_str = " and ".join(driver_parts) + "." if driver_parts else "No significant events recorded."
    reasoning = (
        f"{district_name} shows {overall_level} overall political/security risk "
        f"based on ACLED static district-level historical event counts "
        f"(Relative Score: {relative_score:.2f}). "
        f"Primary event drivers: {driver_str} "
        f"Terrorism relative score is {terrorism_rs:.2f} ({terrorism_level}), "
        f"political/unrest score is {political_rs:.2f} ({political_level}), "
        f"and crime/security score is {crime_rs:.2f} ({crime_level}). "
        f"This is a static assessment derived from historical ACLED incident data."
    )

    return {
        "input_location": location,
        "resolved_location": {
            "district":   district_name,
            "confidence": resolution["confidence"],
            "method":     resolution["method"],
        },
        "political_static_risk": {
            "score":        round(relative_score, 4),
            "level":        overall_level,
            "actual_score": round(relative_score, 4),
            "gauge_score":  round(gauge_score, 4),
            "method":       "ACLED static Relative Score",
        },
        "sub_risks": {
            "terrorism":       {"score": round(terrorism_rs, 4), "level": terrorism_level},
            "political_unrest":{"score": round(political_rs, 4), "level": political_level},
            "crime_security":  {"score": round(crime_rs, 4),     "level": crime_level},
        },
        "score_breakdown": {
            "total_events":  total_events,
            "raw_score":     int(raw_score),
            "relative_score":round(relative_score, 4),
            "terrorism_raw": int(terrorism_raw),
            "political_raw": int(political_raw),
            "crime_raw":     int(crime_raw),
        },
        "top_event_drivers": top_drivers,
        "visualization": {
            "overall_gauge": {
                "label":        "Political / Security Risk",
                "actual_score": round(relative_score, 4),
                "gauge_score":  round(gauge_score, 4),
                "level":        overall_level,
            },
            "risk_cards":            risk_cards,
            "top_event_bar_chart":   top_event_bar_chart,
            "risk_composition_donut":risk_composition_donut,
            "event_table":           event_table,
        },
        "reasoning": reasoning,
    }
