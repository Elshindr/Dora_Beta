import pandas as pd
import numpy as np
import pymysql
from lightfm import LightFM
from lightfm.data import Dataset
import pickle
import os
from tqdm import tqdm

# === CONFIG BASE DE DONNÉES ===
MYSQL_HOST = "database-dora-mysql.c6dmgs40etf5.us-east-1.rds.amazonaws.com"
MYSQL_USER = "admin"
MYSQL_PWD = "projetdora"
MYSQL_DB = "doramysql"
MYSQL_PORT = 3306

# === CONFIG MODEL ===
MODEL_PATH = "lightfm_model_hist.pkl"

# === CONNEXION MYSQL ===
def connect_mysql():
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PWD,
        database=MYSQL_DB,
        port=MYSQL_PORT
    )

# === CHARGEMENT DES DONNÉES ===
def charger_donnees():
    conx = connect_mysql()

    query_avis = """
        SELECT a.idUser, a.idPoi, a.note, c.name AS categorie
        FROM avis a
        JOIN poi_categorie pc ON a.idPoi = pc.idPoi
        JOIN categorie c ON pc.idCat = c.idCat
        WHERE a.note IS NOT NULL
    """
    df_avis = pd.read_sql(query_avis, conx)
    print(f"{len(df_avis)} avis chargés")

    query_hist = """
        SELECT h.idUser, h.idPoi, c.name AS categorie
        FROM historique_voyage h
        JOIN poi_categorie pc ON h.idPoi = pc.idPoi
        JOIN categorie c ON pc.idCat = c.idCat
    """
    df_hist = pd.read_sql(query_hist, conx)
    print(f"{len(df_hist)} visites historiques chargées")

    conx.close()
    return df_avis, df_hist

# === CONSTRUCTION DU DATASET ===
def preparer_dataset(df_avis, df_hist):
    dataset = Dataset()

    # Ensemble unique d'utilisateurs et items
    users = pd.concat([df_avis['idUser'], df_hist['idUser']]).unique()
    items = pd.concat([df_avis['idPoi'], df_hist['idPoi']]).unique()
    item_features_unique = pd.concat([df_avis['categorie'], df_hist['categorie']]).unique()

    dataset.fit(users=users, items=items, item_features=item_features_unique)

    # Interactions explicites
    interactions, weights = dataset.build_interactions(
        ((x['idUser'], x['idPoi'], x['note']) for _, x in tqdm(df_avis.iterrows(),
                                                               total=len(df_avis),
                                                               desc="Interactions explicites"))
    )

    # Interactions implicites (historique de voyage)
    interactions_hist, _ = dataset.build_interactions(
        ((x['idUser'], x['idPoi']) for _, x in tqdm(df_hist.iterrows(),
                                                    total=len(df_hist),
                                                    desc="Interactions implicites"))
    )
    interactions = interactions + interactions_hist  # Fusion des matrices

    # Features des items
    item_features_list = (
        (x['idPoi'], [x['categorie']])
        for _, x in tqdm(pd.concat([df_avis, df_hist]).iterrows(),
                         total=len(df_avis) + len(df_hist),
                         desc="Item features")
    )
    item_features_matrix = dataset.build_item_features(item_features_list)

    return dataset, interactions, item_features_matrix

# === ENTRAÎNEMENT OU CHARGEMENT DU MODÈLE ===
def entrainer_ou_charger_modele(dataset, interactions, item_features):
    if os.path.exists(MODEL_PATH):
        print("Chargement du modèle existant...")
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
    else:
        print("Entraînement du modèle LightFM...")
        model = LightFM(loss='warp', no_components=50)
        model.fit(interactions, item_features=item_features, epochs=10, num_threads=4)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model, f)
        print("Modèle entraîné et sauvegardé.")
    return model

# === RECOMMANDATION ===
def recommander(model, dataset, user_id, item_features, conx, n=10):
    user_idx = list(dataset.mapping()[0].keys()).index(user_id)
    n_items = len(dataset.mapping()[2])
    scores = model.predict(user_idx, np.arange(n_items), item_features=item_features)
    top_items_idx = np.argsort(-scores)[:n]

    item_id_map = {v: k for k, v in dataset.mapping()[2].items()}
    recommended_poi_ids = [item_id_map[i] for i in top_items_idx]

    # Enrichir les POI avec nom + catégorie + note moyenne
    query = f"""
        SELECT p.idPoi, p.name, c.name AS categorie,
               ROUND(AVG(a.note), 2) AS note_moyenne
        FROM poi p
        LEFT JOIN poi_categorie pc ON p.idPoi = pc.idPoi
        LEFT JOIN categorie c ON pc.idCat = c.idCat
        LEFT JOIN avis a ON p.idPoi = a.idPoi
        WHERE p.idPoi IN ({','.join(map(str, recommended_poi_ids))})
        GROUP BY p.idPoi, p.name, c.name
    """
    df_recs = pd.read_sql(query, conx)
    return df_recs

# === MAIN ===
def main():
    print("Chargement des données depuis MySQL...")
    df_avis, df_hist = charger_donnees()

    print("Préparation du dataset LightFM...")
    dataset, interactions, item_features = preparer_dataset(df_avis, df_hist)

    print("Construction du modèle...")
    model = entrainer_ou_charger_modele(dataset, interactions, item_features)

    # Choisir un utilisateur aléatoire
    all_users = pd.concat([df_avis['idUser'], df_hist['idUser']]).unique()
    user_id = int(np.random.choice(all_users))
    print(f"Génération de recommandations pour l'utilisateur {user_id}...")

    conx = connect_mysql()
    recs = recommander(model, dataset, user_id, item_features, conx)
    conx.close()

    print("\nRecommandations personnalisées :")
    print(recs.to_string(index=False))

if __name__ == "__main__":
    main()