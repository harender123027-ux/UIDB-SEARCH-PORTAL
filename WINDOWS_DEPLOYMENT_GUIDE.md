# UIDB Search Portal - Windows 10 Native Deployment Guide

This guide explains how to run the UIDB Search Portal locally on a Windows 10 machine without using Docker. Both the backend (Python/FastAPI) and frontend (React/Vite) will run directly on your host machine.

## Prerequisites

1. **Python 3.10+**: Download and install from [python.org](https://www.python.org/downloads/windows/). Make sure to check **"Add Python to PATH"** during installation.
2. **Node.js (LTS version)**: Download and install from [nodejs.org](https://nodejs.org/). This will install both `node` and `npm`.
3. **Git** (optional but recommended): For version control.

---

## 1. Backend Setup (FastAPI)

The backend uses Python and SQLite.

### Step 1: Open PowerShell or Command Prompt
Open your terminal and navigate to the `backend` folder:
```powershell
cd "f:\UIDB SEARCH PORTAL\backend"
```

### Step 2: Create a Virtual Environment
This keeps the project's Python dependencies isolated.
```powershell
python -m venv .venv
```

### Step 3: Activate the Virtual Environment
```powershell
.\.venv\Scripts\activate
```
*(Your prompt should change to show `(.venv)` at the beginning.)*

### Step 4: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables
1. Make a copy of `.env.example` and name it `.env` (inside the `backend` folder).
2. Edit `.env` to configure your API keys or any other necessary settings.

### Step 6: Start the Backend Server
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Your backend is now running at `http://localhost:8000`.

---

## 2. Frontend Setup (React/Vite)

The frontend is a React application built with Vite.

### Step 1: Open a New Terminal
Open a **new** PowerShell or Command Prompt window (keep the backend one running) and navigate to the project's root folder:
```powershell
cd "f:\UIDB SEARCH PORTAL"
```

### Step 2: Install Node Dependencies
```powershell
npm install
```

### Step 3: Configure Frontend Environment Variables
1. Check the `.env` file in the root folder (`f:\UIDB SEARCH PORTAL\.env`).
2. Make sure it points to your backend URL. It should look like this:
```env
VITE_API_URL=http://localhost:8000
```
*(You can use your machine's IP address instead of localhost if accessing from another device on the network).*

### Step 4: Run the Development Server
```powershell
npm run dev -- --host
```
Your frontend is now accessible at `http://localhost:5173` (or whichever port Vite assigns, check the terminal output).

---

## 3. Production / Persistent Deployment on Windows (Optional)

If you want the application to run continuously in the background even after closing the terminal windows, or if you want it to start automatically when Windows boots up, you can use a process manager like **PM2**.

### Install PM2 Globally
```powershell
npm install -g pm2
```

### Run the Backend with PM2
Open a terminal in the `backend` folder:
```powershell
pm2 start ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000" --name "uidb-backend"
```

### Build and Run the Frontend with PM2
Since Vite is a dev server, for production it's better to build the static files and serve them using a lightweight server like `serve`.

1. Go to the project root folder:
```powershell
cd "f:\UIDB SEARCH PORTAL"
```
2. Build the frontend:
```powershell
npm run build
```
3. Install the `serve` package globally:
```powershell
npm install -g serve
```
4. Start serving the built files with PM2:
```powershell
pm2 start "serve -s dist -l 5173" --name "uidb-frontend"
```

### Save PM2 Processes (Optional)
To ensure PM2 remembers these applications and restarts them automatically:
```powershell
pm2 save
```
You can monitor your running apps anytime using:
```powershell
pm2 status
pm2 logs
```

---
**Summary:**
- Docker files have been removed.
- Use Python's `.venv` and `uvicorn` for the backend.
- Use `npm` for the frontend.
- Consider `pm2` if you want to keep them running as background services on Windows.
