# Mini DevOps Platform

A self-hosted, one-click deployment tool for Linux. A Python/Flask service takes a GitHub repository URL, clones it, builds a Docker image, runs it on a free host port, and lets you start, stop, delete and inspect containers from a web dashboard. Duplicate deployments are rejected, so repeating a deploy request cannot create a second copy of the same app.

## Tech Stack

![CI](https://github.com/Danial-Umer710/Mini-devops-platform/actions/workflows/ci.yml/badge.svg)
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

**Unit tests** (`tests/test_app.py`, 16 tests). `subprocess.run` is replaced with a fake, so they need no Docker daemon or network. They cover port allocation, container-port detection, the clone → build → run flow, the duplicate-deploy guard, failure handling, the dashboard, logs, toggle and delete.

```bash
pip install -r requirements-dev.txt
pytest -v
```

```
tests/test_app.py::test_deploy_clones_builds_and_runs PASSED             [ 50%]
tests/test_app.py::test_deploy_is_idempotent PASSED                      [ 56%]
...
============================== 16 passed in 0.12s ==============================
```

**End-to-end smoke test** (`scripts/smoke_test.sh`, needs Docker). It starts `app.py`, deploys [docker-nginx-website](https://github.com/Danial-Umer710/docker-nginx-website) for real, sends the same deploy again, checks the running app and the logs API, then deletes the container:

```bash
./scripts/smoke_test.sh
```

```
PASS  first deploy           -> http://localhost:5001
PASS  second deploy skipped  -> already deployed
PASS  deployed app           -> HTTP 200
PASS  logs API               -> /logs/docker-nginx-website-container
PASS  delete                 -> container removed
SMOKE TEST PASSED
```

Set `REPO_URL=<any repo with a Dockerfile>` to smoke-test a different project.

**CI:** `.github/workflows/ci.yml` runs the unit tests, then the Docker smoke test, on every push and pull request.
