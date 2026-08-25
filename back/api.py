from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
import pickle
import pymysql
import numpy as np
import pandas as pd
from datetime import datetime
from optimisation_itineraire import optimize_itinerary
import os
from dotenv import load_dotenv
from prometheus_fastapi_instrumentator import Instrumentator 
from prometheus_client import Counter, Gauge, Histogram 

load_dotenv()

app = FastAPI(title="Dora Recommendation API")

# =========================================================
# ======================= CONFIG DB =======================
# =========================================================

MYSQL_PORT = 3306
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")



# Déclaration des métriques 
predictions_total = Counter( "predictions_total", "Nombre total de prédictions", ["model", "status"] ) 
active_requests = Gauge( "active_requests", "Requêtes en cours de traitement", ["route"] ) 
inference_duration = Histogram( "inference_duration_seconds", "Durée d'inférence", buckets=[0.01, 0.1, 0.5, 1.0] )

#Instrumentation automatique 
Instrumentator().instrument(app).expose(app) 

def connect_mysql():
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        port=MYSQL_PORT
    )


# =========================================================
# ========== Charger modèle et dataset au démarrage =======
# =========================================================

# === Charger modèle et dataset au démarrage ===
model = None
try:
    with open("models/lightfm_model_hist.pkl", "rb") as f:
        model = pickle.load(f)
except :
    with open("../models/lightfm_model_hist.pkl", "rb") as f:
        model = pickle.load(f)
dataset = None
try:
    
    with open("models/dataset.pkl", "rb") as f:
        dataset = pickle.load(f)
except : 
        with open("../models/dataset.pkl", "rb") as f:
            dataset = pickle.load(f)

print("Modèle LightFM et dataset chargés avec succès")


# =========================================================
# ======================= SCHEMAS =========================
# =========================================================

class POISelection(BaseModel):
    selected_pois: List[int]
    user_id: int


class POISelectionByIds(BaseModel):
    lstPois: List[int]


class POI(BaseModel):
    id: int
    name: str
    lat: float
    lon: float


class ItineraryRequest(BaseModel):
    start_date: str
    end_date: str
    pois: List[POI]
    max_pois_per_day: Optional[int] = None


# =========================================================
# ======================== UTILS ML =======================
# =========================================================

def recommander_par_liste(selected_pois, top_n=10):

    item_mapping = dataset.mapping()[2]       # idPoi -> index
    reverse_mapping = {v: k for k, v in item_mapping.items()}
    max_index = model.item_embeddings.shape[0]

    if not selected_pois:
        return []

    # -----------------------------------------------------
    # 1. Catégories des POIs sélectionnés
    # -----------------------------------------------------
    conx = connect_mysql()

    placeholders = ','.join(['%s'] * len(selected_pois))

    query = f"""
        SELECT pc.idPoi, c.name AS categorie
        FROM poi_categorie pc
        JOIN categorie c ON pc.idCat = c.idCat
        WHERE pc.idPoi IN ({placeholders})
    """

    df_selected = pd.read_sql(query, conx, params=selected_pois)
    conx.close()

    if df_selected.empty:
        return []

    allowed_categories = df_selected["categorie"].unique().tolist()

    # -----------------------------------------------------
    # 2. Candidats mêmes catégories
    # -----------------------------------------------------
    conx = connect_mysql()

    placeholders = ','.join(['%s'] * len(allowed_categories))

    query = f"""
        SELECT DISTINCT pc.idPoi
        FROM poi_categorie pc
        JOIN categorie c ON pc.idCat = c.idCat
        WHERE c.name IN ({placeholders})
    """

    df_candidates = pd.read_sql(query, conx, params=allowed_categories)
    conx.close()

    candidate_pois = set(df_candidates["idPoi"].tolist())

    # -----------------------------------------------------
    # 3. Embedding utilisateur LightFM
    # -----------------------------------------------------
    item_indices = [
        item_mapping[p]
        for p in selected_pois
        if p in item_mapping and item_mapping[p] < max_index
    ]

    if len(item_indices) == 0:
        return []

    user_embedding = np.mean(model.item_embeddings[item_indices], axis=0)

    # -----------------------------------------------------
    # 4. Scoring global
    # -----------------------------------------------------
    scores = np.dot(model.item_embeddings, user_embedding)
    ranked = np.argsort(-scores)

    # -----------------------------------------------------
    # 5. Filtrage final
    # -----------------------------------------------------
    filtered = []
    for i in ranked:

        poi_id = reverse_mapping.get(i)

        if poi_id is None:
            continue

        if poi_id in selected_pois:
            continue

        if poi_id not in candidate_pois:
            continue

        filtered.append(i)

        if len(filtered) >= top_n:
            break 

    return [reverse_mapping[i] for i in filtered]


