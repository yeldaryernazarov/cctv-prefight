## Windows Setup & Run Guide

This project was originally optimized for Ubuntu + Docker, but it can also run
on Windows with local services. This guide assumes **Windows 10/11**.

### 1. Install required software (once)

- **Python**: Install Python 3.10+ from the official site and check:
  - In a new PowerShell window:
    - `python --version`
- **Node.js**: Install the LTS version (includes `npm`) and check:
  - `node --version`
  - `npm --version`
- **PostgreSQL**:
  - Install PostgreSQL 15+ for Windows.
  - Create:
    - Database: `risk_detection`
    - User: `riskuser`
    - Password: `riskpass123`
- **Redis**:
  - Install Redis for Windows (e.g. via WSL/WSL2 or a Windows port) and run it on `localhost:6379`.

> If you prefer Docker Desktop instead of native installs, you can follow the
> original `README.md` and `docker-compose.yml` after installing Docker Desktop
> and enabling WSL2. No extra code changes are needed for that path.

### 2. Create a Python virtual environment

From the project root (`school-risk-main`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Then install Python dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r .\risk-engine\requirements.txt
python -m pip install -r .\clip-service\requirements.txt
python -m pip install -r .\deepstream-analytics\requirements.txt
```

### 3. Install frontend dependencies

```powershell
cd .\web-ui
npm install
cd ..
```

### 4. Start services (each in its own terminal)

Make sure PostgreSQL and Redis are running first.

#### 4.1 Risk Engine API

```powershell
cd .\risk-engine
.\..\.venv\Scripts\python.exe .\main.py
```

The API will be available at `http://localhost:8001` and docs at
`http://localhost:8001/docs`.

#### 4.2 Clip Service

In a **new** PowerShell window:

```powershell
cd <path-to>\school-risk-main
.\.venv\Scripts\Activate.ps1
cd .\clip-service
.\..\.venv\Scripts\python.exe .\main.py
```

This will listen on `http://localhost:8002`.

#### 4.3 Analytics (optional, for live camera processing)

Requires working RTSP cameras configured in `configs\cameras.yaml`.

```powershell
cd <path-to>\school-risk-main
.\.venv\Scripts\Activate.ps1
cd .\deepstream-analytics
.\..\.venv\Scripts\python.exe .\analytics_service.py
```

#### 4.4 Stream Server (optional, for Live View)

```powershell
cd <path-to>\school-risk-main
.\.venv\Scripts\Activate.ps1
cd .\deepstream-analytics
.\..\.venv\Scripts\python.exe .\stream_server.py
```

### 5. Start the React web UI

In a **new** PowerShell window:

```powershell
cd <path-to>\school-risk-main\web-ui
npm start
```

Open `http://localhost:3000` in your browser.

Default credentials (once backend + DB are up and the admin auto-creation ran):

- Username: `admin`
- Password: `admin123`

### 6. Environment defaults for Windows

The following services now default to `localhost` when no environment variable
is set:

- `risk-engine\main.py`
  - `DATABASE_URL=postgresql+asyncpg://riskuser:riskpass123@localhost:5432/risk_detection`
  - `REDIS_URL=redis://localhost:6379`
- `clip-service\main.py`
  - `DATABASE_URL=postgresql+asyncpg://riskuser:riskpass123@localhost:5432/risk_detection`
- `deepstream-analytics\analytics_service.py`
  - `RISK_ENGINE_URL=http://localhost:8001`

This keeps Docker-based deployments working (they override via env vars) while
making a local Windows run much simpler.

