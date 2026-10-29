FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml requirements.lock requirements-dev.lock ./
COPY portal_app ./portal_app
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install -r requirements.lock && pip install --no-deps . \
    && useradd --create-home portaluser \
    && mkdir -p /run/portal-secrets && chown portaluser:portaluser /run/portal-secrets
USER portaluser
EXPOSE 8000
CMD ["uvicorn", "portal_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
