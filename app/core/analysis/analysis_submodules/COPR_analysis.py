import json
import traceback

from app.core.utils.db_utils import get_dynamic_ens_data
from app.core.utils.db_utils import *
import re
from app.schemas.logger import logger
import locale

try:
    locale.setlocale(locale.LC_ALL, 'en_IN.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, '')

async def company_profile(data, session):
    try:
        logger.info("Performing Company Profile...")

        ens_id = data.get("ens_id")
        session_id = data.get("session_id")
        required_columns = ["legal_name", "state", "city", "address", "website", "e_filing_status", "incorporation_date", "pan",
                            "classification", "alias", "number_of_employees", "email","phone",
                            "shareholdings", "subsidiary","directors", "financial_pnl", "identifier", "entity_type", "identifier_type"]

        retrieved_data = await get_dynamic_ens_data("external_supplier_data", required_columns, ens_id,
                                                    session_id, session)
        retrieved_data = retrieved_data[0]
        identifier=retrieved_data.get("identifier")
        identifier_type=retrieved_data.get("identifier_type")
        entity_type=retrieved_data.get("entity_type")
        logger.info("Processing retrieved company data...")

        supplier_master_data = await get_dynamic_ens_data("supplier_master_data",[ "external_vendor_id", "uploaded_name"],ens_id, session_id, session)
        external_vendor_id = supplier_master_data[0].get("external_vendor_id") if supplier_master_data else None
        uploaded_name = supplier_master_data[0].get("uploaded_name") if supplier_master_data else None
        def format_alias(items):
            if isinstance(items, list):
                items = list({i for i in items if i is not None})
                items = list(set(items))[:7]
                return "\n\n".join(items)
            return items
        def format_shareholders(shareholders):
            if not isinstance(shareholders, list) or not shareholders:
                shareholders_num = 0
                return None
            # Sort safely (missing percentages treated as 0)
            shareholders_num=len(shareholders)
            sorted_shareholders = sorted(
                shareholders,
                key=lambda x: x.get("shareholding_percentage") or 0,
                reverse=True
            )
            total_count = len(sorted_shareholders)
            top_seven = sorted_shareholders[:7]
            formatted_list = []

            for sh in top_seven:
                name = sh.get("name", "Unknown")
                percentage = sh.get("shareholding_percentage")
                if percentage is not None:
                    formatted_list.append(f"{name} ({percentage}%)")
                else:
                    formatted_list.append(name)
            result = "\n".join(formatted_list)
            if total_count > 7:
                result += f"\n+ {total_count - 7} more"
            return result
        def format_subsidiary(subsidiaries):
            if not isinstance(subsidiaries, list) or not subsidiaries:
                subsidiary_num = 0
                return None

            # Sort by share_holding_percentage (missing treated as 0)
            subsidiary_num= len(subsidiaries)
            sorted_subsidiaries = sorted(
                subsidiaries,
                key=lambda x: x.get("share_holding_percentage") or 0,
                reverse=True
            )

            total_count = len(sorted_subsidiaries)
            top_seven = sorted_subsidiaries[:7]

            formatted_list = []

            for sub in top_seven:
                name = sub.get("legal_name", "Unknown")
                percentage = sub.get("share_holding_percentage")

                if percentage is not None:
                    formatted_list.append(f"{name} ({percentage}%)")
                else:
                    formatted_list.append(name)

            result = "\n".join(formatted_list)

            if total_count > 7:
                result += f"\n+ {total_count - 7} more"

            return result
        def format_executives(executives):
            if not isinstance(executives, list) or not executives:
                return None

            total_count = len(executives)
            top_seven = executives[:7]
            formatted_list = []
            result=''
            for sh in top_seven:
                name = sh.get("name", "")
                if name:
                    designation = sh.get("designation","")
                    if designation:
                        formatted_list.append(f"{name} ({designation})")
                    else:
                        formatted_list.append(name)
                    result = "\n".join(formatted_list)
            if total_count > 7:
                result += f"\n+ {total_count - 7} more"
            return result
        def format_revenue(revenue_data):
            if isinstance(revenue_data, dict) and revenue_data:
                revenue = revenue_data.get("net_revenue")
                latest_dict = max(revenue, key=lambda x: int(x["year"]))
                latest_revenue = latest_dict.get('value',0)
                if latest_revenue is not None:
                    formatted_value = format_revenue_num(latest_revenue)
                    return formatted_value
            return None
        def format_revenue_num(value_str):
            try:
                value = int(value_str)
                formatted = locale.format_string("%d", value, grouping=True)
                return formatted
            except ValueError:
                return value_str

        def format_incorporation_date(date):
            if date:
                try:
                    return date.strftime("%d/%m/%Y")
                except AttributeError:
                    from datetime import datetime
                    try:
                        date_obj = datetime.strptime(date, "%Y-%m-%d")
                        return date_obj.strftime("%d/%m/%Y")
                    except ValueError:
                        return date
            return None
        def format_location(city, state):
            if city and state:
                return city+", "+state
            elif city:
                return city
            elif state:
                return state
            return ''

        shareholders_num = len(retrieved_data.get("shareholdings") or [])
        subsidiary_num = len(retrieved_data.get("subsidiary") or [])
        company_data = {
            "name": retrieved_data.get("legal_name",''),
            "location": format_location(retrieved_data.get('city',''),retrieved_data.get('state','')),
            "address": retrieved_data.get("address",''),
            "website": retrieved_data.get("website",''),
            "e_filing_status": retrieved_data.get("e_filing_status",''),
            "category": retrieved_data.get("classification",''),
            "pan_id": retrieved_data.get("pan"),
            "alias": format_alias(retrieved_data.get("alias",[])),
            "incorporation_date": format_incorporation_date(retrieved_data.get("incorporation_date")),
            "shareholders": format_shareholders(retrieved_data.get("shareholdings",[])),
            "revenue": format_revenue(retrieved_data.get("financial_pnl")),
            "subsidiaries": format_subsidiary(retrieved_data.get("subsidiary",[])),
            "key_executives":format_executives(retrieved_data.get("directors",[])),
            "employee": f"{retrieved_data.get('no_of_employee')} employees" if retrieved_data.get("no_of_employee") else None,
            "external_vendor_id": external_vendor_id,
            "uploaded_name": uploaded_name,
            "identifier": identifier,
            "identifier_type": identifier_type,
            "entity_type": entity_type,
            "corporate_group": f"Shareholders: {shareholders_num}\nSubsidiaries: {subsidiary_num}"
        }
        logger.debug(json.dumps(company_data, indent=2))
        columns_data = [company_data]
        result = await upsert_dynamic_ens_data("company_profile", columns_data, ens_id, session_id, session)
        if result.get("status") == "success":
            logger.info("Company profile saved successfully.")
        else:
            logger.error(f"Error saving company profile: {result.get('error')}")

        return {"ens_id": ens_id, "module": "COPR", "status": "completed"}
    except Exception as e:
        logger.error(f"Error while running company profile: {e}")
        traceback.print_exc()
        return {"ens_id": ens_id, "module": "COPR", "status": "failed"}