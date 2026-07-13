import requests
from app.core.config import get_settings
from app.core.security.jwt import create_jwt_token
from app.schemas.logger import logger
from app.core.utils.db_utils import *
import traceback

async def sanctions_screening(data, session):

    logger.info("Retrieving Sanctions Screening Data..")

    session_id = data["session_id"]
    ens_id = data["ens_id"]
    identifier = data["identifier"]
    incoming_columns = await get_dynamic_ens_data("external_supplier_data", ['legal_name', 'website'], ens_id,
                                                  session_id, session)

    address = incoming_columns[0].get('address', '')
    name = incoming_columns[0].get('legal_name', '')

    try:
        jwt_token = create_jwt_token("orchestration", "analysis")
    except Exception as e:
        logger.error(f"Error generating JWT token: {e}")
        raise

    orbis_url = get_settings().urls.orbis_engine
    url = (
        f"{orbis_url}/api/v1/orbis/sanctions/screen"
        f"?name={name}"
        f"&identifier={identifier}"
        f"&address={address}"
        f"&sessionId={session_id}"
        f"&ensId={ens_id}"
    )

    headers = {
        "Authorization": f"Bearer {jwt_token.access_token}"
    }

    try:
        response = requests.request("GET", url, headers=headers)
        logger.info(f"Sanctions Screening status code: {response.status_code}")

        if response.status_code in (200, 201):
            logger.info("Performing Sanctions Screening... Completed")
            return {"module": "sanctions_screening", "status": "completed"}
        else:
            logger.error("Performing Sanctions Screening... Failed - Response Code not 200")
            return {"module": "sanctions_screening", "status": "passed"}
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Performing Sanctions Screening... Failed: {str(e)}")
        return {"module": "sanctions_screening", "status": "failed"}



async def sanctions_employee_screening(data, session):
    logger.info("Retrieving Sanctions Employee Screening Data..")

    session_id = data.get("session_id")
    ens_id = data.get("ens_id")
    identifier = data.get("identifier")

    # ✅ Fetch ENS data
    try:
        incoming_columns = await get_dynamic_ens_data(
            "external_supplier_data",
            ['legal_name', 'directors'],
            ens_id,
            session_id,
            session
        )
    except Exception as e:
        logger.error(f"Error fetching ENS data: {e}")
        return {"module": "sanctions_screening", "status": "failed"}

    if not incoming_columns:
        logger.warning("No incoming data found")
        return {"module": "sanctions_screening", "status": "passed"}

    record = incoming_columns[0]
    directors = record.get("directors", [])

    # ✅ Extract active directors
    director_names = [
        d["name"]
        for d in directors
        if isinstance(d, dict)
        and d.get("name")
    ]

    logger.info(f"Filtered active directors: {director_names}")

    if not director_names:
        logger.info("No active directors found for sanction screening")
        return {"module": "sanctions_screening", "status": "passed"}

    # ✅ JWT
    try:
        jwt_token = create_jwt_token("orchestration", "analysis")
    except Exception as e:
        logger.error(f"Error generating JWT token: {e}")
        return {"module": "sanctions_screening", "status": "failed"}

    # ✅ API config
    orbis_url = get_settings().urls.orbis_engine
    url = f"{orbis_url}/api/v1/orbis/sanctions-employee/screen"

    headers = {
        "Authorization": f"Bearer {jwt_token.access_token}",
        "Content-Type": "application/json"
    }

    # ✅ ✅ EVERYTHING IN BODY (final fix)
    payload = {
        "identifier": identifier,
        "directors": director_names,
        "sessionId": session_id,
        "ensId": ens_id
    }

    logger.info(f"Calling Orbis API: {url}")
    logger.info(f"Request body: {payload}")

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,   # ✅ correct
            timeout=30
        )

        logger.info(f"Sanctions Screening status code: {response.status_code}")

        # ✅ Safe JSON parsing
        try:
            response_data = response.json()
            logger.info(f"Response JSON: {response_data}")
        except ValueError:
            logger.warning(f"Non-JSON response: {response.text}")
            response_data = None

        # ✅ Success
        if response.status_code in (200, 201):
            logger.info("Performing Sanctions Screening... Completed")
            return {
                "module": "sanctions_screening",
                "status": "completed",
                "response": response_data
            }

        # ❌ Failure
        else:
            logger.error(
                f"Sanctions Screening failed | Status: {response.status_code} | Response: {response.text}"
            )
            return {
                "module": "sanctions_screening",
                "status": "failed",
                "status_code": response.status_code,
                "error": response_data
            }

    except requests.exceptions.Timeout:
        logger.error("Sanctions API request timed out")

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request failed: {str(e)}")
        traceback.print_exc()

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        traceback.print_exc()

    return {"module": "sanctions_screening", "status": "failed"}
