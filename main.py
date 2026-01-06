import os
import json
import hashlib
import requests
import time
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from openai import OpenAI
from dotenv import load_dotenv

# --- CẤU HÌNH ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID") 
BASE_URL = "https://support.optisigns.com/api/v2/help_center/en-us/articles.json?page=12&per_page=30"
OUTPUT_DIR = "articles_md"
METADATA_FILE = "vector_store_metadata.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# SCRAPER

def clean_html(html):
    if not html: return ""
    soup = BeautifulSoup(html, "html.parser")
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
                f.write(f"This article can be found at: {article['html_url']}\n\n")
                f.write(markdown)
            
            downloaded_files.append(path)
            count += 1
            if count >= limit: break
        url = data.get("next_page")
    
    return downloaded_files

# HASH MD5

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_delta_files(file_paths):
    """Hash comparison to find new/updated files"""
    old_metadata = {}
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r") as f:
                content = f.read().strip()
                if content: # Chỉ load nếu file có nội dung
                    old_metadata = json.loads(content)
        except (json.JSONDecodeError, IOError):
            print(f"Warning !!! File {METADATA_FILE} crashed or empty. Will be re-created.")
            old_metadata = {}

    new_metadata = {}
    to_upload = []
    to_delete_openai_ids = []
    
    summary = {"added": [], "updated": [], "skipped": []}

    for path in file_paths:
        filename = os.path.basename(path)
        current_hash = calculate_md5(path)
        
        if filename not in old_metadata:
            # New
            to_upload.append(path)
            summary["added"].append(filename)
        elif old_metadata[filename]["hash"] != current_hash:
            # Update
            to_upload.append(path)
            to_delete_openai_ids.append(old_metadata[filename]["file_id"])
            summary["updated"].append(filename)
        else:
            # Skip
            new_metadata[filename] = old_metadata[filename]
            summary["skipped"].append(filename)
            
    return to_upload, to_delete_openai_ids, new_metadata, summary

# OPENAI SYNC

def sync_to_openai(to_upload, to_delete_ids, current_metadata, vs_id):
    # Delete old files from OpenAI if updated
    for fid in to_delete_ids:
        try:
            client.files.delete(fid)
        except: pass

    # Upload new/updated files
    new_file_ids = []
    for path in to_upload:
        filename = os.path.basename(path)
        with open(path, "rb") as f:
            response = client.files.create(file=f, purpose="assistants")
            fid = response.id
            new_file_ids.append(fid)
            # Save hash and new id
            current_metadata[filename] = {
                "hash": calculate_md5(path),
                "file_id": fid
            }

    # 3. Update vector store if new file exist
    if new_file_ids:
        client.vector_stores.file_batches.create_and_poll(
            vector_store_id=vs_id,
            file_ids=new_file_ids
        )
    
    with open(METADATA_FILE, "w") as f:
        json.dump(current_metadata, f, indent=4)

def main():
    # Scrape
    all_files = fetch_and_convert_articles(limit=30)
    
    # Check delta
    to_upload, to_delete, metadata, report = get_delta_files(all_files)
    
    # Get vector store
    global VECTOR_STORE_ID
    if not VECTOR_STORE_ID:
        vs = client.vector_stores.create(name="OptiBot_Knowledge")
        VECTOR_STORE_ID = vs.id
        print(f"New vector store created with id: {VECTOR_STORE_ID}")

    # Sync
    if to_upload or to_delete:
        sync_to_openai(to_upload, to_delete, metadata, VECTOR_STORE_ID)
    
    # LOGS
    print("\n" + "="*40)
    print(f"Skip: {len(report['skipped'])}")
    print(f"Add ({len(report['added'])}): {', '.join(report['added'])}")
    print(f"Update ({len(report['updated'])}): {', '.join(report['updated'])}")
    print("="*40)
    print(f"Added {len(report['added'])}, Updated {len(report['updated'])}, Skipped {len(report['skipped'])}")

if __name__ == "__main__":
    main()