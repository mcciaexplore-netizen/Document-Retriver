FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV STORAGE_PATH=/app/storage
RUN groupadd --system app && useradd --system --gid app app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
RUN mkdir -p /app/storage && chown app:app /app/storage
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
