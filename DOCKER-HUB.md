# Docker Hub Deployment

## Build and Push to Docker Hub

### Prerequisites
- Docker Desktop installed
- Docker Hub account
- Login to Docker Hub: `docker login`

### 1. Build and Push (Windows)
```bash
build-and-push.bat
```

### 2. Build and Push (Linux/Mac)
```bash
chmod +x build-and-push.sh
./build-and-push.sh
```

### 3. Manual Build and Push
```bash
# Build image
docker build -f Dockerfile.production -t haregdev/procurement-platform:latest .

# Tag versions
docker tag haregdev/procurement-platform:latest haregdev/procurement-platform:v1.0.0

# Push to Docker Hub
docker push haregdev/procurement-platform:latest
docker push haregdev/procurement-platform:v1.0.0
```

## Run from Docker Hub

### Quick Start
```bash
# Pull and run with PostgreSQL
docker-compose -f docker-compose.hub.yml up
```

### Manual Run
```bash
# Pull image
docker pull haregdev/procurement-platform:latest

# Run with environment variables
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://postgres:password@host:5432/procurement \
  -e SECRET_KEY=your-secret-key \
  haregdev/procurement-platform:latest
```

## Docker Hub Repository
- **Image**: `haregdev/procurement-platform`
- **Tags**: `latest`, `v1.0.0`
- **Size**: ~200MB
- **Base**: Python 3.11 slim

## Access Application
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

Ready for production deployment! 🚀