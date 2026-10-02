# FastAPI backend with the Microsoft ODBC driver for SQL Server.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ACCEPT_EULA=Y
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates unixodbc \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
      > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update && apt-get install -y --no-install-recommends msodbcsql18 \
 && apt-get purge -y gnupg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements ./requirements
RUN pip install --no-cache-dir -r requirements/base.txt
COPY backend/ .

RUN useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs http://localhost:8000/api/v1/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
