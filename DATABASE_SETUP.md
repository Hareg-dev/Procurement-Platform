# Database Setup Instructions

## Error Encountered
The server failed to start with: `role "user" does not exist`

This means the `.env` file is using default credentials that don't match your PostgreSQL setup.

## Solution: Create .env File

Create a file named `.env` in the project root with your actual PostgreSQL credentials:

```bash
# Database Configuration (UPDATE WITH YOUR CREDENTIALS)
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/procurement_db

# If you use a different username:
# DATABASE_URL=postgresql+psycopg://YOUR_USERNAME:YOUR_PASSWORD@localhost:5432/procurement_db

# Ollama Configuration
OLLAMA_MODEL=tinyllama:1.1b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TEMPERATURE=0.7

# JWT Configuration
SECRET_KEY=your-secret-key-change-this-in-production-make-it-long-and-random
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Configuration
API_V1_STR=/api/v1
PROJECT_NAME=Procurement Platform
PROJECT_VERSION=0.1.0

# CORS Configuration
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Environment
ENVIRONMENT=development

# Pagination
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Steps to Fix

1. **Find your PostgreSQL credentials:**
   - Default username is usually `postgres`
   - Password is what you set during PostgreSQL installation

2. **Create the database (if not done):**
   ```bash
   createdb procurement_db
   ```

3. **Create the .env file** with the template above

4. **Restart the server:**
   ```bash
   uv run uvicorn app.main:app --reload
   ```

## Common PostgreSQL Usernames

- `postgres` (most common)
- Your system username
- Custom username you created

## Test Your Credentials

You can test if your credentials work with:
```bash
psql -U YOUR_USERNAME -d procurement_db
```

If this works, use the same credentials in your `.env` file!
