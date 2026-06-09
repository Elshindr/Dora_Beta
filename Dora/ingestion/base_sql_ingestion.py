import duckdb
import pymysql
import pandas as pd
import requests
from datetime import datetime

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


def get_categorie_data():
    try:
        df_p = pd.read_parquet("categories-data/categories.zstd.parquet")
        df_p = df_p[["category_id", "category_name"]]
        df_p.head()
        df_p["idCatFsq"] = None

        df_c = pd.read_csv("Categorie.csv")
        split_col = df_c.category_label.str.split(" > ")
        df_c["last"] = df_c.category_label.apply(lambda x: x.split(" > ")[-1])

        for i, row_p in df_p.iterrows():
            for j, row_c in df_c.iterrows():
                if row_p["category_name"] == row_c["last"]:
                    df_p.loc[i, "idCatFsq"] = row_c.category_id
                    break

        df_p = df_p.dropna()
        df_p = df_p.astype({"idCatFsq": "int64"})
        return df_p
    except Exception as e:
        print(e)


def get_communes_data():
    df = pd.read_csv("communes_France.csv")
    df = df[
        [
            "code_commune_INSEE",
            "nom_commune_complet",
            "latitude",
            "longitude",
            "code_postal",
            "nom_departement",
            "nom_region",
        ]
    ]
    df = df.dropna()
    return df


def connexion_database():
    try:

        
        conx = pymysql.connect(
            host=host, 
            user=user, 
            password=pwd, 
            database=database, 
            port=port
        )

        print(" Connexion réussie !")

        # Test simple
        with conx.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"Version MySQL : {version[0]}")

        return conx
    except pymysql.Error as e:
        print(f"Erreur : {e}")


def ingest_categories():
    try:
        df = get_categorie_data()
        cox = connexion_database()
        lst_insert = []
        for i, row in df.iterrows():
            lst_insert.append((row.category_id, row["category_name"] ,row.idCatFsq ))
            
        
            cursor = cox.cursor()
            query = "INSERT IGNORE INTO categorie(idCat, name, idFsq) VALUES(%s, %s, %s)"
            cursor.executemany(query, lst_insert)
        cox.commit()
        cox.close()
    except Exception as e:
        print(e)



def ingest_communes():
    df = get_communes_data()
    cox = connexion_database()
    lst_insert= []
    for i, row in df.iterrows():
        lst_insert.append( (
            row.code_postal,
            row.nom_commune_complet,
            row.code_commune_INSEE,
            row.latitude,
            row.longitude,
            row.nom_region,
            row.nom_departement,
        ))
    
    try:
        cursor = cox.cursor()
        #query = "INSERT IGNORE INTO ville(cp, name, idCity,latitudeCity, longitudeCity, region, departement) VALUES(%s, %s,%s,%s,%s,%s,%s)"
        """cursor.executemany(
            query,
            lst_insert,
        )"""
        query = "INSERT INTO ville (cp, name, idCity, latitudeCity, longitudeCity, region, departement) VALUES ('75000', 'Paris', '97618', 48.8626304852, 2.33629344655, 'Île-de-France', 'Paris');"
        cursor.execute(query)  # execute() au lieu de executemany()
        
    except Exception as e:
        print(e)
    cox.commit()
    cox.close()


def ingest_poi():

    # Étapes S3 pour DuckDB
    duckdb.sql("INSTALL httpfs;")
    duckdb.sql("LOAD httpfs;")
    duckdb.sql("SET s3_region='us-east-1';")
    duckdb.sql("SET s3_url_style='path';")
        
    query = """
        SELECT
            fsq_place_id,
            name,
            latitude,
            longitude,
            address,
            fsq_category_ids,
            locality,
            region
        FROM read_parquet(
            's3://fsq-os-places-us-east-1/release/dt=2024-11-19/places/parquet/*.parquet',
            union_by_name=true
        )
        WHERE latitude IS NOT NULL 
        AND longitude IS NOT NULL 
        AND country = 'FR' 
        AND (locality = 'Paris' OR locality = 'PARIS') 
        AND region IS NOT NULL 
        AND address IS NOT NULL
    """
        
    print("Récupération des POIs")
    results_fsq = duckdb.sql(query).fetchall()
    print(f"POIs récupérés depuis S3")
        
    # Connexion à la base de données
    conx = connexion_database()
    cursor = conx.cursor()
        
    try:
        print(f"Connexion établie - autocommit: {conx.autocommit}")
        batch_size = 1000
        lst_insert_poi = []
            
        # Préparation des données POI
        for row in results_fsq:
            idFsq = row[0]
            name = row[1]
            lat = row[2]
            long = row[3]
            address = row[4]
            cats = row[5]
            idCity = 97618
            
            lst_insert_poi.append((idFsq, name, idCity, address, lat, long))
            
        print(f"POIs ok")
            
        # Insertion des POIs
            
        insrt_poi = """
            INSERT INTO poi(idFsq, name, idCity, address, latitudePoi, longitudePoi) 
            VALUES(%s, %s, %s, %s, %s, %s)
            
        """
            
        for i in range(0, len(lst_insert_poi), batch_size):
            batch = lst_insert_poi[i:i + batch_size]
            cursor.executemany(insrt_poi, batch)
            conx.commit()
            print(f"Batch {i//batch_size + 1}: {len(batch)} POIs insérés")
        
        # Récupérer les mappings poi/poi_cat
        print("Récupération des mappings POI")
        
        cursor.execute("SELECT idPoi, idFsq FROM poi")
        poi_mapping = {row[1]: row[0] for row in cursor.fetchall()}
        print(f"mappage ok: taille {len(poi_mapping)}")
            
        # Préparer les catégories
        print("Préparation des poi_cat...")
        lst_insert_cat_poi = []
            
        for row in results_fsq:
            idFsq = row[0]
            cats = row[5]
            idPoi = poi_mapping.get(idFsq)
                
            if idPoi:
                if isinstance(cats, str):
                    cat_list = [c.strip() for c in cats.split(',') if c.strip()]
                elif isinstance(cats, list):
                    cat_list = cats
                else:
                    cat_list = []
                    
                for cat in cat_list:
                    if cat:
                        lst_insert_cat_poi.append((cat, idPoi))
            
        # Insertion des poi_catégories
        print(f"Insertion des poi_cat")
            
        insrt_cat = """
            INSERT  INTO poi_categorie(idCat, idPoi) 
            VALUES(%s, %s)
            ON DUPLICATE KEY UPDATE idCat=VALUES(idCat)
        """
            
        for i in range(0, len(lst_insert_cat_poi), batch_size):
            batch = lst_insert_cat_poi[i:i + batch_size]
            cursor.executemany(insrt_cat, batch)
            
            print(f" Batch {i//batch_size + 1}: {len(batch)} relations insérées")
            
        print("Insertion ok")
        conx.commit()   
    except Exception as e:
        print(f"Erreur lors de l'insertion en base : {e}")
        conx.rollback()
            
    finally:
        cursor.close()
        conx.close()



