import json
from datetime import datetime
from app.core.utils.db_utils import *
from app.schemas.logger import logger
import traceback

async def legal_analysis(data, session):
    logger.info("Performing Legal Analysis...")

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

        LEG1A = kpi_template.copy()
        LEG2A = kpi_template.copy()
        LEG1A["kpi_code"] = "LEG1A"
        LEG1A["kpi_definition"] = "Legal History"

        LEG2A["kpi_code"] = "LEG2A"
        LEG2A["kpi_definition"] = "Open Charges"

        # Data for Org-Level
        required_columns = ["legal_history", "open_charges", "legal_name"]
        try:
            retrieved_data = await get_dynamic_ens_data("external_supplier_data", required_columns, ens_id_value, session_id_value, session)
        except Exception as e:
            logger.error(f"Failed to retrieve data: {e}")
            return {
                "ens_id": ens_id_value, "module": kpi_area_module, "status": "failure", "info": f"data_fetch_error: {e}"
            }
        if not retrieved_data:
            return {
                "ens_id": ens_id_value, "module": kpi_area_module, "status": "completed", "info": "no_data"
            }
        retrieved_data = retrieved_data[0] if isinstance(retrieved_data, (list, tuple)) else retrieved_data

        legal_history = retrieved_data.get("legal_history")
        open_charge = retrieved_data.get("open_charges")
        legal_name = retrieved_data.get("legal_name", "")

        if (not legal_history) and (not open_charge):
            logger.info(f"{kpi_area_module} Analysis... Completed With No Data")
            return {
                "ens_id": ens_id_value, "module": kpi_area_module, "status": "completed", "info": "no_data"
            }

        # --- LEG1A: Legal History Analysis ---
        leg_data = legal_history or []
        severity_order = {"low": 1, "medium": 2, "high": 3}
        # defensive: some entries may lack severity or date
        try:
            leg_data = sorted(
                leg_data,
                key=lambda x: (
                    severity_order.get((x.get("severity") or "").lower(), 0),
                    str(x.get("date") or "")
                ),
                reverse=True,
            )
        except Exception as e:
            logger.warning(f"Sorting legal history failed: {e}")
            leg_data = leg_data

        legal_lists_direct = []
        unique_legal_data = set()
        all_events_detail = "Following are Legal History"
        counter = 0
        kpi_rating = 'Low'
        LEG1A["kpi_flag"] = False

        for event in leg_data:  # defensive iteration
            if counter >= 10:
                break
            try:
                if (
                    event.get('petitioner') == legal_name or
                    event.get('case_status', '').lower() != 'pending'
                ):
                    continue
            except Exception:
                continue

            key = (
                event.get("date"),
                event.get("petitioner"),
                event.get("respondent"),
            )
            if key in unique_legal_data:
                continue
            unique_legal_data.add(key)

            LEG1A["kpi_flag"] = True
            event_date = 'Unavailable'
            try:
                if event.get("date"):
                    try:
                        event_date_dt = datetime.strptime(event.get("date"), "%Y-%m-%d")
                        event_date = event_date_dt.strftime("%d.%m.%y")
                    except Exception:
                        event_date = 'Unavailable'
            except Exception:
                event_date = 'Unavailable'

            status = (event.get("case_status") or "").lower()
            if status == "pending":
                kpi_rating = 'High'
            else:
                kpi_rating = 'Medium'

            para_header = (
                f"{counter + 1}. Date: {event_date} | Severity: {event.get('severity', 'Unknown')} | Status: {event.get('case_status', 'Unknown')}"
            )
            para_body = (
                f"Case No. {event.get('case_number', 'Unknown')} was filed before the {event.get('court', 'Unknown')} under the category of {event.get('case_category', 'Unknown')}. "
                f"This matter pertains to {event.get('case_type', 'Unknown')}, where {event.get('petitioner', 'Unknown')} has initiated proceedings against {event.get('respondent', 'Unknown')}.\n"
            )
            para_template = para_header + '\n' + para_body
            obj = {
                "date": event_date,
                "case_number": event.get("case_number", "Unknown"),
                "Description": para_body,
                "severity": event.get("severity", "Unknown"),
                "status": event.get("case_status", ""),
                "category": event.get("case_category", "")
            }
            legal_lists_direct.append(obj)
            all_events_detail += '\n' + para_template
            counter += 1

        LEG1A["kpi_rating"] = kpi_rating
        try:
            LEG1A["kpi_value"] = json.dumps(legal_lists_direct)
        except Exception as e:
            LEG1A["kpi_value"] = "[]"
            logger.warning(f"Failed to serialize LEG1A kpi_value: {e}")
        LEG1A["kpi_details"] = all_events_detail

        # --- LEG2A: Open Charges ---
        oc_data = open_charge or []
        try:
            oc_data = sorted(
                oc_data,
                key=lambda x: x.get("date") or "",
                reverse=True
            )
        except Exception as e:
            logger.warning(f"Sorting open charges failed: {e}")
            oc_data = oc_data

        legal_lists_direct = []
        unique_legal_data = set()
        all_events_detail = ''
        high_risk_rating_trigger = False
        medium_risk_rating_trigger = False
        counter = 0
        LEG2A["kpi_flag"] = False

        for event in oc_data:
            if counter >= 5:
                break
            key = (
                event.get("date"),
                event.get("holder_name"),
                event.get("amount"),
            )
            if key in unique_legal_data:
                continue
            unique_legal_data.add(key)

            LEG2A["kpi_flag"] = True

            amount = 0
            try:
                amount = int(event.get("amount", 0) or 0)
            except Exception:
                amount = 0

            holder = event.get("holder_name", "Unknown")

            event_date_str = event.get("date", "")
            date_display = "Unavailable"
            event_year_diff = None
            try:
                event_date_dt = datetime.strptime(event_date_str, "%Y-%m-%d")
                date_display = event_date_dt.strftime("%d.%m.%y")
                event_year_diff = datetime.now().year - event_date_dt.year
            except Exception:
                event_date_dt = None
                event_year_diff = None

            # Calculate risk triggers
            if event_year_diff is not None:
                if event_year_diff <= 5:
                    if amount > 100000:
                        high_risk_rating_trigger = True
                    elif amount > 0:
                        medium_risk_rating_trigger = True
                elif event_year_diff <= 10 and amount > 100000:
                    medium_risk_rating_trigger = True

            charge_type = event.get("type", "Unknown")
            obj = {
                "date": date_display,
                "amount": amount,
                "holder_name": holder,
                "charge_type": charge_type,
            }
            legal_lists_direct.append(obj)
            para_template = generate_charge_paragraph_safe(event, counter + 1)
            all_events_detail += para_template
            counter += 1

        if high_risk_rating_trigger:
            LEG2A["kpi_rating"] = 'High'
        elif medium_risk_rating_trigger:
            LEG2A["kpi_rating"] = 'Medium'
        else:
            LEG2A["kpi_rating"] = 'Low'

        try:
            LEG2A["kpi_value"] = json.dumps(legal_lists_direct)
        except Exception as e:
            LEG2A["kpi_value"] = "[]"
            logger.warning(f"Failed to serialize LEG2A kpi_value: {e}")
        LEG2A["kpi_details"] = all_events_detail

        legal_kpis = [LEG1A, LEG2A]

        try:
            insert_status = await upsert_kpi("legal", legal_kpis, ens_id_value, session_id_value, session)
        except Exception as e:
            logger.error(f"Error while saving to DB: {e}")
            return {
                "ens_id": ens_id_value, "module": kpi_area_module, "status": "failure", "info": "database_saving_error"
            }

        if insert_status.get("status") == "success":
            logger.info(f"{kpi_area_module} Analysis... Completed Successfully")
            return {"ens_id": ens_id_value, "module": kpi_area_module, "status": "completed", "info": "analysed"}
        else:
            return {"ens_id": ens_id_value, "module": kpi_area_module, "status": "failure", "info": "database_saving_error"}

    except Exception as e:
        logger.error(f"Error in module: {kpi_area_module}: {str(e)}")
        traceback.print_exc()
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": str(e),
        }

def generate_charge_paragraph_safe(charge, index):
    try:
        amount = charge.get("amount", 0)
        try:
            amount_str = f"{int(amount):,}" if isinstance(amount, (int, float, str)) and str(amount).replace('.', '', 1).isdigit() else "0"
        except Exception:
            amount_str = "0"
        holder = charge.get("holder_name", "Unknown")
        date_str = charge.get("date", "")
        date_disp = "Unavailable"
        try:
            event_date = datetime.strptime(str(date_str), "%Y-%m-%d")
            date_disp = event_date.strftime("%d.%m.%y")
        except Exception:
            date_disp = "Unavailable"
        charge_type = charge.get("type", "Unknown")
        para = f"{index}. {charge_type} of Rs.{amount_str} in favour of {holder} dated {date_disp}\n"
    except Exception as e:
        return []
    return para
