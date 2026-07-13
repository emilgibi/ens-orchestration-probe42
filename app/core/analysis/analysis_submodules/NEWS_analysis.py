import asyncio
import requests
from datetime import datetime
from app.core.utils.db_utils import *
import os
import json
from app.core.config import get_settings

import requests
from datetime import datetime
from app.schemas.logger import logger
import random
import httpx


async def newsscreening_main_company(data, session):
    logger.warning("Performing News Analysis...")
    kpi_area_module = "NWS"

    kpi_template = {
        "kpi_area": kpi_area_module,
        "kpi_code": "",
        "kpi_definition": "",
        "kpi_flag": False,
        "kpi_value": None,
        "kpi_rating": "",
        "kpi_details": "",
        "kpi_data": []
    }

    NWS1A = kpi_template.copy()
    NWS1A["kpi_code"] = "NWS1A"
    NWS1A["kpi_definition"] = "Adverse Media - Additional Screening"

    ens_id = data.get("ens_id")
    session_id = data.get("session_id")

    required_columns = ["name", "country"]
    retrieved_data = await get_dynamic_ens_data("external_supplier_data", required_columns, ens_id, session_id, session)
    retrieved_data = retrieved_data[0]

    name = retrieved_data.get("name")
    country = retrieved_data.get("country")
    logger.info("checkpoint 1")

    news_url = get_settings().urls.news_backend
    url = f"{news_url}/items/news_ens_data"
    logger.info(f"url: {url}")

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    total_news = 0
    current_year = datetime.now().year
    min_year = current_year-3
    news_data = []
    response=[]
    while total_news < 5 and current_year >= min_year:
        start_date = f"{current_year}-01-01"
        if current_year == datetime.now().year:
            end_date = datetime.now().strftime("%Y-%m-%d")
        else:
            end_date = f"{current_year}-12-31"

        data = {
            "name": name,
            "flag": "Entity",
            "company": "",
            "domain": [""],
            "start_date": start_date,
            "end_date": end_date,
            "country": country,
            "request_type": "single"
        }
        logger.info(f"----news data::: {data}")
        try:
            logger.info(f"Checking news for year {current_year}...")
            response = requests.post(url, headers=headers, json=data)
            logger.info(f"-----response {response.status_code}")

            if response.status_code == 200:
                year_news = response.json().get("data", [])
                logger.info(f"Found {len(year_news)} news articles for {current_year}")
                if isinstance(year_news, list):
                    logger.debug("data is a list")
                    if len(year_news)>0:
                        valid_or_not = year_news[0].get("link", 'N/A')
                    else:
                        valid_or_not = 'N/A'
                else:
                    valid_or_not = 'N/A'
                if valid_or_not == 'N/A':
                    logger.debug("link is not present skipping")
                    current_year -= 1
                    continue
                news_data.extend(year_news)
                total_news += len(year_news)

                if total_news >= 5:
                    break
            else:
                logger.error(f"Error fetching news for {current_year}: {response.status_code}")
                return {"ens_id": ens_id, "module": "NEWS", "status": "completed"}

            current_year -= 1  # Move to the previous year
        except:
            return {"ens_id": ens_id, "module": "NEWS", "status": "failed"}
    logger.info(f"Total news collected: {total_news}")

    if not news_data:
        logger.info("No relevant news found.")
        return {"ens_id": ens_id, "module": "NEWS", "status": "completed"}

    # Process the collected news
    unique_data_points = []
    current_year = datetime.now().year  # Get current year for filtering
    kpi_value_list = []

    for i, record in enumerate(news_data):
        sentiment = record.get("sentiment", "").lower()
        news_date = record.get("date", "")
        category = record.get("category", "").strip().lower()
        summary = record.get("summary", "").strip()
        title = record.get("title", "").strip()
        link = record.get("link", "").strip()

        if sentiment == "negative" and news_date:
            try:
                news_date_obj = datetime.strptime(news_date, "%Y-%m-%d")
                news_time_period = current_year - news_date_obj.year

                if news_time_period <= 5:
                    # Categorize the news item
                    category_map = {
                        "general": "Adverse Media finding",
                        "adverse media - business ethics / reputational risk / code of conduct": "Adverse Media - Other Reputational Risk",
                        "bribery / corruption / fraud": "Bribery, Fraud or Corruption",
                        "regulatory": "Regulation",
                        "adverse media - other criminal activity": "Adverse Media - Other Criminal Activities"
                    }

                    cat = category_map.get(category, None)
                    if not cat:
                        continue

                    NWS1A["kpi_flag"] = True
                    kpi_value_list.append(title)
                    NWS1A["kpi_rating"] = "High"

                    current_unique_detail = f"{cat}: {title} - {summary}\n Source: {link} (Date: {news_date_obj.strftime('%Y-%m-%d')})"
                    unique_data_points.append(current_unique_detail)

            except ValueError:
                continue

    if NWS1A["kpi_flag"]:
        NWS1A["kpi_value"] = "; ".join(kpi_value_list)

        data_point_counter = 1
        details = "Following Additional Screening:\n"
        for finding in unique_data_points:
            finding = f"{data_point_counter}. {finding}\n"
            details += finding
            data_point_counter += 1

        NWS1A["kpi_details"] = details
        NWS1A["kpi_data"] = unique_data_points
    else:
        NWS1A["kpi_value"] = ""
        NWS1A["kpi_rating"] = "INFO"
        NWS1A["kpi_details"] = "Screening Results Indicate No Adverse Media for This Entity"
        NWS1A["kpi_data"] = []

    kpi_list = [NWS1A]
    logger.debug(f"kpi_list: {kpi_list}")

    insert_status = await upsert_kpi("news", kpi_list, ens_id, session_id, session)

    logger.debug("Stored in the database")
    logger.info("Performing News Screening Analysis for Company... Completed")

    return {"ens_id": ens_id, "module": "NEWS", "status": "completed"}
