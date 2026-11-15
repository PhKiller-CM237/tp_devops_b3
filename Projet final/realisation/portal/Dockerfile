FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS test
RUN pip install --no-cache-dir pytest==8.3.4
COPY app.py pytest.ini ./
COPY templates ./templates
COPY static ./static
COPY tests ./tests
RUN mkdir -p reports && pytest -q --junitxml=reports/junit.xml

FROM base AS runtime
ARG APP_VERSION=1.0
ENV APP_VERSION=$APP_VERSION ODOO_URL="" PGADMIN_URL=""
LABEL org.opencontainers.image.title="legeni-academy" org.opencontainers.image.version=$APP_VERSION
RUN useradd --create-home --uid 10001 appuser
COPY app.py entrypoint.sh releases.txt ./
COPY templates ./templates
COPY static ./static
RUN chmod 0755 /opt/entrypoint.sh
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"
ENTRYPOINT ["/opt/entrypoint.sh"]
