import requests
from markdownify import markdownify as md
from bs4 import BeautifulSoup
import os

BASE_URL = "https://support.optisigns.com/api/v2/help_center/en-us/articles.json?page=12&per_page=30"
OUTPUT_DIR = "articles_md"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_html(html):
    if not html: return ""
    soup = BeautifulSoup(html, "html.parser")
    # Remove scripts, styles, nav, footer if any
    for tag in soup(["script", "style", "nav", "footer", "aside"]):
        tag.decompose()
    return str(soup)

def fetch_and_convert_articles(limit=30):
    """Scrape and save md file, return list of files url"""
    url = BASE_URL
    count = 0
    downloaded_files = []
    
    print(f"Scrape {limit} articles...")
    while url and count < limit:
        res = requests.get(url)
        data = res.json()

        for article in data.get("articles", []):
            slug = article["html_url"].split("/")[-1]
            clean = clean_html(article["body"])
            markdown = md(clean, heading_style="ATX")

            path = os.path.join(OUTPUT_DIR, f"{slug}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {article['title']}\n\n")
                f.write(markdown)
            
            downloaded_files.append(path)
            count += 1
            if count >= limit: break
        url = data.get("next_page")

fetch_and_convert_articles()
