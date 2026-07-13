import json
import traceback
from app.core.utils.db_utils import *
from app.schemas.logger import logger
from datetime import datetime


async def financial_analysis(data, session):
    logger.info("Performing Financial Basics Analysis.... Started")

    kpi_area_module = "FSTB"
    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")

    try:
        # ---------- KPI template ----------
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "INFO",
            "kpi_details": "",
        }

        # ---------- KPI objects ----------
        FSTB2A = kpi_template.copy()  # Balance Sheet
        FSTB3A = kpi_template.copy()  # P&L

        FSTB2A["kpi_code"] = "FSTB2A"
        FSTB2A["kpi_definition"] = "Finance - Balance Sheet"

        FSTB3A["kpi_code"] = "FSTB3A"
        FSTB3A["kpi_definition"] = "Finance - Profit And Loss"

        # ---------- Fetch data ----------
        required_columns = [
            "financial_bs",
            "financial_ratios",
            "financial_cash_flow",
            "financial_pnl",
            "ratio_factors"
        ]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session,
        )

        if not retrieved_data:
            logger.warning("No external supplier data found for financial analysis")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        row = retrieved_data[0] or {}

        financial_ratios   = row.get("financial_ratios")   or {}
        financial_pnl      = row.get("financial_pnl")      or {}
        financial_bs       = row.get("financial_bs")       or {}
        financial_cash_flow = row.get("financial_cash_flow") or {}
        ratio_factors      = row.get("ratio_factors")      or {}

        # ---------- Helper to build KPI data (values in Lakhs) ----------
        def build_kpi_data(source_data: dict, required_fields: list[str]):
            result = []
            for field in required_fields:
                obj: dict[str, str | float | None] = {"factor": field.replace("_", " ").title() + " (₹ in Lakhs)"}
                entries = source_data.get(field) or []
                if isinstance(entries, list) and entries:
                    for x in entries:
                        year  = x.get("year")
                        value = x.get("value")
                        if year:
                            obj[str(year)] = to_lakhs(value)
                    result.append(obj)
            return result

        # ---------- Profit & Loss ----------
        pnl_fields = ["net_revenue", "profit_after_tax"]
        pnl_data = build_kpi_data(financial_pnl, pnl_fields)

        if pnl_data:
            FSTB3A["kpi_flag"]    = True
            FSTB3A["kpi_value"]   = json.dumps(pnl_data)
            FSTB3A["kpi_details"] = json.dumps(pnl_data)

        # ---------- Balance Sheet ----------
        bs_fields = [
            "total_current_assets",
            "total_other_non_current_assets",
            "net_fixed_assets",
            "total_current_liabilities",
            "total_non_current_liabilities",
            "total_equity",
        ]
        bs_data = build_kpi_data(financial_bs, bs_fields)

        if bs_data:
            FSTB2A["kpi_flag"]    = True
            FSTB2A["kpi_value"]   = json.dumps(bs_data)
            FSTB2A["kpi_details"] = json.dumps(bs_data)

        # ---------- Upsert KPIs ----------
        fstb_kpis = [FSTB2A, FSTB3A]

        await upsert_kpi(
            "finance",
            fstb_kpis,
            ens_id_value,
            session_id_value,
            session,
        )

        logger.info(f"{kpi_area_module} financial analysis completed successfully")

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "success",
            "info": "analysis_completed"
        }

    except Exception as e:
        logger.error(
            f"Financial analysis failed for ENS {ens_id_value}: {str(e)}",
            exc_info=True
        )
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "analysis_error"
        }

async def related_party_transaction(data, session):
    logger.info("Performing related party transaction Analysis.... Started")

    kpi_area_module = "FSTB"

    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")

    try:
        # ---- KPI template ----
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "",
            "kpi_details": "",
        }

        FSTB5A = kpi_template.copy()
        FSTB5A["kpi_code"] = "FSTB5A"
        FSTB5A["kpi_definition"] = "Finance - Related Party Transaction"
        FSTB5A["kpi_rating"] = "INFO"

        # ---- Fetch data ----
        required_columns = ["related_party_transaction"]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session
        )

        if not retrieved_data or not retrieved_data[0]:
            logger.warning("No external supplier data row found")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        transactions = retrieved_data[0].get("related_party_transaction")

        if not transactions or not isinstance(transactions, list):
            logger.info("No related party transaction data found")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        # ---- Helper: safe float conversion ----
        def safe_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        # ---- Clean & filter numeric amounts ----
        clean_transactions = [
            txn for txn in transactions
            if safe_float(txn.get("amount")) is not None
        ]

        if not clean_transactions:
            logger.info("All related party transaction amounts are masked or invalid")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_numeric_data"
            }

        # ---- Sort by amount DESC ----
        clean_transactions = sorted(
            clean_transactions,
            key=lambda x: safe_float(x.get("amount")),
            reverse=True
        )

        # ---- Prepare top 10 records ----
        new_data = []
        for txn in clean_transactions[:10]:
            new_data.append({
                "name": txn.get("legal_name", ""),
                "amount (₹ in Lakhs)": to_lakhs(txn.get("amount", 0)),
                "relationship": txn.get("relationship", ""),
                "type_of_transaction": txn.get("type_of_transaction", "")
            })

        # ---- Populate KPI ----
        FSTB5A["kpi_flag"] = True
        FSTB5A["kpi_value"] = json.dumps(new_data)
        FSTB5A["kpi_details"] = json.dumps(new_data)

        # ---- Save KPI ----
        await upsert_kpi(
            "finance",
            [FSTB5A],
            ens_id_value,
            session_id_value,
            session
        )

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "success",
            "info": "analysis_completed"
        }

    except Exception as e:
        logger.error(f"Related_party_transaction analysis failed - {str(e)}", exc_info=True)
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "analysis_error"
        }

