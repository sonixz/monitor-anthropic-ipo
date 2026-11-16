#!/bin/sh
# Boot script of the machine. deploy.sh copies it to /data/start.sh; the machine
# runs it at every start and writes its output to /data/start.log.
# It keeps the service of the current release running and restarts it if it stops.

while true; do
  if cd /data/current 2>/dev/null; then
    IPO_HOST=127.0.0.1 IPO_PORT=8000 IPO_RELEASE="$(cat RELEASE 2>/dev/null || echo unknown)" \
      .venv/bin/python -m ipo_monitor &
    echo $! > /data/service.pid
    wait $!
    echo "start.sh: service stopped with status $?; starting again in 2 seconds"
  else
    echo "start.sh: /data/current is missing; waiting for a deployment"
  fi
  sleep 2
done