async def newsscreening_main_company_throttle(data, session):
    logger.info("Performing News Analysis...")
    kpi_area_module = "NWS"

    kpi_template = {
        "kpi_area": kpi_area_module,
        "kpi_code": "",
        "kpi_definition": "",
        "kpi_flag": False,
        "kpi_value": None,
        "kpi_rating": "",
        "kpi_details": "",
    }

    NWS1A = kpi_template.copy()
    NWS1A["kpi_code"] = "NWS1A"
    NWS1A["kpi_definition"] = "Adverse Media - Google News Screening"

    ens_id = data.get("ens_id")
    session_id = data.get("session_id")

    required_columns = ["legal_name"]
    retrieved_data = await get_dynamic_ens_data("external_supplier_data", required_columns, ens_id, session_id, session)
    retrieved_data = retrieved_data[0]

    name = retrieved_data.get("legal_name")
    country = "IN"
    logger.debug("checkpoint 1")

    news_url = get_settings().urls.news_backend
    url = f"{news_url}/items/news_ens_data_throttle"
    logger.debug(f"url: {url}")

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    total_news = 0
    current_year = 2026
    min_year = 2021
    news_data = []
    response = None

    async with httpx.AsyncClient(
            timeout=httpx.Timeout(600.0, connect=600.0),
            limits=httpx.Limits(max_connections=1)
    ) as client:
        while total_news < 5 and current_year >= min_year:
            start_date = f"{current_year}-01-01"
            if current_year == datetime.now().year:
                end_date = datetime.now().strftime("%Y-%m-%d")
            else:
                end_date = f"{current_year}-12-31"

            data = {
                "name": name,
                "flag": "Entity",
                "company": "",
                "domain": [""],
                "start_date": start_date,
                "end_date": end_date,
                "country": country,
                "request_type": "single",
                "mode": "probe42",
            }

            try:
                response = await client.post(url, headers=headers, json=data)
                logger.info(f"Checking news for year {current_year}...")

                if response.status_code == 200:
                    year_news = response.json().get("data", [])
                    logger.info(f"Found {len(year_news)} news articles for {current_year}")
                    if isinstance(year_news, list):
                        logger.debug("data is a list")
                        if len(year_news) > 0:
                            valid_or_not = year_news[0].get("link", 'N/A')
                        else:
                            valid_or_not = 'N/A'
                    else:
                        valid_or_not = 'N/A'

                    if valid_or_not == 'N/A':
                        logger.debug("link is not present skipping")
                        current_year -= 1
                        continue

                    news_data.extend(year_news)
                    total_news += len(year_news)

                    if total_news >= 5:
                        break
                else:
                    logger.error(f"Error fetching news for {current_year}: {response.status_code}")

            except httpx.RequestError as e:
                logger.error(f"HTTP request failed for {current_year}: {e}")

            current_year -= 1  # Move to the previous year

    logger.debug(f"Total news collected: {total_news}")

    if not news_data:
        logger.info("No relevant news found.")
        return {"ens_id": ens_id, "module": "NEWS", "status": "completed"}

    # Process the collected news
    unique_data_points = []
    current_year = datetime.now().year
    kpi_value_list = []

    for i, record in enumerate(news_data):
        sentiment = record.get("sentiment", "").lower()
        news_date = record.get("date", "")
        category = record.get("category", "").strip().lower()
        summary = record.get("summary", "").strip()
        title = record.get("title", "").strip()
        link = record.get("link", "").strip()

        if sentiment == "negative" and news_date:
            try:
                news_date_obj = datetime.strptime(news_date, "%Y-%m-%d")
                news_time_period = current_year - news_date_obj.year

                if news_time_period <= 5:
                    category_map = {
                        "general": "Adverse Media finding",
                        "adverse media - business ethics / reputational risk / code of conduct": "Adverse Media - Other Reputational Risk",
                        "bribery / corruption / fraud": "Bribery, Fraud or Corruption",
                        "regulatory": "Regulation",
                        "adverse media - other criminal activity": "Adverse Media - Other Criminal Activities"
                    }

                    cat = category_map.get(category, None)
                    if not cat:
                        continue

                    # Update KPI
                    NWS1A["kpi_flag"] = True
                    kpi_value_list.append(title)
                    NWS1A["kpi_rating"] = "High"

                    current_unique_detail = f" {cat}: {title} - {summary}\n Source: {link} (Date:{news_date_obj.strftime('%Y-%m-%d')})"
                    unique_data_points.append(current_unique_detail)

            except ValueError:
                continue
    if NWS1A["kpi_flag"]:
        NWS1A["kpi_value"] = "; ".join(kpi_value_list)

        data_point_counter = 1
        details = "Following Additional Screening:\n"
        for finding in unique_data_points:
            finding = f"{data_point_counter}. {finding}\n"
            details += finding
            data_point_counter += 1

        NWS1A["kpi_details"] = details
    else:
        NWS1A["kpi_value"] = ""
        NWS1A["kpi_rating"] = "INFO"
        NWS1A["kpi_details"] = "Screening Results Indicate No Adverse Media for This Entity"

    kpi_list = [NWS1A]
    logger.debug(f"kpi_list: {kpi_list}")

    insert_status = await upsert_kpi("adverse_media", kpi_list, ens_id, session_id, session)

    columns_data = [{
        "sentiment_aggregation": response.json().get("sentiment-data-agg", [])
    }]
    logger.debug(columns_data)

    # await insert_dynamic_ens_data("report_plot", columns_data, ens_id, session_id, session)

    logger.debug("Stored in the database")
    logger.info("Performing News Screening Analysis for Company... Completed")

    return {"ens_id": ens_id, "module": "NEWS", "status": "completed"}