def enrich_pois(poi_ids):

    if len(poi_ids) == 0:
        return []

    conx = connect_mysql()

    query = f"""
        SELECT 
            p.idPoi,
            p.name AS name,
            c.name AS categorie,
            ROUND(AVG(a.note), 2) AS note_moyenne
        FROM poi p
        LEFT JOIN poi_categorie pc ON p.idPoi = pc.idPoi
        LEFT JOIN categorie c ON pc.idCat = c.idCat
        LEFT JOIN avis a ON p.idPoi = a.idPoi
        WHERE p.idPoi IN ({','.join(map(str, poi_ids))})
        GROUP BY p.idPoi
    """

    df = pd.read_sql(query, conx)
    conx.close()
    df['note_moyenne'] = df['note_moyenne'].fillna(3)
    return df.to_dict(orient="records")


# =========================================================
# ======================= ENDPOINTS =======================
# =========================================================

@app.get("/health")
def health():
    active_requests.labels(route="health").inc() 
    active_requests.labels(route="health").dec() 
    return {"status": "ok", "model_loaded": True}


@app.get("/api/pois")
def list_pois(limit: int = 50, offset: int = 0):
    active_requests.labels(route="api/pois").inc() 
    with inference_duration.time():
        conx = connect_mysql()

        query = f"""
            SELECT p.idPoi, p.name, c.name AS categorie
            FROM poi p
            LEFT JOIN poi_categorie pc ON p.idPoi = pc.idPoi
            LEFT JOIN categorie c ON pc.idCat = c.idCat
            LIMIT {limit} OFFSET {offset}
        """

        df = pd.read_sql(query, conx)
        conx.close()
    active_requests.labels(route="api/pois").dec() 

    return df.to_dict(orient="records")


@app.get("/api/poi/{poi_id}")
def get_poi(poi_id: int):

    active_requests.labels(route="api/poi/:id").inc() 
    with inference_duration.time(): 
        conx = connect_mysql()

        query = f"""
            SELECT 
                p.idPoi,
                p.name,
                c.name AS categorie,
                ROUND(AVG(a.note), 2) AS note_moyenne
            FROM poi p
            LEFT JOIN poi_categorie pc ON p.idPoi = pc.idPoi
            LEFT JOIN categorie c ON pc.idCat = c.idCat
            LEFT JOIN avis a ON p.idPoi = a.idPoi
            WHERE p.idPoi = {poi_id}
            GROUP BY p.idPoi
        """

        df = pd.read_sql(query, conx)
        conx.close()

    if df.empty:
        raise HTTPException(status_code=404, detail="POI non trouvé")
    active_requests.labels(route="api/poi/:id").dec() 
    df['note_moyenne'] = df['note_moyenne'].fillna(3)
    return df.iloc[0].to_dict()


@app.get("/api/categories")
def list_categories():
    active_requests.labels(route="api/categories").inc() 
    with inference_duration.time(): 
        conx = connect_mysql()

        query = "SELECT idCat, name FROM categorie"

        df = pd.read_sql(query, conx)
        conx.close()
    active_requests.labels(route="api/categories").dec()
    return df.to_dict(orient="records")


@app.get("/api/search")
def search_poi(q: str = Query(..., min_length=2), limit: int = 20):
    active_requests.labels(route="api/search").inc() 
    with inference_duration.time(): 
        conx = connect_mysql()

        query = f"""
            SELECT p.idPoi, p.name, c.name AS categorie
            FROM poi p
            LEFT JOIN poi_categorie pc ON p.idPoi = pc.idPoi
            LEFT JOIN categorie c ON pc.idCat = c.idCat
            WHERE p.name LIKE '%{q}%'
            LIMIT {limit}
        """

        df = pd.read_sql(query, conx)
        conx.close()
    active_requests.labels(route="api/search").dec()

    return df.to_dict(orient="records")


@app.get("/api/user/{user_id}/history")
def user_history(user_id: int, limit: int = 50):
    active_requests.labels(route="api/user/:id/history").inc() 
    with inference_duration.time():
        conx = connect_mysql()

        query = f"""
            SELECT 
                h.idPoi,
                p.name,
                c.name AS categorie,
                h.dateVisite
            FROM historique_voyage h
            JOIN poi p ON h.idPoi = p.idPoi
            LEFT JOIN poi_categorie pc ON p.idPoi = pc.idPoi
            LEFT JOIN categorie c ON pc.idCat = c.idCat
            WHERE h.idUser = {user_id}
            ORDER BY h.dateVisite DESC
            LIMIT {limit}
        """

        df = pd.read_sql(query, conx)
        conx.close()
    active_requests.labels(route="api/user/:id/history").dec()
    return df.to_dict(orient="records")


@app.post("/api/recommend_from_selection")
def recommend_from_selection(selection: POISelection):
    active_requests.labels(route="api/recommend_from_selection").inc() 
    try:
        with inference_duration.time():
            recommended_ids = recommander_par_liste(selection.selected_pois, top_n=10)
            results = enrich_pois(recommended_ids)
            predictions_total.labels(model="v1", status="success").inc() 
        active_requests.labels(route="api/recommend_from_selection").dec()
        return results
    except Exception as e: 
        predictions_total.labels(model="v1", status="error").inc()
        active_requests.labels(route="api/recommend_from_selection").dec()
        raise e 

        
    


