FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim@sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36
USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    PATH=/opt/nusa-venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYSPARK_PYTHON=/opt/nusa-venv/bin/python \
    LAKE_ROOT=/opt/nusa-project/artifacts/lake
RUN python -m venv /opt/nusa-venv && useradd --uid 10001 --create-home nusa
WORKDIR /opt/nusa-project
COPY requirements-reference.txt requirements-spark.txt ./
RUN /opt/nusa-venv/bin/pip install --no-cache-dir -r requirements-spark.txt
COPY --chown=nusa:nusa src ./src
COPY --chown=nusa:nusa sql ./sql
COPY --chown=nusa:nusa dbt ./dbt
COPY --chown=nusa:nusa scripts ./scripts
COPY --chown=nusa:nusa tests ./tests
COPY --chown=nusa:nusa dags ./dags
COPY --chown=nusa:nusa data ./data
COPY --chown=nusa:nusa pyproject.toml ./
RUN /opt/nusa-venv/bin/pip install --no-deps -e . \
    && mkdir -p artifacts && chown -R nusa:nusa /opt/nusa-project
USER nusa
ENTRYPOINT ["/opt/nusa-venv/bin/python","-m","nusacommerce.cli"]
