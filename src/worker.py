import redis
import time
import torch
import os
import logging
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# --- CONFIGURATION ---
REDIS_HOST = "localhost"
REDIS_PORT = 6379
QUEUE_NAME = "dns_traffic"

# Paths
BLOCK_DIR = "blocklists"
AI_LOG_FILE = f"{BLOCK_DIR}/ai_blocks.txt"
WHITELIST_FILE = f"{BLOCK_DIR}/whitelist.txt"
BLACKLIST_FILE = f"{BLOCK_DIR}/blacklist.txt"
FINAL_FILE = f"{BLOCK_DIR}/final_blocklist.txt"
MODEL_PATH = "model"

# --- LOGGING SETUP ---
logging.basicConfig(
    format='%(asctime)s - WORKER - %(levelname)s - %(message)s',
    level=logging.INFO
)

def get_file_domains(filepath, needs_parsing=False):
    """Reads a file and returns a set of domains."""
    if not os.path.exists(filepath):
        return set()
    
    domains = set()
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # If reading final_blocklist.txt (Format: 0.0.0.0 domain.com)
                if needs_parsing:
                    parts = line.split()
                    if len(parts) >= 2:
                        domains.add(parts[1]) # Add the domain part
                else:
                    # Standard list (just domain.com)
                    domains.add(line)
    except Exception as e:
        logging.error(f"Error reading {filepath}: {e}")
    return domains

def load_global_cache():
    """Loads ALL lists to prevent redundant AI checks."""
    # 1. Load Whitelist
    whitelist = get_file_domains(WHITELIST_FILE)
    
    # 2. Load Manual Blacklist
    blacklist = get_file_domains(BLACKLIST_FILE)
    
    # 3. Load Existing AI Blocks (Don't check what we already caught)
    ai_blocks = get_file_domains(AI_LOG_FILE)
    
    # 4. Load the MASSIVE Final List (The 2 Million Domains)
    # We parse this so we don't ask AI about Pornhub/Gambling sites already blocked.
    # Note: This takes a second but saves massive bandwidth.
    final_blocks = get_file_domains(FINAL_FILE, needs_parsing=True)

    # Combine all known domains into one "Ignore Set"
    # If a domain is in ANY of these, AI should sleep.
    ignore_set = whitelist | blacklist | ai_blocks | final_blocks
    
    logging.info(f"🔄 Cache Updated. Knowing {len(ignore_set)} domains to ignore.")
    return ignore_set

# --- LOAD AI MODEL ---
logging.info("🧠 Loading AI Model...")
try:
    device = torch.device("cpu")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH).to(device)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    model.eval()
    logging.info("✅ AI Model Loaded!")
except Exception as e:
    logging.error(f"❌ Failed to load model: {e}")
    exit(1)

# --- CONNECT TO REDIS ---
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    logging.info("✅ Connected to Redis.")
except Exception as e:
    logging.error(f"❌ Redis Connection Failed: {e}")
    exit(1)

def is_haram(domain):
    """Returns True if AI thinks the domain is bad."""
    try:
        inputs = tokenizer(domain, return_tensors="pt", truncation=True, max_length=64).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            confidence = probs[0][1].item()
        return confidence > 0.90
    except Exception as e:
        logging.error(f"AI Prediction Error: {e}")
        return False

def save_block(domain):
    """Writes to AI file (and appends to our local memory cache)."""
    with open(AI_LOG_FILE, "a") as f:
        f.write(f"{domain}\n")
    logging.warning(f"⛔ HARAM DETECTED: {domain}")

def main():
    logging.info("🚀 Smart Worker Started. Waiting for traffic...")
    
    # Initial Cache Load
    ignore_set = load_global_cache()
    last_update = time.time()
    
    # How often to reload the massive list (Seconds)
    # 300 seconds (5 mins) is a good balance for the huge list.
    CACHE_REFRESH_RATE = 300 

    while True:
        # Periodic Cache Refresh
        if time.time() - last_update > CACHE_REFRESH_RATE:
            ignore_set = load_global_cache()
            last_update = time.time()

        # Get domain from Redis (Timeout allows loop to check cache timer)
        job = r.blpop(QUEUE_NAME, timeout=1)
        
        if job:
            domain = job[1]
            
            # 1. THE ULTIMATE CHECK
            # If we know this domain (Good OR Bad), SKIP IT.
            if domain in ignore_set:
                continue 

            # 2. RUN AI CHECK (Only for truly new/unknown sites)
            if is_haram(domain):
                save_block(domain)
                ignore_set.add(domain) # Add to memory immediately so we don't re-check it in 1 second

if __name__ == "__main__":
    main()
