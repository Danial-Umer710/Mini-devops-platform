# 🚀 Mini DevOps Platform

A simple CI/CD-like platform built with Flask and Docker that allows users to deploy GitHub repositories with one click and manage them through a web dashboard.

---

## 📌 Features

- 🔗 Deploy any public GitHub repository  
- 🐳 Automatically builds Docker images  
- 🚀 Runs containers with dynamic port allocation  
- 📊 Interactive dashboard to:
  - View active deployments  
  - Start / Stop containers  
  - Delete containers  
  - View live logs  
- 🕒 Deployment history tracking  
- ⚠️ Prevents duplicate deployments (idempotent behavior)  

---

## 🛠️ Tech Stack

- **Backend:** Python (Flask)  
- **Containerization:** Docker  
- **Frontend:** HTML, CSS, Bootstrap  
- **Version Control:** Git & GitHub  

---

## ⚙️ How It Works

1. Enter a GitHub repository URL  
2. The platform:
   - Clones the repository  
   - Builds a Docker image  
   - Runs a container on an available port  
3. The deployed app becomes accessible via:
   ```
   http://localhost:<port>
   ```
4. Manage deployments from the dashboard  

---

## ▶️ Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd mini-devops-platform
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Linux / WSL
venv\Scripts\activate      # Windows
```

### 3. Install dependencies
```bash
pip install flask
```

### 4. Run the application
```bash
python app.py
```

### 5. Open in browser
```
http://localhost:5000
```

---


## 🚧 Future Improvements

- 🔄 GitHub Webhook integration (auto deploy on push)  
- 🌐 Public URL support (like Heroku)  
- 📡 Live container status updates  
- 🔐 Authentication system  

---

## 🧠 What I Learned

- How CI/CD pipelines work internally  
- Docker image building and container lifecycle  
- Handling port conflicts and deployment issues  
- Building a real-world full-stack project  

---

## 📬 Feedback

Feel free to open an issue or suggest improvements!

---

## ⭐ Support

If you like this project, consider giving it a star ⭐
