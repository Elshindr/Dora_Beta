import osmnx as ox
import pandas as pd
import pymysql
from sqlalchemy import create_engine

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


# Connexion SQLAlchemy (pour to_sql)
engine = create_engine(
    f"mysql+pymysql://{mysql_user}:{mysql_pwd}@{mysql_host}:{mysql_port}/{mysql_db}"
)

# Connexion PyMySQL (pour requêtes directes)
conx = pymysql.connect(
    host=host,
    user=user,
    password=pwd,
    database=db,
    port=port
)
cursor = conx.cursor()

# Télécharger le graphe routier pour Paris
print("🚀 Téléchargement du graphe routier pour Paris...")
G = ox.graph_from_place("Paris, France", network_type="drive")

# Charger POI
df = pd.read_sql("SELECT idPoi, latitudePoi, longitudePoi FROM poi", conx)
print(f"➡️ {len(df)} POI récupérés depuis MySQL")

# Calcul des nearestNodeId en une passe
df['nearestNodeId'] = ox.distance.nearest_nodes(
    G,
    X=df['longitudePoi'].values,
    Y=df['latitudePoi'].values
)
print("✅ nearestNodeId calculés")

# Sauvegarder résultats dans une table temporaire avec to_sql
print("📂 Insertion des résultats dans la table temporaire...")
df[['idPoi','nearestNodeId']].to_sql("tmp_nearest", engine, if_exists="replace", index=False)

# Ajouter un index sur idPoi pour stabiliser le JOIN
cursor.execute("ALTER TABLE tmp_nearest ADD INDEX (idPoi)")

# Mise à jour en une seule requête SQL
print("⚡ Mise à jour de la table poi...")
cursor.execute("""
UPDATE poi p
JOIN tmp_nearest t ON p.idPoi = t.idPoi
SET p.nearestNodeId = t.nearestNodeId
""")

conx.commit()

# Vérification
cursor.execute("SELECT COUNT(*) FROM poi WHERE nearestNodeId IS NOT NULL")
nb = cursor.fetchone()[0]
print(f"🎉 Mise à jour terminée avec succès ! {nb} POI enrichis.")

# Fermeture
cursor.close()
conx.close()