async def credit_risk_score_analysis(data, session):
    logger.info("Performing Credit Risk Score Analysis.... Started")

    kpi_area_module = "FSTB"

    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")
    try:
        # ---------- KPI template ----------
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "INFO",
            "kpi_details": ""
        }

        # ---------- KPI object ----------
        FSTB6A = kpi_template.copy()
        FSTB6A["kpi_code"] = "FSTB6A"
        FSTB6A["kpi_definition"] = "Finance - Credit Risk Analysis"

        # ---------- Fetch data ----------
        required_columns = ["credit_rating"]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session
        )

        if not retrieved_data:
            logger.warning("No external supplier data row found for credit risk analysis")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        credit_data = retrieved_data[0].get("credit_rating")

        if not credit_data or not isinstance(credit_data, list):
            logger.info("No credit rating data available")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        # ---------- Safe sorting (newest first) ----------
        def safe_rating_date(entry):
            return entry.get("rating_date") or ""

        sorted_data = sorted(
            credit_data,
            key=safe_rating_date,
            reverse=True
        )

        # ---------- Take latest 10 records ----------
        new_list_of_credit_scores = []
        for credit in sorted_data[:10]:
            new_list_of_credit_scores.append({
                "amount (₹ in Lakhs)": to_lakhs(credit.get("amount")),
                "rating": credit.get("rating"),
                "rating_agency": credit.get("rating_agency"),
                "rating_date": format_date(credit.get("rating_date")),
                "type_of_loan": credit.get("type_of_loan")
            })

        if not new_list_of_credit_scores:
            logger.info("Credit rating data present but no usable records")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_valid_records"
            }

        # ---------- Populate KPI ----------
        FSTB6A["kpi_flag"] = True
        FSTB6A["kpi_value"] = json.dumps(new_list_of_credit_scores)
        FSTB6A["kpi_details"] = json.dumps(new_list_of_credit_scores)

        # ---------- Persist KPI ----------
        await upsert_kpi(
            "finance",
            [FSTB6A],
            ens_id_value,
            session_id_value,
            session
        )

        logger.info("Credit Risk Score Analysis completed successfully")

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "success",
            "info": "analysis_completed"
        }

    except Exception as e:
        logger.error(
            f"Credit Risk Score Analysis failed for ENS {ens_id_value}: {str(e)}",
            exc_info=True
        )
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "analysis_error"
        }


async def gst_registration_analysis(data, session):
    logger.info("Performing GST Filing Analysis.... Started")

    kpi_area_module = "FSTB"
    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")

    try:
        # ---------- KPI template ----------
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "INFO",
            "kpi_details": ""
        }

        # ---------- KPI object ----------
        FSTB7A = kpi_template.copy()
        FSTB7A["kpi_code"] = "FSTB7A"
        FSTB7A["kpi_definition"] = "Finance - GST Registration Analysis"

        # ---------- Fetch data ----------
        required_columns = ["gst_details", "uploaded_client_onboarding_date"]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session
        )

        if not retrieved_data:
            logger.warning("No external supplier data row found for GST registration analysis")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        gst_data = retrieved_data[0].get("gst_details")
        client_onboarding_date = retrieved_data[0].get("uploaded_client_onboarding_date")

        if not gst_data or not isinstance(gst_data, list):
            logger.info("No GST registration details available")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        # ---------- Sort GST data (earliest first) ----------
        gst_data = sort_all_gstins_filings(
            gst_data,
            latest_first=False,
            limit=10
        )

        active_gst_list = []
        counter = 0
        kpi_rating = 'Low'
        earliest_gst_date = None

        for gst in gst_data:
            status = str(gst.get("status", "")).lower()
            if status == "active":
                gst_registration_date = gst.get("date_of_registration")
                active_gst_list.append({
                    "gst_in": gst.get("gstin"),
                    "state_of_registration": gst.get("state"),
                    "filing_timeliness": gst.get("filing_timeliness"),
                    "date_of_registration": format_date(gst_registration_date)
                })

                # Capture earliest GST registration date (first in sorted list)
                if earliest_gst_date is None:
                    earliest_gst_date = gst_registration_date

                if gst.get("filing_timeliness", '') and not gst.get("filing_timeliness").lower() == 'filed on time':
                    counter += 1
                    if counter < 5:
                        kpi_rating = 'Medium'
                    else:
                        kpi_rating = 'High'

        if not active_gst_list:
            logger.info("GST data present but no ACTIVE registrations found")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_active_gst_found"
            }

        # ---------- Risk Analysis: Check if GST registration is within ±2 months of onboarding ----------
        if earliest_gst_date and client_onboarding_date:
            gst_date = parse_date_safe(earliest_gst_date)
            onboarding_date = parse_date_safe(client_onboarding_date)

            # Ignore if GST registration is before July 2017 (legacy/initial GST)
            if gst_date and onboarding_date and gst_date >= datetime(2017, 7, 1):
                date_diff_days = abs((gst_date - onboarding_date).days)

                # ±2 months = ±60 days
                if date_diff_days <= 60:
                    kpi_rating = 'High'
                    logger.info(
                        f"GST registration within ±2 months of onboarding ({date_diff_days} days). Rating set to High.")

        # ---------- Populate KPI ----------
        FSTB7A["kpi_flag"] = True
        FSTB7A["kpi_rating"] = kpi_rating
        FSTB7A["kpi_value"] = json.dumps(active_gst_list)
        FSTB7A["kpi_details"] = json.dumps(active_gst_list)

        # ---------- Persist KPI ----------
        await upsert_kpi(
            "finance",
            [FSTB7A],
            ens_id_value,
            session_id_value,
            session
        )

        logger.info("GST Registration Analysis completed successfully")

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "success",
            "info": "analysis_completed"
        }

    except Exception as e:
        logger.error(
            f"GST Registration Analysis failed for ENS {ens_id_value}: {str(e)}",
            exc_info=True
        )
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "analysis_error"
        }

