@echo off
REM Build and push Docker image to Docker Hub (Windows)

REM Set variables
set IMAGE_NAME=haregdev/procurement-platform
set VERSION=latest

echo Building Docker image...
docker build -f Dockerfile.production -t %IMAGE_NAME%:%VERSION% .

echo Tagging with version...
docker tag %IMAGE_NAME%:%VERSION% %IMAGE_NAME%:v1.0.0

echo Pushing to Docker Hub...
docker push %IMAGE_NAME%:%VERSION%
docker push %IMAGE_NAME%:v1.0.0

echo Docker image pushed successfully!
echo Pull with: docker pull %IMAGE_NAME%:%VERSION%
pause