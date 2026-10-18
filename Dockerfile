FROM python:3.12.0-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --no-cache-dir \
        torch --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check

COPY app/ ./app/
COPY scripts/ ./scripts/

RUN useradd --create-home appuser \
    && mkdir -p /models \
    && chown -R appuser:appuser /app /models

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]