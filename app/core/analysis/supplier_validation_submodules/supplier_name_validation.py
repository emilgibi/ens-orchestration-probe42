
from app.core.security.jwt import create_jwt_token
from app.core.utils.db_utils import *
from app.core.analysis.supplier_validation_submodules.utilities import *
from app.models import *
import requests
from urllib.parse import quote
from app.core.config import get_settings
from itertools import groupby
from operator import itemgetter
from app.schemas.logger import logger

async def supplier_name_validation(data, session, search_engine:str):
    results = []
    print("entered the main function")
    print(data)

    incoming_ens_id = data["ens_id"]
    incoming_name = data["uploaded_name"]
    session_id = data["session_id"]
    incoming_identifier = data.get("uploaded_identifier", '')
    incoming_identifier_type = data.get("uploaded_identifier_type", '')
    incoming_entity_type = data.get("uploaded_entity_type", '')

    logger.info("================================================")
    logger.info(f"[SNV] ens_id = {incoming_ens_id}")

    def get_possible_suppliers(payload, static_case=None):
        try:
            # Generate JWT token
            jwt_token = create_jwt_token("orchestration", "analysis")
            logger.debug(f"TOKEN: {jwt_token}")
        except Exception as e:
            logger.error("Error generating JWT token: %s", e)
            raise
        orbis_url = get_settings().urls.orbis_engine

        base_url = f"{orbis_url}/api/v1/orbis/instaFinancial/getCompanybyName"
        print("----> base url",base_url)

        # Ensure all values are properly URL-encoded
        query_params = {
            "orgName": quote(payload["orgName"])
        }
        if payload["orgIdentifier"]:
            query_params['orgIdentifier']=quote(payload["orgIdentifier"])
        if payload["orgIdentifierType"]:
            query_params['orgIdentifierType']=quote(payload["orgIdentifierType"])
        if payload["orgEntityType"]:
            query_params['orgEntityType']=quote(payload["orgEntityType"])

        query_string = "&".join(f"{key}={value}" for key, value in query_params.items())
        url = f"{base_url}?{query_string}"
        try:
            headers = {
                "Authorization": f"Bearer {jwt_token.access_token}"
            }
            response = requests.get(url, headers=headers)
            # Raise an error if the response status is not 200
            if response.status_code != 200:
                raise requests.HTTPError(f"API request failed with status code {response.status_code}: {response.text}")

            try:
                response_json = response.json()  # Try parsing JSON
            except ValueError as e:
                raise ValueError("API response is not valid JSON") from e

            # Check if "data" key exists
            if "data" not in response_json:
                raise KeyError("Missing 'data' key in API response")

            # Extract supplier data from response
            matched_supplier_data, potential_pass, matched = filter_supplier_data(response_json)

            return matched_supplier_data, potential_pass, matched

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch supplier data: {e}")

    match_payload = {
        "orgName": str(incoming_name),
        "orgIdentifier": str(incoming_identifier),
        "orgIdentifierType": str(incoming_identifier_type),
        "orgEntityType": str(incoming_entity_type)
    }

    matched_supplier_data, potential_pass, matched = get_possible_suppliers(match_payload, static_case=False)
 
    try:
        logger.info(" ------- ORBIS MATCH IDENTIFIED: ")

        logger.info(json.dumps(matched_supplier_data, indent=2))

        final_validation_status = FinalValidatedStatus.REVIEW
        if matched:
            logger.info(
                f"[SNV] Matched Status (Direct Match): {matched} with score {matched_supplier_data.get('confidence')}")
            final_validation_status = FinalValidatedStatus.AUTO_ACCEPT
            orbis_status = OribisMatchStatus.MATCH
            validation_status = ValidationStatus.VALIDATED
            name = str(matched_supplier_data.get('matched_company', {}).get('legal_name', 'N/A'))
            identifier_type = str(matched_supplier_data.get('identifierType', 'N/A'))
            entity_type = str(matched_supplier_data.get('entityType', 'N/A'))
            identifier = str(matched_supplier_data.get('matched_company', {}).get(f'{identifier_type.lower()}', 'N/A'))
            bid = str(matched_supplier_data.get('matched_company', {}).get('bid', 'N/A'))
        elif potential_pass:
            logger.info(
                f"[SNV] Potential pass (Needs Review): {potential_pass} with score {matched_supplier_data.get('confidence')}")
            final_validation_status = FinalValidatedStatus.REVIEW
            orbis_status = OribisMatchStatus.MATCH
            validation_status = ValidationStatus.VALIDATED
            name = str(matched_supplier_data.get('matched_company', {}).get('legal_name', 'N/A'))
            identifier_type = str(matched_supplier_data.get('identifierType', 'N/A'))
            entity_type = str(matched_supplier_data.get('entityType', 'N/A'))
            identifier = str(matched_supplier_data.get('matched_company', {}).get(f'{identifier_type.lower()}', 'N/A'))
            bid = str(matched_supplier_data.get('matched_company', {}).get('bid', 'N/A'))
        else:
            logger.info(
                f"[SNV] No Match (Reject): {potential_pass} with score {matched_supplier_data.get('confidence')}")
            final_validation_status = FinalValidatedStatus.AUTO_REJECT
            orbis_status = OribisMatchStatus.NO_MATCH
            validation_status = ValidationStatus.NOT_VALIDATED
            name = 'N/A'
            identifier_type ='N/A'
            entity_type = 'N/A'
            identifier = 'N/A'
            bid = 'N/A'


        updated_data = {
            "validation_status": validation_status,
            "orbis_matched_status": orbis_status,
            "final_validation_status": final_validation_status,
            "match_percentage": matched_supplier_data.get('confidence',0),

            "name": name,
            "identifier": identifier,
            "identifier_type": identifier_type,
            "entity_type": entity_type,
            "bid": bid,

            "suggested_name": name,
            "suggested_identifier": identifier,
            "suggested_bid": bid,
            "suggested_identifier_type": identifier_type,
            "suggested_entity_type": entity_type,
        }
        print("update", updated_data)

        # Checking for pre-existing BVD-ID
        logger.info("ENSID BEFORE------- %s", incoming_ens_id)
        if final_validation_status is not FinalValidatedStatus.AUTO_REJECT:
            processed_ens_id, duplicate = await check_and_update_unique_value(
                table_name="upload_supplier_data",
                column_name="identifier",
                cin_id_to_check=identifier,
                ens_id=incoming_ens_id,
                session=session
            )

            # Assign ens_id as the processed one (pre-existing if found)
            incoming_ens_id = processed_ens_id
            logger.info("ENS ID AFTER %s", incoming_ens_id)
            if duplicate["status"] == "unique":
                updated_data["preexisting_cin_id"] = False
            elif duplicate["status"] == "duplicate":
                updated_data["preexisting_cin_id"] = True

        api_response = {
            "ens_id": incoming_ens_id,
            "L2_verification": "Not Required",
            "L2_confidence": None,
            "verification_details": updated_data
        }

        # Update Data To Table
        update_status = await update_dynamic_ens_data("upload_supplier_data", updated_data, ens_id=incoming_ens_id,
                                                      session_id=session_id, session=session)
        api_response["status"] = "Updated in DB" if update_status["status"] == "success" else "Failed to update DB"

        results.append(api_response)

        logger.info(f"[SNV] Process completed for {incoming_ens_id}")

        return True, results

    except Exception as e:

        logger.error(f"Supplier Name Validation Failed - {str(e)}")
        raise


