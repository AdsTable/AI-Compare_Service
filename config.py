# config.py
import os
from models.mobile_service_provider import ServiceProvider
from models.business import BusinessData
from typing import List, Dict, Optional, Union

# DeepSeek API Configuration
LLM_MODEL = "deepseek/deepseek-chat"
API_TOKEN = os.getenv("Deepseek_API_KEY") or "sk-your-key-here"

# Select data model: "mobile_service_provider" or "business"
DATA_MODEL = "mobile_service_provider"  # Change to "business" for yellow pages scraping

# Initialize variables
BASE_URL = ""
CSS_SELECTOR = ""
SCRAPER_INSTRUCTIONS = ""
DATA_MODEL_CLASS = None
MAX_PAGES = 3
TRUSTPILOT_SEARCH_URL = "https://no.trustpilot.com/search?query="
MAX_ELEMENTS_PER_PAGE = 20  # Ограничение для обработки элементов

# Set model class based on selection
if DATA_MODEL == "mobile_service_provider":
    DATA_MODEL_CLASS = ServiceProvider
    BASE_URL = "https://www.mobilabonnement.no"
    CSS_SELECTOR = "div.bg-white.rounded-lg.shadow-md" 
    SCRAPER_INSTRUCTIONS = (
        "Extract mobile plan details from HTML. Return JSON with: "
        "name (h3.text-lg), operator (div.flex.items-center span.ml-2), "
        "monthly_price (div.text-2xl), data_limit (div:-soup-contains('GB')), "
        "features (ul.list-disc li). "
        "Example: {'name': 'Telia Frihet', 'operator': 'Telia', "
        "'monthly_price': 299, 'data_limit': 'Ubegrenset', "
        "'features': ['5G inkludert', 'EU-roaming']}"
    )
    MAX_PAGES = 1 

elif DATA_MODEL == "business":
    DATA_MODEL_CLASS = BusinessData
    # Business data configuration (yellow pages)
    BASE_URL = "https://www.yellowpages.ca/search/si/{page_number}/Dentists/Toronto+ON"
    CSS_SELECTOR = ".listing"  # More general selector
    SCRAPER_INSTRUCTIONS = (
        "Extract Canadian businesses with: name, address, website, phone_number, description. "
        "Return JSON with keys: name, address, website, phone_number, description."
    )

# Функции для обработки мобильных тарифов
def parse_data_limit(text: str) -> Union[float, str]:
    """Convert data limit text to numeric value or 'unlimited'"""
    text_lower = text.lower()
    if "ubegrenset" in text_lower or "unlimited" in text_lower:
        return "unlimited"
    try:
        return float(''.join(filter(str.isdigit, text)))
    except:
        return 0.0

features_mapping = {
    "Data Rollover": "data_rollover",
    "EU-roaming": "eu_roaming",
    "5G": "5g_included",
    "Fri tale": "free_calls",
    "Fri SMS": "free_sms"
}