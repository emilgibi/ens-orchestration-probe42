import requests
import traceback
from app.core.config import get_settings
from app.core.security.jwt import create_jwt_token
from app.schemas.logger import logger
from app.core.utils.db_utils import get_dynamic_ens_data
from app.core.analysis.analysis_submodules.address_analysis import *


async def google_rating_screening(data, session):
    logger.info("Retrieving Google Rating Screening Data..")

    session_id = data["session_id"]
    ens_id = data["ens_id"]
    identifier = data["identifier"]

    incoming_columns = await get_dynamic_ens_data(
        "external_supplier_data",
        ["legal_name", "identifier_type", "entity_type", "address"],
        ens_id,
        session_id,
        session,
    )

    row = incoming_columns[0]

    params = {
        "name": row.get("legal_name", ""),
        "identifier": identifier,
        "address": row.get("address", ""),
        "entity_type": row.get("entity_type", ""),
        "identifier_type": row.get("identifier_type", ""),
    }

    try:
        jwt_token = create_jwt_token("orchestration", "analysis")
    except Exception as e:
        logger.error(f"JWT error: {e}")
        raise

    url = f"{get_settings().urls.orbis_engine}/api/v1/orbis/location/rating"

    headers = {
        "Authorization": f"Bearer {jwt_token.access_token}"
    }

    try:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code in (200, 201):
            logger.info("Google Rating Screening Completed")
            return {"module": "Google Rating screening", "status": "completed"}

        logger.error("Google Rating Screening Failed")
        return {"module": "Google Rating screening", "status": "passed"}

    except Exception as e:
        traceback.print_exc()
        logger.error(f"Google Rating Screening Exception: {e}")
        return {"module": "Google Rating screening", "status": "failed"}

async def google_photo_screening(data, session):
    logger.info("Retrieving Google Photo Screening Data..")

    session_id = data.get("session_id")
    ens_id = data.get("ens_id")
    identifier = data.get("identifier")

    try:
        rows = await get_dynamic_ens_data(
            "supplier_master_data",
            ["uploaded_address"],
            ens_id,
            session_id,
            session,
        )
        if not rows or not rows[0].get("uploaded_address"):
            logger.info("Address not uploaded. Finding in external_supplier_data")
            rows = await get_dynamic_ens_data(
                "external_supplier_data",
                ["address", "legal_name"],
                ens_id,
                session_id,
                session,
            )
            if not rows or not rows[0].get("address"):
                logger.info(
                    "No address found | session_id=%s ens_id=%s",
                    session_id, ens_id
                )
                return {"module": "Google Photo Validation", "status": "passed"}
            else:
                logger.info("Address not uploaded. Using Probe42 Address.Continuing")
                address = rows[0]["address"]
                name= rows[0]["legal_name"]
        else:
            logger.info("Address uploaded. Continuing")
            address = rows[0]["uploaded_address"]
            name =  rows[0]["legal_name"]
    except Exception as e:
        logger.error(f"Failed to fetch address: {e}")
        return {"module": "Google Photo screening", "status": "failed"}

    try:
        jwt_token = create_jwt_token("orchestration", "analysis")
    except Exception as e:
        logger.error(f"JWT generation failed: {e}")
        return {"module": "Google Photo screening", "status": "failed"}

    url = f"{get_settings().urls.orbis_engine}/api/v1/orbis/location/images"

    headers = {
        "Authorization": f"Bearer {jwt_token.access_token}"
    }

    params = {
        "orgName": name,
        "identifier": identifier,
        "address": address,
        "ensId": ens_id,
        "sessionId": session_id,
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30
        )

        logger.info(f"Google Photo Screening status code: {response.status_code}")

        try:
            response_data = response.json()
        except Exception:
            logger.error("Response is not valid JSON")
            logger.error(response.text)
            return {"module": "Google Photo screening", "status": "failed"}

        if response.status_code in (200, 201):
            return {
                "module": "Google Photo screening",
                "status": "completed",
                "data": response_data
            }

        return {
            "module": "Google Photo screening",
            "status": "passed",
            "data": response_data
        }

    except Exception as e:
        logger.error(f"Google Photo Screening exception: {e}")
        return {"module": "Google Photo screening", "status": "failed"}

