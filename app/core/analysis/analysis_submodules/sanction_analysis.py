import json
from datetime import datetime
from app.core.utils.db_utils import *
from app.schemas.logger import logger
import traceback


async def sanctions_analysis(data, session):
    logger.info("Performing Legal Analysis...")

    kpi_area_module = "LEG"

    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")

    try:
        # ---------------- KPI TEMPLATE ----------------
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "",
            "kpi_details": "",
        }

        LEG3A = kpi_template.copy()
        LEG3A["kpi_code"] = "LEG3A"
        LEG3A["kpi_definition"] = "Sanctions"

        # ---------------- FETCH DATA ----------------
        required_columns = ["sanctions"]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session
        )

        if not retrieved_data:
            logger.info("No row found in the database")
            return []

        retrieved_row = retrieved_data[0]
        sanctions_history = retrieved_row.get("sanctions")

        # ---------------- NO DATA CASE ----------------
        if not sanctions_history:
            logger.info(f"{kpi_area_module} Analysis completed with no data")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "completed",
                "info": "no_data"
            }

        # Ensure proper structure
        if not isinstance(sanctions_history, dict):
            logger.warning("Sanctions data is not in expected dictionary format")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "completed",
                "info": "invalid_data"
            }

        LEG3A["kpi_flag"] = True
        kpi_rating='High'

        LEG3A["kpi_rating"] = kpi_rating
        LEG3A["kpi_value"] = json.dumps(sanctions_history)
        LEG3A["kpi_details"] = json.dumps(sanctions_history)

        # ---------------- SAVE KPI ----------------
        legal_kpis = [LEG3A]

        insert_status = await upsert_kpi(
            "legal",
            legal_kpis,
            ens_id_value,
            session_id_value,
            session
        )

        if insert_status.get("status") == "success":
            logger.info(f"{kpi_area_module} Analysis completed successfully")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "completed",
                "info": "analysed"
            }
        else:
            logger.error("Database saving error")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "database_saving_error"
            }

    except Exception as e:
        logger.error(f"Error in module {kpi_area_module}: {str(e)}")
        traceback.print_exc()
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": str(e)
        }

async def sanctions_employee_analysis(data, session):
    logger.info("Performing Sanction Employee Analysis...")

    kpi_area_module = "LEG"

    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")

    try:
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "",
            "kpi_details": "",
        }

        LEG3B = kpi_template.copy()
        LEG3B["kpi_code"] = "LEG3B"
        LEG3B["kpi_definition"] = "Sanctions - Key Management Personnel (KMP)"

        # ───────────────── Fetch DB data ─────────────────
        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            ["sanctions_employee"],
            ens_id_value,
            session_id_value,
            session
        )

        if not retrieved_data:
            logger.info("No row found in the database")
            return []

        sanctions_history = retrieved_data[0].get("sanctions_employee")
        logger.info(f"sanction--------> {sanctions_history}")

        if not sanctions_history:
            logger.info("LEG Analysis SAnction employee completed with no employee sanctions data")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "completed",
                "info": "no_data"
            }

        # ✅ Handle JSON parsing
        try:
            san_data = json.loads(sanctions_history)
        except Exception:
            san_data = sanctions_history  # already JSON

        if not isinstance(san_data, list):
            logger.error("sanctions_employee is not a list")
            return []

        # ───────────────── Analysis ─────────────────
        LEG3B["kpi_flag"] = False
        LEG3B["kpi_rating"] = 'Low'
        filtered_results=[]
        for entry in san_data:

            if not entry.get("matched", False):
                continue

            LEG3B["kpi_flag"] = True
            LEG3B["kpi_rating"]='High'

            datasets = ", ".join(entry.get("datasets", [])) if entry.get("datasets") else ""
            # urls = ", ".join(entry.get("urls", [])) if entry.get("urls") else ""
            topics = ", ".join(entry.get("topics", [])) if entry.get("topics") else ""

            filtered_results.append({
                "director": entry.get("director"),
                "matchName": entry.get("matchName"),
                "datasets": datasets,
                "urls": entry.get("urls", []),
                "last_seen": entry.get("last_seen"),
                "topics": topics
            })

        # ✅ ✅ DIRECTLY STORE sanctions_employee DATA
        LEG3B["kpi_value"] = json.dumps(filtered_results)
        LEG3B["kpi_details"] = json.dumps(filtered_results)

        # ───────────────── Save KPI ─────────────────
        insert_status = await upsert_kpi(
            "legal",
            [LEG3B],
            ens_id_value,
            session_id_value,
            session
        )

        if insert_status.get("status") == "success":
            logger.info("LEG Sanction Employee Analysis completed successfully")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "completed",
                "info": "analysed"
            }

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "database_saving_error"
        }

    except Exception as e:
        logger.error(f"Error in module {kpi_area_module}: {str(e)}")
        traceback.print_exc()
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": str(e)
        }