import pandas as pd
import numpy as np
import pymysql
from lightfm import LightFM
from lightfm.data import Dataset
import pickle
from tqdm import tqdm
import os
from dotenv import load_dotenv
load_dotenv()

# === CONFIG DB (même que recommandations_lightfmHistMLFLOW.py) ===
MYSQL_HOST     = os.getenv("MYSQL_HOST")
MYSQL_USER     = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB       = os.getenv("MYSQL_DB")
MYSQL_PORT = 3306

import os
from dotenv import load_dotenv

load_dotenv()

print("=== DEBUG ENV ===")
print(f"MYSQL_HOST     = {os.getenv('MYSQL_HOST')}")
print(f"MYSQL_USER     = {os.getenv('MYSQL_USER')}")
print(f"MYSQL_PASSWORD = {os.getenv('MYSQL_PASSWORD')}")
print(f"MYSQL_DB       = {os.getenv('MYSQL_DB')}")
print("=================")

MODEL_PATH = "lightfm_model_hist.pkl"
DATASET_PATH = "dataset.pkl"

# === Connexion MySQL ===
def connect_mysql():
    print("host:"+os.getenv("MYSQL_HOST"))
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        port=MYSQL_PORT
    )
    

# === Chargement des données ===
def charger_donnees():
    conx = connect_mysql()

    # Avis utilisateurs
    query_avis = """
        SELECT a.idUser, a.idPoi, a.note, c.name AS categorie
        FROM avis a
        JOIN poi_categorie pc ON a.idPoi = pc.idPoi
        JOIN categorie c ON pc.idCat = c.idCat
        WHERE a.note IS NOT NULL
    """
    df_avis = pd.read_sql(query_avis, conx)

    # Historique de voyage (implicite)
    query_hist = """
        SELECT h.idUser, h.idPoi, c.name AS categorie
        FROM historique_voyage h
        JOIN poi_categorie pc ON h.idPoi = pc.idPoi
        JOIN categorie c ON pc.idCat = c.idCat
    """
    df_hist = pd.read_sql(query_hist, conx)

    # Tous les POIs, avec catégorie si existante
    query_pois = """
        SELECT p.idPoi, COALESCE(c.name, 'Unknown') AS categorie
        FROM poi p
        LEFT JOIN poi_categorie pc ON p.idPoi = pc.idPoi
        LEFT JOIN categorie c ON pc.idCat = c.idCat
    """
    df_pois = pd.read_sql(query_pois, conx)

    conx.close()
    return df_avis, df_hist, df_pois

# === Préparer le dataset LightFM ===
def preparer_dataset(df_avis, df_hist, df_pois):
    dataset = Dataset()

    # Utilisateurs uniques
    users = pd.concat([df_avis['idUser'], df_hist['idUser']]).unique()
    
    # Tous les items (POIs), même sans interactions
    items = df_pois['idPoi'].unique()

    # Toutes les catégories uniques
    item_features_unique = df_pois['categorie'].unique()

    dataset.fit(users=users, items=items, item_features=item_features_unique)

    # Interactions explicites
    interactions, _ = dataset.build_interactions(
        ((x['idUser'], x['idPoi'], x['note']) for _, x in tqdm(df_avis.iterrows(),
                                                               total=len(df_avis),
                                                               desc="Interactions explicites"))
    )

    # Interactions implicites
    interactions_hist, _ = dataset.build_interactions(
        ((x['idUser'], x['idPoi']) for _, x in tqdm(df_hist.iterrows(),
                                                    total=len(df_hist),
                                                    desc="Interactions implicites"))
    )

    interactions = interactions + interactions_hist

    # Features des items : tous les POIs, catégorie par défaut si manquante
    item_features_list = (
        (row['idPoi'], [row['categorie']] if pd.notna(row['categorie']) else ['Unknown'])
        for _, row in df_pois.iterrows()
    )
    item_features_matrix = dataset.build_item_features(item_features_list)

    return dataset, interactions, item_features_matrix

# === Entraînement et sauvegarde ===
def main():
    print("Chargement des données...")
    df_avis, df_hist, df_pois = charger_donnees()

    print("Préparation du dataset LightFM...")
    dataset, interactions, item_features = preparer_dataset(df_avis, df_hist, df_pois)

    print("Entraînement du modèle LightFM...")
    model = LightFM(loss="warp", no_components=50)
    model.fit(interactions, item_features=item_features, epochs=10, num_threads=4)

    # Sauvegarde du modèle
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    # Sauvegarde du dataset
    with open(DATASET_PATH, "wb") as f:
        pickle.dump(dataset, f)

    print("Modèle et dataset sauvegardés avec tous les POIs inclus")


if __name__ == "__main__":
    main()

