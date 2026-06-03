FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Открываем порт
EXPOSE 8080

# Запуск приложения
# uvloop + httptools (уже в requirements) дают быстрее event loop и HTTP-парсер.
# WEB_CONCURRENCY управляет числом воркеров (дефолт 2; контейнер 4 ядра / concurrency 16).
ENV WEB_CONCURRENCY=2
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8080 --loop uvloop --http httptools --workers ${WEB_CONCURRENCY}"]
