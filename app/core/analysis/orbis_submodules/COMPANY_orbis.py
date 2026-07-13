import requests
from app.core.config import get_settings
from app.core.security.jwt import create_jwt_token
from app.core.utils.db_utils import get_probe42_data_by_identifier
from app.schemas.logger import logger
import json, os, ssl, urllib.request, urllib.error
import httpx
from openai import OpenAI


def _response_json(response):
    try:
        return response.json()
    except ValueError:
        return {"raw_response": response.text}


async def call_get_company_full_data_js_endpoint(identifier, org_type, identifier_type):
    try:
        # Generate JWT token
        jwt_token = create_jwt_token("orchestration", "analysis")
    except Exception as e:
        logger.error(f"Error generating JWT token: {e}")
        raise

    orbis_url = get_settings().urls.orbis_engine.rstrip("/")
    url = f"{orbis_url}/api/v1/orbis/instaFinancial/getCompanyFullData"
    headers = {
        "Authorization": f"Bearer {jwt_token.access_token}"
    }
    params = {
        "orgIdentifier": identifier,
        "orgType": org_type,
        "identifierType": identifier_type,
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response_payload = _response_json(response)
        logger.info(f"Company Data status code: {response.status_code}")

        if (response.status_code == 200) or (response.status_code == 201):
            logger.info("Performing Orbis Company Retrieval... Completed")
            message = "Successfully saved data"
            response_data = response_payload
            if isinstance(response_payload, dict):
                message = response_payload.get("message", message)
                response_data = response_payload.get("data", response_payload)
            return {
                "module": "data_orbis_company",
                "status": "completed",
                "success": True,
                "upstream_status_code": response.status_code,
                "message": message,
                "data": response_data,
            }

        logger.error("Performing Orbis Company Retrieval... Failed")
        message = "Performing Orbis Company Retrieval failed"
        if isinstance(response_payload, dict):
            message = response_payload.get("message") or response_payload.get("error") or message
        return {
            "module": "data_orbis_company",
            "status": "failed",
            "success": False,
            "upstream_status_code": response.status_code,
            "message": message,
            "data": response_payload,
        }

    except requests.RequestException as e:
        logger.error(f"Performing Orbis Company Retrieval... Failed: {str(e)}")
        return {
            "module": "data_orbis_company",
            "status": "failed",
            "success": False,
            "upstream_status_code": 502,
            "message": str(e),
            "data": {},
        }


async def search_probe42_companies_by_name(org_name):
    logger.info("Searching Probe42 companies by name..")

    if not org_name or len(str(org_name).strip()) < 3:
        return {
            "module": "probe42_name_search",
            "status": "failed",
            "success": False,
            "upstream_status_code": 400,
            "message": "orgName must be at least 3 characters long",
            "data": [],
        }

    try:
        jwt_token = create_jwt_token("orchestration", "analysis")
    except Exception as e:
        logger.error(f"Error generating JWT token: {e}")
        raise

    orbis_url = get_settings().urls.orbis_engine.rstrip("/")
    url = f"{orbis_url}/api/v1/orbis/probe42/nameSearch"
    headers = {
        "Authorization": f"Bearer {jwt_token.access_token}",
        "Accept": "application/json",
    }
    params = {
        "orgName": str(org_name).strip(),
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response_payload = _response_json(response)
        logger.info(f"Probe42 name search status code: {response.status_code}")

        if response.status_code in (200, 201):
            message = "Successful"
            response_data = response_payload
            if isinstance(response_payload, dict):
                message = response_payload.get("message", message)
                response_data = response_payload.get("data", response_payload)

            return {
                "module": "probe42_name_search",
                "status": "completed",
                "success": True,
                "upstream_status_code": response.status_code,
                "message": message,
                "data": response_data,
            }

        message = "Probe42 name search failed"
        if isinstance(response_payload, dict):
            message = response_payload.get("message") or response_payload.get("error") or message

        return {
            "module": "probe42_name_search",
            "status": "failed",
            "success": False,
            "upstream_status_code": response.status_code,
            "message": message,
            "data": response_payload,
        }

    except requests.RequestException as e:
        logger.error(f"Probe42 name search failed: {str(e)}")
        return {
            "module": "probe42_name_search",
            "status": "failed",
            "success": False,
            "upstream_status_code": 502,
            "message": str(e),
            "data": [],
        }


async def orbis_company(data, session):

    logger.info("Retrieving Orbis - Company Data..")

    # Define the query parameters as variables
    session_id = data["session_id"]
    ens_id = data["ens_id"]
    identifier = data["identifier"]
    org_type= data["entity_type"]
    identifier_type=data["identifier_type"]
    try:
        # Generate JWT token
        jwt_token = create_jwt_token("orchestration", "analysis")
    except Exception as e:
        logger.error(f"Error generating JWT token: {e}")
        raise
    orbis_url = get_settings().urls.orbis_engine
    url = f"{orbis_url}/api/v1/orbis/instaFinancial/getCompanyData?sessionId={session_id}&ensId={ens_id}&orgIdentifier={identifier}&orgType={org_type}&identifierType={identifier_type}"
    # Prepare headers with the JWT token
    # url = f"{orbis_url}/api/v1/orbis/instaFinancial/getCompanyData?orgIdentifier=U15549PN1992FTC065522&sessionId=sesion001&ensId=ens002"
    headers = {
        "Authorization": f"Bearer {jwt_token.access_token}"
    }
    payload = {}
    try:
        response = requests.request("GET", url, headers=headers, data=payload)
        logger.info(f"Company Data status code: {response}")

        if (response.status_code == 200) or (response.status_code == 201):
            logger.info("Performing Orbis Company Retrieval... Completed")
            return {"module": "data_orbis_company", "status": "completed"}
        else:
            logger.error("Performing Orbis Company Retrieval... Failed")
            return {"module": "data_orbis_company", "status": "failed"}
    except Exception as e:
        logger.error(f"Performing Orbis Company Retrieval... Failed: {str(e)}")
        return {"module": "data_orbis_company", "status": "failed"}

async def orbis_complete_company_data(data, session):

    logger.info("Retrieving Orbis - Company Complete Data..")

    # Define the query parameters as variables
    identifier = data["identifier"]
    org_type = data["entity_type"]
    identifier_type = data["identifier_type"]

    existing_data = await get_probe42_data_by_identifier(identifier, session)
    if existing_data:
        logger.info("Probe42 data found in database. Skipping Orbis call.")
        return {
            "module": "data_orbis_company",
            "status": "completed",
            "success": True,
            "upstream_status_code": 200,
            "message": "Data fetched from probe42_data",
            "data": existing_data,
        }

    return await call_get_company_full_data_js_endpoint(identifier, org_type, identifier_type)


_GENERIC_SYSTEM = """You are a senior vendor risk analyst. Produce a structured brief in EXACTLY this format:

RISK TIER: [LOW / MODERATE / HIGH / CRITICAL]

EXECUTIVE SUMMARY
[2-3 sentence assessment]

STRENGTHS
• [3-4 strengths with specific data points]

RISK FLAGS
• [3-5 specific risks with data points]

FINANCIAL HEALTH
[2 sentences with specific numbers]

RED LINE ITEMS
• [Hard blockers or NONE IDENTIFIED]

RECOMMENDATION
[2 sentences: proceed or not, with conditions]

Rules: Be specific. Cite exact numbers. No hallucination. Use only provided data."""

_PROCUREMENT_SYSTEM = """You are a senior procurement risk advisor for pharmaceutical and industrial supply chains. Produce a focused brief in EXACTLY this format:

PROCUREMENT RISK ASSESSMENT
Context: [1 line restatement of contract]
Verdict: [PROCEED / PROCEED WITH CONDITIONS / ESCALATE / DO NOT PROCEED]

KEY PROCUREMENT RISKS
• [3-4 risks specific to THIS category, value, and duration]

MITIGATIONS REQUIRED BEFORE PO ISSUANCE
1. [Specific and actionable]
2.
3.

CONTRACT CLAUSE PRIORITIES
• [Specific to this category and contract value]

MONITORING DURING CONTRACT EXECUTION
[What to watch, how often]

Rules: Reference actual data. Be specific to pharma/industrial SCM. No generic advice."""


def _cfg(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip().strip('"').strip("'")


def _call_gemini(probe42_data: dict, brief_type: str, procurement_context: dict | None) -> str:
    key   = _cfg("GEMINI__API_KEY")
    model = _cfg("GEMINI_MODEL", "gemini-2.5-flash")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")

    system = _PROCUREMENT_SYSTEM if brief_type == "procurement" else _GENERIC_SYSTEM

    if brief_type == "procurement" and procurement_context:
        ctx = "\n".join(f"  {k}: {v}" for k, v in procurement_context.items() if v is not None)
        data_text = f"Procurement context:\n{ctx}\n\nVendor data:\n\n{json.dumps(probe42_data, ensure_ascii=False, indent=2)}"
    else:
        data_text = f"Vendor data:\n\n{json.dumps(probe42_data, ensure_ascii=False, indent=2)}"

    prompt = f"{system}\n\n{data_text}"

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":     0.3,
            "maxOutputTokens": 1500,
            "thinkingConfig":  {"thinkingBudget": 0},
        },
    }).encode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    ctx_ssl = ssl.create_default_context()
    ctx_ssl.check_hostname = False
    ctx_ssl.verify_flags   = ssl.VERIFY_DEFAULT

    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx_ssl, timeout=60) as r:
            resp_json = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini API HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:800]}")
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}")

    try:
        return resp_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Unexpected Gemini response: {json.dumps(resp_json)[:400]}")


