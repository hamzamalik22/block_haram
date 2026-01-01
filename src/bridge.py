import time
import redis
import re
import subprocess

# CONFIG
LOG_FILE = "logs/query.log"
r = redis.Redis(host='localhost', port=6379, db=0)

print("🌉 Bridge Started: Watching DNS -> Sending to AI...")

# Open the log file
# We use subprocess 'tail' because it handles file rotation better than Python
f = subprocess.Popen(['tail','-F',LOG_FILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

while True:
    line = f.stdout.readline()
    if line:
        text = line.decode('utf-8')
        # Extract domain using Regex (looks for "A IN domain.com.")
        # CoreDNS Log format: ... A IN google.com. ...
        match = re.search(r'A\s+IN\s+([a-zA-Z0-9.-]+)\.', text)
        if match:
            domain = match.group(1)
            # Ignore local/weird domains
            if "udp" not in domain and "tcp" not in domain:
                # Push to AI Queue
                r.lpush("dns_traffic", domain)
                print(f"➡️  Sent to AI: {domain}")
