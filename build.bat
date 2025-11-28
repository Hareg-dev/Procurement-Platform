@echo off
echo Building Procurement Platform Docker Image...

docker build -t procurement-platform:latest .

echo.
echo Image built successfully!
echo To run: docker run -p 8000:8000 procurement-platform:latest