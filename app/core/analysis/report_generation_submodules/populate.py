import json

from app.core.analysis.orbis_submodules.annexure import *
from app.core.utils.db_utils import *
import asyncio
from app.core.analysis.report_generation_submodules.utilities import *
import pandas as pd
from typing import List, Dict, Any
async def populate_profile(incoming_ens_id, incoming_session_id, session):
    profile = await get_dynamic_ens_data(
        "company_profile", 
        required_columns=["all"], 
        ens_id=incoming_ens_id, 
        session_id=incoming_session_id, 
        session=session
    )

    # Define keys and use `.get()` with a check for None values
    keys = [
        "name", "uploaded_name", "external_vendor_id", "location", "address",
        "website", "e_filing_status", "category", "pan_id",
        "alias", "incorporation_date", "shareholders",
        "revenue", "subsidiaries", "key_executives", "employee", "identifier",
        "corporate_group", "entity_type", "identifier_type"
    ]

    # Ensure profile is not empty
    if not profile or not isinstance(profile, list) or not profile[0]:
        return {key: "N/A" for key in keys}

    # Return dictionary ensuring no None values
    return {key: profile[0].get(key, "N/A") if profile[0].get(key) is not None else "N/A" for key in keys}

# kpi_area, kpi_code, kpi_flag, kpi_value, kpi_details,                     kpi_definition
# SAN,      SAN1A,      True,       [],      Following sanctions imposed.., Title to the finding 

async def populate_legal(incoming_ens_id, incoming_session_id, session):
    sape = await get_dynamic_ens_data(
        "legal",
        required_columns=["all"], 
        ens_id=incoming_ens_id, 
        session_id=incoming_session_id, 
        session=session
    )
    # print(f"\n\nSanctions: {sape}")

    # Ensure `sape` is not empty
    if not sape:
        return {"legal": pd.DataFrame()}

    # Lists to store filtered rows
    sanctions_data = []

    # Loop through the list of dictionaries and categorize rows
    for row in sape:
        if row.get("kpi_area") == "LEG" and row.get("kpi_flag"):
            sanctions_data.append(row)
    
    if not sanctions_data:
        return {"legal": pd.DataFrame()}

    # Convert lists to DataFrames
    sanctions_df = pd.DataFrame(sanctions_data)

    return {
        "legal": sanctions_df,
    }

async def populate_pep(incoming_ens_id, incoming_session_id, session):
    sape = await get_dynamic_ens_data(
        "sown",
        required_columns=["all"],
        ens_id=incoming_ens_id,
        session_id=incoming_session_id,
        session=session
    )
    # print(f"\n\PeP: {sape}")

    # Ensure `sape` is not empty
    if not sape:
        return {"pep": pd.DataFrame()}

    # Lists to store filtered rows
    pep_data = []

    # Loop through the list of dictionaries and categorize rows
    for row in sape:
        if row.get("kpi_area") == "PEP" and row.get("kpi_flag"):
            pep_data.append(row)

    # Convert lists to DataFrames
    pep_df = pd.DataFrame(pep_data)

    return {
        "pep": pep_df,
    }

async def populate_anti(incoming_ens_id, incoming_session_id, session):
    bcr = await get_dynamic_ens_data(
        "rfct", 
        required_columns=["all"], 
        ens_id=incoming_ens_id, 
        session_id=incoming_session_id, 
        session=session
    )
    # print(f"\n\nBr and Cor: {bcr}")

    # Ensure `bcr` is not empty
    if not bcr:
        return {"bribery": pd.DataFrame(), "corruption": pd.DataFrame()}

    # Lists to store filtered rows
    bribery_corruption_fraud_data = []
    corruption_data = []

    # Loop through the list of dictionaries and categorize rows
    for row in bcr:
        if row.get("kpi_area") == "BCF" and row.get("kpi_flag"): #Fixed to right area code + appending method
            bribery_corruption_fraud_data.append(row)

    # Convert lists to DataFrames
    bribery_df = pd.DataFrame(bribery_corruption_fraud_data)
    corruption_df = pd.DataFrame(corruption_data)

    # TODO: Consider removing the separate "corruption" report sub-section, depending on risk methodology sign-off
    # Currently it is not a separate section, corruption, fraud etc are KPIs under the area B.C.F

    return {
        "bribery": bribery_df,
        "corruption": corruption_df
    }

