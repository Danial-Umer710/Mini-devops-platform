# Mini DevOps Platform

A self-hosted, one-click deployment tool for Linux. A Python/Flask service takes a GitHub repository URL, clones it, builds a Docker image, runs it on a free host port, and lets you start, stop, delete and inspect containers from a web dashboard. Duplicate deployments are rejected, so repeating a deploy request cannot create a second copy of the same app.

## Tech Stack

![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Engine-2496ED?logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Ubuntu-FCC624?logo=linux&logoColor=black)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)

- **Backend:** Python 3, Flask 3.1 (`app.py`)
- **Container runtime:** Docker Engine CLI, driven from Python through `subprocess`
- **Source control:** `git clone` of any public GitHub repository that has a `Dockerfile`
- **Frontend:** Jinja2 templates with Bootstrap 5 (`templates/`)
- **State:** JSON deployment history (`deployments/deployments.json`)

## Key Engineering Features

- **Automated container lifecycle.** One POST to `/deploy` runs `git clone` → `docker build` → `docker run -d`. The dashboard then calls `docker start`, `docker stop`, `docker rm -f` and `docker logs` through HTTP endpoints, so you never need the Docker CLI by hand.
- **Idempotent duplicate prevention.** Container and image names come from the repo name (`<repo>-container`, `<repo>-image`). Before any build, the platform checks `docker ps -a`. If the container already exists, the request is rejected with *"already deployed"*. Leftover images or folders from failed runs are cleaned up before a fresh deploy.
- **Automatic port allocation.** Host ports start at `5001`. The platform reads the ports already published in `docker ps` and picks the next free one. The container port is read from the repo's `Dockerfile` `EXPOSE` line, with fallbacks for nginx (`80`), Node (`3000`) and the default (`5000`).
- **Auditable history.** Every deploy, start, stop and delete is written with a timestamp to `deployments/deployments.json` and shown at `/history`.

## Architecture & Workflow

```
 Browser ──► Flask app (app.py, :5000)
               │
   POST /deploy  repo=<github-url>
               │
               ├─ 1. docker ps -a  ──► container "<repo>-container" exists? ──► reject: "already deployed"
               ├─ 2. cleanup leftovers (docker rm -f / docker rmi -f, old clone folder)
               ├─ 3. git clone <url> deployments/<repo>
               ├─ 4. docker build -t <repo>-image deployments/<repo>
               ├─ 5. container port  ◄── Dockerfile EXPOSE (fallback 80 / 3000 / 5000)
               │     host port       ◄── first free port >= 5001 from `docker ps`
               ├─ 6. docker run -d -p <host>:<container> --name <repo>-container <repo>-image
               └─ 7. append {repo, time, status} to deployments/deployments.json
                                   │
                                   ▼
                     App served at http://localhost:<host-port>
```

| Route | Method | Action |
|---|---|---|
| `/` | GET | Redirects to `/deploy` |
| `/deploy` | GET / POST | Deploy form; POST field `repo` = GitHub URL |
| `/dashboard` | GET | Lists all containers with status, port and URL |
| `/history` | GET | Deployment history from `deployments.json` |
| `/logs/<name>` | GET | JSON `{"logs": ...}` from `docker logs` |
| `/toggle/<name>` | GET | Starts or stops a container |
| `/delete/<name>` | GET | Removes a container (`docker rm -f`) |

## How to Run / Quickstart

Prerequisites: a Linux host (or WSL2) with Python 3, `git`, and Docker Engine. Your user must be able to run `docker` without `sudo`. No environment variables are needed.

```bash
git clone https://github.com/Danial-Umer710/Mini-devops-platform.git
cd Mini-devops-platform

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python app.py          # Flask dev server on http://127.0.0.1:5000
```

Open http://127.0.0.1:5000, paste a public GitHub repo URL that contains a `Dockerfile` (for example `https://github.com/Danial-Umer710/docker-nginx-website.git`), and click deploy. Run `app.py` from the repo root: it creates `deployments/` in the current directory to store clones and history.

## Testing & Verification

The repo has no automated test suite yet. You can check the full deploy lifecycle and the duplicate guard from a second terminal while `python app.py` is running:

```bash
REPO=https://github.com/Danial-Umer710/docker-nginx-website.git

# 1. Deploy: returns the URL of the running app
curl -s -X POST http://127.0.0.1:5000/deploy -d repo=$REPO | grep -o 'http://localhost:[0-9]*'

# 2. Same request again: rejected (idempotent duplicate prevention)
curl -s -X POST http://127.0.0.1:5000/deploy -d repo=$REPO | grep -o 'already deployed'

# 3. Container is running on the allocated port and serving traffic
docker ps --format '{{.Names}}  {{.Ports}}'
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:5001

# 4. Logs API and history
curl -s http://127.0.0.1:5000/logs/docker-nginx-website-container | head -c 120
cat deployments/deployments.json

# 5. Clean up
curl -s -o /dev/null http://127.0.0.1:5000/delete/docker-nginx-website-container
```

Expected output:

```
http://localhost:5001
already deployed
docker-nginx-website-container  0.0.0.0:5001->80/tcp, [::]:5001->80/tcp
200
{
  "logs": "/docker-entrypoint.sh: /docker-entrypoint.d/ is not empty, ...
[
  {
    "repo": "docker-nginx-website",
    "time": "2026-11-05 17:05:29",
    "status": "running"
  }
]
```

The first deploy of a small nginx-based repo took about 1.5 s on a warm Docker cache.
