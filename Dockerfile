# Stage 1 — installer les dépendances
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2 — image finale légère
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY app.py .
COPY static/ static/
ENV PATH=/root/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data
EXPOSE 5080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5080/healthz')"
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:5080", "--timeout", "120", "--access-logfile", "-", "app:app"]