async def generate_vendor_ai_brief(data: dict, session) -> dict:
    """
    Controller for POST /vendor-risk/ai-brief.
    1. Validates brief_type.
    2. Fetches probe42_data from DB using existing get_probe42_data_by_identifier.
    3. Calls Gemini and returns a standard result dict.
    """
    identifier          = (data.get("identifier") or "").strip()
    brief_type          = (data.get("brief_type") or "generic").strip().lower()
    procurement_context = data.get("procurement_context")

    logger.info(f"generate_vendor_ai_brief called for identifier={identifier}, brief_type={brief_type}")

    # 1. Validate brief_type
    if brief_type not in ("generic", "procurement"):
        return {
            "module": "vendor_ai_brief",
            "status": "failed",
            "success": False,
            "upstream_status_code": 400,
            "message": f"brief_type must be 'generic' or 'procurement', got '{brief_type}'",
            "data": {},
        }

    # 2. Fetch from probe42_data table (reuses existing db_utils function)
    row = await get_probe42_data_by_identifier(identifier, session)

    if row is None or not row.get("probe42_data"):
        return {
            "module": "vendor_ai_brief",
            "status": "failed",
            "success": False,
            "upstream_status_code": 404,
            "message": f"No Probe42 data found for identifier '{identifier}'. Run /get-complete-company-data first.",
            "data": {},
        }

    # 3. Call Gemini
    try:
        brief_text = _call_gemini(
            probe42_data=row["probe42_data"],
            brief_type=brief_type,
            procurement_context=procurement_context,
        )
    except RuntimeError as e:
        logger.error(f"Gemini call failed for {identifier}: {e}")
        return {
            "module": "vendor_ai_brief",
            "status": "failed",
            "success": False,
            "upstream_status_code": 502,
            "message": str(e),
            "data": {},
        }

    logger.info(f"AI brief generated successfully for {identifier}")
    return {
        "module": "vendor_ai_brief",
        "status": "completed",
        "success": True,
        "upstream_status_code": 200,
        "message": f"AI brief generated successfully for {row.get('name') or identifier}",
        "data": {
            "brief":      brief_text,
            "brief_type": brief_type,
            "identifier": identifier,
            "name":       row.get("name"),
        },
    }