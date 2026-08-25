"""
DAG : met à jour la base de données puis relance l'entraînement du
modèle de recommandation.
"""
import os
import socket
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.operators.trigger_dagrun import TriggerDagRunOperator



MYSQL_HOST = os.environ.get("MYSQL_HOST")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_USER = os.environ.get("MYSQL_USER")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
MYSQL_DB = os.environ.get("MYSQL_DB")
API = os.environ.get("API")

default_args = {
    "owner": "dora-reco",
    "retries": 1,
    "retry_delay": timedelta(seconds=1),
}

with DAG(
    dag_id="update_db_and_retrain_model",
    description="Ingestion des nouvelles données POI puis ré-entraînement du modèle",
    default_args=default_args,
    schedule=None, #"@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["dora", "ml", "database"],
) as dag:

    def _check_db_connection(**context):
        """
        Logue les infos de connexion et vérifie que la base MySQL ciblée est bien joignable. 
        """

        

        print("=== Config de connexion résolue par Airflow ===")
        print(f"MYSQL_HOST = {MYSQL_HOST}")
        print(f"MYSQL_PORT = {MYSQL_PORT}")
        print(f"MYSQL_USER = {MYSQL_USER}")
        print(f"MYSQL_DB   = {MYSQL_DB}")
        print(f"MYSQL_PASSWORD = {'(vide)' if not MYSQL_PASSWORD else '*** (définie, non affichée)'}")
        print(f"API ={API}")

        try:
            import pymysql
        except ImportError:
            print(
                "AVERTISSEMENT : pymysql n'est pas installé dans l'image "
                "Airflow, le test réseau ci-dessus est passé mais la "
                "connexion applicative n'a pas pu être vérifiée. Ajoute "
                "pymysql à _PIP_ADDITIONAL_REQUIREMENTS dans "
                "docker-compose.airflow.yml pour activer ce test complet."
            )
            return

        if not MYSQL_HOST or not MYSQL_USER or not MYSQL_DB:
            raise AirflowFailException(
                "Variables DB manquantes ou vides"
            )

        try:
            conn = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB,
                connect_timeout=5,
            )
            with conn.cursor() as cursor:
                cursor.execute("SELECT DATABASE(), @@hostname, VERSION();")
                db_name, server_hostname, version = cursor.fetchone()
                print(f"Connecté à la base '{db_name}' sur le serveur '{server_hostname}' (MySQL {version}).")
            conn.close()
        except Exception as exc:
            raise AirflowFailException(f"Connexion applicative à MySQL échouée : {exc}")

    check_db_connection = PythonOperator(
        task_id="check_db_connection",
        python_callable=_check_db_connection,
    )

    update_database = BashOperator(
        task_id="update_database",
        bash_command="python /opt/airflow/scripts/base_maj.py",
    )

    trigger_training = TriggerDagRunOperator(
        task_id="trigger_train_lightfm",
        trigger_dag_id="train_lightfm_model", 
        wait_for_completion=False, 
    )


    check_db_connection >> update_database >> trigger_training