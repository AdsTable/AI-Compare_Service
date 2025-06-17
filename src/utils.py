# src/utils.py
# src/utils.py
import csv
import re
import asyncio
import random
from pydantic import BaseModel
from typing import Dict, Any
from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext, ElementHandle

def is_duplicated(name: str, seen_names: set) -> bool:
    """Checks if a name has already been processed in the current session"""
    return name in seen_names

def save_data_to_csv(records: list, data_struct: BaseModel, filename: str):
    """
    Saves extracted records to a CSV file using the structure defined in the Pydantic model
    Args:
        records: List of dictionaries containing the data
        data_struct: Pydantic model class defining the data structure
        filename: Output CSV file path
    """
    if not records:
        print("No records to save.")
        return
    
    # Get field names from the Pydantic model
    fieldnames = list(data_struct.__fields__.keys())
    
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    
    print(f"Saved {len(records)} records to '{filename}'.")

async def extract_plan_data(element: ElementHandle) -> dict:
    """
    Directly extracts mobile plan data from HTML element using Playwright
    Args:
        element: Playwright ElementHandle of the mobile plan container
    Returns:
        Dictionary containing extracted plan data
    """
    try:
        # Extract plan name
        name_elem = await element.query_selector("h3.text-lg")
        name = await name_elem.inner_text() if name_elem else "Unknown Plan"
        
        # Extract operator name
        operator_elem = await element.query_selector("div.flex.items-center span.ml-2")
        operator = await operator_elem.inner_text() if operator_elem else "Unknown"
        
        # Extract monthly price
        price_elem = await element.query_selector("div.text-2xl")
        price_text = await price_elem.inner_text() if price_elem else "0"
        try:
            price = float(price_text.replace("kr", "").replace(",", ".").strip())
        except ValueError:
            price = 0.0
        
        # Extract data limit
        data_limit = "Unknown"
        data_elems = await element.query_selector_all("div.flex.items-center")
        for el in data_elems:
            text = await el.inner_text()
            if "GB" in text or "ubegrenset" in text.lower():
                data_limit = text
                break
        
        # Extract plan features
        features = []
        feature_list = await element.query_selector("ul.list-disc")
        if feature_list:
            feature_items = await feature_list.query_selector_all("li")
            features = [await item.inner_text() for item in feature_items]
        
        return {
            "name": f"{operator} {name}",
            "operator": operator,
            "monthly_price": price,
            "data_limit": data_limit,
            "features": features
        }
    except Exception as e:
        print(f"Direct extraction error: {str(e)}")
        return {}

async def extract_trustpilot_data(provider_name: str, context: BrowserContext) -> Dict[str, Any]:
    """
    Fetches Trustpilot review data for a service provider
    Args:
        provider_name: Name of the service provider to search for
        context: Playwright browser context to use for the request
    Returns:
        Dictionary containing Trustpilot score, review count and URL
    """
    if not provider_name:
        return {
            "trustpilot_score": None,
            "trustpilot_reviews": None,
            "trustpilot_url": None
        }
    
    page = None
    try:
        # Create a new page in the existing context
        page = await context.new_page()
        search_query = provider_name.replace(' ', '%20')
        search_url = f"https://no.trustpilot.com/search?query={search_query}"
        
        # Navigate to Trustpilot with realistic delays
        await page.goto(search_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(random.randint(1000, 3000))
        
        # Get page content for parsing
        content = await page.content()
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Try to find the business card using multiple selectors
        card = (soup.select_one('.styles_businessUnitCard__container__2M5Mv') or 
                soup.select_one('.business-unit-card') or 
                soup.select_one('.card'))
        
        if not card:
            return {
                "trustpilot_score": None,
                "trustpilot_reviews": None,
                "trustpilot_url": None
            }
        
        # Extract rating score
        rating_element = card.select_one('.styles_rating__size-m__3HwQJ, .star-rating')
        score = float(rating_element.text.replace(',', '.')) if rating_element else None
        
        # Extract review count
        reviews_element = card.select_one('.styles_text__2FFSI, .review-count')
        reviews_text = reviews_element.text if reviews_element else ""
        reviews_match = re.search(r'(\d[\d\s]*)', reviews_text.replace(' ', ''))
        reviews = int(reviews_match.group(1)) if reviews_match else None
        
        # Extract review page URL
        link_element = card.select_one('a[href^="/review/"], a.business-unit-card')
        url = "https://no.trustpilot.com" + link_element['href'] if link_element else None
        
        return {
            "trustpilot_score": score,
            "trustpilot_reviews": reviews,
            "trustpilot_url": url
        }
    except Exception as e:
        print(f"[Trustpilot] Error for '{provider_name}': {str(e)}")
        return {
            "trustpilot_score": None,
            "trustpilot_reviews": None,
            "trustpilot_url": None
        }
    finally:
        # Ensure the page is always closed
        if page:
            await page.close()