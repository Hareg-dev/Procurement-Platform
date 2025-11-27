# Quick Start Guide

## Automatic Database Setup

The platform now automatically creates database tables on startup!

### Option 1: SQLite (Easiest - No PostgreSQL needed)

1. **Create `.env` file** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and change the DATABASE_URL to**:
   ```
   DATABASE_URL=sqlite+aiosqlite:///./procurement.db
   ```

3. **Update Ollama model**:
   ```
   OLLAMA_MODEL=tinyllama:1.1b
   ```

4. **Run the startup script**:
   ```bash
   uv run python startup.py
   ```

5. **Start the server**:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

### Option 2: PostgreSQL (Production-ready)

1. **Create the database**:
   ```bash
   createdb procurement_db
   ```

2. **Create `.env` file** and keep the PostgreSQL URL:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/procurement_db
   OLLAMA_MODEL=tinyllama:1.1b
   ```

3. **Run startup script and start server** (same as above)

## What Happens Automatically

✅ **Database tables are created** on first startup  
✅ **No manual migrations needed** for local development  
✅ **Works with both SQLite and PostgreSQL**  

## Testing

Once the server is running, visit:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Troubleshooting

**Ollama not running?**
```bash
ollama serve
```

**Model not found?**
```bash
ollama pull tinyllama:1.1b
```

**Database errors?**
- For SQLite: No setup needed, file is created automatically
- For PostgreSQL: Make sure `createdb procurement_db` was run
