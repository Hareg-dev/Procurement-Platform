#!/usr/bin/env python3
"""
Minimal Railway startup - bypass migrations if they fail
"""
import os
import uvicorn
from fastapi import FastAPI

# Create minimal app for testing
app = FastAPI(title="Procurement Platform")

@app.get("/")
def root():
    return {"message": "Procurement Platform", "status": "running"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)