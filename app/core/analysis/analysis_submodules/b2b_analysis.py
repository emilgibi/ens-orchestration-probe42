import json
from datetime import datetime
from app.core.utils.db_utils import *
from app.schemas.logger import logger

async def b2b_analysis(data, session):
    logger.info("Performing b2b Analysis...")

    kpi_area_module = "B2B"

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

        B2B1A = kpi_template.copy()

        B2B1A["kpi_code"] = "B2B1A"
        B2B1A["kpi_definition"] = "B2B Validation"


        # Data for Org-Level
        required_columns = ["b2b_validation", "legal_name"]
        retrieved_data = await get_dynamic_ens_data("external_supplier_data", required_columns, ens_id_value,
                                                    session_id_value, session)
        retrieved_data = retrieved_data[0]

        b2b_info = retrieved_data.get("b2b_validation", None)
        legal_name = retrieved_data.get("legal_name", None)

        if b2b_info is None:
            logger.info(f"{kpi_area_module} Analysis... Completed With No Data")
            return {"ens_id": ens_id_value, "module": kpi_area_module, "status": "completed", "info": "no_data"}

        if not b2b_info.get('result', {}):
            logger.info(f"{kpi_area_module} Analysis... Completed With No Data")
            return {"ens_id": ens_id_value, "module": kpi_area_module, "status": "completed", "info": "no_data"}
        company=b2b_info.get('result',{})
        # para=generate_seller_paragraph(company)
        details = []

        for key, value in company.items():
            obj = {
                'factor': key.replace("_", " ").title(),
                'value': value,
            }
            details.append(obj)
        B2B1A["kpi_rating"] = "Low"
        B2B1A["kpi_flag"] = True
        B2B1A['kpi_value'] = json.dumps(company)
        B2B1A['kpi_details'] = json.dumps(details)
        b2b_kpis = [B2B1A]

        insert_status = await upsert_kpi("entity_existance", b2b_kpis, ens_id_value, session_id_value, session)
        logger.info(f"{kpi_area_module} Analysis... Completed With Data")

    except:
        logger.error(f"{kpi_area_module}Analysis.. entered exception")
    return []

def generate_seller_paragraph(seller):
    # If no seller found
    if not seller:
        return (
            "No listing was identified for the entity on IndiaMART based on the "
            "provided details."
        )

    company = seller.get("company_name", "The entity")
    city = seller.get("city")
    state = seller.get("state")
    address = seller.get("address")
    gst = seller.get("gstNumber")
    member = seller.get("member_since")
    url = seller.get("url")

    location = ", ".join(filter(None, [city, state]))

    paragraph = f"{company} is listed on IndiaMART"

    if location:
        paragraph += f" and is based in {location}"

    if address:
        paragraph += f", with an address at {address}"

    paragraph += "."

    if gst:
        paragraph += f" The entity holds a GST registration ({gst})."

    if member:
        paragraph += f" It has been associated with the platform since {member}."

    if url:
        paragraph += f" Profile reference: {url}."

    return paragraph
