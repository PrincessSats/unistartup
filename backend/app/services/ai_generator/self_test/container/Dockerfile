# IMPORTANT: the playwright pin in requirements.txt MUST match this image tag
# (v1.60.0 here ⇒ playwright==1.60.0). Mismatch ⇒ "Executable doesn't exist" at launch.
# 1.60 ships a far more stable headless Chromium than 1.49 (which crashed the
# renderer in this serverless runtime).
FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .

# Run as the base image's pre-provisioned browser user (pwuser) which owns
# /ms-playwright and has a writable HOME — required for Chromium to launch.
# (A custom --no-create-home user has no HOME and crashes Chromium at startup.)
ENV HOME=/home/pwuser
USER pwuser

# Single worker — one request at a time, one browser instance.
# Yandex Serverless Containers route to $PORT (default 8080).
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--log-level", "info"]

EXPOSE 8080