def ingest_poi_cat():
    # Étapes S3 pour DuckDB
    duckdb.sql("INSTALL httpfs;")
    duckdb.sql("LOAD httpfs;")
    duckdb.sql("SET s3_region='us-east-1';")
    duckdb.sql("SET s3_url_style='path';")
        
    query = """
        SELECT
            fsq_place_id,
            fsq_category_ids,
 
        FROM read_parquet(
            's3://fsq-os-places-us-east-1/release/dt=2024-11-19/places/parquet/*.parquet',
            union_by_name=true
        )
        WHERE latitude IS NOT NULL 
        AND longitude IS NOT NULL 
        AND country = 'FR' 
        AND (locality = 'Paris' OR locality = 'PARIS') 
        AND region IS NOT NULL 
        AND address IS NOT NULL
    """
        
    print("Récupération de S3")
    results_fsq = duckdb.sql(query).fetchall()
    print(f"POIs récupérés depuis S3")
    # Connexion à la base de données
    conx = connexion_database()
    cursor = conx.cursor()
            
    try:
        print(f"Connexion établie")
        batch_size = 1000
                
        # Récupérer les mappings poi/poi_cat
        print("Récupération des mappings POI")
            
        cursor.execute("SELECT idPoi, idFsq FROM poi")
        poi_mapping = {row[1]: row[0] for row in cursor.fetchall()}
        print(f"mappage ok: taille {len(poi_mapping)}")
                
        # Préparer les catégories
        print("Préparation des poi_cat...")
        lst_insert_cat_poi = []
                
        for row in results_fsq:
            idFsq = row[0]
            cats = row[1]
            idPoi = poi_mapping.get(idFsq)
                    
            if idPoi:
                if isinstance(cats, str):
                    cat_list = [c.strip() for c in cats.split(',') if c.strip()]
                elif isinstance(cats, list):
                    cat_list = cats
                else:
                    cat_list = []
                        
                for cat in cat_list:
                    if cat:
                        lst_insert_cat_poi.append((cat, idPoi))
                
        # Insertion des poi_catégories
        print(f"Insertion des poi_cat")
                
        insrt_cat = """
            INSERT IGNORE INTO poi_categorie(idCat, idPoi) 
            VALUES(%s, %s)
            
        """
                
        for i in range(0, len(lst_insert_cat_poi), batch_size):
            batch = lst_insert_cat_poi[i:i + batch_size]
            cursor.executemany(insrt_cat, batch)
                
            print(f" Batch {i//batch_size + 1}: {len(batch)} relations insérées")
                
        print("Insertion ok")
        conx.commit()   
    except Exception as e:
        print(f"Erreur lors de l'insertion en base : {e}")
        conx.rollback()
                
    finally:
        cursor.close()
        conx.close()



def ingest_photos():
    try:
        HEADERS = {
            "Accept": "application/json",
            "Authorization": "fsq3tB6lIGQ41ijR/HguHAb8djpamppZZNliNmJJzR045lw="
        }

        # Récupère tous les POI avec leur idFsq et idPoi
        conn = connexion_database()
        cur = conn.cursor()
        cur.execute("SELECT idPoi, idFsq FROM poi")
        places = cur.fetchall()
        print(places)
        for idPoi, fsq_id in places:
            url = f"https://api.foursquare.com/v3/places/{fsq_id}/photos"
            res = requests.get(url, headers=HEADERS)
            if res.status_code != 200:
                continue

            for photo in res.json():
                idImage = photo.get("id")
                prefix = photo.get("prefix")
                suffix = photo.get("suffix")
                width = photo.get("width", 500)
                height = photo.get("height", 500)

                if idImage and prefix and suffix:
                    cur.execute("""
                        INSERT INTO image_poi (idImage, prefix, suffix, width, height, idPoi)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        
                    """, (idImage, prefix, suffix, width, height, idPoi))
            conn.commit()

        
        cur.close()
        conn.close()
        print("✅ Photos insérées dans la table image_poi.")
    except Exception as e:
        print(e)
        


#ingest_categories()
#ingest_communes()
#ingest_poi()
ingest_poi_cat()