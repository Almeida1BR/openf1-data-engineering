FROM apache/airflow:3.3.1-python3.12
COPY requirements.txt /tmp/openf1-requirements.txt
RUN pip install --no-cache-dir "apache-airflow==3.3.1" -r /tmp/openf1-requirements.txt
COPY --chown=airflow:root config /opt/project/config
COPY --chown=airflow:root src /opt/project/src
COPY --chown=airflow:root sql /opt/project/sql
COPY --chown=airflow:root dags /opt/airflow/dags
ENV PYTHONPATH=/opt/project
WORKDIR /opt/project
