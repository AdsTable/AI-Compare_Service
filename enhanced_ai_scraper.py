# enhanced_ai_scraper.py
import os
import re
import time
import warnings
import requests
import litellm
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urlparse

# Warning suppression
try:
    from pydantic import PydanticSerializationWarning
    warnings.filterwarnings("ignore", category=PydanticSerializationWarning)
except ImportError:
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Load environment variables
load_dotenv()

# Global cost tracker
TOTAL_COST = 0.0

def get_domain_type(url):
    """Determine content type based on domain"""
    domain = urlparse(url).netloc.lower()
    
    if 'wikipedia' in domain:
        return "encyclopedia"
    elif 'news' in domain or 'reuters' in domain or 'bbc' in domain:
        return "news"
    elif 'reddit' in domain or 'forum' in domain:
        return "forum"
    elif 'github' in domain:
        return "technical"
    elif 'amazon' in domain or 'ebay' in domain:
        return "ecommerce"
    elif 'youtube' in domain or 'vimeo' in domain:
        return "media"
    elif 'research' in domain or 'arxiv' in domain:
        return "academic"
    else:
        return "general"

def get_system_prompt(content_type):
    """Get appropriate system prompt based on content type"""
    prompts = {
        "encyclopedia": "You are an expert encyclopedia analyst. Provide a comprehensive yet concise overview focusing on key facts, historical context, and significance.",
        "news": "You are a news analyst. Identify the 5W1H (Who, What, When, Where, Why, How). Highlight key events, stakeholders, and implications.",
        "forum": "You are a social media analyst. Summarize main opinions, controversies, and sentiment trends. Identify key participants.",
        "technical": "You are a technical documentation specialist. Extract key concepts, code examples, and technical specifications. Explain technical terms.",
        "ecommerce": "You are an e-commerce analyst. Focus on products, prices, features, specifications, and customer reviews.",
        "academic": "You are a research paper analyst. Identify research questions, methodology, key findings, and contributions to the field.",
        "media": "You are a media content analyst. Describe content themes, presentation style, and audience engagement aspects.",
        "general": "You are a professional content analyst. Provide a comprehensive summary highlighting key information and insights."
    }
    return prompts.get(content_type, prompts["general"])

def scrape_website(url, max_chars=50000):
    """Scrape text content from a website with enhanced extraction"""
    try:
        # Set headers to mimic a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        
        print(f"🌐 Fetching content from: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise error for bad status codes
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unnecessary elements
        for element in soup(["script", "style", "header", "footer", "nav", "form", "iframe", "button", "img"]):
            element.decompose()
            
        # Prioritize main content areas
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'\b(content|main|body)\b'))
        
        # Use prioritized content or fallback to entire soup
        content_source = main_content or soup
        
        # Get clean text content
        text = content_source.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Clean excessive whitespace
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
        
        # Truncate to character limit
        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars] + "\n\n[CONTENT TRUNCATED]"
        
        print(f"✅ Scraped {len(clean_text)} characters from {url}")
        return clean_text
    
    except Exception as e:
        print(f"⛔ Scraping error: {str(e)}")
        return None

def analyze_content(url, content, content_type="general"):
    """Send scraped content to DeepSeek for analysis"""
    global TOTAL_COST
    
    try:
        system_prompt = get_system_prompt(content_type)
        
        response = litellm.completion(
            model="deepseek/deepseek-chat",
            api_key=os.getenv("Deepseek_API_KEY"),
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": f"Analyze this content from {url}:\n\n{content}"
                }
            ],
            max_tokens=700,
            temperature=0.3
        )
        
        # Calculate and track costs
        usage = response.usage
        input_cost = (usage.prompt_tokens / 1000) * 0.001
        output_cost = (usage.completion_tokens / 1000) * 0.002
        cost = input_cost + output_cost
        TOTAL_COST += cost
        
        print(f"💵 API Cost: ${cost:.6f} | Tokens: {usage.total_tokens} (Input: {usage.prompt_tokens}, Output: {usage.completion_tokens})")
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"⛔ API Error: {str(e)}")
        return None

def save_analysis(url, analysis, content_type):
    """Save analysis to a formatted file"""
    domain = urlparse(url).netloc.replace("www.", "").split(".")[0]
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"analysis_{domain}_{content_type}_{timestamp}.txt"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\n")
        f.write(f"Content Type: {content_type}\n")
        f.write(f"Analysis Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n" + "=" * 80 + "\n")
        f.write(analysis)
    
    print(f"💾 Analysis saved to: {filename}")
    return filename

def main():
    """Main execution function"""
    print("🚀 AI Web Scraper and Content Analyzer")
    print("=" * 60)
    
    # Sample URLs for different content types
    urls = [
        "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "https://www.reuters.com/technology/",
        "https://www.reddit.com/r/MachineLearning/",
        "https://github.com/BerriAI/litellm",
        "https://www.amazon.com/dp/B09Q2PJMS5",  # Example product
        "https://arxiv.org/abs/2303.08774"  # AI research paper
    ]
    
    for url in urls:
        try:
            print("\n" + "=" * 60)
            print(f"🔍 Processing: {url}")
            
            # Determine content type
            content_type = get_domain_type(url)
            print(f"📝 Content Type: {content_type}")
            
            # Scrape content with delay to avoid rate limiting
            content = scrape_website(url)
            time.sleep(1)  # Be polite to servers
            
            if not content:
                print("⏩ Skipping due to scraping error")
                continue
            
            # Analyze content
            analysis = analyze_content(url, content, content_type)
            
            if not analysis:
                print("⏩ Skipping due to API error")
                continue
                
            # Display and save results
            print("\n" + "=" * 60)
            print(f"📝 {content_type.capitalize()} Analysis:")
            print("=" * 60)
            print(analysis)
            print("=" * 60)
            
            # Save to file
            save_analysis(url, analysis, content_type)
            
        except Exception as e:
            print(f"⚠️ Unexpected error: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"💰 Total Session Cost: ${TOTAL_COST:.6f}")
    print("=" * 60)
    print("🎉 Analysis completed!")

if __name__ == "__main__":
    main()