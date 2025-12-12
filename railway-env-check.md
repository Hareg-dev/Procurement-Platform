# Railway Environment Variables Check

Make sure these are set in Railway dashboard:

## Required Variables:
```
DATABASE_URL=postgresql+asyncpg://postgres:eLQJYwHgCpUNWyEvRYuuZZRheDMuSJOy@postgres.railway.internal:5432/railway
SECRET_KEY=your-production-secret-key-here
```

## Optional Variables:
```
ENVIRONMENT=production
PROJECT_NAME=Procurement Platform
API_V1_STR=/api/v1
BACKEND_CORS_ORIGINS=["https://*.railway.app"]
```

## Check Railway Logs:
The startup script will show:
- Missing environment variables (if any)
- Database URL (first 50 chars)
- Server startup on correct port

If health check fails, check Railway logs for error messages.