async def msme_payment_analysis(data, session):
    logger.info("Performing MSME Payment Analysis.... Started")

    kpi_area_module = "FSTB"
    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")
    try:
        # ---------- KPI template ----------
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "INFO",
            "kpi_details": "",
        }

        # ---------- KPI object ----------
        FSTB8A = kpi_template.copy()
        FSTB8A["kpi_code"] = "FSTB8A"
        FSTB8A["kpi_definition"] = "Finance - MSME Payment Analysis"

        # ---------- Fetch data ----------
        required_columns = ["msme"]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session
        )

        if not retrieved_data:
            logger.warning("No external supplier data row found for MSME payment analysis")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        msme_data = retrieved_data[0].get("msme")

        if not msme_data or not isinstance(msme_data, list):
            logger.info("No MSME payment details available")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        # ---------- Optional: basic validation / normalization ----------
        clean_msme_data = []
        for entry in msme_data:
            if isinstance(entry, dict):
                obj={}
                obj['period']=entry.get("period") or '-'
                obj['Amount (₹ in Lakhs)']=to_lakhs(entry.get("amount")) or 0
                clean_msme_data.append(obj)

        if not clean_msme_data:
            logger.info("MSME payment data present but no valid records found")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_valid_records"
            }

        # ---------- Populate KPI ----------
        FSTB8A["kpi_flag"] = True
        FSTB8A["kpi_value"] = json.dumps(clean_msme_data)
        FSTB8A["kpi_details"] = json.dumps(clean_msme_data)

        # ---------- Persist KPI ----------
        await upsert_kpi(
            "finance",
            [FSTB8A],
            ens_id_value,
            session_id_value,
            session
        )

        logger.info("MSME Payment Analysis completed successfully")

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "success",
            "info": "analysis_completed"
        }

    except Exception as e:
        logger.error(
            f"Financial MSME Payment Analysis failed for ENS {ens_id_value}: {str(e)}",
            exc_info=True
        )
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "analysis_error"
        }

