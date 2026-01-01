import os
import requests
import datetime

# --- CONFIGURATION ---
# FIXED: Variable name is now consistent everywhere
BLOCKLIST_DIR = "data/blocklists"

FINAL_FILE = f"{BLOCKLIST_DIR}/final_blocklist.txt"
AI_FILE = f"{BLOCKLIST_DIR}/ai_blocks.txt"
WHITELIST_FILE = f"{BLOCKLIST_DIR}/whitelist.txt"
BLACKLIST_FILE = f"{BLOCKLIST_DIR}/blacklist.txt"

# --- BLOCK SOURCES (The Bad Guys) ---
BLOCKLIST_URLS = {
    "OISD Big": "https://big.oisd.nl/domainswild",
    "StevenBlack (Gambling+Porn)": "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/gambling-porn/hosts",
    "Hagezi Pro++": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/pro.plus.txt",
    "Sinfonietta Porn": "https://raw.githubusercontent.com/Sinfonietta/hostfiles/master/pornography-hosts"
}

# --- WHITELIST SOURCES (The Good Guys) ---
WHITELIST_URLS = {
    "Community Whitelist": "https://raw.githubusercontent.com/anudeepND/whitelist/master/domains/whitelist.txt",
    "Hagezi Whitelist": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/whitelist.txt"
}

def log(msg):
    print(f"[{datetime.datetime.now()}] {msg}")

def get_file_lines(filepath):
    if not os.path.exists(filepath): return set()
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return set([l.strip() for l in f if l.strip() and not l.startswith("#")])

def extract_domain(line):
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("!"): return None
    line = line.split("#")[0].strip()
    parts = line.split()
    if len(parts) >= 2 and (parts[0] == "0.0.0.0" or parts[0] == "127.0.0.1"): return parts[1]
    return parts[0]

def download_from_urls(url_dict):
    total_domains = set()
    for name, url in url_dict.items():
        try:
            log(f"⬇️  Downloading {name}...")
            r = requests.get(url, timeout=45)
            if r.status_code == 200:
                lines = r.text.split("\n")
                count = 0
                for line in lines:
                    domain = extract_domain(line)
                    if domain:
                        total_domains.add(domain)
                        count += 1
                log(f"    ✅ Found {count} domains in {name}")
            else:
                log(f"    ❌ Failed {name} (Status: {r.status_code})")
        except Exception as e:
            log(f"    ❌ Error {name}: {e}")
    return total_domains

def update():
    log("🚀 Manager Started: Fixing the internet...")

    # 1. Download The Bad Lists
    bad_domains = download_from_urls(BLOCKLIST_URLS)
    
    # 2. Download The Good Lists (Community Whitelists)
    log("🛡️  Downloading Community Whitelists (Auto-Fixes)...")
    good_domains = download_from_urls(WHITELIST_URLS)

    # 3. Read Local Files
    ai_data = get_file_lines(AI_FILE)
    blacklist_data = get_file_lines(BLACKLIST_FILE)
    local_whitelist = get_file_lines(WHITELIST_FILE)

    # 4. MERGE: (Bad Lists + AI + Manual Block)
    full_blocklist = bad_domains | ai_data | blacklist_data
    
    # 5. FILTER: Remove (Community Whitelist + Local Whitelist)
    total_whitelist = good_domains | local_whitelist
    final_list = full_blocklist - total_whitelist
    
    auto_fixed_count = len(full_blocklist) - len(final_list)
    log(f"✨ Auto-Fixed {auto_fixed_count} false positives using Community Whitelists!")

    # 6. Write Final File
    try:
        log(f"💾 Writing {len(final_list)} domains to firewall...")
        with open(FINAL_FILE, "w") as f:
            f.write(f"# Updated: {datetime.datetime.now()}\n")
            f.write("127.0.0.1 localhost\n::1 localhost\n")
            for domain in sorted(final_list):
                f.write(f"0.0.0.0 {domain}\n")
                f.write(f":: {domain}\n") # IPv6 Support
        
        log("✅ Success! System updated.")
    
    except Exception as e:
        log(f"❌ Critical Error: {e}")

if __name__ == "__main__":
    update()
