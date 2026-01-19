# Dockerfile for FastAPI + Playwright (sync_api) project
# Playwright base image already includes browsers & system deps
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app

# Expose the app port (project uses 4000 in run.py)
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips *"]