async def populate_other_adv_media(incoming_ens_id, incoming_session_id, session):
    news = await get_dynamic_ens_data(
        "adverse_media",
        required_columns=["all"],
        ens_id=incoming_ens_id,
        session_id=incoming_session_id,
        session=session
    )
    # print(f"\n\nSanctions: {sape}")
    rfct=news
    # Ensure `sape` is not empty
    if not rfct:
        return {"adv_media": pd.DataFrame()}

    # Lists to store filtered rows
    adv_data = []

    # Loop through the list of dictionaries and categorize rows
    for row in rfct:
        if row.get("kpi_area") == "NWS" and row.get("kpi_flag"):
            adv_data.append(row)
    
    if not adv_data:
        return {"adv_media": pd.DataFrame()}

    # Convert lists to DataFrames
    adv_df = pd.DataFrame(adv_data)

    return {
        "adv_media": adv_df,
    }

async def populate_regulatory_legal(incoming_ens_id, incoming_session_id, session):
    rfct = await get_dynamic_ens_data(
        "rfct", 
        required_columns=["all"], 
        ens_id=incoming_ens_id, 
        session_id=incoming_session_id, 
        session=session
    )
    lgrk = await get_dynamic_ens_data(
        "legal",
        required_columns=["all"], 
        ens_id=incoming_ens_id, 
        session_id=incoming_session_id, 
        session=session
    )
    # print(f"\n\nSanctions: {sape}")
    # Lists to store filtered rows
    regulatory_data = []
    for row in rfct:
        if row.get("kpi_area") == "REG" and row.get("kpi_flag"):
            regulatory_data.append(row)
    legal_data = []
    for row in lgrk:
        if row.get("kpi_area") == "LEG" and row.get("kpi_flag"):
            legal_data.append(row)
    
    result = {
        "reg_data": "",
        "legal_data": ""
    }

    if not regulatory_data:
        result["reg_data"] = pd.DataFrame()
    else:
        reg_df = pd.DataFrame(regulatory_data)
        result["reg_data"] = reg_df

    if not legal_data:
        result["legal_data"] = pd.DataFrame()
    else:
        legal_df = pd.DataFrame(legal_data)
        result["legal_data"] = legal_df

    return result


# async def populate_financials(incoming_ens_id, incoming_session_id, session):
#     fstb = await get_dynamic_ens_data(
#         "fstb", 
#         required_columns=["all"], 
#         ens_id=incoming_ens_id, 
#         session_id=incoming_session_id, 
#         session=session
#     )
#     # print(f"\n\nFinancial: {fstb}")

#     # Ensure `fstb` is not empty
#     if not fstb:
#         return {"financial": pd.DataFrame(), "bankruptcy": pd.DataFrame()}

#     # Lists to store filtered rows
#     financial_data = []
#     bankruptcy_data = []

#     # Loop through the list of dictionaries and categorize rows
#     for row in fstb:
#         if row.get("kpi_area") == "FIN" and row.get("kpi_flag") and row.get("kpi_rating") != "INFO":
#             # if row.get("kpi_code", "").startswith("FIN1"):  # Update condition as needed
#             financial_data.append(row)
#     for row in fstb:
#         if row.get("kpi_area") == "BKR" and row.get("kpi_flag"):  # Update condition as needed
#             bankruptcy_data.append(row)

#     # Convert lists to DataFrames
#     financial_df = pd.DataFrame(financial_data)
#     bankruptcy_df = pd.DataFrame(bankruptcy_data)

#     return {
#         "financial": financial_df,
#         "bankruptcy": bankruptcy_df
#     }

async def populate_financials_risk(incoming_ens_id, incoming_session_id, session):
    fstb = await get_dynamic_ens_data(
        "fstb",
        required_columns=["all"],
        ens_id=incoming_ens_id,
        session_id=incoming_session_id,
        session=session
    )

    # Ensure `fstb` is not empty
    if not fstb:
        return {"financial": pd.DataFrame()}

    # List to store all relevant records (both FIN and BKR)
    financial_data = []

    # Loop through the list of dictionaries and filter records
    for row in fstb:
        if row.get("kpi_area") == "BKR" and row.get("kpi_flag") and row.get("kpi_rating") != "INFO":
            financial_data.append(row)

    # Convert list to DataFrame
    financial_df = pd.DataFrame(financial_data)

    if not financial_df.empty:
        # Define custom sorting order for kpi_rating
        rating_order = {"High": 1, "Medium": 2, "Low": 3, "Info": 4}
        
        # Sort the DataFrame based on kpi_rating priority
        financial_df["sort_order"] = financial_df["kpi_rating"].map(rating_order).fillna(5)
        financial_df = financial_df.sort_values(by="sort_order").drop(columns=["sort_order"])

    return {"financial": financial_df}


