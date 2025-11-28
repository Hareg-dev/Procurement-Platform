@echo off
echo Pushing Procurement Platform to Docker Hub...

set /p DOCKER_USERNAME="Enter your Docker Hub username: "

echo Tagging image...
docker tag procurement-platform:latest %DOCKER_USERNAME%/procurement-platform:latest

echo Pushing to Docker Hub...
docker push %DOCKER_USERNAME%/procurement-platform:latest

echo Done! Image available at: %DOCKER_USERNAME%/procurement-platform:latest