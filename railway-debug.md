# Railway Debug Steps

## 1. Check Railway Service Settings
- Service Type: Web Service (not Worker)
- Port: Should auto-detect from $PORT
- Domain: Should be auto-generated

## 2. Check Environment Variables
Railway dashboard → Variables tab:
- PORT should be set automatically
- No custom variables needed for basic test

## 3. Check Railway Logs
Railway dashboard → Deployments → View Logs:
- Look for "Starting server on port XXXX"
- Check for Python errors
- Verify container starts

## 4. Manual Test
If app starts but health check fails:
- Try accessing the Railway URL directly
- Check if /health endpoint works manually

## 5. Railway CLI Debug
```bash
railway login
railway logs
railway status
```