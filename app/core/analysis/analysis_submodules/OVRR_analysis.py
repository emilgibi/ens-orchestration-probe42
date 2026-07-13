from app.core.utils.db_utils import *
from app.schemas.logger import logger

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

RATING_TO_SCORE = {
    "Low":       10,   # Green
    "Medium":     7,   # Yellow
    "High":       5,   # Red
    "No Alerts": 10,   # Same as Low
    "INFO":      10,
    "":          10,
}


def _rating_score(rating: str) -> float:
    return RATING_TO_SCORE.get(rating, 10)


def _score_to_rating(score: float) -> str:
    if score >= 8:
        return "Low"
    elif score >= 5:
        return "Medium"
    else:
        return "High"


def _avg_score_for_codes(rows: list, kpi_codes: list) -> float:
    total = 0.0
    for code in kpi_codes:
        matched = next(
            (row for row in rows if row.get("kpi_code") == code),
            None
        )
        rating = matched.get("kpi_rating", "Low") if matched else "Low"
        score = _rating_score(rating)
        logger.info(f'            | code={code:<12} | rating={rating:<10} | score={score}')
        total += score
    avg = total / len(kpi_codes)
    if len(kpi_codes) > 1:
        logger.info(f'            | average score across {kpi_codes} = {avg:.3f}')
    return avg


def _weighted_section_score(rows: list, sub_section_map: dict) -> float:
    section_score = 0.0
    for label, (weight, kpi_codes) in sub_section_map.items():
        avg_score = _avg_score_for_codes(rows, kpi_codes)
        contribution = avg_score * weight
        section_score += contribution
        logger.info(
            f'         sub-section [{label}]'
            f' | avg_score={avg_score:.3f}'
            f' | weight={int(weight * 100)}%'
            f' | contribution={contribution:.3f}'
        )
    return section_score


# ---------------------------------------------------------------------------
# Main OVRR function
# ---------------------------------------------------------------------------