async def populate_financials_value(incoming_ens_id, incoming_session_id, session):
    fstb = await get_dynamic_ens_data(
        "finance",
        required_columns=["all"],
        ens_id=incoming_ens_id,
        session_id=incoming_session_id,
        session=session
    )

    # Ensure `fstb` is not empty
    if not fstb:
        return {"financial": pd.DataFrame()}

    # List to store all relevant records (both FIN and BKR)
    financial_data = []

    # Loop through the list of dictionaries and filter records
    for row in fstb:
        if row.get("kpi_area") == 'FSTB' and row.get("kpi_flag"):
            financial_data.append(row)

    # Convert list to DataFrame
    financial_df = pd.DataFrame(financial_data)

    return {"financial": financial_df}


async def populate_entity(incoming_ens_id, incoming_session_id, session):
    sown = await get_dynamic_ens_data(
        "entity_existance",
        required_columns=["all"], 
        ens_id=incoming_ens_id, 
        session_id=incoming_session_id, 
        session=session
    )
    # print(f"\n\nSown: {sown}")

    if not sown:
        return {"entity_existence": pd.DataFrame()}

    direct_ownership_data = []

    for row in sown:
        if row.get("kpi_flag"):
            direct_ownership_data.append(row)


    return {
        "entity_existence": pd.DataFrame(direct_ownership_data)
    }

async def populate_cybersecurity(incoming_ens_id, incoming_session_id, session):
    cyb = await get_dynamic_ens_data(
        "cyber_esg",
        required_columns=["all"], 
        ens_id=incoming_ens_id, 
        session_id=incoming_session_id, 
        session=session
    )
    # print(f"\n\nCyber: {cyb}")
    if not cyb:
        return {"cyber_esg": pd.DataFrame()}

    cybersecurity_data = []

    for row in cyb:
        if row.get("kpi_flag"):
            cybersecurity_data.append(row)

    return {
        "cyber_esg": pd.DataFrame(cybersecurity_data),
    }

async def populate_esg(incoming_ens_id, incoming_session_id, session):
    esg = await get_dynamic_ens_data(
        "cyes", 
        required_columns=["all"], 
        ens_id=incoming_ens_id, 
        session_id=incoming_session_id, 
        session=session
    )
    # print(f"\n\nESG: {esg}")

    if not esg:
        return {"esg": pd.DataFrame()}

    esg_data = []

    for row in esg:
        if row.get("kpi_area") == "ESG" and row.get("kpi_flag"):
            esg_data.append(row)

    return {
        "esg": pd.DataFrame(esg_data)
    }

async def populate_country_risk(incoming_ens_id, incoming_session_id, session):
    cr = await get_dynamic_ens_data(
        "sown",
        required_columns=["all"],
        ens_id=incoming_ens_id,
        session_id=incoming_session_id,
        session=session
    )
    # print(f"\n\nSown: {sown}")

    if not cr:
        return {"country_risk": pd.DataFrame()}

    country_risk = []

    for row in cr:
        if row.get("kpi_area") == "CR" and row.get("kpi_flag"):
            country_risk.append(row)


    return {
        "country_risk": pd.DataFrame(country_risk)
    }

async def populate_ownership_flag(incoming_ens_id, incoming_session_id, session):
    ownf = await get_dynamic_ens_data(
        "oval",
        required_columns=["all"],
        ens_id=incoming_ens_id,
        session_id=incoming_session_id,
        session=session
    )
    # print(f"\n\nSown: {sown}")

    if not ownf:
        return {"ownership_flag": pd.DataFrame()}

    ownership_flag = []

    for row in ownf:
        if row.get("kpi_flag"):
            ownership_flag.append(row)


    return {
        "ownership_flag": pd.DataFrame(ownership_flag)
    }

async def populate_news(incoming_ens_id, incoming_session_id, session):
    sown = await get_dynamic_ens_data(
        "news",
        required_columns=["all"],
        ens_id=incoming_ens_id,
        session_id=incoming_session_id,
        session=session
    )
    # print(f"\n\nSown: {sown}")

    if not sown:
        return {"other_news": pd.DataFrame()}

    other_news_data = []

    for row in sown:
        if row.get("kpi_flag") and row.get("kpi_area") == "ESG":
            other_news_data.append(row)


    return {
        "other_news": pd.DataFrame(other_news_data)
    }


