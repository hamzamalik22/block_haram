from google import genai
from google.genai import types
from dotenv import load_dotenv
import time
import os
import sys
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
MODEL_NAME = "gemma-3-12b-it"

# File Paths
AI_BLOCKS_FILE = "data/blocklists/ai_blocks.txt"
BLACKLIST_FILE = "data/blocklists/blacklist.txt"
WHITELIST_FILE = "data/blocklists/whitelist.txt"

# Setup Client
if not API_KEY:
    print("❌ Error: API_KEY not found in environment variables.")
    sys.exit(1)

try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    print(f"❌ Configuration Error: {e}")
    sys.exit(1)

def get_lines(filepath):
    if not os.path.exists(filepath): return []
    with open(filepath, "r") as f:
        return sorted(list(set([l.strip() for l in f if l.strip()])))

def append_line(filepath, line):
    with open(filepath, "a") as f:
        f.write(f"{line}\n")

def overwrite_file(filepath, lines):
    with open(filepath, "w") as f:
        f.write("\n".join(lines) + "\n")

def get_website_info(domain):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        url = f"http://{domain}"
        response = requests.get(url, headers=headers, timeout=5) # Increased timeout
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else "No Title"
            meta = soup.find('meta', attrs={'name': 'description'})
            desc = meta['content'].strip() if meta else "No Description"
            return f"Title: {title[:100]} | Description: {desc[:200]}"
    except:
        return "Offline/Blocked"
    return "No Data"

def ask_the_judge(domain, site_info):
    prompt = f"""
    Domain: "{domain}"
    Content: "{site_info}"
    Task: Classify as SAFE or UNSAFE.
    Rules:
    - UNSAFE: Porn, Gambling, Malware, Phishing.
    - SAFE: News, Blogs, Shops, Tech, Social.
    Reply ONE word: SAFE or UNSAFE.
    """
    
    # Retry logic inside the request
    for attempt in range(3):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            answer = response.text.strip().upper()
            if "UNSAFE" in answer: return "UNSAFE"
            if "SAFE" in answer: return "SAFE"
        except Exception as e:
            if "429" in str(e): # Rate Limit
                time.sleep(10) # Wait a bit
            else:
                print(f"  ⚠️ Error: {e}")
                return "ERROR"
    return "ERROR"

def main():
    suspects = get_lines(AI_BLOCKS_FILE)
    if not suspects:
        print("DONE_SIGNAL")
        return

    print(f"👨‍⚖️  Judge starting on {len(suspects)} cases...")
    
    # List to keep domains that fail/error so we can try again later
    retry_list = []
    
    safe_count = 0
    banned_count = 0

    for i, domain in enumerate(suspects):
        print(f"[{i+1}/{len(suspects)}] {domain}...", end=" ", flush=True)
        
        evidence = get_website_info(domain)
        verdict = ask_the_judge(domain, evidence)
        
        print(f"[{verdict}]")

        if verdict == "SAFE":
            append_line(WHITELIST_FILE, domain)
            safe_count += 1
        elif verdict == "UNSAFE":
            append_line(BLACKLIST_FILE, domain)
            banned_count += 1
        else:
            # If ERROR, keep it in the list!
            retry_list.append(domain)

        time.sleep(2) # Politeness delay

    # IMPORTANT: Overwrite the file with ONLY the ones that failed
    # This removes the processed ones but keeps the errors for next time.
    overwrite_file(AI_BLOCKS_FILE, retry_list)

    print(f"✅ DONE. Banned: {banned_count}, Safe: {safe_count}, Retrying Next Time: {len(retry_list)}")
    print("DONE_SIGNAL")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
