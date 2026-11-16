# Deployment

## Where it runs

| | |
|---|---|
| Host | One Fly.io machine, provisioned and exposed through **Agent Manager GD** (Online machine) |
| Size | `shared-cpu-1x-256` (256 MB), region `yyz` |
| Disk | Persistent volume mounted at `/data` (1 GB); the rest of the disk is reset on image updates |
| Service port | `8000`, the one port bound to the public URL |
| Public URL | https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev (HTTPS terminated by Fly.io) |
| Boot | The machine runs `/data/start.sh` at every start; output goes to `/data/start.log`. Fly.io restarts the machine if it stops |

Responsibilities:

- **Agent Manager** owns the machine, the network, the tunnel and the public exposure (bind/unbind).
  Exposure and infrastructure changes need the owner's approval.
- **This repository** owns the service: its code, `start.sh`, its tests and its health check.

Every service other than the public one (database, workers, admin) listens on `127.0.0.1` only.

## Layout on the machine

```
/data/start.sh     boot script (copied from deploy/placeholder/start.sh)
/data/app/         service code
/data/www/         static files
/data/start.log    boot and service log
```

## Current service: placeholder

`deploy/placeholder/` is the temporary page online since 2026-11-15: static HTML, `GET /health`,
Python 3 standard library only, about 20 MB of memory.

Run it locally:

```sh
ROOT=deploy/placeholder/www PORT=8000 python3 deploy/placeholder/serve.py
# then open http://localhost:8000 and http://localhost:8000/health
```

Check the live service:

```sh
curl -s https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev/health
```

## Not yet in place

Automated deployment from this repository (CI/CD), tests before release, rollback and deployment
logs are planned for a later loop, after Loop 001. Until then, updates are copied to the machine
by the coding agent through its Agent Manager session.