async def z_altman_score_analysis(data, session):
    logger.info("Performing Z Altman Score Analysis.... Started")

    kpi_area_module = "FSTB"

    if not isinstance(data, dict):
        logger.error("Invalid input data received in z_altman_score_analysis")
        return {
            "ens_id": None,
            "module": kpi_area_module,
            "status": "failure",
            "info": "invalid_input"
        }

    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")

    try:
        # ---------- KPI template ----------
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "INFO",
            "kpi_details": "",
        }

        # ---------- KPI object ----------
        FSTB9A = kpi_template.copy()
        FSTB9A["kpi_code"] = "FSTB9A"
        FSTB9A["kpi_definition"] = "Finance - Z Altman Score Analysis"

        # ---------- Fetch data ----------
        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            ["z_altman_factors"],
            ens_id_value,
            session_id_value,
            session
        )

        rows = await get_dynamic_ens_data(
            "supplier_master_data",
            ["uploaded_client_z_altman_type"],
            ens_id_value,
            session_id_value,
            session,
        )

        if not retrieved_data or not rows:
            logger.warning("No external supplier data found for Z Altman analysis")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        factors = retrieved_data[0].get("z_altman_factors")
        raw_z_altman_type = rows[0].get("uploaded_client_z_altman_type")

        if not factors or not isinstance(factors, dict):
            logger.info("Z Altman - Factors missing or invalid")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        # ---------- Helpers ----------
        def normalize_type(value):
            if value is None:
                return None
            value = str(value).strip().lower()
            return value if value else None

        def to_float(value):
            """
            Safely convert numeric values to float.
            Returns None if invalid.
            """
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def get_rating(score):
            if score <= 1.8:
                return "High"
            elif score <= 2.9:
                return "Medium"
            return "Low"

        def rating_rank(rating):
            rank_map = {
                "Low": 1,
                "Medium": 2,
                "High": 3
            }
            return rank_map.get(rating, 0)

        # ---------- Weights ----------
        WEIGHTS = {
            "trading": (6.56, 3.26, 6.72, 1.05, 0.0),
            "manufacturing": (1.2, 1.4, 3.3, 0.6, 1.0),
        }

        # ---------- Extract + sanitize ----------
        total_assets = to_float(factors.get("total_assets"))
        working_capital = to_float(factors.get("working_capital"))
        retained_earnings = to_float(factors.get("retained_earnings"))
        ebit = to_float(factors.get("ebit"))
        total_equity = to_float(factors.get("total_equity"))
        total_liabilities = to_float(factors.get("total_liabilities"))
        sales = to_float(factors.get("sales"))

        if sales is None:
            sales = 0.0

        # ---------- Validate ----------
        required = {
            "total_assets": total_assets,
            "working_capital": working_capital,
            "retained_earnings": retained_earnings,
            "ebit": ebit,
            "total_equity": total_equity,
            "total_liabilities": total_liabilities,
        }

        missing_fields = [key for key, value in required.items() if value is None]
        if missing_fields:
            logger.info(f"Z Altman - Missing required parameters: {missing_fields}")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "missing_required_parameters"
            }

        if total_assets == 0:
            logger.error("Z Altman - total_assets is zero, cannot divide")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "invalid_total_assets"
            }

        if total_liabilities == 0:
            logger.error("Z Altman - total_liabilities is zero, cannot divide")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "invalid_total_liabilities"
            }

        # ---------- Ratios ----------
        wc_ta = working_capital / total_assets
        re_ta = retained_earnings / total_assets
        ebit_ta = ebit / total_assets
        eq_tl = total_equity / total_liabilities
        sales_ta = sales / total_assets

        def calculate_z_score(model_type):
            w = WEIGHTS.get(model_type)
            if not w:
                return None, None

            z_score = round(
                wc_ta * w[0] +
                re_ta * w[1] +
                ebit_ta * w[2] +
                eq_tl * w[3] +
                sales_ta * w[4],
                2
            )

            z_result = {
                "parameter": f"Altman Z Score ({model_type})",
                "calculation": z_score
            }

            return z_result, get_rating(z_score)

        z_altman_type = normalize_type(raw_z_altman_type)
        z_results = []

        if z_altman_type in WEIGHTS:
            result, kpi_rating = calculate_z_score(z_altman_type)
            if not result:
                logger.error(f"Z Altman - Failed calculation for type: {z_altman_type}")
                return {
                    "ens_id": ens_id_value,
                    "module": kpi_area_module,
                    "status": "failure",
                    "info": "calculation_error"
                }
            z_results.append(result)

        elif not z_altman_type:
            trading_result, trading_rating = calculate_z_score("trading")
            manufacturing_result, manufacturing_rating = calculate_z_score("manufacturing")

            if trading_result:
                z_results.append(trading_result)

            if manufacturing_result:
                z_results.append(manufacturing_result)

            if not z_results:
                logger.error("Z Altman - Could not calculate any score")
                return {
                    "ens_id": ens_id_value,
                    "module": kpi_area_module,
                    "status": "failure",
                    "info": "calculation_error"
                }

            kpi_rating = max(
                [r for r in [trading_rating, manufacturing_rating] if r],
                key=rating_rank
            )
        else:
            logger.error(f"Unsupported Z Altman type received: {raw_z_altman_type}")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "invalid_z_altman_type"
            }

        # ---------- KPI assignment ----------
        FSTB9A["kpi_flag"] = True
        FSTB9A["kpi_rating"] = kpi_rating
        FSTB9A["kpi_value"] = json.dumps(z_results)
        FSTB9A["kpi_details"] = json.dumps(z_results)

        # ---------- Persist KPI ----------
        await upsert_kpi(
            "finance",
            [FSTB9A],
            ens_id_value,
            session_id_value,
            session
        )

        logger.info("Z Altman Score Analysis completed successfully")

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "success",
            "info": "analysis_completed"
        }

    except Exception as e:
        logger.error(
            f"Z Altman Score Analysis failed for ENS {ens_id_value}: {str(e)}",
            exc_info=True
        )
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "analysis_error"
        }

