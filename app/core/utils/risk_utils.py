"""
Shared risk scoring utilities.
"""

RISK_THRESHOLDS: list[tuple[float, str]] = [
    (7.0, "High"),
    (4.0, "Medium"),
    (0.0, "Low"),
]


def score_to_level(score: float) -> str:
    for threshold, level in RISK_THRESHOLDS:
        if score >= threshold:
            return level
    return "Low"


def to_gauge_score(score: float) -> float:
    return min(score, 10.0)
