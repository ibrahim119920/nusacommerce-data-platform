# Build the app image first; this keeps Spark/Java identical in both runtimes.
FROM nusacommerce-reference:day14
USER root
RUN python -m venv /opt/airflow-venv \
    && /opt/airflow-venv/bin/pip install --no-cache-dir apache-airflow==3.1.0 \
       --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.1.0/constraints-3.11.txt \
    && mkdir -p /opt/airflow && chown -R nusa:nusa /opt/airflow
ENV AIRFLOW_HOME=/opt/airflow \
    PATH=/opt/airflow-venv/bin:/opt/nusa-venv/bin:$PATH
USER nusa
WORKDIR /opt/airflow
ENTRYPOINT ["/opt/airflow-venv/bin/airflow"]