@app.get("/api/cats")
async def get_categories():
    active_requests.labels(route="api/cats").inc() 
    with inference_duration.time():
        conx = connect_mysql()

        with conx.cursor() as cursor:
            cursor.execute('SELECT name, idCat FROM categorie WHERE isActive=1 ORDER BY name;')
            res = cursor.fetchall()


    active_requests.labels(route="api/cats").dec() 
    return [
        {"name": row[0], "idCat": row[1]}
        for row in res
    ]



@app.get("/api/poisbycats/{idCat}")
async def get_poi_by_idcat(idCat):
    active_requests.labels(route="api/poisbycats/:id").inc() 
    try:
        with inference_duration.time():
            conx = connect_mysql()

            with conx.cursor() as cursor:
                cursor.execute("""
                    SELECT p.idPoi, p.idFsq, p.name, p.latitudePoi, p.longitudePoi,
                        p.address, c.name, c.idCat, AVG(a.note)
                    FROM poi p
                    JOIN poi_categorie pc ON pc.idPoi = p.idPoi
                    JOIN categorie c ON c.idCat = pc.idCat
                    JOIN avis a ON a.idPoi = p.idPoi
                    WHERE c.idCat=%s
                    GROUP BY p.idPoi
                """, [idCat])

                res = cursor.fetchall()

            active_requests.labels(route="api/poisbycats/:id").dec()

            return [
                {
                    "idPoi": r[0],
                    "idFsq": r[1],
                    "namePoi": r[2],
                    "latitudePoi": r[3],
                    "longitudePoi": r[4],
                    "address": r[5],
                    "nameCat": r[6],
                    "idCat": r[7],
                    "note": r[8]
                }
                for r in res
            ]
    except Exception as e:
        print("Error in gett_poi_by_idcat:"+str(e))
        active_requests.labels(route="api/poisbycats/:id").dec()
        return []
               

@app.post("/api/optimize-itinerary/")
async def get_optimized_itinerary(request: ItineraryRequest):
    active_requests.labels(route="api/optimize-itinerary").inc() 
    try:
         with inference_duration.time():

            active_requests.labels(route="api/optimize-itinerary").dec()
            return optimize_itinerary(
                start_date=request.start_date,
                end_date=request.end_date,
                pois=[poi.dict() for poi in request.pois],
                max_pois_per_day=request.max_pois_per_day
            )

    except Exception as e:
        active_requests.labels(route="api/optimize-itinerary").dec()
        raise HTTPException(status_code=400, detail=str(e))



@app.get("/api/avisbypoi/{idPoi}")
async def get_avis_by_poi(idPoi):
    active_requests.labels(route="api/avisbypoi/:id").inc() 

    try:
        with inference_duration.time():
            conx = connect_mysql()

            with conx.cursor() as cursor:
                cursor.execute(
                    'SELECT idTip, content, note FROM avis WHERE idPoi=%s',
                    [idPoi]
                )

                res = cursor.fetchall()
            active_requests.labels(route="api/avisbypoi/:id").dec()
            return [
                {"idTip": r[0], "content": r[1], "note": r[2]}
                for r in res
            ]
    except Exception as e:
        active_requests.labels(route="api/avisbypoi/:id").dec()
        return []

    


@app.post("/api/poi_by_ids")
async def get_list_pois_by_ids(lstPois: POISelectionByIds):
    active_requests.labels(route="api/poi_by_ids").inc() 
    try: 
        with inference_duration.time():
            if not lstPois.lstPois:
                return []

            conx = connect_mysql()

            placeholders = ','.join(['%s'] * len(lstPois.lstPois))

            query = f"""
                SELECT 
                    p.idPoi, p.idFsq, p.name, p.latitudePoi, p.longitudePoi,
                    p.address, c.name, c.idCat, ROUND(AVG(a.note), 2)
                FROM poi p
                JOIN poi_categorie pc ON pc.idPoi = p.idPoi
                JOIN categorie c ON c.idCat = pc.idCat
                LEFT JOIN avis a ON a.idPoi = p.idPoi
                WHERE p.idPoi IN ({placeholders})
                GROUP BY p.idPoi
            """

            with conx.cursor() as cursor:
                cursor.execute(query, lstPois.lstPois)
                results = cursor.fetchall()

            active_requests.labels(route="api/poi_by_ids").dec()

            return [
                {
                    "idPoi": r[0],
                    "idFsq": r[1],
                    "namePoi": r[2],
                    "latitudePoi": r[3],
                    "longitudePoi": r[4],
                    "address": r[5],
                    "nameCat": r[6],
                    "idCat": r[7],
                    "note": r[8]
                }
                for r in results
            ]
    except Exception as e:
        active_requests.labels(route="api/poi_by_ids").dec()
        return []
