#!/bin/bash
echo "Pushing Procurement Platform to Docker Hub..."

read -p "Enter your Docker Hub username: " DOCKER_USERNAME

echo "Tagging image..."
docker tag procurement-platform:latest $DOCKER_USERNAME/procurement-platform:latest

echo "Pushing to Docker Hub..."
docker push $DOCKER_USERNAME/procurement-platform:latest

echo "Done! Image available at: $DOCKER_USERNAME/procurement-platform:latest"