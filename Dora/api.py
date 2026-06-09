from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional,Dict
import pickle
import pymysql
import numpy as np
import pandas as pd
from datetime import datetime
from optimisation_itineraire import  optimize_itinerary
import os
from dotenv import load_dotenv
load_dotenv()
app = FastAPI(title="Dora Recommendation API")

# === CONFIG DB ===

MYSQL_PORT = 3306
MYSQL_HOST     = os.getenv("MYSQL_HOST")
MYSQL_USER     = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB       = os.getenv("MYSQL_DB")

def connect_mysql():
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        port=MYSQL_PORT
    )

# === Charger modèle et dataset au démarrage ===
with open("lightfm_model_hist.pkl", "rb") as f:
    model = pickle.load(f)

with open("dataset.pkl", "rb") as f:
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
# ======================= UTILS ML ========================
# =========================================================

def recommander_par_liste(selected_pois, top_n=10):

    item_mapping = dataset.mapping()[2]       # idPoi -> index
    reverse_mapping = {v: k for k, v in item_mapping.items()}

    max_index = model.item_embeddings.shape[0]

    item_indices = [
        item_mapping[p]
        for p in selected_pois
        if p in item_mapping and item_mapping[p] < max_index
    ]
    
    # Garder uniquement les POI connus
    #item_indices = [item_mapping[p] for p in selected_pois if p in item_mapping]

    if len(item_indices) == 0:
        return []

    # Embeddings des POI sélectionnés
    item_embeddings = model.item_embeddings[item_indices]

    # Profil utilisateur temporaire = moyenne
    user_embedding = np.mean(item_embeddings, axis=0)

    # Score tous les items
    scores = np.dot(model.item_embeddings, user_embedding)

    # Trier
    ranked = np.argsort(-scores)

    # Enlever déjà sélectionnés
    ranked = [i for i in ranked if i not in item_indices]

    # Top N
    top_indices = ranked[:top_n]

    # Retour idPoi
    recommended_ids = [reverse_mapping[i] for i in top_indices]

    return recommended_ids


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

    return df.to_dict(orient="records")


# =========================================================
# ======================= ENDPOINTS =======================
# =========================================================

# -------- HEALTH CHECK --------
@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": True}


# -------- LISTE DES POIS --------
@app.get("/api/pois")
def list_pois(limit: int = 50, offset: int = 0):

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

    return df.to_dict(orient="records")


# -------- POI PAR ID --------
@app.get("/api/poi/{poi_id}")
def get_poi(poi_id: int):

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

    return df.iloc[0].to_dict()


# -------- LISTE DES CATEGORIES --------
@app.get("/api/categories")
def list_categories():

    conx = connect_mysql()

    query = "SELECT idCat, name FROM categorie"

    df = pd.read_sql(query, conx)
    conx.close()

    return df.to_dict(orient="records")


# -------- SEARCH POI --------
@app.get("/api/search")
def search_poi(q: str = Query(..., min_length=2), limit: int = 20):

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

    return df.to_dict(orient="records")


# -------- HISTORIQUE UTILISATEUR --------
@app.get("/api/user/{user_id}/history")
def user_history(user_id: int, limit: int = 50):

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

    return df.to_dict(orient="records")


# -------- RECOMMANDATION LIGHTFM --------
@app.post("/api/recommend_from_selection")
def recommend_from_selection(selection: POISelection):
    print(selection)
    # 1. Recommandations LightFM
    recommended_ids = recommander_par_liste(selection.selected_pois, top_n=10)
    print(recommended_ids)
    # 2. Enrichissement base
    results = enrich_pois(recommended_ids)
    print(results)
    return results

# -------- CAtegorie bis --------
@app.get("/api/cats")
async def get_categories():
    try:
        host = MYSQL_HOST
        user = MYSQL_USER
        port = 3306
        database = MYSQL_DB
        pwd = MYSQL_PASSWORD

            
        conx = pymysql.connect(
            host=host, 
            user=user, 
            password=pwd, 
            database=database, 
            port=port
        )
        print(" Connexion réussie !")

        with conx.cursor() as cursor:
            cursor.execute('SELECT * FROM categorie ORDER BY name;')
            res = cursor.fetchall()
            
            lstCats= []
            
            for row in res:
                cat= {
                    "name": row[0],
                    "idCat": row[1],
                    "idFsq": row[4]
                }
                
                lstCats.append(cat)

        return lstCats
    except pymysql.Error as e:
        print(f"Erreur Cats: {e}")


