# scr/scraper.py
import json
import asyncio
from datetime import datetime
from typing import List, Set, Tuple, Dict, Any
from pydantic import BaseModel
from crawl4ai import (
    AsyncWebCrawler, BrowserConfig, CacheMode, 
    CrawlerRunConfig, LLMExtractionStrategy, LLMConfig
)
from src.utils import is_duplicated, extract_trustpilot_data
from config import LLM_MODEL, API_TOKEN, TRUSTPILOT_SEARCH_URL

def get_browser_config() -> BrowserConfig:
    """Returns minimal browser configuration for crawl4ai"""
    return BrowserConfig(
        browser_type="chromium",  # Options: chromium, firefox, webkit
        headless=True             # Run without GUI
        # Removed all unsupported parameters: args, user_agent, proxy, etc.
        #proxy=None,               # Proxy settings (if needed)
        #args=[],                  # Additional browser arguments
        #user_agent=None,          # Custom User-Agent string
    )

def get_llm_strategy(llm_instructions: str, output_format: BaseModel) -> LLMExtractionStrategy:
    """Creates LLM extraction strategy configuration"""
    # Create LLM configuration
    llm_config = LLMConfig(
        provider=LLM_MODEL,
        api_token=API_TOKEN
    )
    
    return LLMExtractionStrategy(
        llm_config=llm_config,  # Use the new llm_config parameter
        schema=output_format.schema(),
        extraction_type="schema",
        instruction=llm_instructions,
        input_format="markdown",
        verbose=False
    )

async def check_no_results(crawler: AsyncWebCrawler, url: str, session_id: str) -> bool:
    """Checks if 'No Results Found' message is present on the page"""
    try:
        result = await crawler.arun(
            url=url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                session_id=session_id,
                timeout=30000  # 30 seconds timeout
            ),
        )
        return result.success and "No Results Found" in result.cleaned_html
    except Exception as e:
        print(f"[NoResults] Error: {str(e)}")
        return False

async def fetch_trustpilot_reviews(provider_name: str, crawler: AsyncWebCrawler) -> Dict[str, Any]:
    """Fetches Trustpilot data for a service provider"""
    if not provider_name:
        return {"score": None, "reviews": None, "url": None}
    
    try:
        search_url = f"{TRUSTPILOT_SEARCH_URL}{provider_name.replace(' ', '%20')}"
        result = await crawler.arun(
            url=search_url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                css_selector=".styles_businessUnitCard__container__2M5Mv",
                timeout=30000
            )
        )
        
        if result.success:
            return extract_trustpilot_data(result.cleaned_html)
    except Exception as e:
        print(f"[Trustpilot] Error for '{provider_name}': {str(e)}")
    
    return {"score": None, "reviews": None, "url": None}

async def fetch_and_process_page(
    crawler: AsyncWebCrawler,
    page_number: int,
    base_url: str,
    css_selector: str,
    llm_strategy: LLMExtractionStrategy,
    session_id: str,
    seen_names: Set[str],
    model_type: str  # "mobile_service_provider" or "business"
) -> Tuple[List[Dict[str, Any]], bool]:
    """Fetches and processes a single page of data"""
    url = base_url.format(page_number=page_number)
    print(f"🔄 Loading page {page_number}: {url}")
    
    # Check for "no results" message
    try:
        no_results = await check_no_results(crawler, url, session_id)
        if no_results:
            print("⛔ No more results found")
            return [], True
    except Exception as e:
        print(f"[CheckResults] Error: {str(e)}")

    # Fetch page content with extraction strategy
    try:
        result = await crawler.arun(
            url=url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=llm_strategy,
                css_selector=css_selector,
                session_id=session_id,
                timeout=30000
            ),
        )

        if not result or not result.success:
            print(f"⛔ Error loading page {page_number}")
            return [], False

        # Parse extracted content
        extracted_data = []
        if result.extracted_content:
            try:
                extracted_data = json.loads(result.extracted_content)
                if not isinstance(extracted_data, list):
                    extracted_data = [extracted_data]
            except json.JSONDecodeError:
                print(f"⚠️ JSON decoding error on page {page_number}")
    except Exception as e:
        print(f"[PageProcess] Error: {str(e)}")
        return [], False

    if not extracted_data:
        print(f"ℹ️ No data found on page {page_number}")
        return [], False

    # Process and enrich records
    all_records = []
    for record in extracted_data:
        try:
            name = record.get("name", "")
            if not name or is_duplicated(name, seen_names):
                continue

            # Add Trustpilot data only for service providers
            if model_type == "mobile_service_provider":
                trustpilot_data = await fetch_trustpilot_reviews(name, crawler)
                record.update({
                    "trustpilot_score": trustpilot_data.get("score"),
                    "trustpilot_reviews": trustpilot_data.get("reviews"),
                    "trustpilot_url": trustpilot_data.get("url")
                })
            
            # Add timestamp
            record["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            
            seen_names.add(name)
            all_records.append(record)
            print(f"✅ Added record: {name}")
        except Exception as e:
            print(f"[RecordProcess] Error: {str(e)}")

    print(f"📊 Extracted records: {len(all_records)}")
    return all_records, False