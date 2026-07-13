# util functions 
import json
from app.schemas.logger import logger
##########################################################

# for google
def get_country_code_google(country_name, country_data):
    for country in country_data:
        if country["countryName"].lower() == country_name.lower():
            return country["countryCode"]
    return None  
def get_country_google(country_code, country_data):
    country_mapping = {entry['countryCode']: entry['countryName'] for entry in country_data}
    country = country_mapping.get(country_code, "not found")
    return country

# for bing
def get_country_code_bing(country_name, country_data):
    for country in country_data["countries"]:
        if country["country_name"].lower() == country_name.lower():
            return country["country_code"]
    return None

def get_country_bing(country_code, country_data):
    country_mapping = {entry['country_code']: entry['country_name'] for entry in country_data["countries"]}
    country = country_mapping.get(country_code, "not found")
    return country

##########################################################

def aggregate_verified_flag(data):
    try:
        # Check if input is a valid list of dictionaries
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ValueError("LLM Output Error: Input must be a list of dictionaries.")

        # Ensure the required keys exist in all dictionaries
        required_keys = {"country", "company", "verified"}
        if not all(required_keys.issubset(item.keys()) for item in data):
            logger.error("Each dictionary must contain the keys")
            raise KeyError(f"Each dictionary must contain the keys: {required_keys}")

        # Aggregate country and company (assuming they are consistent across the list)
        country = data[0]['country']
        company = data[0]['company']

        # Count 'Yes' and 'No' occurrences in the 'verified' field
        yes_count = sum(1 for item in data if item['verified'].lower() == 'yes')
        no_count = sum(1 for item in data if item['verified'].lower() == 'no')

        # Determine the aggregated 'verified' flag based on the presence of 'Yes'
        if yes_count > 0:
            aggregated_verified = 'Yes'
        else:
            aggregated_verified = 'No'

        # Calculate the percentage of 'Yes' responses
        total_count = len(data)
        yes_percentage = (yes_count / total_count) * 100 if total_count > 0 else 0

        # Return the aggregated result along with the '%_yes' key and 'num_articles' key
        return {
            "country": str(country),
            "company": str(company),
            "verified": str(aggregated_verified),
            "num_yes": int(yes_count),
            "num_analysed": int(total_count)
        }
    except Exception as e:
        logger.error(f"Aggregation of verified flag error: {str(e)}")

def calculate_metric(num_true, num_analyzed, max_articles=10):
    if num_analyzed == 0:
        return 0  # No articles analyzed, metric is 0
    
    true_percentage = num_true / num_analyzed
    weight = num_analyzed / max_articles
    metric = true_percentage * weight
    return metric

def filter_supplier_data(json_data):

    try:
        # Extract the data list from the JSON
        supplier_data = json_data.get('data', [])
        potential_pass = False
        matched = False

        # 0. No Matches from Orbis
        if not supplier_data:
            return {}, False, False
        selected_match = supplier_data

        if selected_match:
            # Get top selected match with national id, else get top match
            if supplier_data.get('decision','') == 'AUTO_ACCEPT':
                matched = True
            elif supplier_data.get('decision','') == 'REVIEW':
                potential_pass = True

            return selected_match, potential_pass, matched
        return {}, potential_pass, matched

    except Exception as e:
        logger.error(f"Error found filtering supplier data ---> {str(e)}")
        return {}, False, False