async def ensid_duplicate_in_session(session_id, session):

    logger.debug("---- STARTING DUPLICATION CHECK")

    data_for_sessionId = await get_dynamic_ens_data("upload_supplier_data", required_columns=["all"],ens_id=None, session_id=session_id, session=session)

    data_for_sessionId = [entry for entry in data_for_sessionId if (entry.get( "validation_status","")!=ValidationStatus.NOT_VALIDATED.value)]
    # Sort the data by the key(s) you want to group by
    data_for_sessionId.sort(key=itemgetter('ens_id'))
    grouped = groupby(data_for_sessionId, key=itemgetter('ens_id'))
    print(grouped)

    for ens_id, group in grouped:

        group_list = list(group)

        # TAKE ONLY CASES WHERE MORE THAN ONE ENTRY FOR SAME ENS ID
        if len(group_list) < 2:
            continue

        # Initialize a flag to track if 'maximum' has been assigned within this group
        max_assigned = False

        # If no national id entries, just assign the maximum
        top_match = max(group_list, key=itemgetter('match_percentage'))['match_percentage']

        for entry in group_list:
            if entry['match_percentage'] == top_match and not max_assigned:
                update_entry = {"duplicate_in_session": DUPINSESSION.RETAIN}
                res = await update_for_ensid_svm_duplication(update_entry, entry["id"],session_id, session)
                max_assigned = True  # Ensure only one maximum is assigned
            else:
                update_entry = {"duplicate_in_session":  DUPINSESSION.REMOVE, "final_validation_status": FinalValidatedStatus.AUTO_REJECT}
                res = await update_for_ensid_svm_duplication(update_entry, entry["id"], session_id, session)

    return