def calculate_financial_ratios(ratio_factors):

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────
    def safe_divide(n, d):
        if n is None or d in (None, 0):
            return None
        return round(n / d, 2)

    def safe_divide_pct(n, d):
        """Returns ratio as a percentage rounded to 2 decimal places."""
        if n is None or d in (None, 0):
            return None
        return round((n / d) * 100, 2)

    def extract(field, year):
        if not isinstance(field, list):
            return None
        for entry in field:
            if str(entry.get("year")) == str(year):
                return entry.get("value")
        return None

    def get_all_years(data):
        years = set()
        for v in data.values():
            if isinstance(v, list):
                for e in v:
                    if "year" in e:
                        years.add(e["year"])
        return sorted(years)

    years = get_all_years(ratio_factors)

    # ──────────────────────────────────────────────
    # Output buckets
    # ──────────────────────────────────────────────
    output = {
        "profitability": [],
        "liquidity": [],
        "operating": [],
        "capital_structure": []
    }

    # Storage for ratio values
    ratios = {
        "Profit Margin Ratio (%)": {},
        "EBITDA Margin (%)": {},
        "ROE (%)": {},
        "ROCE (%)": {},
        "ROA (%)": {},
        "Current Ratio": {},
        "Quick Ratio": {},
        "Cash Ratio": {},
        "Asset Turnover Ratio": {},
        "Inventory Days": {},
        "Debtor Days": {},
        "Creditor Days": {},
        "Debt Equity Ratio": {},
        "Interest Coverage Ratio": {}
    }

    # ──────────────────────────────────────────────
    # Calculations per year
    # ──────────────────────────────────────────────
    for year in years:

        # Balance Sheet
        tca = extract(ratio_factors.get("total_current_assets"), year)
        tcl = extract(ratio_factors.get("total_current_liabilities"), year)
        assets = extract(ratio_factors.get("given_assets_total"), year)
        equity = extract(ratio_factors.get("total_equity"), year)
        debt = extract(ratio_factors.get("total_debt"), year)

        inventories = extract(ratio_factors.get("inventories"), year)
        receivables = extract(ratio_factors.get("trade_receivables"), year)
        payables = extract(ratio_factors.get("trade_payables"), year)

        cash_and_bank_balances = extract(ratio_factors.get("cash_and_bank_balances"), year)
        other_current_assets = extract(ratio_factors.get("other_current_assets"), year)
        share_capital = extract(ratio_factors.get("share_capital"), year)
        reserves_and_surplus = extract(ratio_factors.get("reserves_and_surplus"), year)
        total_non_current_liabilities = extract(ratio_factors.get("total_non_current_liabilities"), year)  # ← here

        # P&L
        revenue = extract(ratio_factors.get("net_revenue"), year)
        pat = extract(ratio_factors.get("profit_after_tax"), year)
        pbt = extract(ratio_factors.get("profit_before_tax"), year)
        interest = extract(ratio_factors.get("interest"), year)
        tax = extract(ratio_factors.get("income_tax"), year)
        dep = extract(ratio_factors.get("depreciation"), year)

        # Cash Flow
        cfo = extract(
            ratio_factors.get("cash_flows_from_used_in_operating_activities"),
            year
        )

        # COGS construction
        cost_of_materials = extract(
            ratio_factors.get("total_cost_of_materials_consumed"),
            year
        )
        purchases_stock = extract(
            ratio_factors.get("total_purchases_of_stock_in_trade"),
            year
        )
        change_inventory = extract(
            ratio_factors.get("total_changes_in_inventories_or_finished_goods"),
            year
        )

        cogs = (
            cost_of_materials + purchases_stock + change_inventory
            if None not in (cost_of_materials, purchases_stock, change_inventory)
            else None
        )

        # Derived
        ebitda = (
            pat + interest + tax + dep
            if None not in (pat, interest, tax, dep)
            else None
        )

        pbit = (
            pbt + interest
            if None not in (pbt, interest)
            else None
        )

        # quick_assets = (
        #     tca - inventories
        #     if None not in (tca, inventories)
        #     else None
        # )
        quick_assets = (
            tca - inventories - other_current_assets #todo
            if None not in (tca, inventories, other_current_assets)
            else None
        )

        capital_employed = (
            assets - tcl
            if None not in (assets, tcl)
            else None
        )

        shareholders_equity = (
            share_capital + reserves_and_surplus
            if None not in (share_capital, reserves_and_surplus)
            else None
        )

        total_liabilities = (
            tcl + total_non_current_liabilities
            if None not in (tcl, total_non_current_liabilities)
            else None
        )

        # ──────────────────────────────────────────────
        # Store ratios
        # ──────────────────────────────────────────────

        # Profitability — all as percentages (%) rounded to 2 decimal places
        ratios["Profit Margin Ratio (%)"][year]  = safe_divide_pct(pat, revenue)
        ratios["EBITDA Margin (%)"][year]        = safe_divide_pct(ebitda, revenue)
        # ratios["ROE (%)"][year]                  = safe_divide_pct(pat, equity)
        ratios["ROE (%)"][year]                  = safe_divide(pat, shareholders_equity)
        ratios["ROCE (%)"][year]                 = safe_divide_pct(pbit, capital_employed)
        ratios["ROA (%)"][year]                  = safe_divide_pct(pat, assets)

        # Liquidity — 2 decimal places
        ratios["Current Ratio"][year] = safe_divide(tca, tcl)
        ratios["Quick Ratio"][year]   = safe_divide(quick_assets, tcl)
        # ratios["Cash Ratio"][year]    = safe_divide(cfo, tcl)
        ratios["Cash Ratio"][year] = safe_divide(cash_and_bank_balances, tcl)

        # Operating — 2 decimal places
        ratios["Asset Turnover Ratio"][year] = safe_divide(revenue, assets)

        # Operating Cycle Days — absolute whole numbers
        ratios["Inventory Days"][year] = (
            abs(round((inventories / cogs) * 365))
            if inventories is not None and cogs not in (None, 0)
            else None
        )

        ratios["Debtor Days"][year] = (
            abs(round((receivables / revenue) * 365))
            if receivables is not None and revenue not in (None, 0)
            else None
        )

        ratios["Creditor Days"][year] = (
            abs(round((payables / cogs) * 365))
            if payables is not None and cogs not in (None, 0)
            else None
        )

        # Capital Structure — 2 decimal places
        ratios["Debt Equity Ratio"][year] = safe_divide(total_liabilities, shareholders_equity)
        ratios["Interest Coverage Ratio"][year] = safe_divide(ebitda, interest)

    # ──────────────────────────────────────────────
    # Group ratios
    # ──────────────────────────────────────────────
    def add(section, names):
        for n in names:
            if any(v is not None for v in ratios[n].values()):
                output[section].append({
                    "factor": n,
                    **ratios[n]
                })

    add("profitability", [
        "Profit Margin Ratio (%)",
        "EBITDA Margin (%)",
        "ROE (%)",
        "ROCE (%)",
        "ROA (%)"
    ])

    add("liquidity", [
        "Current Ratio",
        "Quick Ratio",
        "Cash Ratio"
    ])

    add("operating", [
        "Inventory Days",
        "Debtor Days",
        "Creditor Days",
        "Asset Turnover Ratio"
    ])

    add("capital_structure", [
        "Debt Equity Ratio",
        "Interest Coverage Ratio"
    ])

    return output

