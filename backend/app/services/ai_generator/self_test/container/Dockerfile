FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .

# Non-root user for security
RUN useradd --uid 1001 --no-create-home selftest && chown -R selftest /app
USER 1001

# Single worker — one request at a time, one browser instance
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--log-level", "info"]

EXPOSE 8080
