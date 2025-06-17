# check_api_with_scraping.py
import os
import warnings
import requests
import litellm
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Warning suppression
try:
    from pydantic import PydanticSerializationWarning
    warnings.filterwarnings("ignore", category=PydanticSerializationWarning)
except ImportError:
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Load environment variables
load_dotenv()

def scrape_website(url):
    """Scrape text content from a website"""
    try:
        # Set headers to mimic a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise error for bad status codes
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unnecessary elements
        for element in soup(["script", "style", "header", "footer", "nav", "form", "iframe"]):
            element.decompose()
            
        # Get clean text content
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        print(f"✅ Scraped {len(clean_text)} characters from {url}")
        return clean_text[:15000]  # Return first 15,000 characters to avoid token limits
    
    except Exception as e:
        print(f"⛔ Scraping error: {str(e)}")
        return None

def analyze_content(url):
    """Send scraped content to DeepSeek for analysis"""
    content = scrape_website(url)
    if not content:
        return "Scraping failed"
    
    try:
        response = litellm.completion(
            model="deepseek/deepseek-chat",
            api_key=os.getenv("Deepseek_API_KEY"),
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert web content analyst. Provide a concise 3-point summary."
                },
                {
                    "role": "user", 
                    "content": f"Analyze this scraped content from {url}:\n\n{content}"
                }
            ],
            max_tokens=500
        )
        
        # Print API usage information
        usage = response.usage
        input_cost = (usage.prompt_tokens / 1000) * 0.001
        output_cost = (usage.completion_tokens / 1000) * 0.002
        print(f"💵 API Cost: ${input_cost + output_cost:.6f} | Tokens: {usage.total_tokens}")
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"API Error: {str(e)}"

if __name__ == "__main__":
    # Test with Wikipedia page about AI
    url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
    print(f"🌐 Analyzing content from: {url}")
    
    analysis = analyze_content(url)
    print("\n" + "=" * 60)
    print("📝 Content Analysis:")
    print("=" * 60)
    print(analysis)
    print("=" * 60)