# -------- liste poi par categorie --------
@app.get("/api/poisbycats/{idCat}")
async def get_poi_by_idcat(idCat):
    try:
        host = MYSQL_HOST
        user = MYSQL_USER
        port = 3306
        database = MYSQL_DB
        pwd = MYSQL_PASSWORD

                
        conx = pymysql.connect(
            host=host, 
            user=user, 
            password=pwd, 
            database=database, 
            port=port
        )
        print(" Connexion réussie !")

        with conx.cursor() as cursor:
            cursor.execute(
                'SELECT p.idPoi, p.idFsq, p.name as namePoi, p.latitudePoi, p.longitudePoi, p.address, c.name as nameCat, c.idCat, AVG(a.note) as note FROM poi as p JOIN poi_categorie as pc ON pc.idPoi = p.idPoi JOIN categorie as c ON c.idCat = pc.idCat JOIN avis as a on a.idPoi=p.idPoi  WHERE c.idCat=%s GROUP BY p.idPoi ;',
                [idCat]
            )
            res = cursor.fetchall()
                
            lstPois= []
            
            for row in res:
                poi= {
                    "idPoi": row[0],
                    "idFsq": row[1],
                    "namePoi": row[2],
                    "latitudePoi": row[3],
                    "longitudePoi": row[4],
                    "address": row[5],
                    "nameCat": row[6],
                    "idCat": row[7],
                    "note": row[8]
                }
                    
                lstPois.append(poi)

        return lstPois
    except pymysql.Error as e:
        print(f"Erreur  poi_by_cats: {e}")


# -------- liste poi pour trajet optimisé --------
@app.post("/api/optimize-itinerary/")
async def get_optimized_itinerary(request: ItineraryRequest):
    try:
        itinerary = optimize_itinerary(
            start_date=request.start_date,
            end_date=request.end_date,
            pois=[poi.dict() for poi in request.pois],
            max_pois_per_day=request.max_pois_per_day
        )
        return itinerary
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- liste des avis par poi --------
@app.get("/api/avisbypoi/{idPoi}")
async def get_avis_by_poi(idPoi):
    try:
        host = MYSQL_HOST
        user = MYSQL_USER
        port = 3306
        database = MYSQL_DB
        pwd = MYSQL_PASSWORD

                    
        conx = pymysql.connect(
            host=host, 
            user=user, 
            password=pwd, 
            database=database, 
            port=port
        )
        print(" Connexion réussie !")

        with conx.cursor() as cursor:
            cursor.execute(
                'SELECT a.idTip, a.content, a.note FROM avis a WHERE a.idPoi = %s;',
                [idPoi]
            )
            res = cursor.fetchall()
                    
            lstAvis= []
                
            for row in res:
                poi= {
                    "idTip": row[0],
                    "content": row[1],
                    "note": row[2],
                }

                lstAvis.append(poi)

        return lstAvis
    except pymysql.Error as e:
        print(f"Erreur Avis : {e}")
    

@app.post("/api/poi_by_ids")
async def get_list_pois_by_ids(lstPois: POISelectionByIds):
    """
    Récupère une liste de POIs avec leurs notes moyennes
    """
    try:
        print(lstPois.lstPois)
        if not lstPois or len(lstPois.lstPois) == 0:
            return []
        
        conx = connect_mysql() 
        
        # Construire la clause IN 
        placeholders = ','.join(['%s'] * len(lstPois.lstPois))
        
        query = f"""
            SELECT 
                p.idPoi, 
                p.idFsq, 
                p.name as namePoi, 
                p.latitudePoi, 
                p.longitudePoi, 
                p.address, 
                c.name as nameCat, 
                c.idCat, 
                ROUND(AVG(a.note), 2) as note 
            FROM poi as p 
            JOIN poi_categorie as pc ON pc.idPoi = p.idPoi 
            JOIN categorie as c ON c.idCat = pc.idCat 
            LEFT JOIN avis as a ON a.idPoi = p.idPoi  
            WHERE p.idPoi IN ({placeholders})
            GROUP BY p.idPoi, p.idFsq, p.name, p.latitudePoi, p.longitudePoi, p.address, c.name, c.idCat
        """
        
        with conx.cursor() as cursor:
            cursor.execute(query, lstPois.lstPois) 
            results = cursor.fetchall()
        
        conx.close()
        
        # Construire la liste de résultats
        pois_list = []
        for row in results:
            poi = {
                "idPoi": row[0],
                "idFsq": row[1],
                "namePoi": row[2],
                "latitudePoi": row[3],
                "longitudePoi": row[4],
                "address": row[5],
                "nameCat": row[6],
                "idCat": row[7],
                "note": row[8]
            }
            pois_list.append(poi)
        
        print(f"{len(pois_list)} POIs récupérés")
        return pois_list
        
    except pymysql.Error as e:
        print(f"Erreur SQL pois_by_ids: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur base de données: {str(e)}")
    except Exception as e:
        print(f"Erreur pois_by_ids: {e}")
        raise HTTPException(status_code=500, detail=str(e))