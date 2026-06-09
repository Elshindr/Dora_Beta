import pymysql
import random
from datetime import datetime, timedelta
from tqdm import tqdm

from dotenv import load_dotenv
import os
from pathlib import Path


load_dotenv(Path("../.env")) 

# === Config MySQL ===
host     = os.getenv("MYSQL_HOST")
user     = os.getenv("MYSQL_USER")
pwd = os.getenv("MYSQL_PASSWORD")
db       = os.getenv("MYSQL_DB")
port=3306

# === CONNEXION MYSQL ===
def connect_mysql():
    return pymysql.connect(
        host=host,
        user=user,
        password=pwd,
        database=db,
        port=port
    )

def generer_historique_fictif(nb_visites_par_user=50):
    conx = connect_mysql()
    cursor = conx.cursor()

    # Récupérer tous les utilisateurs et POI
    cursor.execute("SELECT DISTINCT idUser FROM avis")
    users = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT idPoi FROM poi")
    pois = [row[0] for row in cursor.fetchall()]

    print(f"➡️ {len(users)} utilisateurs")
    print(f"➡️ {len(pois)} POI")

    historique = []

    for user in tqdm(users, desc="Génération historique"):
        # Pour chaque utilisateur, choisir des POI au hasard sans doublon
        visited_pois = random.sample(pois, min(nb_visites_par_user, len(pois)))
        for poi in visited_pois:
            # Date aléatoire dans les 365 derniers jours
            random_days = random.randint(0, 365)
            date_visite = datetime.now() - timedelta(days=random_days)
            historique.append((user, poi, date_visite))

    # Insertion en masse avec IGNORE pour éviter les erreurs de doublons
    print("➡️ Insertion en base...")
    query = """
        INSERT IGNORE INTO historique_voyage (idUser, idPoi, dateVisite)
        VALUES (%s, %s, %s)
    """
    cursor.executemany(query, historique)
    conx.commit()
    cursor.close()
    conx.close()
    print(f"✅ {len(historique)} visites historiques fictives insérées.")

if __name__ == "__main__":
    generer_historique_fictif(nb_visites_par_user=50)