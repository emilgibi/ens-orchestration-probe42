import requests
from app.core.config import get_settings
from app.core.security.jwt import create_jwt_token
from app.schemas.logger import logger
from app.core.utils.db_utils import *
import traceback
from app.core.analysis.analysis_submodules.FSTB_analysis import *
import html
from datetime import date as dt_date

async def msme_screening(data, session):

    logger.info("Retrieving MSME Screening Data..")

    session_id = data["session_id"]
    ens_id = data["ens_id"]
    identifier = data["identifier"]

    incoming_columns = await get_dynamic_ens_data(
        "external_supplier_data",
        ["legal_name", "website", "pan", "incorporation_date"],
        ens_id,
        session_id,
        session,
    )

    rows = await get_dynamic_ens_data(
        "supplier_master_data",
        ["uploaded_client_msme_status"],
        ens_id,
        session_id,
        session,
    )

    record = incoming_columns[0] if incoming_columns else {}
    client_msme_status = rows[0].get("uploaded_client_msme_status") or 'Not Provided'
    data['client_msme_status'] = client_msme_status

    # ─────────────────────────────────────
    # Normalize inputs
    # ─────────────────────────────────────
    name = html.unescape(record.get("legal_name", "")).strip().upper()
    pan = record.get("pan", "")

    inc_date = record.get("incorporation_date")
    if isinstance(inc_date, dt_date):
        date_str = inc_date.strftime("%d/%m/%Y")
    else:
        date_str = ""

    logger.info(f"MSME input: NAME={name}, PAN={pan}, DATE={date_str}")

    try:
        jwt_token = create_jwt_token("orchestration", "analysis")
    except Exception as e:
        logger.error(f"Error generating JWT token: {e}")
        raise

    orbis_url = get_settings().urls.orbis_engine
    url = f"{orbis_url}/api/v1/orbis/msme"

    headers = {
        "Authorization": f"Bearer {jwt_token.access_token}"
    }

    # ✅ Always use query params dict
    params = {
        "name": name,
        "identifier": identifier,
        "pan": pan,
        "date": date_str,
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        logger.info(f"MSME Screening status code: {response.status_code}")
        response_json = response.json()
        logger.debug(f"MSME response: {response_json}")

        if response.status_code in (200, 201):
            logger.info("Performing MSME Screening... Completed")
            await msme_analysis(data, response_json, session)
            return {"module": "msme_screening", "status": "completed"}

        else:
            logger.warning(
                f"MSME Screening skipped. Status={response.status_code}, Response={response_json}"
            )
            return {"module": "msme_screening", "status": "passed"}

    except Exception as e:
        traceback.print_exc()
        logger.error(f"Performing MSME Screening... Failed: {str(e)}", exc_info=True)
        return {"module": "msme_screening", "status": "failed"}
