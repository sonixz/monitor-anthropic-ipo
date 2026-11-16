#!/bin/sh
# Started by the machine at every boot; output goes to /data/start.log.
echo "start.sh: $(date -u +%FT%TZ) starting placeholder service on :8000"
exec python3 /data/app/serve.py