async def financial_ratio_analysis(data, session):
    logger.info("Performing Financial Basics Analysis.... Started")

    kpi_area_module = "FSTB"
    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")

    try:
        # ---------- KPI template ----------
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "INFO",
            "kpi_details": "",
        }

        # ---------- KPI objects ----------
        FSTB1B = kpi_template.copy()
        FSTB1C = kpi_template.copy()
        FSTB1D = kpi_template.copy()
        FSTB1E = kpi_template.copy()

        FSTB1B["kpi_code"] = "FSTB1B"
        FSTB1B["kpi_definition"] = "Finance - Profitability Analysis"

        FSTB1C["kpi_code"] = "FSTB1C"
        FSTB1C["kpi_definition"] = "Finance - Liquidity Analysis"

        FSTB1D["kpi_code"] = "FSTB1D"
        FSTB1D["kpi_definition"] = "Finance - Operating Cycle"

        FSTB1E["kpi_code"] = "FSTB1E"
        FSTB1E["kpi_definition"] = "Finance - Capital Structure"

        # ---------- Fetch data ----------
        required_columns = [
            "ratio_factors"
        ]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session,
        )

        if not retrieved_data:
            logger.warning("No external supplier data found for financial analysis")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        row = retrieved_data[0] or {}
        ratio_factors = row.get("ratio_factors") or {}

        ratio_data = calculate_financial_ratios(ratio_factors)


        if ratio_data:

            if ratio_data.get("profitability"):
                FSTB1B["kpi_flag"] = True
                FSTB1B["kpi_rating"] = rate_profitability(ratio_data["profitability"])
                FSTB1B["kpi_value"] = json.dumps(ratio_data["profitability"])
                FSTB1B["kpi_details"] = json.dumps(ratio_data["profitability"])

            if ratio_data.get("liquidity"):
                FSTB1C["kpi_flag"] = True
                FSTB1C["kpi_rating"] = rate_liquidity(ratio_data["liquidity"])
                FSTB1C["kpi_value"] = json.dumps(ratio_data["liquidity"])
                FSTB1C["kpi_details"] = json.dumps(ratio_data["liquidity"])

            if ratio_data.get("operating"):
                FSTB1D["kpi_flag"] = True
                FSTB1D["kpi_rating"] = rate_operating(ratio_data["operating"])
                FSTB1D["kpi_value"] = json.dumps(ratio_data["operating"])
                FSTB1D["kpi_details"] = json.dumps(ratio_data["operating"])

            if ratio_data.get("capital_structure"):
                FSTB1E["kpi_flag"] = True
                FSTB1E["kpi_rating"] = rate_capital_structure(ratio_data["capital_structure"])
                FSTB1E["kpi_value"] = json.dumps(ratio_data["capital_structure"])
                FSTB1E["kpi_details"] = json.dumps(ratio_data["capital_structure"])



        # ---------- Persist KPIs ----------
        fstb_kpis = [FSTB1B, FSTB1C, FSTB1E, FSTB1D]

        await upsert_kpi(
            "finance",
            fstb_kpis,
            ens_id_value,
            session_id_value,
            session,
        )

        logger.info(f"{kpi_area_module} financial analysis completed successfully")

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "success",
            "info": "analysis_completed"
        }

    except Exception as e:
        logger.error(
            f"Financial analysis failed for ENS {ens_id_value}: {str(e)}",
            exc_info=True
        )
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "analysis_error"
        }

def get_year_values(ratio_entry):
    values = []
    for k, v in ratio_entry.items():
        if k != "factor" and v is not None:
            values.append((int(k), v))
    values.sort()
    return [v for _, v in values]

def detect_trend(values):
    if len(values) < 2:
        return "fluctuating"

    inc = all(values[i] <= values[i + 1] for i in range(len(values) - 1))
    dec = all(values[i] >= values[i + 1] for i in range(len(values) - 1))

    if inc:
        return "increasing"
    if dec:
        return "decreasing"
    return "fluctuating"

def latest_value(values):
    return values[-1] if values else None

def rate_profitability(data):
    trends = []

    for r in data:
        if r["factor"] in [
            "Profit Margin Ratio",
            "EBITDA Margin (%)",
            "ROA",
            "ROCE",
        ]:
            values = get_year_values(r)
            trends.append(detect_trend(values))

    if all(t == "increasing" for t in trends):
        return "Low"
    if any(t == "decreasing" for t in trends):
        return "High"
    return "Medium"

def rate_liquidity(data):
    cr = qr = cash = None
    cr_trend = qr_trend = "fluctuating"

    for r in data:
        values = get_year_values(r)
        lv = latest_value(values)

        if r["factor"] == "Current Ratio":
            cr, cr_trend = lv, detect_trend(values)
        if r["factor"] == "Quick Ratio":
            qr, qr_trend = lv, detect_trend(values)
        if r["factor"] == "Cash Ratio":
            cash = lv

    if (cr and cr >= 2) and (qr and qr >= 1) and (cash and cash >= 0.5):
        return "Low"

    if (
        (cr_trend == "decreasing" and cr and cr < 2)
        or (qr_trend == "decreasing" and qr and qr < 1)
        or (cash is not None and cash < 0.2)
    ):
        return "High"

    return "Medium"

def rate_operating(data):
    days_trends = []
    atr = None

    for r in data:
        values = get_year_values(r)
        if r["factor"] in ["Inventory Days", "Debtor Days", "Creditor Days"]:
            days_trends.append(detect_trend(values))
        if r["factor"] == "Asset Turnover Ratio":
            atr = latest_value(values)

    if all(t == "decreasing" for t in days_trends) and atr and atr >= 2.5:
        return "Low"

    if any(t == "increasing" for t in days_trends) and (not atr or atr < 2.5):
        return "High"

    return "Medium"

