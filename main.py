from fastapi import FastAPI
from pydantic import BaseModel
import pickle
import numpy as np
import pymysql
import pandas as pd
import os
from dotenv import load_dotenv
load_dotenv()



app = FastAPI(title="API Recommandations Dora")

# -------------------------------
# Charger modèle + mappings
# -------------------------------
with open("lightfm_model_hist.pkl", "rb") as f:
    model = pickle.load(f)

with open("user_id_map.pkl", "rb") as f:
    user_id_map = pickle.load(f)

with open("item_id_map.pkl", "rb") as f:
    item_id_map = pickle.load(f)

item_id_map_inv = {v: k for k, v in item_id_map.items()}

# -------------------------------
# Connexion MySQL
# -------------------------------
def connect_mysql():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
        port=3306,
        cursorclass=pymysql.cursors.DictCursor
    )

# -------------------------------
# Schéma POST
# -------------------------------
class RecommendationRequest(BaseModel):
    user_id: int
    poi_list: list[int]
    n: int = 10

# -------------------------------
# Endpoint recommandations filtrées
# -------------------------------
@app.post("/recommendations_by_list")
def recommendations_by_list(req: RecommendationRequest):
    user_id = req.user_id
    poi_list = req.poi_list
    n = req.n

    if user_id not in user_id_map:
        return {"error": "Utilisateur inconnu du modèle"}

    user_idx = user_id_map[user_id]

    indices = [item_id_map[poi] for poi in poi_list if poi in item_id_map]

    if not indices:
        return {"error": "Aucun POI valide dans la liste"}

    scores = model.predict(user_idx, np.array(indices))
    top_idx = np.argsort(-scores)[:n]
    top_items = [indices[i] for i in top_idx]
    recommended_poi_ids = [item_id_map_inv[i] for i in top_items]

    conx = connect_mysql()
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
    df = pd.read_sql(query, conx)
    conx.close()

    return df.to_dict(orient="records")