# http://127.0.0.1:8000/#/


from app.core.security.jwt import create_jwt_token
import requests
from app.core.analysis.report_generation_submodules.populate import *
from app.schemas.logger import logger

load_dotenv()
def remove_time_keys(obj):
    if isinstance(obj, dict):
        # Remove 'create_time' and 'update_time' if they exist
        obj.pop('create_time', None)
        obj.pop('update_time', None)
        # obj.pop('kpi_value', None)
        obj.pop('id', None)
        obj.pop('ens_id', None)
        obj.pop('session_id', None)
        # Recursively clean any nested dictionaries
        for key, value in obj.items():
            obj[key] = remove_time_keys(value)
    elif isinstance(obj, list):
        # Recursively clean any elements in the list
        for i in range(len(obj)):
            obj[i] = remove_time_keys(obj[i])
    return obj


async def report_generation_poc(data, session, diff_notification, annexure_from_diff, upload_to_blob: bool, save_locally: bool, ts_data=None):
    incoming_ens_id = data["ens_id"]
    session_id = data["session_id"]
    all_diff_code=list(diff_notification.keys())



    def get_day_with_suffix(day):
        if 11 <= day <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return f"{day}{suffix}"

    try:

        logger.info(f"====== Begin: Reports for supplier. Saving locally: {save_locally} ======")
        count = 0
        results = {}

        # Make sure the table that is referenced here has unique supplier records #TODO WHAT IS THIS FOR
        required_columns = ["name"]
        supplier_data = await get_dynamic_ens_data("upload_supplier_data", required_columns=required_columns,
                                                   ens_id=incoming_ens_id, session_id=session_id, session=session)
        if supplier_data:
            incoming_name = supplier_data[0]["name"]
        else:
            incoming_name = ''

        required_columns = ["google_image_name"]
        external_data = await get_dynamic_ens_data("external_supplier_data", required_columns=required_columns,
                                                   ens_id=incoming_ens_id, session_id=session_id, session=session)
        if external_data:
            google_image_name = external_data[0].get("google_image_name","")
        else:
            google_image_name = ''

        print("=-------external data", external_data)
        print("=---------image data", google_image_name)

        process_details = {
            "ens_id": incoming_ens_id,
            "supplier_name": incoming_name,
            "L2_supplier_name_validation": "",
            "local": {
                "save_locally": save_locally,
                "docx": "NA",
                "pdf": "NA"
            },
            "blob": {
                "upload_to_blob": upload_to_blob,
                "docx": "NA",
                "pdf": "NA"
            },
            "populate_sections": {
                "profile": "",
                "financial": "",
                "adverse_media": "",
                "entity_existance": "",
                "legal":"",
                "cyber_esg":""
            }
        }

        logger.info(f"--> Generating reports for ID: {incoming_ens_id}")

        # Format the date
        current_date = datetime.now()
        formatted_date = f"{get_day_with_suffix(current_date.day)} {current_date.strftime('%B')}, {current_date.year}"


        context = {}
        # sanctions = await sape_summary(data, session)
        #
        # bcf = await bcf_summary(data, session)
        #
        # sco = await state_ownership_summary(data, session)
        #
        # financials = await financials_summary(data, session)
        #
        # adverse_media = await adverse_media_summary(data, session)
        #
        # additional_indicators = await additional_indicators_summary(data, session)
        # regal = await legal_regulatory_summary(data, session)
        #
        # summary = await overall_summary(data, session, supplier_name=incoming_name)

        # static_entries = {
        #     'date': formatted_date,
        #     'risk_level': "Medium",
        #     'summary_of_findings': summary,
        #     'sanctions_summary': sanctions,
        #     'anti_summary': bcf,
        #     'gov_summary': sco,
        #     'financial_summary': financials,
        #     'adv_summary': adverse_media,
        #     'additional_indicators_summary': additional_indicators,
        #     'ral_summary': regal
        # }
        # context.update(static_entries)

        # Get ratings for all sections
        ratings_data = await get_dynamic_ens_data(
            "ovar",
            required_columns=["all"],
            ens_id=incoming_ens_id,
            session_id=session_id,
            session=session
        )

        if ratings_data:
            for row in ratings_data:
                if row.get("ens_id") == incoming_ens_id and row.get("session_id") == session_id:
                    if row.get("kpi_code") == "entity_existence" and row.get("kpi_area") == "theme_rating":
                        context["entity_existence_rating"] = row.get("kpi_rating", "No Alert")
                    elif row.get("kpi_code") == "legal" and row.get("kpi_area") == "theme_rating":
                        context["legal_rating"] = row.get("kpi_rating","No Alert")
                    elif row.get("kpi_code") == "financials" and row.get("kpi_area") == "theme_rating":
                        context["financial_rating"] = row.get("kpi_rating", "No Alert")
                    elif row.get("kpi_code") == "adverse_media" and row.get("kpi_area") == "theme_rating":
                        context["adverse_media_rating"] = row.get("kpi_rating", "No Alert")
                    elif row.get("kpi_code") == "cyber_esg" and row.get("kpi_area") == "theme_rating":
                        context["cyber_esg_rating"] = row.get("kpi_rating", "No Alert")
                    elif row.get("kpi_code") == "supplier" and row.get("kpi_area") == "overall_rating":
                        context["risk_level"] = row.get("kpi_rating", "No Alert")
        else:
            no_ratings = {
                "financial_rating": "None",
                "adverse_media_rating": "None",
                "legal_rating": "None",
                "entity_existence_rating": "None",
                "risk_level": "None"
            }
            context.update(no_ratings)

        context["name"] = incoming_name

        ############################################################################################################################

        # Profile Data
        profile_data = await populate_profile(incoming_ens_id=incoming_ens_id, incoming_session_id=session_id,
                                              session=session)
        context["name"] = profile_data["name"]
        context["google_image_name"]=google_image_name
        context["uploaded_name"] = profile_data["uploaded_name"]
        context["external_vendor_id"] = profile_data["external_vendor_id"]
        context["location"] = profile_data["location"]
        context["address"] = profile_data["address"]
        context["e_filing_status"] = profile_data["e_filing_status"]
        context["category"] = profile_data["category"]
        context["pan_id"] = profile_data["pan_id"]+" (PAN Number)"
        context["alias"] = profile_data["alias"]
        context["incorporation_date"] = profile_data["incorporation_date"]
        context["shareholders"] = profile_data["shareholders"]
        context["revenue"] = profile_data["revenue"]
        context["subsidiaries"] = profile_data["subsidiaries"]
        context["key_executives"] = profile_data["key_executives"]
        context["employee_count"] = profile_data["employee"]
        context["website"] = profile_data["website"]
        context["company_corporate_group"]=profile_data['corporate_group']
        context["identifier"]=profile_data["identifier"]
        context["identifier_type"]=profile_data["identifier_type"]

        # ========== ANNEXURE ===========
        try:
            annexure_data = await populate_annexure_data(annexure_from_diff, incoming_ens_id, session_id, session)
            context["annexure"] = annexure_data
            logger.info(f"Successfully populated {len(annexure_data)} annexure sections for ENS ID: {incoming_ens_id}")
        except Exception as e:
            logger.error(f"Error populating annexure data: {str(e)}")
            context["annexure"] = []

        ############################################################################################################################

        # Sanctions DataFrames
        try:
            data = await populate_legal(incoming_ens_id=incoming_ens_id, incoming_session_id=session_id,
                                            session=session)
            temp = data["legal"]
            if not temp.empty:
                legal_data = temp.to_dict(orient='records')
                legal_data= remove_time_keys(legal_data)
                context["legal_findings"] = True
                # for n in sape_data:
                #     kpi_code=n['kpi_code']
                #     if kpi_code in all_diff_code:
                #         # logger.debug(diff_notification[kpi_code] or 'xyz')
                #         details=n['kpi_details']
                #         for sentence in diff_notification[kpi_code]:
                #             if sentence in details:
                #                 details=details.replace(sentence,f'<p>{sentence}</p>')
                #         n['kpi_details']=details
                context["legal_data"] = legal_data
            else:
                context["legal_findings"] = False
            process_details["populate_sections"]["legal"] = "success"
        except Exception as e:
            tb = traceback.format_exc()
            process_details["populate_sections"]["legal"] = "failure"

        ############################################################################################################################

        try:
            data = await populate_other_adv_media(incoming_ens_id=incoming_ens_id, incoming_session_id=session_id,
                                        session=session)
            temp = data["adv_media"]
            if not temp.empty:
                media_data = temp.to_dict(orient='records')
                media_data = remove_time_keys(media_data)
                context["adverse_media_findings"] = True
                # for n in sape_data:
                #     kpi_code=n['kpi_code']
                #     if kpi_code in all_diff_code:
                #         # logger.debug(diff_notification[kpi_code] or 'xyz')
                #         details=n['kpi_details']
                #         for sentence in diff_notification[kpi_code]:
                #             if sentence in details:
                #                 details=details.replace(sentence,f'<p>{sentence}</p>')
                #         n['kpi_details']=details
                context["adverse_media_data"] = media_data
            else:
                context["adverse_media_findings"] = False
            process_details["populate_sections"]["adverse_media"] = "success"
        except Exception as e:
            tb = traceback.format_exc()
            process_details["populate_sections"]["adverse_media"] = "failure"


        ############################################################################################################################

        try:
            # Financials DataFrames
            financials_data_1 = await populate_financials_value(incoming_ens_id=incoming_ens_id,
                                                                incoming_session_id=session_id, session=session)
            financial_df_1 = financials_data_1["financial"]
            if not financial_df_1.empty:
                temp = financials_data_1["financial"]
                financial_data_1 = temp.to_dict(orient='records')
                financial_data_1 = remove_time_keys(financial_data_1)
                context["financial_findings"] = True
                # for n in financial_data_1:
                #     kpi_code=n['kpi_code']
                #     if kpi_code in all_diff_code:
                #         logger.debug(diff_notification[kpi_code] or 'xyz')
                #         details=n['kpi_details']
                #         for sentence in diff_notification[kpi_code]:
                #             if sentence in details:
                #                 details=details.replace(sentence,f'<p>{sentence}</p>')
                #         n['kpi_details']=details
                context["financial_data"] = financial_data_1
            else:
                context["financial_findings"] = False
            process_details["populate_sections"]["financial"] = "success"
        except Exception as e:
            tb = traceback.format_exc()
            process_details["populate_sections"]["financial"] = "failure"

        ############################################################################################################################

        try:
            # Entity Existance DataFrame
            ownership_data = await populate_entity(incoming_ens_id=incoming_ens_id, incoming_session_id=session_id,
                                                      session=session)
            state_ownership_df = ownership_data["entity_existence"]
            if not state_ownership_df.empty:
                temp = ownership_data["entity_existence"]
                sown_data = temp.to_dict(orient='records')
                sown_data = remove_time_keys(sown_data)
                context["entity_existence_findings"] = True
                # for n in sown_data:
                #     kpi_code=n['kpi_code']
                #     if kpi_code in all_diff_code:
                #         logger.debug(diff_notification[kpi_code] or 'xyz')
                #         details=n['kpi_details']
                #         for sentence in diff_notification[kpi_code]:
                #             if sentence in details:
                #                 details=details.replace(sentence,f'<p>{sentence}</p>')
                #         n['kpi_details']=details
                context["entity_existence_data"] = sown_data
            else:
                context["entity_existence_findings"] = False
            process_details["populate_sections"]["entity_existence"] = "success"
        except Exception as e:
            tb = traceback.format_exc()
            process_details["populate_sections"]["entity_existence"] = "failure"

        ############################################################################################################################

        try:
            # Cyber Esg DataFrame
            ownership_data = await populate_cybersecurity(incoming_ens_id=incoming_ens_id, incoming_session_id=session_id,
                                                      session=session)
            print("----cyber findings",ownership_data)
            state_ownership_df = ownership_data["cyber_esg"]
            if not state_ownership_df.empty:
                temp = ownership_data["cyber_esg"]
                sown_data = temp.to_dict(orient='records')
                sown_data = remove_time_keys(sown_data)
                context["cyber_esg_findings"] = True
                # for n in sown_data:
                #     kpi_code=n['kpi_code']
                #     if kpi_code in all_diff_code:
                #         logger.debug(diff_notification[kpi_code] or 'xyz')
                #         details=n['kpi_details']
                #         for sentence in diff_notification[kpi_code]:
                #             if sentence in details:
                #                 details=details.replace(sentence,f'<p>{sentence}</p>')
                #         n['kpi_details']=details
                context["cyber_esg_data"] = sown_data
            else:
                context["cyber_esg_data"] = False
            process_details["populate_sections"]["cyber_esg"] = "success"
        except Exception as e:
            tb = traceback.format_exc()
            process_details["populate_sections"]["cyber_esg"] = "failure"

        ############################################################################################################################

        # Fetch `ts_flag` from ts_data
        if ts_data:
            matching_entry = next((entry for entry in ts_data["results"] if entry["ens_id"] == incoming_ens_id), None)
            if matching_entry:
                process_details["L2_supplier_name_validation"] = matching_entry["verification_details"]["is_verified"]
                context['ts_flag'] = matching_entry["verification_details"]["is_verified"]
        else:
            process_details["L2_supplier_name_validation"] = False

        # doc.render(context)
        context["session_id"]=session_id
        context["ens_id"]=incoming_ens_id
        context["disable-regulator-and-legal"] = True
        #Call orbis engine endpoint
        # print("context", context)
        logger.info("Retrieving Orbis - Report Generation..")
        with open(f"123_{context.get("name")}.json", 'w')as file:
            json.dump(context,file,indent=2)
        try:
            # Generate JWT token
            jwt_token = create_jwt_token("orchestration", "analysis")
        except Exception as e:
            logger.error(f"Error generating JWT token: {e}")
            raise
        orbis_url = get_settings().urls.orbis_engine
        logger.debug(f"url { orbis_url}")
        url = f"{orbis_url}/api/v1/internal/report-generation-node"
        # Prepare headers with the JWT token
        headers = {
            "Authorization": f"Bearer {jwt_token.access_token}"
        }
        try:
            logger.debug("in try")
            response = requests.post(url, headers=headers, json=context)
            logger.debug("response of report %s", response.status_code)
            if response.status_code == 200:
                process_details["blob"]["pdf"] = "success"
                process_details["blob"]["docx"] = "success"
            else:
                process_details["blob"]["pdf"] = "failed"
                process_details["blob"]["docx"] = "failed"
            return process_details, response.status_code
        except:
            logger.error("in inner except")
            tb = traceback.format_exc()  # Capture the full traceback

            process_details = {
                "ens_id": incoming_ens_id,
                "supplier_name": incoming_name,
                "L2_supplier_name_validation": "",
                "error": f"ReportGenerationCode - {str(e)}"
            }

            logger.error(f"Process details: {process_details}")  # Use logger.error for exceptions

            return process_details, 500
    except Exception as e:
        logger.error("in outer except")
        tb = traceback.format_exc()  # Capture the full traceback
        logger.error(tb)

        process_details = {
            "ens_id": incoming_ens_id,
            "supplier_name": '',
            "L2_supplier_name_validation": "",
            "error": f"ReportGenerationCode - {str(e)}" # Add detailed traceback info
        }

        logger.error(f"Process details: {process_details}")  # Use logger.error for exceptions

        return process_details, 500