async def populate_annexure_data(annexure_from_diff,incoming_ens_id: str, incoming_session_id: str, session) -> List[Dict[str, Any]]:
    annexure_list = []

    try:
        shareholders_data = await get_dynamic_ens_data(
            table_name="external_supplier_data",
            required_columns=["shareholdings"],
            ens_id=incoming_ens_id,
            session_id=incoming_session_id,
            session=session
        )

        if shareholders_data and shareholders_data[0].get("shareholdings"):
            shareholder_list = shareholders_data[0]["shareholdings"]

            formatted_shareholders = []
            for sh in shareholder_list:
                if isinstance(sh, dict) and sh.get("name"):
                    formatted_shareholders.append({
                        "name": sh["name"].strip(),
                        "percentage": sh.get("shareholding_percentage", ""),
                        "significance": True if sh.get("shareholding_percentage", 0) > 5 else False
                    })

            if formatted_shareholders:
                annexure_list.append({
                    "id": "1",
                    "title": "Full List of Shareholders",
                    "contents": format_shareholders_for_annexure(formatted_shareholders)
                })

    except Exception as e:
        logger.error(f"Shareholder processing error: {str(e)}")
        annexure_list.append({
            "id": "1",
            "title": "Full List of Shareholders",
            "contents": "Information not available"
        })

    try:
        # Get management data (already a list)
        management_data = await get_dynamic_ens_data(
            table_name="external_supplier_data",
            required_columns=["directors"],
            ens_id=incoming_ens_id,
            session_id=incoming_session_id,
            session=session
        )

        if management_data and management_data[0].get("directors"):
            management_list = management_data[0]["directors"]

            formatted_management = []
            for mgmt in management_list:
                if isinstance(mgmt, dict) and mgmt.get("name"):
                    formatted_management.append({
                        "name": mgmt["name"].strip(),
                        "designation": mgmt.get("designation", "").strip()
                    })

            if formatted_management:
                annexure_list.append({
                    "id": "2",
                    "title": "Key Management Personnel",
                    "contents": format_management_for_annexure(formatted_management)
                })

    except Exception as e:
        logger.error(f"Management processing error: {str(e)}")
        annexure_list.append({
            "id": "2",
            "title": "Key Management Personnel",
            "contents": "Information not available"
        })

    try:
        # Get management data (already a list)
        subsidiary_data = await get_dynamic_ens_data(
            table_name="external_supplier_data",
            required_columns=["subsidiary"],
            ens_id=incoming_ens_id,
            session_id=incoming_session_id,
            session=session
        )

        if subsidiary_data and subsidiary_data[0].get("subsidiary"):
            sub_list = subsidiary_data[0]["subsidiary"]
            formatted_sub = []
            for sub in sub_list:
                if isinstance(sub, dict) and sub.get("legal_name"):
                    formatted_sub.append({
                        "legal_name": sub["legal_name"].strip(),
                        "share_holding_percentage": sub.get("share_holding_percentage", "")
                    })
            if formatted_sub:
                annexure_list.append({
                    "id": "3",
                    "title": "Full List of Subsidiary",
                    "contents": format_subsidiaries_for_annexure(formatted_sub)
                })
    except Exception as e:
        logger.error(f"Subsidiary processing error: {str(e)}")
        annexure_list.append({
            "id": "3",
            "title": "Full List of Subsidiary",
            "contents": "Information not available"
        })

    try:
        # Get all legal data (already a list)
        legal_data = await get_dynamic_ens_data(
            table_name="external_supplier_data",
            required_columns=["legal_history", "legal_name"],
            ens_id=incoming_ens_id,
            session_id=incoming_session_id,
            session=session
        )

        if legal_data and legal_data[0].get("legal_history"):
            sub_list = legal_data[0]["legal_history"]
            legal_name = legal_data[0]["legal_name"]
            if sub_list and isinstance(sub_list,list):
                annexure_list.append({
                    "id": "4",
                    "title": "Full List of Legal History",
                    "contents": format_legal_for_annexure(legal_name,sub_list)
                })
    except Exception as e:
        logger.error(f"Legal History processing error: {str(e)}")
        annexure_list.append({
            "id": "3",
            "title": "Full List of Legal History",
            "contents": []
        })

    try:
        # Get all legal data (already a list)
        legal_data = await get_dynamic_ens_data(
            table_name="external_supplier_data",
            required_columns=["director_network"],
            ens_id=incoming_ens_id,
            session_id=incoming_session_id,
            session=session
        )

        if legal_data and legal_data[0].get("director_network"):
            dir_network_list = legal_data[0]["director_network"]
            if dir_network_list and isinstance(dir_network_list,list):
                annexure_list.append({
                    "id": "4",
                    "title": "Full List of Director Network",
                    "contents": format_director_network_for_annexure(dir_network_list)
                })
    except Exception as e:
        logger.error(f"Director Network processing error: {str(e)}")
        annexure_list.append({
            "id": "3",
            "title": "Full List of Director Network",
            "contents": []
        })
    return annexure_list



    