async def ovrr(data, session):

    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")

    kpi_area_module = "OVR"

    try:
        required_columns = ["kpi_area", "kpi_code", "kpi_rating", "kpi_flag"]

        logger.info("=" * 70)
        logger.info(f"  OVRR ANALYSIS STARTED")
        logger.info(f"  ens_id={ens_id_value} | session_id={session_id_value}")
        logger.info("=" * 70)

        # ------------------------------------------------------------------ ENTITY EXISTENCE
        logger.info("")
        logger.info("[ 1/5 ] ENTITY EXISTENCE  (section weight = 15%)")
        logger.info("-" * 50)
        logger.info("  Sub-sections:  ADD1A=70%  |  DOM1A=15%  |  B2B1A=15%")

        entity = await get_dynamic_ens_data(
            "entity_existance", required_columns, ens_id_value, session_id_value, session
        )
        logger.info(f"  Fetched {len(entity)} KPI row(s) from [entity_existance] table")

        entity_sub = {
            "address_validation":  (0.70, ["ADD1A"]),
            "domain_verification": (0.15, ["DOM1A"]),
            "b2b_verification":    (0.15, ["B2B1A"]),
        }
        entity_score = _weighted_section_score(entity, entity_sub)
        entity_rating = _score_to_rating(entity_score)

        logger.info(f"  >>> Entity Existence Section Score  = {entity_score:.3f}")
        logger.info(f"  >>> Entity Existence Section Rating = {entity_rating}")

        entity_overall = {
            "kpi_area": "theme_rating",
            "kpi_code": "entity_existence",
            "kpi_rating": entity_rating,
        }

        # ------------------------------------------------------------------ LEGAL & SANCTIONS
        logger.info("")
        logger.info("[ 2/5 ] LEGAL & SANCTIONS  (section weight = 25%  [base 20% + 5% from ESG])")
        logger.info("-" * 50)
        logger.info("  Sub-sections:  LEG1A=60%  |  LEG3A+LEG3B=40% (averaged)")

        legal = await get_dynamic_ens_data(
            "legal", required_columns, ens_id_value, session_id_value, session
        )
        logger.info(f"  Fetched {len(legal)} KPI row(s) from [legal] table")

        legal_sub = {
            "historic_legal_cases": (0.60, ["LEG1A"]),
            "sanctions":            (0.40, ["LEG3A", "LEG3B"]),
        }
        legal_score = _weighted_section_score(legal, legal_sub)
        legal_rating = _score_to_rating(legal_score)

        logger.info(f"  >>> Legal & Sanctions Section Score  = {legal_score:.3f}")
        logger.info(f"  >>> Legal & Sanctions Section Rating = {legal_rating}")

        legal_overall = {
            "kpi_area": "theme_rating",
            "kpi_code": "legal",
            "kpi_rating": legal_rating,
        }

        # ------------------------------------------------------------------ ADVERSE MEDIA
        logger.info("")
        logger.info("[ 3/5 ] ADVERSE MEDIA  (section weight = 10%)")
        logger.info("-" * 50)
        logger.info("  Sub-sections:  NWS1A=70%  |  NWS2A=30%")

        news = await get_dynamic_ens_data(
            "adverse_media", required_columns, ens_id_value, session_id_value, session
        )
        logger.info(f"  Fetched {len(news)} KPI row(s) from [adverse_media] table")

        am_sub = {
            "adverse_media_reports": (0.70, ["NWS1A"]),
            "google_reviews":        (0.30, ["NWS2A"]),
        }
        am_score = _weighted_section_score(news, am_sub)
        am_rating = _score_to_rating(am_score)

        logger.info(f"  >>> Adverse Media Section Score  = {am_score:.3f}")
        logger.info(f"  >>> Adverse Media Section Rating = {am_rating}")

        other_adverse_media_overall = {
            "kpi_area": "theme_rating",
            "kpi_code": "adverse_media",
            "kpi_rating": am_rating,
        }

        # ------------------------------------------------------------------ FINANCIAL
        logger.info("")
        logger.info("[ 4/5 ] FINANCIAL  (section weight = 40%  [base 35% + 5% from ESG])")
        logger.info("-" * 50)
        logger.info("  Sub-sections:  FSTB7A=10%  |  FSTB10A=10%  |  FSTB6A=20%")
        logger.info("                 FSTB1B+1C+1D+1E=55% (averaged)  |  FSTB14A=5%")
        logger.info("  Note: Contingent Liabilities excluded; its 5% added to Detailed Financial")

        fin = await get_dynamic_ens_data(
            "finance", required_columns, ens_id_value, session_id_value, session
        )
        logger.info(f"  Fetched {len(fin)} KPI row(s) from [finance] table")

        fin_sub = {
            "gst_filing":         (0.10, ["FSTB7A"]),
            "msme":               (0.10, ["FSTB10A"]),
            "credit_score":       (0.20, ["FSTB6A"]),
            "detailed_financial": (0.55, ["FSTB1B", "FSTB1C", "FSTB1D", "FSTB1E"]),
            "auditors_opinion":   (0.05, ["FSTB14A"]),
        }
        fin_score = _weighted_section_score(fin, fin_sub)
        fin_rating = _score_to_rating(fin_score)

        logger.info(f"  >>> Financial Section Score  = {fin_score:.3f}")
        logger.info(f"  >>> Financial Section Rating = {fin_rating}")

        financials_overall = {
            "kpi_area": "theme_rating",
            "kpi_code": "financials",
            "kpi_rating": fin_rating,
        }

        # ------------------------------------------------------------------ CYBER
        logger.info("")
        logger.info("[ 5/5 ] CYBER  (section weight = 10%)")
        logger.info("-" * 50)
        logger.info("  Sub-sections:  CYB1A=100%")
        logger.info("  Note: ESG excluded; its 10% split as Legal+5% and Financial+5%")

        cyb = await get_dynamic_ens_data(
            "cyber_esg", required_columns, ens_id_value, session_id_value, session
        )
        logger.info(f"  Fetched {len(cyb)} KPI row(s) from [cyber_esg] table")

        cyb_sub = {
            "cyber_score": (1.0, ["CYB1A"]),
        }
        cyb_score = _weighted_section_score(cyb, cyb_sub)
        cyb_rating = _score_to_rating(cyb_score)

        logger.info(f"  >>> Cyber Section Score  = {cyb_score:.3f}")
        logger.info(f"  >>> Cyber Section Rating = {cyb_rating}")

        cyb_overall = {
            "kpi_area": "theme_rating",
            "kpi_code": "cyber_esg",
            "kpi_rating": cyb_rating,
        }

        # ------------------------------------------------------------------ OVERALL SCORE
        section_weights = {
            "entity":    0.15,
            "legal":     0.25,
            "adverse":   0.10,
            "financial": 0.40,
            "cyber":     0.10,
        }
        section_scores = {
            "entity":    entity_score,
            "legal":     legal_score,
            "adverse":   am_score,
            "financial": fin_score,
            "cyber":     cyb_score,
        }

        overall_score = sum(
            section_scores[k] * section_weights[k] for k in section_scores
        )
        supplier_rating = _score_to_rating(overall_score)

        logger.info("")
        logger.info("=" * 70)
        logger.info("  OVERALL SCORE CALCULATION")
        logger.info("=" * 70)
        logger.info(f"  {'Section':<20} | {'Score':>7} | {'Weight':>7} | {'Contribution':>13}")
        logger.info(f"  {'-'*20}-+-{'-'*7}-+-{'-'*7}-+-{'-'*13}")
        for k in section_scores:
            contribution = section_scores[k] * section_weights[k]
            logger.info(
                f"  {k:<20} | {section_scores[k]:>7.3f} | {int(section_weights[k]*100):>6}% | {contribution:>13.3f}"
            )
        logger.info(f"  {'-'*20}-+-{'-'*7}-+-{'-'*7}-+-{'-'*13}")
        logger.info(f"  {'TOTAL':<20} | {'':>7} | {'100%':>7} | {overall_score:>13.3f}")
        logger.info("")
        logger.info(f"  FINAL OVERALL SCORE  = {overall_score:.3f}")
        logger.info(f"  FINAL SUPPLIER RATING = {supplier_rating}  (Green>=8 | Yellow>=5 | Red<5)")
        logger.info("=" * 70)

        supplier_overall = {
            "kpi_area": "overall_rating",
            "kpi_code": "supplier",
            "kpi_rating": supplier_rating,
        }

        ovr_kpis = [
            other_adverse_media_overall,
            financials_overall,
            entity_overall,
            legal_overall,
            cyb_overall,
            supplier_overall,
        ]

        insert_status = await upsert_kpi("ovar", ovr_kpis, ens_id_value, session_id_value, session)

        if insert_status["status"] == "success":
            logger.info(f"{kpi_area_module} Analysis... Completed Successfully")
            return {"ens_id": ens_id_value, "module": kpi_area_module, "status": "completed", "info": "analysed"}
        else:
            logger.error(insert_status)
            return {"ens_id": ens_id_value, "module": kpi_area_module, "status": "failure", "info": "database_saving_error"}

    except Exception as e:
        logger.error(f"Error in module: {kpi_area_module}, {str(e)}")
        return {"ens_id": ens_id_value, "module": kpi_area_module, "status": "failure", "info": str(e)}