import json
from datetime import datetime
from app.core.utils.db_utils import *
from app.schemas.logger import logger
from rapidfuzz import fuzz
import traceback

async def cyber_analysis(data, session):
    logger.info("Performing CYB Analysis...")

    kpi_area_module = "CYB"

    if not isinstance(data, dict):
        logger.error("Invalid input data received in domain_analysis")
        return []
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

        CYB1A = kpi_template.copy()
        CYB1A["kpi_code"] = "CYB1A"
        CYB1A["kpi_definition"] = "Cyber Risk Validation"

        required_columns = ["cyber_risk"]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session
        )

        if not retrieved_data:
            logger.info("CYB Analysis... No data found")
            return []

        retrieved_data = retrieved_data[0]
        cyber_info = retrieved_data.get("cyber_risk")
        print("----cyber info",cyber_info, type(cyber_info))

        if not isinstance(cyber_info, dict):
            logger.info("CYB Analysis... cyber_validation missing or invalid")
            return []
        print(cyber_info.get("cyber_risk_level", "N/A"))
        if cyber_info.get("cyber_risk_level", "N/A"):
            print("check 1")
            result = format_output_as_json(cyber_info)
            cyber_info.get("cyber_risk_level", "N/A")
            CYB1A["kpi_flag"] = True
            print("check 2")
            CYB1A["kpi_rating"] = cyber_info.get("cyber_risk_level", "N/A")
            CYB1A["kpi_value"] = json.dumps(result)
            CYB1A["kpi_details"] = json.dumps(result)
            print("check 3")

            await upsert_kpi(
                "cyber_esg",
                [CYB1A],
                ens_id_value,
                session_id_value,
                session
            )
            print("check 4")

            logger.info("CYB Analysis... Completed With Data")
            return []
        logger.info("CYB Analysis... Completed With No Data- No rating")
        return []

    except Exception as e:
        traceback.print_exc()
        logger.error(f"CYB Analysis failed: {str(e)}", exc_info=True)
        return []

def format_output_as_json(result):
    return [
        {"factor": "Resolved IP",              "value": result.get("resolved_ip", "N/A")},
        # {"factor": "Cyber Risk Score",         "value": f"{result.get('cyber_risk_score', 0)} / 100"},
        {"factor": "Botnet Threat",            "value": "YES" if result.get("botnet") else "NO"},
        {"factor": "Malware Hosting Threat",   "value": "YES" if result.get("malware_hosting") else "NO"},
        {"factor": "Command & Control Threat", "value": "YES" if result.get("command_and_control") else "NO"},
        {"factor": "Spam Server Threat",       "value": "YES" if result.get("spam_server") else "NO"},
        {"factor": "Overall Compromised",      "value": "YES" if result.get("compromised") else "NO"},
        # {"factor": "Evidence Detected",        "value": ", ".join(result.get("evidence", [])) or "None"},
        {"factor": "Vendor / 3rd-Party Risk",  "value": result.get("vendor_cyber_risk", "N/A")},
        {"factor": "Fraud / Compliance Flag",  "value": result.get("fraud_compliance_red_flag", "N/A")},
    ]