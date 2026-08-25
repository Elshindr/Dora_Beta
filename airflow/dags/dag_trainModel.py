from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from datetime import datetime
from docker.types import Mount
import os

with DAG(
    dag_id="train_lightfm_model",
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["dora", "ml", "model"],
) as dag:

    train_model = DockerOperator(
        task_id="train_lightfm",
        image="dora-model:latest",
        api_version="auto",
        auto_remove=True,
        command="python train_lightfm.py",
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        mounts=[
            Mount(
                source=os.getenv("PATH_MODEL"),
                target="/app/models",
                type="bind",
            )
        ],
        environment={
            "MYSQL_HOST": os.getenv("MYSQL_HOST"),
            "MYSQL_USER": os.getenv("MYSQL_USER"),
            "MYSQL_PASSWORD": os.getenv("MYSQL_PASSWORD"),
            "MYSQL_DB": os.getenv("MYSQL_DB"),
        },
    )
