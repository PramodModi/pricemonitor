FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

CMD ["sh", "-c", "uvicorn app.fastapi.main:app --host 0.0.0.0 --port ${PORT:-8080}"]