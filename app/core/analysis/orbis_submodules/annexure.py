import traceback
from app.schemas.logger import logger
import re
from typing import List, Dict, Any, Union
from datetime import datetime


def format_shareholders_for_annexure(shareholders: List[Dict[str, Any]]) -> str:
    """
    Format shareholders list for annexure display with ownership percentages
    Categorizes shareholders into Direct and Indirect based on significance
    """
    if not isinstance(shareholders, list) or not shareholders:
        return "No shareholder information available."

    direct_shareholders = []
    indirect_shareholders = []
    shareholders = sorted(shareholders, key=lambda x: x["percentage"], reverse=True)
    for shareholder in shareholders:
        if isinstance(shareholder, dict):
            name = shareholder.get("name", "").strip()
            shareholding= shareholder.get("percentage",0)
            significant_ownership = shareholder.get('significance',False)
            if not name:
                continue
            if not shareholding:
                shareholding=''
            else:
                shareholding = f" {shareholding}%"
            final_display = f"{name}{shareholding}"
            if significant_ownership:
                direct_shareholders.append(final_display)
            else:
                indirect_shareholders.append(final_display)

    # Format the output
    result_parts = []

    if direct_shareholders:
        result_parts.append("\n\nSignificant Shareholders\n\n")
        for i, shareholder in enumerate(direct_shareholders, 1):
            result_parts.append(f"{i}. {shareholder}")

    if indirect_shareholders: # AKA INSIGNIFICANT
        if result_parts:
            result_parts.append("")
            result_parts.append("\n\nOther Shareholders\n\n")
        for i, shareholder in enumerate(indirect_shareholders, 1):
            result_parts.append(f"{i}. {shareholder}")

    if not result_parts:
        return "No shareholder information available."

    return "\n".join(result_parts)

def format_management_for_annexure_pause(management_data: List[Dict[str, Any]]) -> str:
    """
    Management/key executives list for annexure
    """
    if not isinstance(management_data, list) or not management_data:
        return "No management information available."

    current_execs = []
    previous_execs = []
    executive_hierarchy_word_sets = {
        1: {'chief', 'executive', 'officer'},
        2: {'chairman'},
        3: {'vice', 'chairman'},
        4: {'president'},
        5: {'chief', 'operating', 'officer'},
        6: {'chief', 'financial', 'officer'},
        7: {'chief', 'technology', 'officer'},
        8: {'chief', 'marketing', 'officer'},
        9: {'chief', 'human', 'resources', 'officer'},
        10: {'chief', 'information', 'officer'},
        11: {'chief', 'legal', 'officer'},
        12: {'chief', 'revenue', 'officer'},
        13: {'chief', 'communications', 'officer'},
        14: {'chief', 'strategy', 'officer'},
        15: {'chief', 'digital', 'officer'},
        16: {'highest', 'executive'},
        17: {'deputy', 'executive'},
        18: {'chief', 'officer'},
        19: {'chief', 'executive'},
        20: {'vice', 'president'},
        21: {'member', 'board'},
        22: {'proxyholders'},
        23: {'representative'},
        24: {'investor', 'relations'},
        25: {'manager'},
        26: {'executive'},
        28: {'employee'},
        29: {'unspecified', 'executive'}
    }
    # logger.debug("checkpoint 1")

    for employee in management_data:
        if isinstance(employee, dict):
            consider_job_title = 0
            employee['priority'] = int(27)
            designation_cleaned = re.sub(r'[^a-zA-Z\s]', ' ', employee.get("designation",''))
            logger.debug("set1",employee.get("hierarchy",''),set(designation_cleaned.lower().split()))
            for official_priority, official_words_set in executive_hierarchy_word_sets.items():
                if official_words_set.issubset(set(designation_cleaned.lower().split())):
                    employee['priority'] = int(official_priority)
                    break

            # logger.debug("checkpoint 2")
            logger.debug("priority",employee['priority'])
            # logger.debug("checkpoint 3")
            name = employee.get("name", "").strip()
            designation = employee.get("designation", "").strip()

            if not name:
                continue

            employee['description'] = f"{name} - {designation}" if designation else name

            current_execs.append(employee)
        else:
            logger.debug("without dic found",employee)
    sections = []
    logger.debug("done")
    if current_execs:
        current_execs = sorted(current_execs, key=lambda x: x.get('priority',99))
        current_section = ["Current Key Executives\n\n"]
        current_section.extend(f"{i}. {exec['description']}" for i, exec in enumerate(current_execs, 1))
        sections.append("\n".join(current_section))

    # with open('priority.json', 'w')as file:
    #     json.dump(current_execs+previous_execs,file,indent=2)
    if not sections:
        return "No management information available."

    return "\n".join(sections)

def format_management_for_annexure(management_data: List[Dict[str, Any]]) -> str:
    result=[]
    index=1
    for employee in management_data:
        if isinstance(employee, dict):
            name=employee.get("name", "").strip()
            designation=employee.get("designation", "").strip()

            description=f"{index}. {name} - {designation}" if designation else f"{index}. {name}"
            if not result:
                result.append("")
                result.append("\n\nKey Management\n\n")
            result.append(description)
            index+=1
    if not result:
        return "No management information available."
    return "\n".join(result)