def rate_capital_structure(data):
    icr = de = None
    icr_trend = "fluctuating"

    for r in data:
        values = get_year_values(r)
        if r["factor"] == "Interest Coverage Ratio":
            icr = latest_value(values)
            icr_trend = detect_trend(values)
        if r["factor"] == "Debt Equity Ratio":
            de = latest_value(values)

    if icr and icr >= 2.5 and de is not None and de < 0.5:
        return "Low"

    if (icr_trend in ["decreasing", "fluctuating"] and icr and icr < 2.5) or (
        de and de > 2
    ):
        return "High"

    return "Medium"

def sort_all_gstins_filings(gst_data, latest_first=True, limit=None):
    """
    Safely sort filings for all GSTIN records.
    """
    result = []

    def sort_filings_by_date(gst_record, latest_first=True, limit=None):
        """
        Sort filings inside a single GSTIN record safely.
        """
        filings = gst_record.get("filings", [])

        valid_filings = [
            f for f in filings
            if parse_date_safe(f.get("date_of_filing")) is not None
        ]

        sorted_filings = sorted(
            valid_filings,
            key=lambda f: parse_date_safe(f.get("date_of_filing")),
            reverse=latest_first
        )

        if limit:
            return sorted_filings[:limit]

        return sorted_filings

    for gst in gst_data:
        gst_copy = gst.copy()
        gst_copy["filings"] = sort_filings_by_date(
            gst,
            latest_first=latest_first,
            limit=limit
        )
        result.append(gst_copy)

    return result

