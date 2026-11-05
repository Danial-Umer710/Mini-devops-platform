import json
import os
import subprocess

import pytest

import app as app_module

REPO_URL = "https://github.com/example/My-Site.git"
CONTAINER = "my-site-container"


class FakeRunner:
    """Stands in for subprocess.run so tests never touch git or Docker."""

    def __init__(self, existing=(), ports="", running="false", fail=None):
        self.existing = list(existing)
        self.ports = ports
        self.running = running
        self.fail = fail or {}
        self.calls = []

    def __call__(self, cmd, *args, **kwargs):
        self.calls.append(cmd)
        key = " ".join(cmd[:2])
        if key in self.fail:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=self.fail[key])
        out = ""
        if key == "docker ps":
            fmt = cmd[-1]
            if fmt == "{{.Names}}":
                out = "\n".join(self.existing)
            elif fmt == "{{.Ports}}":
                out = self.ports
            else:
                out = "\n".join(f"{n}|Up 2 minutes|0.0.0.0:5001->80/tcp" for n in self.existing)
        elif key == "git clone":
            os.makedirs(cmd[3], exist_ok=True)
            with open(os.path.join(cmd[3], "Dockerfile"), "w") as f:
                f.write("FROM nginx:alpine\nEXPOSE 80\n")
        elif key == "docker logs":
            out = "hello from container"
        elif key == "docker inspect":
            out = self.running
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    def ran(self, *prefix):
        return [c for c in self.calls if c[: len(prefix)] == list(prefix)]


@pytest.fixture
def env(tmp_path, monkeypatch):
    history = tmp_path / "deployments.json"
    history.write_text("[]")
    monkeypatch.setattr(app_module, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(app_module, "HISTORY_FILE", str(history))
    app_module.app.config["TESTING"] = True

    def use(runner):
        monkeypatch.setattr(app_module.subprocess, "run", runner)
        return runner

    return app_module.app.test_client(), use, history


def test_next_port_starts_at_5001(monkeypatch):
    monkeypatch.setattr(app_module.subprocess, "run", FakeRunner())
    assert app_module.get_next_port() == 5001


def test_next_port_skips_ports_in_use(monkeypatch):
    ports = "0.0.0.0:5001->80/tcp, [::]:5001->80/tcp\n0.0.0.0:5002->5000/tcp"
    monkeypatch.setattr(app_module.subprocess, "run", FakeRunner(ports=ports))
    assert app_module.get_next_port() == 5003


@pytest.mark.parametrize(
    "dockerfile, expected",
    [
        ("FROM python:3.12-slim\nEXPOSE 8080\n", "8080"),
        ("FROM nginx:alpine\n", "80"),
        ("FROM node:20\n", "3000"),
        ("FROM python:3.12-slim\n", "5000"),
    ],
)
def test_detect_container_port(tmp_path, dockerfile, expected):
    (tmp_path / "Dockerfile").write_text(dockerfile)
    assert app_module.detect_container_port(str(tmp_path)) == expected


def test_detect_container_port_without_dockerfile(tmp_path):
    assert app_module.detect_container_port(str(tmp_path)) == "5000"


def test_deploy_clones_builds_and_runs(env):
    client, use, history = env
    runner = use(FakeRunner())

    resp = client.post("/deploy", data={"repo": REPO_URL})

    assert resp.status_code == 200
    assert b"http://localhost:5001" in resp.data
    assert runner.ran("git", "clone", REPO_URL)
    assert runner.ran("docker", "build", "-t", "my-site-image")
    assert runner.ran("docker", "run", "-d", "-p", "5001:80", "--name", CONTAINER, "my-site-image")
    assert json.loads(history.read_text())[0]["status"] == "running"


def test_deploy_is_idempotent(env):
    client, use, history = env
    runner = use(FakeRunner(existing=[CONTAINER]))

    resp = client.post("/deploy", data={"repo": REPO_URL})

    assert b"is already deployed" in resp.data
    assert not runner.ran("git", "clone")
    assert not runner.ran("docker", "build")
    assert not runner.ran("docker", "run")
    assert json.loads(history.read_text()) == []


def test_deploy_reports_clone_failure(env):
    client, use, history = env
    use(FakeRunner(fail={"git clone": "repository not found"}))

    resp = client.post("/deploy", data={"repo": REPO_URL})

    assert b"Git clone failed" in resp.data
    assert json.loads(history.read_text()) == []


def test_deploy_reports_build_failure(env):
    client, use, _ = env
    runner = use(FakeRunner(fail={"docker build": "no Dockerfile"}))

    resp = client.post("/deploy", data={"repo": REPO_URL})

    assert b"Docker build failed" in resp.data
    assert not runner.ran("docker", "run")


def test_dashboard_lists_containers(env):
    client, use, _ = env
    use(FakeRunner(existing=[CONTAINER]))

    resp = client.get("/dashboard")

    assert resp.status_code == 200
    assert CONTAINER.encode() in resp.data
    assert b"http://localhost:5001" in resp.data


def test_logs_returns_container_output(env):
    client, use, _ = env
    use(FakeRunner())

    resp = client.get(f"/logs/{CONTAINER}")

    assert resp.get_json() == {"logs": "hello from container"}


@pytest.mark.parametrize("running, action", [("true", "stop"), ("false", "start")])
def test_toggle_stops_or_starts(env, running, action):
    client, use, history = env
    runner = use(FakeRunner(running=running))

    resp = client.get(f"/toggle/{CONTAINER}")

    assert resp.status_code == 302
    assert runner.ran("docker", action, CONTAINER)
    assert json.loads(history.read_text())[0]["status"] == ("stopped" if action == "stop" else "started")


def test_delete_removes_container_and_records_history(env):
    client, use, history = env
    runner = use(FakeRunner(existing=[CONTAINER]))

    resp = client.get(f"/delete/{CONTAINER}")

    assert resp.status_code == 302
    assert runner.ran("docker", "rm", "-f", CONTAINER)
    entry = json.loads(history.read_text())[0]
    assert (entry["repo"], entry["status"]) == (CONTAINER, "deleted")
