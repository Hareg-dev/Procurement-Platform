# Local Development Setup

## Quick Start with Docker

### Prerequisites
- Docker Desktop installed
- Git

### 1. Clone and Run
```bash
git clone https://github.com/Hareg-dev/Procurement-Platform.git
cd procurement-platform
docker-compose -f docker-compose.local.yml up --build
```

### 2. Access the Application
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 3. Database Access
- **Host**: localhost
- **Port**: 5432
- **Database**: procurement
- **Username**: postgres
- **Password**: password123

## Manual Setup (Without Docker)

### 1. Install PostgreSQL
```bash
# Install PostgreSQL locally
# Create database: procurement
# User: postgres, Password: password123
```

### 2. Setup Python Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
copy .env.local .env
```

### 4. Run Migrations and Start
```bash
python migrate.py
uvicorn app.main:app --reload
```

## Test the System

### Create Test User
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "first_name": "Test",
    "last_name": "User",
    "role": "buyer"
  }'
```

### Login and Test
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test@example.com",
    "password": "password123"
  }'
```

## Stop Services
```bash
docker-compose -f docker-compose.local.yml down
```

Ready to test the procurement platform locally! 🚀