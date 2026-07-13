from app.core.utils.db_utils import *
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import json
from app.schemas.logger import logger

async def b2b_validation(data, session):
    ens_id = data.get('ens_id','')
    session_id = data.get('session_id')
    incoming_columns = await get_dynamic_ens_data("external_supplier_data", ['legal_name', 'city', 'gst_details'],ens_id,session_id,session)


    city=incoming_columns[0].get('city','')
    name=incoming_columns[0].get('legal_name','')
    gst_details=incoming_columns[0].get('gst_details',[])
    identifier = data.get('identifier', '')
    legal_name = incoming_columns[0].get('legal_name', '')
    if not name:
        return {'status': 'Not Found'}
    try:
        all_gst=[]
        for gst in gst_details:
            if gst.get('gstin'):
                all_gst.append(gst.get('gstin'))
        result = await check_indiamart_entity(name, city, all_gst)
        website = 'india_mart'
        if result.get("listed"):
            logger.info("b2b info found")
            company = result.get('value',{})
            valid_result = {'website': website, 'result': company}
            column = [{'b2b_validation': valid_result, 'identifier': identifier, 'legal_name': legal_name}]
            await upsert_dynamic_ens_data("external_supplier_data", column, ens_id,session_id,session)
            return {'status': 'passed'}
        else:
            logger.info("b2b info not found")
            valid_result = {'website': website, 'result': None}
            column = [{'b2b_validation': valid_result, 'identifier': identifier, 'legal_name': legal_name}]
            x=await upsert_dynamic_ens_data("external_supplier_data", column, ens_id, session_id, session)
            return {'status': 'passed'}
    except expression as e:
        traceback.print_exc()
        logger.error(f"B2B validation error - {str(e)}")
        return {'status': 'failed'}


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.indiamart.com/"
}


# -------------------------------------------------
# Step 1: Search IndiaMART (Next.js JSON extraction)
# -------------------------------------------------
async def search_indiamart(session, entity_name, city):

    url = "https://dir.indiamart.com/search.mp"
    params = {"ss": entity_name, "cq": city}

    async with session.get(url, params=params, headers=HEADERS, timeout=20) as resp:
        html = await resp.text()
    soup = BeautifulSoup(html, "html.parser")

    # Extract embedded JSON
    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag:
        return []


    json_data = json.loads(script_tag.string)
    fields = json_data["props"]["pageProps"]["searchResponse"]["results"]
    # Exact confirmed path
    try:
        field_list = []
        for x in fields:
            field_list.append(x["fields"])
            for y in x["more_results"]:
                field_list.append(y)


    except KeyError:
        return []

    sellers = []

    if isinstance(field_list, list):
        for item in field_list:
            seller = {
                "company_name": item.get("companyname",""),
                "city": item.get("city"),
                "address": item.get("address"),
                "member_since": item.get("memberSince"),
                "url": item.get("catalog_url"),
                "state": item.get("state"),
                "gstNumber": item.get("gstNumber"),
                "zipcode": item.get("zipcode"),
                # "rating": item.get("sellerRating"),
                # "review_count": item.get("reviewCount"),
                # "has_gst": item.get("isGSTVerified"),
                # "company_id": item.get("companyId"),
            }

            if seller["company_name"]:
                sellers.append(seller)

    return sellers

async def search_indiamart1(session, entity_name, city):

    url = "https://dir.indiamart.com/search.mp"
    params = {"ss": entity_name, "cq": city}

    async with session.get(url, params=params, headers=HEADERS, timeout=20) as resp:
        html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")

    # Extract embedded JSON
    # filename = f"{"xyz".replace(' ', '_')}.html"
    # with open(filename, "w", encoding="utf-8") as f:
    #     f.write(html)

    parent_div = soup.select_one("#__next .listingPage .sideBarAndListing")
    parent_div = soup.select_one("#__next .sideBarAndListing .listingContainer .listingCardContainer")
    # if not parent_div:
    #     listing_div = parent_div.select("div.card")
    script_tag = ''
    if not script_tag:
        return []

    json_data = json.loads(script_tag.string)
    fields = json_data["props"]["pageProps"]["searchResponse"]["results"]
    # Exact confirmed path
    try:
        field_list = []
        for x in fields:
            field_list.append(x["fields"])
            for y in x["more_results"]:

                field_list.append(y)


    except KeyError:
        return []

    sellers = []

    if isinstance(field_list, list):
        for item in field_list:
            seller = {
                "company_name": item.get("companyname",""),
                "city": item.get("city"),
                "address": item.get("address"),
                "member_since": item.get("memberSince"),
                "url": item.get("catalog_url"),
                "state": item.get("state"),
                "gstNumber": item.get("gstNumber"),
                "zipcode": item.get("zipcode"),
                # "rating": item.get("sellerRating"),
                # "review_count": item.get("reviewCount"),
                # "has_gst": item.get("isGSTVerified"),
                # "company_id": item.get("companyId"),
            }

            if seller["company_name"]:
                sellers.append(seller)

    return sellers


# -------------------------------------------------
# Step 2: Verify best company match
# -------------------------------------------------
def verify_company(input_name, sellers, all_gst, min_score=85,):
    verified_name = []
    verified_gst=[]
    if not sellers:
        return []

    for s in sellers:
        if s['gstNumber'] in all_gst:
            match= True
        else:
            match=False
        score = fuzz.token_sort_ratio(
            input_name.lower(),
            s["company_name"].lower()
        )
        s["match_score"] = score
        s["gst_match"] = match
        if score >= min_score:
            verified_name.append(s)
        if match:
            verified_gst.append(s)

    verified_gst.sort(key=lambda x: x["match_score"], reverse=True)
    verified_name.sort(key=lambda x: x["match_score"], reverse=True)

    if verified_gst:
        return verified_gst
    else:
        return verified_name



# -------------------------------------------------
# MAIN ORCHESTRATOR
# -------------------------------------------------
async def check_indiamart_entity(entity_name, city, all_gst):

    async with aiohttp.ClientSession() as session:
        sellers = await search_indiamart(session, entity_name, city)
        if not sellers:
            return {
                "listed": False,
                "reason": "No sellers found"
            }
        verified = verify_company(entity_name, sellers, all_gst)

        if not verified:
            return {
                "status": "failed",
                "listed": False,
                "reason": "Only backup sellers found"
            }

        best = verified[0]

        confidence = (
            "HIGH" if best.get("gstNumber")
            else "MEDIUM"
        )

        return {
            "listed": True,
            "confidence": confidence,
            "value": best
        }
