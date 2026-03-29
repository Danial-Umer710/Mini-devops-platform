import os
import shutil
import subprocess
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

BASE_DIR = "deployments"
HISTORY_FILE = os.path.join(BASE_DIR, "deployments.json")
START_PORT = 5001

# Ensure directories/files exist
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w") as f:
        json.dump([], f)

# ----------------- Helper Functions -----------------

def get_next_port():
    used_ports = set()
    result = subprocess.run(["docker", "ps", "--format", "{{.Ports}}"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        parts = line.split(",")
        for part in parts:
            if "->" in part:
                host_part = part.split("->")[0]
                if ":" in host_part:
                    port = host_part.split(":")[-1]
                    if port.isdigit():
                        used_ports.add(int(port))
    port = START_PORT
    while port in used_ports:
        port += 1
    return port

def detect_container_port(repo_path):
    dockerfile_path = os.path.join(repo_path, "Dockerfile")
    try:
        with open(dockerfile_path, "r") as f:
            for line in f:
                line = line.strip().upper()
                if line.startswith("EXPOSE"):
                    return line.split()[1]
                if "NGINX" in line:
                    return "80"
                if "NODE" in line:
                    return "3000"
    except:
        pass
    return "5000"

def cleanup_old_container(container_name, image_name):
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
    subprocess.run(["docker", "rmi", "-f", image_name], capture_output=True)

def get_all_containers():
    containers = []
    result = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}|{{.Ports}}"],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        try:
            name, status, ports = line.split("|")
            host_port = "N/A"
            if "->" in ports:
                for part in ports.split(","):
                    if "->" in part:
                        host_part = part.split("->")[0]
                        if ":" in host_part:
                            host_port = host_part.split(":")[-1]
            containers.append({
                "name": name,
                "status": status,
                "port": host_port,
                "url": f"http://localhost:{host_port}" if host_port != "N/A" else "#"
            })
        except:
            continue
    return containers

def read_history():
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)

def write_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def add_history(repo_name, status):
    history = read_history()
    history.append({
        "repo": repo_name,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status
    })
    write_history(history)

# ----------------- ROUTES -----------------

@app.route('/')
def home():
    return redirect(url_for('deploy_page'))

@app.route('/deploy', methods=['GET', 'POST'])
def deploy_page():
    if request.method == 'POST':
        repo_url = request.form['repo']
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_path = os.path.join(BASE_DIR, repo_name)
        container_name = f"{repo_name.lower()}-container"
        image_name = f"{repo_name.lower()}-image"

        # ✅ CHECK IF ALREADY DEPLOYED
        check = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        existing_containers = check.stdout.splitlines()

        if container_name in existing_containers:
            return render_template(
                "deploy.html",
                error=f"⚠️ Repo '{repo_name}' is already deployed! Go to dashboard."
            )

        # Clean any leftover (safety)
        cleanup_old_container(container_name, image_name)

        # Remove repo folder if exists
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)

        # Clone repo
        clone = subprocess.run(["git", "clone", repo_url, repo_path], capture_output=True, text=True)
        if clone.returncode != 0:
            return render_template("deploy.html", error=f"Git clone failed:\n{clone.stderr}")

        # Build image
        build = subprocess.run(["docker", "build", "-t", image_name, repo_path], capture_output=True, text=True)
        if build.returncode != 0:
            return render_template("deploy.html", error=f"Docker build failed:\n{build.stderr}")

        # Run container
        container_port = detect_container_port(repo_path)
        host_port = get_next_port()

        run = subprocess.run(
            ["docker", "run", "-d", "-p", f"{host_port}:{container_port}", "--name", container_name, image_name],
            capture_output=True, text=True
        )
        if run.returncode != 0:
            return render_template("deploy.html", error=f"Docker run failed:\n{run.stderr}")

        add_history(repo_name, "running")

        return render_template(
            "deploy.html",
            success=True,
            repo=repo_name,
            url=f"http://localhost:{host_port}"
        )

    return render_template("deploy.html")

@app.route('/dashboard')
def dashboard():
    return render_template("dashboard.html", containers=get_all_containers())

@app.route('/history')
def history():
    return render_template("history.html", history=read_history())

@app.route('/logs/<name>')
def logs(name):
    result = subprocess.run(["docker", "logs", name], capture_output=True, text=True)
    return jsonify({"logs": result.stdout})

@app.route('/toggle/<name>')
def toggle_container(name):
    result = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name], capture_output=True, text=True)
    if result.stdout.strip() == "true":
        subprocess.run(["docker", "stop", name])
        add_history(name, "stopped")
    else:
        subprocess.run(["docker", "start", name])
        add_history(name, "started")
    return redirect(url_for("dashboard"))

@app.route('/delete/<name>')
def delete_container(name):
    subprocess.run(["docker", "rm", "-f", name])
    add_history(name, "deleted")
    return redirect(url_for("dashboard"))

# ----------------- RUN -----------------

if __name__ == "__main__":
    app.run(debug=True)
