# Production pins the built image ID in /etc/scriptlattes/runner.env.
# Override BASE_IMAGE with an approved digest when rebuilding.
ARG BASE_IMAGE=python:3.13-slim-bookworm
FROM ${BASE_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp SCRIPTLATTES_CHROME_NO_SANDBOX=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && chromium --version && chromedriver --version
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY scriptLattes.py ./
COPY scriptLattes/ ./scriptLattes/
COPY css/ ./css/
COPY js/ ./js/
COPY scripts/ ./scripts/
RUN ln -s /usr/bin/chromedriver /app/chromedriver
USER 65532:65532
ENTRYPOINT ["python", "scripts/inct_update.py"]

# Build with --target test for CI. The default/final target remains production.
FROM runtime AS test
USER root
RUN apt-get update && apt-get install -y --no-install-recommends shellcheck \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY pytest.ini .ruff.toml ./
COPY tests/ ./tests/
COPY deploy/inct/ ./deploy/inct/
USER 65532:65532
ENTRYPOINT ["python", "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"]

FROM runtime AS production
