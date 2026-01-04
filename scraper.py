import requests
from markdownify import markdownify as md
from bs4 import BeautifulSoup
import os

BASE_URL = "https://support.optisigns.com/api/v2/help_center/articles.json"
OUTPUT_DIR = "articles_md"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # Remove scripts, styles, nav, footer if any
    for tag in soup(["script", "style", "nav", "footer", "aside"]):
        tag.decompose()

    return str(soup)

def save_article(article):
    slug = article["name"].replace(" ", "-").replace("/", "-").replace("?", "") # handle special character in name and turn it into slug
    html_body = article["body"]

    clean = clean_html(html_body)
    markdown = md(clean, heading_style="ATX")

    path = os.path.join(OUTPUT_DIR, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {article['title']}\n\n")
        f.write(markdown)

def fetch_articles():
    url = BASE_URL
    count = 0 # number of articles pulled

    while url and count < 30:
        res = requests.get(url)
        data = res.json()

        for article in data["articles"]:
            save_article(article)
            count += 1
            if count >= 30:
                break

        url = data.get("next_page")

fetch_articles()
