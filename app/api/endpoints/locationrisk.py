"""
Climate Static Risk Router
GET /location-risk/climate-static?location=<district>
"""

import logging
from fastapi import APIRouter, HTTPException, Query, status
from app.core.analysis.location_risk_submodules.climate_static_risk_service import get_climate_static_risk
from app.core.analysis.location_risk_submodules.political_static_risk_service import get_political_static_risk
from app.core.analysis.location_risk_submodules.infrastructure_static_risk_service import get_infrastructure_static_risk

logger = logging.getLogger(__name__)


from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api import deps
from app.models import User

router = APIRouter()



@router.get(
    "/climate-static",
    summary="Climate static risk assessment (ThinkHazard district data)",
    description=(
        "Returns a static climate/environmental hazard risk assessment for an Indian district "
        "using pre-computed ThinkHazard data from `thinkhzrd.csv`.\n\n"
        "**Hazards**: River flood · Urban flood · Coastal flood · Earthquake · Landslide "
        "· Tsunami · Volcano · Cyclone · Water scarcity · Extreme heat · Wildfire\n\n"
        "**Scoring**: Severity→score (High=10, Medium=6, Low=3, Very low=1), "
        "weighted average across available hazards. "
        "0–3.9=Low, 4–6.9=Medium, 7+=High\n\n"
        "**Resolution**: exact → prefix → substring → fuzzy match on district name."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_climate_static(
    location: str = Query(
        None,
        description="District or city name. Examples: `Pune`, `Balasore`, `Mumbai`.",
    ),
) -> dict:
    if not location or not location.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="location query parameter is required and must not be empty",
        )

    location = location.strip()
    logger.info("GET /climate-static  location='%s'", location)

    try:
        result = get_climate_static_risk(location)
        logger.info(
            "GET /climate-static  location='%s' → district='%s'  level='%s'  score=%.4f",
            location,
            result["resolved_location"]["district"],
            result["climate_static_risk"]["level"],
            result["climate_static_risk"]["score"],
        )
        return result

    except FileNotFoundError as exc:
        logger.error("ThinkHazard CSV missing: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    except ValueError as exc:
        msg = str(exc)
        logger.warning("GET /climate-static  location='%s': %s", location, msg)
        if "could not be resolved" in msg or "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg) from exc

    except Exception as exc:
        logger.exception("GET /climate-static failed for location='%s': %s", location, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Climate static risk analysis failed: {exc}",
        ) from exc


@router.get(
    "/infrastructure-static",
    summary="Infrastructure static risk assessment (derived from climate + political data)",
    description=(
        "Returns a derived infrastructure disruption risk score for an Indian district.\n\n"
        "**Formula**: `0.6 × climate_disruption + 0.4 × political_disruption`\n\n"
        "**Climate component** uses infra-relevant hazard weights: "
        "River flood (18), Urban flood (15), Coastal flood (10), Cyclone (18), "
        "Landslide (12), Earthquake (10), Extreme heat (8), Water scarcity (6), Wildfire (3).\n\n"
        "**Political component** = ACLED Relative Score.\n\n"
        "**Note**: This score reflects potential disruption to infrastructure from "
        "environmental and political events — not direct infrastructure quality data.\n\n"
        "0–3.9=Low, 4–6.9=Medium, 7+=High"
    ),
    status_code=status.HTTP_200_OK,
)
async def get_infrastructure_static(
    location: str = Query(
        None,
        description="District or city name. Examples: `Pune`, `Srinagar`, `Mumbai`.",
    ),
) -> dict:
    if not location or not location.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="location query parameter is required and must not be empty",
        )

    location = location.strip()
    logger.info("GET /infrastructure-static  location='%s'", location)

    try:
        result = get_infrastructure_static_risk(location)
        logger.info(
            "GET /infrastructure-static  location='%s' → district='%s'  level='%s'  score=%.4f",
            location,
            result["resolved_location"]["district"],
            result["infrastructure_static_risk"]["level"],
            result["infrastructure_static_risk"]["score"],
        )
        return result

    except FileNotFoundError as exc:
        logger.error("Data file missing: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    except ValueError as exc:
        msg = str(exc)
        logger.warning("GET /infrastructure-static  location='%s': %s", location, msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc

    except Exception as exc:
        logger.exception("GET /infrastructure-static failed for location='%s': %s", location, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Infrastructure static risk analysis failed: {exc}",
        ) from exc


@router.get(
    "/political-static",
    summary="Political static risk assessment (ACLED district data)",
    description=(
        "Returns a static political/security risk assessment for an Indian district "
        "using pre-computed ACLED historical event data from `ACLED_updated.xlsx`.\n\n"
        "**Sub-risks**: Terrorism · Political Unrest · Crime/Security\n\n"
        "**Scoring**: ACLED Relative Score (district share × 364). "
        "0–3.9=Low, 4–6.9=Medium, 7+=High\n\n"
        "**Resolution**: exact → fuzzy → substring match on district name."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_political_static(
    location: str = Query(
        None,
        description="District or city name. Examples: `Srinagar`, `Pune`, `Imphal West`.",
    ),
) -> dict:
    if not location or not location.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="location query parameter is required and must not be empty",
        )

    location = location.strip()
    logger.info("GET /political-static  location='%s'", location)

    try:
        result = get_political_static_risk(location)
        logger.info(
            "GET /political-static  location='%s' → district='%s'  level='%s'  score=%.4f",
            location,
            result["resolved_location"]["district"],
            result["political_static_risk"]["level"],
            result["political_static_risk"]["score"],
        )
        return result

    except FileNotFoundError as exc:
        logger.error("ACLED file missing: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    except ValueError as exc:
        msg = str(exc)
        logger.warning("GET /political-static  location='%s': %s", location, msg)
        if "not found" in msg.lower() or "sample districts" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg) from exc

    except Exception as exc:
        logger.exception("GET /political-static failed for location='%s': %s", location, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Political static risk analysis failed: {exc}",
        ) from exc
