#!/bin/bash
# 1. Run the Manager to merge lists
python3 src/ai_worker/manager.py >> logs/deploy.log 2>&1

# 2. Restart DNS to apply changes
systemctl restart block_haram_dns

echo "[$(date)] Changes Applied & DNS Restarted" >> logs/deploy.log
