#!/bin/bash
# 1. Run the Manager to merge lists
/usr/bin/python3 /root/block_haram/src/manager.py >> /root/block_haram/logs/deploy.log 2>&1

# 2. Restart DNS to apply changes
systemctl restart block_haram_dns

echo "[$(date)] Changes Applied & DNS Restarted" >> /root/block_haram/logs/deploy.log