def format_subsidiaries_for_annexure(subsidiaries_data: List[Dict[str, Any]]) -> str:
    result=[]
    index=1
    subsidiaries_data = sorted(subsidiaries_data, key=lambda x: x["share_holding_percentage"], reverse=True)
    for subsidiary in subsidiaries_data:
        if isinstance(subsidiary, dict):
            name=subsidiary.get("legal_name", "").strip()
            shareholding=subsidiary.get("share_holding_percentage", "")
            description=f"{index}. {name} - {shareholding}%" if shareholding else f"{index}. {name}"
            if not result:
                result.append("")
                result.append("\n\nSubsidiary\n\n")
            result.append(description)
            index+=1
    if not result:
        return "No subsidiaries information available."
    return "\n".join(result)

def format_legal_for_annexure(legal_name: str, legal_data: List[Dict[str, Any]]) -> Union[List[Dict[str, Any]], str]:
    severity_order = {"low": 1, "medium": 2, "high": 3}

    # Defensive sorting
    try:
        legal_data = sorted(
            legal_data,
            key=lambda x: (
                severity_order.get(str(x.get("severity", "")).lower(), 0),
                str(x.get("date") or "")
            ),
            reverse=True
        )
    except Exception:
        logger.warning("Annexure Legal: Sort Failed")
        pass

    result = []
    for event in legal_data:
        try:
            if event.get('petitioner') == legal_name:
                continue

            # Date handling
            event_date = 'Unavailable'
            date_str = event.get("date")
            if date_str:
                try:
                    event_date_dt = datetime.strptime(str(date_str), "%Y-%m-%d")
                    event_date = event_date_dt.strftime("%d.%m.%y")
                except Exception:
                    event_date = 'Unavailable'

            para_body = (
                "Case No. {case_number} was filed before the {court} under the category of {case_category}. "
                "This matter pertains to {case_type}, where {petitioner} has initiated proceedings against {respondent}.\n"
            ).format(
                case_number=event.get("case_number", "Unknown"),
                court=event.get("court", "Unknown"),
                case_category=event.get("case_category", "Unknown"),
                case_type=event.get("case_type", "Unknown"),
                petitioner=event.get("petitioner", "Unknown"),
                respondent=event.get("respondent", "Unknown"),
            )

            obj = {
                "date": event_date,
                "case_number": event.get("case_number", "Unknown"),
                "Description": para_body,
                "severity": event.get("severity", "Unknown"),
                "status": event.get("case_status", ""),
                "category": event.get("case_category", "")
            }
            result.append(obj)
        except Exception as e:
            logger.warning("Annexure Legal: Exception reached")
            traceback.print_exc()
            continue

    if not result:
        return []
    return result

def format_director_network_for_annexure(director_network_data: List[Dict[str, Any]]) -> Union[List[Dict[str, Any]], str]:

    result = []
    for event in director_network_data:
        try:
            network = event.get('network', {})
            companies = network.get('companies', [])
            llps = network.get('llps', [])

            # Build network paragraph
            network_points = []

            for company in companies:
                name = company.get("legal_name", "Unknown")
                designation = company.get("designation", "")
                date_of_appointment = company.get("date_of_appointment", "")
                date_of_cessation = company.get("date_of_cessation")
                status = company.get("company_status", "")
                compliance = company.get("active_compliance", "")

                duration = f"{date_of_appointment} – {date_of_cessation if date_of_cessation else 'Present'}"
                flags = []
                if status and status != "ACTIVE":
                    flags.append(status)
                if compliance and compliance != "ACTIVE compliant":
                    flags.append(compliance)
                flag_str = f" [{', '.join(flags)}]" if flags else ""

                network_points.append(f"• {name} — {designation} ({duration}){flag_str}")

            for llp in llps:
                name = llp.get("legal_name", "Unknown")
                designation = llp.get("designation", "")
                date_of_appointment = llp.get("date_of_appointment", "")
                date_of_cessation = llp.get("date_of_cessation")
                status = llp.get("status", "")

                duration = f"{date_of_appointment} – {date_of_cessation if date_of_cessation else 'Present'}"
                flags = []
                if status and status != "ACTIVE":
                    flags.append(status)
                flag_str = f" [{', '.join(flags)}]" if flags else ""

                network_points.append(f"• {name} (LLP) — {designation} ({duration}){flag_str}")

            network_paragraph = "\n".join(network_points) if network_points else "No network data available"

            obj = {
                "Director Name": event.get('name', 'Unknown'),
                "DIN": event.get("din", "Unknown"),
                "Network": network_paragraph,
            }
            result.append(obj)

        except Exception as e:
            logger.warning("Annexure Legal: Exception reached")
            traceback.print_exc()
            continue

    if not result:
        return []
    return result