def parse_date_safe(date_str):
    """
    Safely parse YYYY-MM-DD date strings.
    Returns None if parsing fails.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
 # ---------- Helper: convert raw value to Lakhs ----------
def to_lakhs(value):
    """Converts a numeric value to Lakhs (÷ 1,00,000), rounded to 2 decimal places."""
    if value is None:
        return None
    try:
        return round(float(value) / 100000, 2)
    except (TypeError, ValueError):
        return None

async def msme_analysis(data, retrieved_data, session):
    logger.info("Performing MSME Analysis...")

    kpi_area_module = "FSTB"

    if not isinstance(data, dict):
        logger.error("Invalid input data received in msme_analysis")
        return []

    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")
    identifier = data.get("identifier")
    client_msme_status = data.get("client_msme_status")

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

        FSTB10A = kpi_template.copy()
        FSTB10A["kpi_code"] = "FSTB10A"
        FSTB10A["kpi_definition"] = "Finance - MSME Registration Status"

        if not retrieved_data:
            logger.info("MSME Analysis... No data found")
            return []

        data1 = retrieved_data.get("data", {})
        msme_status = data1.get("msme_status")

        def normalize_msme_status(value):
            if value is None:
                return ""
            return str(value).strip().lower()

        def format_msme_status(value):
            if value is None:
                return ""
            return str(value).strip().replace("_", " ").title()

        verified_status = normalize_msme_status(msme_status)
        client_status = normalize_msme_status(client_msme_status)

        verified_is_msme = verified_status == "already_registered"
        client_is_msme = client_status == "already_registered"
        client_status_unknown = client_status == ""

        # KPI value payload (for UI / audit)
        kpi_value = [
            {
                "factor": "MSME Status (Verified)",
                "value": format_msme_status(msme_status),
            },
            {
                "factor": "MSME Status (Client Database)",
                "value": format_msme_status(client_msme_status),
            }
        ]

        # Rating mapping:
        # Green  -> Low    -> verified MSME status matches client database
        # Yellow -> Medium -> vendor not MSME, client says MSME
        # Red    -> High   -> vendor MSME, client says not MSME
        # Unknown client status -> Medium

        if client_status_unknown:
            kpi_rating = "Medium"
            reason = "Client MSME status is unknown"

        elif verified_status == client_status:
            kpi_rating = "Low"
            reason = "Client MSME status matches with verified MSME status"

        elif not verified_is_msme and client_is_msme:
            kpi_rating = "Medium"
            reason = "Vendor is not MSME, but client database marks vendor as MSME"

        elif verified_is_msme and not client_is_msme:
            kpi_rating = "High"
            reason = "Vendor is MSME, but client database marks vendor as not MSME"

        else:
            kpi_rating = "Medium"
            reason = "MSME status unavailable or could not be confidently matched"

        FSTB10A["kpi_flag"] = True
        FSTB10A["kpi_rating"] = kpi_rating

        kpi_value.append(
            {
                "factor": "Reason",
                "value": reason,
            }
        )

        FSTB10A["kpi_value"] = json.dumps(kpi_value)
        FSTB10A["kpi_details"] = json.dumps(kpi_value)

        await upsert_kpi(
            "finance",
            [FSTB10A],
            ens_id_value,
            session_id_value,
            session,
        )

        logger.info(
            f"MSME Analysis... Completed | Rating={kpi_rating} | Status={format_msme_status(msme_status)}"
        )
        return []

    except Exception as e:
        traceback.print_exc()
        logger.error(f"MSME Analysis failed: {str(e)}", exc_info=True)
        return []


def format_date(date_val):
    if date_val is None:
        return None

    # If it's already a datetime/date object
    if isinstance(date_val, datetime):
        return date_val.strftime("%d.%m.%y")

    # If it's a string — try to parse it
    if isinstance(date_val, str):
        date_val = date_val.strip()
        if not date_val:
            return None
        # Try common formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                d = datetime.strptime(date_val, fmt)
                return d.strftime("%d.%m.%y")
            except ValueError:
                continue
        # Could not parse — return as-is
        return date_val

    # If it's a number (epoch timestamp)
    if isinstance(date_val, (int, float)):
        try:
            d = datetime.fromtimestamp(date_val)
            return d.strftime("%d.%m.%y")
        except Exception:
            return None

    # Unknown type — return as-is
    return str(date_val)


async def epfo_analysis(data, session):
    logger.info("Performing EPFO Analysis.... Started")

    kpi_area_module = "FSTB"
    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")
    try:
        # ---------- KPI template ----------
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "INFO",
            "kpi_details": "",
        }

        # ---------- KPI object ----------
        FSTB13A = kpi_template.copy()
        FSTB13A["kpi_code"] = "FSTB13A"
        FSTB13A["kpi_definition"] = "Finance - EPFO Registration"

        # ---------- Fetch data ----------
        required_columns = ["epfo"]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session
        )

        if not retrieved_data:
            logger.warning("No external supplier data row found for MSME payment analysis")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        epfo_data = retrieved_data[0].get("epfo")

        if not epfo_data or not isinstance(epfo_data, list):
            logger.info("No EPFO details available")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        # ---------- Optional: basic validation / normalization ----------
        clean_epfo_data = []
        for entry in epfo_data:
            for k, v in entry.items():
                if k.lower() != "filing_details":
                    clean_epfo_data.append({'Parameter': k.replace("_", " ").title(), 'Value': v})

        if not clean_epfo_data:
            logger.info("EPFO present but no valid records found")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_valid_records"
            }

        # ---------- Populate KPI ----------
        FSTB13A["kpi_flag"] = True
        FSTB13A["kpi_value"] = json.dumps(clean_epfo_data)
        FSTB13A["kpi_details"] = json.dumps(clean_epfo_data)

        # ---------- Persist KPI ----------
        await upsert_kpi(
            "finance",
            [FSTB13A],
            ens_id_value,
            session_id_value,
            session
        )

        logger.info("EPFO Analysis completed successfully")

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "success",
            "info": "analysis_completed"
        }

    except Exception as e:
        logger.error(
            f"EPFO Analysis failed for ENS {ens_id_value}: {str(e)}",
            exc_info=True
        )
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "analysis_error"
        }

async def auditor_comment_analysis(data, session):
    logger.info("Performing Auditor Comment Analysis.... Started")

    kpi_area_module = "FSTB"
    ens_id_value = data.get("ens_id")
    session_id_value = data.get("session_id")
    try:
        # ---------- KPI template ----------
        kpi_template = {
            "kpi_area": kpi_area_module,
            "kpi_code": "",
            "kpi_definition": "",
            "kpi_flag": False,
            "kpi_value": None,
            "kpi_rating": "INFO",
            "kpi_details": "",
        }

        # ---------- KPI object ----------
        FSTB14A = kpi_template.copy()
        FSTB14A["kpi_code"] = "FSTB14A"
        FSTB14A["kpi_definition"] = "Finance - Auditor Comments"

        # ---------- Fetch data ----------
        required_columns = ["auditors"]

        retrieved_data = await get_dynamic_ens_data(
            "external_supplier_data",
            required_columns,
            ens_id_value,
            session_id_value,
            session
        )

        if not retrieved_data:
            logger.warning("No external supplier data row found for Auditor analysis")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        auditor_data = retrieved_data[0].get("auditors")

        if not auditor_data or not isinstance(auditor_data, dict):
            logger.info("No auditor data details available")
            return {
                "ens_id": ens_id_value,
                "module": kpi_area_module,
                "status": "failure",
                "info": "no_data_found"
            }

        # ---------- Extract latest adverse remark ----------
        adverse_list = auditor_data.get("report_has_adverse_remarks", [])

        latest_adverse_value = False

        if isinstance(adverse_list, list) and adverse_list:
            try:
                sorted_list = sorted(
                    adverse_list,
                    key=lambda x: int(x.get("year") or 0),
                    reverse=True
                )
                latest_record = sorted_list[0]
                latest_adverse_value = latest_record.get("value", False)
            except Exception:
                logger.warning("Error while sorting adverse remarks, defaulting to False")

        is_adverse = latest_adverse_value

        # ---------- KPI logic ----------
        if is_adverse:
            kpi_rating = 'High'
            value = 'True'
        else:
            kpi_rating = 'Low'
            value = 'False'

        obj = [
            {
                "Parameter": "Adverse Filing",
                "Value": value
            }
        ]

        # ---------- Populate KPI ----------
        FSTB14A["kpi_flag"] = True
        FSTB14A["kpi_rating"] = kpi_rating
        FSTB14A["kpi_value"] = json.dumps(obj)
        FSTB14A["kpi_details"] = json.dumps(obj)

        # ---------- Persist KPI ----------
        await upsert_kpi(
            "finance",
            [FSTB14A],
            ens_id_value,
            session_id_value,
            session
        )

        logger.info("Auditor Analysis completed successfully")

        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "success",
            "info": "analysis_completed"
        }

    except Exception as e:
        logger.error(
            f"Auditor Analysis failed for ENS {ens_id_value}: {str(e)}",
            exc_info=True
        )
        return {
            "ens_id": ens_id_value,
            "module": kpi_area_module,
            "status": "failure",
            "info": "analysis_error"
        }