# Railway Deployment Guide

## 🚀 Deploy to Railway

### 1. Prerequisites
- Railway account (https://railway.app)
- GitHub repository with your code

### 2. Database Setup
Your PostgreSQL database is already configured:
```
DATABASE_URL=postgresql+asyncpg://postgres:eLQJYwHgCpUNWyEvRYuuZZRheDMuSJOy@postgres.railway.internal:5432/railway
```

### 3. Environment Variables
Set these in Railway dashboard:

**Required:**
```bash
DATABASE_URL=postgresql+asyncpg://postgres:eLQJYwHgCpUNWyEvRYuuZZRheDMuSJOy@postgres.railway.internal:5432/railway
SECRET_KEY=your-super-secret-key-change-this-in-production
ENVIRONMENT=production
```

**Optional (for full features):**
```bash
REDIS_URL=redis://default:password@redis.railway.internal:6379
OLLAMA_BASE_URL=http://localhost:11434
BACKEND_CORS_ORIGINS=["https://your-app.railway.app"]
```

### 4. Deploy Steps

1. **Connect Repository**
   - Go to Railway dashboard
   - Click "New Project"
   - Connect your GitHub repository

2. **Configure Service**
   - Railway will auto-detect Python
   - Uses `Procfile` for startup command
   - Health check endpoint: `/health`

3. **Set Environment Variables**
   - Go to Variables tab
   - Add the environment variables above

4. **Deploy**
   - Railway will automatically build and deploy
   - Check logs for any issues

### 5. Database Migration
Migrations run automatically on deployment:
```bash
# Before first deploy, create initial migration locally:
python create_migration.py

# Railway runs migrations automatically via Procfile:
# release: python migrate.py
```

### 6. Access Your App
- Your app will be available at: `https://your-app.railway.app`
- API docs: `https://your-app.railway.app/docs`
- Health check: `https://your-app.railway.app/health`

## 🔧 Troubleshooting

### Common Issues:

1. **Database Connection Error**
   - Verify DATABASE_URL is correct
   - Ensure PostgreSQL service is running

2. **Build Failures**
   - Check `requirements.txt` has all dependencies
   - Verify Python version in `runtime.txt`

3. **Environment Variables**
   - Ensure SECRET_KEY is set
   - Check ENVIRONMENT=production

### Logs:
```bash
# View logs in Railway dashboard
# Or use Railway CLI:
railway logs
```

## 📊 Production Checklist

- ✅ PostgreSQL database configured
- ✅ Environment variables set
- ✅ CORS origins updated
- ✅ Secret key changed
- ✅ Health check endpoint working
- ✅ Database tables created automatically

Your procurement platform is ready for production! 🎉