# cli.py
import argparse
import asyncio
from main import crawl_data

def main():
    parser = argparse.ArgumentParser(description="AI Web Scraper")
    parser.add_argument('--model', choices=['mobile_service_provider', 'business'], 
                       default='mobile_service_provider', help="Data model to use")
    parser.add_argument('--start', action='store_true', help="Start crawling")
    parser.add_argument('--download', action='store_true', help="Download results")
    
    args = parser.parse_args()
    
    if args.start:
        # Update configuration
        from config import DATA_MODEL
        DATA_MODEL = args.model
        asyncio.run(crawl_data())
    
    if args.download:
        # Implement download functionality
        print("Downloading results...")

if __name__ == "__main__":
    main()