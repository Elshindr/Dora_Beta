import os
from dotenv import load_dotenv
from pathlib import Path
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from ORM import Base, Categorie, Ville, Poi,Poi_Categorie, User,Avis, Historique_Voyage, Version
from pyiceberg.catalog import load_catalog
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.mysql import insert as mysql_insert
from pyiceberg.expressions import And, NotIn, IsNull, NotNull
import numpy as np
import pandas as pd
from faker import Faker
import random
from tqdm import tqdm
from datetime import datetime, timedelta

# === Config MySQL ===
#load_dotenv(Path(".dev.env"))

API = os.getenv("API")
host = os.getenv("MYSQL_HOST")
user = os.getenv("MYSQL_USER")
pwd = os.getenv("MYSQL_PASSWORD")
db = os.getenv("MYSQL_DB")
port = 3306

engine = create_engine(f"mysql+mysqlconnector://{user}:{pwd}@{host}:{port}/{db}")

Session = sessionmaker(bind=engine)


def get_poi_bd():
    df_bd = None
    with engine.connect() as conn:
        df_bd = pd.read_sql("SELECT * FROM poi", conn)
    return df_bd


def get_cat_bd():
    df_bd = None
    with engine.connect() as conn:
        df_bd = pd.read_sql("SELECT * FROM categorie", conn)
    return df_bd


def data_cat():
    df_cat_cur = None
    try:
        print("categories")

        # Charger le catalogue et filtrer
        catalog = load_catalog(
            "default",
            **{
                "warehouse": "places",
                "uri": "https://catalog.h3-hub.foursquare.com/iceberg",
                "token": API,
                "header.content-type": "application/vnd.api+json",
                "rest-metrics-reporting-enabled": "false",
            },
        )

        excluded_values = ["Home (private)", "Office", "Adult Education", "Adult Store", "Advertising Agency", "Agriculture and Forestry Service", "Agriturismo", "AIDS Resource", "Alternative Medicine Clinic"]
        selected_columns = ["category_id", "category_name"]
        table = catalog.load_table("datasets.categories_os")
        idSnapShotPlaceCur= str(table.current_snapshot().snapshot_id).strip()
       
        df_cat_cur = table.scan(
            selected_fields=selected_columns, 
            row_filter=And(
            NotNull("category_name"),
            NotIn("category_name", excluded_values)
        )
        ).to_pandas()
        return df_cat_cur,idSnapShotPlaceCur

    except Exception as e:
        print("Erreur dans data_categorie:" + str(e))
        return None, None


def data_poi():

    # Charger le catalogue places os
    catalog = load_catalog(
        "default",
        **{
            "warehouse": "places",
            "uri": "https://catalog.h3-hub.foursquare.com/iceberg",
            "token": API,
            "header.content-type": "application/vnd.api+json",
            "rest-metrics-reporting-enabled": "false",
        },
    )

    selected_columns = [
        "fsq_place_id", "name", "latitude", "longitude",
        "address", "postcode", "tel", "website", "fsq_category_ids",
        "date_refreshed","date_closed"
    ]

    print("Chargement de la table poi")
    table = catalog.load_table('datasets.places_os')
    print("Table chargée ! Transformation en DataFrame")

    df_plc = table.scan(
            selected_fields=selected_columns,
            row_filter=(
            "(latitude IS NOT NULL) AND "
            "(longitude IS NOT NULL) AND "
            "(country = 'FR') AND "
            #"(locality = 'Paris' OR locality = 'PARIS') AND "
            "(postcode LIKE '75%') AND"
            "(region IS NOT NULL) AND "
            "(address IS NOT NULL)"
                
        )#, limit=1000
    ).to_pandas()

    lastDatePoi = pd.to_datetime(df_plc["date_refreshed"].max())#.date()
    idSnapShotPlace= table.current_snapshot().snapshot_id

    df_plc = df_plc[~df_plc['fsq_category_ids'].isna()]

    print(lastDatePoi)
    print(idSnapShotPlace)

    return df_plc, idSnapShotPlace, lastDatePoi


def compare_version_poi():

    # Récupérer la date max et idSnapshot du catalogue place en base de donnée
    with engine.connect() as conn:
        df_vers = pd.read_sql("SELECT source, idSnapShot, dateLastCheck FROM version WHERE source = 'place' ORDER BY dateLastCheck DESC LIMIT 1;", conn)
    row = df_vers.iloc[0]

    source = row["source"]
    idSnapshotPlacedb = str(row["idSnapShot"]).strip()
    lastDateRefreshedPoidb = pd.to_datetime(row["dateLastCheck"])#.date()



    # Récupérer l'id snapshot du catalogue place actuel
    # Charger le catalogue places os
    catalog = load_catalog(
        "default",
        **{
            "warehouse": "places",
            "uri": "https://catalog.h3-hub.foursquare.com/iceberg",
            "token": API,
            "header.content-type": "application/vnd.api+json",
            "rest-metrics-reporting-enabled": "false",
        },
    )

    selected_columns = [
        "fsq_place_id", "name", "latitude", "longitude",
        "address", "postcode", "tel", "website", "fsq_category_ids",
        "date_refreshed","date_closed"
    ]

    table = catalog.load_table('datasets.places_os')
    idSnapShotPlaceCur= str(table.current_snapshot().snapshot_id).strip()

    if idSnapshotPlacedb == idSnapShotPlaceCur:
        print("idSnapshotplaces identiques: pas de maj: db="+idSnapshotPlacedb+", cur:"+idSnapShotPlaceCur)
        return None, None, None
 
    print("ids différents= > check de la date max")
    df_poi, idSnapShotPlaceCur, lastDateRefreshedPoiCur = data_poi()
    print(lastDateRefreshedPoiCur)
    print(lastDateRefreshedPoidb)

    if lastDateRefreshedPoidb > lastDateRefreshedPoiCur:
        print("En vrai pas la peine")
        return None, None, None

    print("!!! une maj doit etre effectuée !!!")

    print(f"BD:{idSnapshotPlacedb}, CUR:{idSnapShotPlaceCur}")
    print(f"BD:{lastDateRefreshedPoidb}, CUR:{lastDateRefreshedPoiCur}")

    return df_poi, idSnapShotPlaceCur, lastDateRefreshedPoiCur


def compare_cat(cat_cur, cat_bd):

    cat_merge = cat_bd.merge(cat_cur, left_on="idCat", right_on="category_id", how="outer",  indicator=True,suffixes=("_bd", "_cur"))

    cat_merge["id"] = cat_merge["idCat"].fillna(cat_merge["category_id"])
    cat_merge["name_"] = np.where(cat_merge["category_name"].notna(), cat_merge["category_name"], cat_merge["name"])
    cat_merge = cat_merge.drop(columns=["category_id", "idCat", "name", "category_name"]).rename(columns={"id":"idCat", "name_":"name"})

    cat_new = cat_merge[cat_merge["_merge"] == "right_only"] # new cats
    cat_upt = cat_merge[cat_merge['_merge'] == "both"] # to update?
    cat_rmv = cat_merge[cat_merge["_merge"] == "left_only"] # isActive = False old categorie in bd mais plus en courant

    return cat_new, cat_upt, cat_rmv


def compare_poi(poi_cur, poi_bd):
   # on merge les colonnes de bd et cur

    poi_merge = poi_bd.merge(
        poi_cur,
        left_on="idFsq",
        right_on="fsq_place_id",
        how="outer",
        indicator=True,
        suffixes=("_bd", "_cur")
    )
    poi_merge = poi_merge.explode("fsq_category_ids").rename(columns={"fsq_category_ids":"idCat"})
    
    # recupére que les colonnes actuelles puis on renomme
    #df_merge = df_merge.drop(columns=["name_x", "address_x", "latitudePoi", "longitudePoi", "tel_x", "postcode_x", "fsq_place_id"])
    #df_merge = df_merge.rename({"name_y":"name"})


    #poi_sans_cat=poi_merge[~poi_merge['idCat'].isin(cat_merge['idCat'])]
    #poi_merge = poi_merge[poi_merge['idCat'].isin(cat_merge['idCat'])]
    

    poi_new = poi_merge[poi_merge["_merge"] == "right_only"] # nouveau poi
    poi_upt = poi_merge[poi_merge["_merge"] == "both"] # ceux mis à jour
    poi_rmv = poi_merge[poi_merge["_merge"] == "left_only"] # disparu?

    return poi_new, poi_upt, poi_rmv



    def upsert_categories(cat_new, cat_upt, cat_rmv):
        with Session() as session:
        
            # INSERT des nouvelles catégories
            if not cat_new.empty:
                records = [
                    {"idCat": row["idCat"], "name": row["name"], "isActive": True}
                    for _, row in cat_new.iterrows()
                ]
                stmt = mysql_insert(Categorie).values(records)
                stmt = stmt.on_duplicate_key_update(
                    name=stmt.inserted.name,
                    isActive=True
                )
                session.execute(stmt)

            # UPDATE des catégories existantes (nom potentiellement changé)
            if not cat_upt.empty:
                records = [
                    {"idCat": row["idCat"], "name": row["name"], "isActive": True}
                    for _, row in cat_upt.iterrows()
                ]
                stmt = mysql_insert(Categorie).values(records)
                stmt = stmt.on_duplicate_key_update(
                    name=stmt.inserted.name,
                    isActive=True
                )
                session.execute(stmt)

            # Soft delete des catégories disparues
            if not cat_rmv.empty:
                ids = cat_rmv["idCat"].tolist()
                session.query(Categorie)\
                       .filter(Categorie.idCat.in_(ids))\
                       .update({"isActive": False}, synchronize_session=False)

            session.commit()
            print(f"Catégories — new: {len(cat_new)}, upt: {len(cat_upt)}, rmv: {len(cat_rmv)}")



    def upsert_pois(poi_new, poi_upt, poi_rmv):
        with Session() as session:

            # Préconstruire un dict postcode → idCity pour éviter N requêtes
            existing_cities = {v.cp: v.idCity for v in session.query(Ville).all()}

            def resolve_city(postcode):
                if postcode not in existing_cities:
                    city = Ville(cp=postcode, name=postcode, region="", departement="")
                    session.add(city)
                    session.flush()
                    existing_cities[postcode] = city.idCity
                return existing_cities[postcode]

            # INSERT nouveaux POI (déduplication sur fsq_place_id)
            if not poi_new.empty:
                # poi_new est déjà explodé sur idCat : on déduplique d'abord
                poi_unique = poi_new.drop_duplicates(subset="fsq_place_id")
                records = []
                for _, row in poi_unique.iterrows():
                    records.append({
                        "idFsq":        row["fsq_place_id"],
                        "name":         row["name"],
                        "idCity":       resolve_city(str(row["postcode"])),
                        "address":      row.get("address"),
                        "latitudePoi":  row.get("latitude"),
                        "longitudePoi": row.get("longitude"),
                        "tel":          row.get("tel"),
                        "website":      row.get("website"),
                        "postcode":     str(row.get("postcode", "")),
                        "isActive":     True,
                    })
                stmt = mysql_insert(Poi).values(records)
                stmt = stmt.on_duplicate_key_update(
                    name=stmt.inserted.name,
                    address=stmt.inserted.address,
                    latitudePoi=stmt.inserted.latitudePoi,
                    longitudePoi=stmt.inserted.longitudePoi,
                    tel=stmt.inserted.tel,
                    website=stmt.inserted.website,
                    isActive=True,
                )
                session.execute(stmt)
                session.flush()

            # UPDATE POI existants
            if not poi_upt.empty:
                poi_unique = poi_upt.drop_duplicates(subset="fsq_place_id")
                records = []
                for _, row in poi_unique.iterrows():
                    records.append({
                        "idFsq":        row["fsq_place_id"],
                        "name":         row.get("name_cur", row.get("name")),
                        "idCity":       resolve_city(str(row["postcode_cur"])),
                        "address":      row.get("address_cur"),
                        "latitudePoi":  row.get("latitude"),
                        "longitudePoi": row.get("longitude"),
                        "tel":          row.get("tel_cur"),
                        "website":      row.get("website_cur"),
                        "postcode":     str(row.get("postcode_cur", "")),
                        "isActive":     True,
                    })
                stmt = mysql_insert(Poi).values(records)
                stmt = stmt.on_duplicate_key_update(
                    name=stmt.inserted.name,
                    address=stmt.inserted.address,
                    latitudePoi=stmt.inserted.latitudePoi,
                    longitudePoi=stmt.inserted.longitudePoi,
                    tel=stmt.inserted.tel,
                    website=stmt.inserted.website,
                    isActive=True,
                )
                session.execute(stmt)

            # Soft delete POI disparus
            if not poi_rmv.empty:
                ids = poi_rmv["idFsq"].dropna().tolist()
                session.query(Poi)\
                       .filter(Poi.idFsq.in_(ids))\
                       .update({"isActive": False}, synchronize_session=False)

            session.commit()
            print(f"POI — new: {len(poi_new.drop_duplicates('fsq_place_id'))}, "
                  f"upt: {len(poi_upt.drop_duplicates('fsq_place_id'))}, "
                  f"rmv: {len(poi_rmv)}")


 

    def upsert_poi_categories(poi_new, poi_upt):
        """
        Reconstruit les liaisons POI ↔ Catégorie.
        poi_new et poi_upt sont déjà explodés sur idCat (une ligne par catégorie).
        """
        with Session() as session:


            fsq_to_idpoi = {
                p.idFsq: p.idPoi
                for p in session.query(Poi.idFsq, Poi.idPoi).all()
            }

            valid_cats = {c.idCat for c in session.query(Categorie.idCat).all()}

            rows_to_insert = []
            for df in [poi_new, poi_upt]:
                if df.empty:
                    continue
                for _, row in df.iterrows():
                    fsq_id = row.get("fsq_place_id")
                    cat_id = row.get("idCat")
                    if fsq_id not in fsq_to_idpoi or cat_id not in valid_cats:
                        continue
                    rows_to_insert.append({
                        "idPoi": fsq_to_idpoi[fsq_id],
                        "idCat": cat_id,
                    })

            if rows_to_insert:

                seen = set()
                unique_rows = []
                for r in rows_to_insert:
                    key = (r["idPoi"], r["idCat"])
                    if key not in seen:
                        seen.add(key)
                        unique_rows.append(r)

                stmt = mysql_insert(Poi_Categorie).values(unique_rows)

                stmt = stmt.on_duplicate_key_update(idPoiCat=stmt.inserted.idPoiCat)
                session.execute(stmt)
                session.commit()
                print(f"Poi_Categorie — {len(unique_rows)} liaisons insérées/ignorées")




    def update_version(source, id_snapshot, last_date):
        with Session() as session:
            stmt = mysql_insert(Version).values(
                source=source,
                idSnapshot=str(id_snapshot),
                dateLastCheck=last_date,
            )

            session.execute(stmt)
            session.commit()




def upsert_categories(cat_new, cat_upt, cat_rmv):

    cat_to_upsert = pd.concat(
        [cat_new, cat_upt],
        ignore_index=True
    )

    with Session() as session:

        if not cat_to_upsert.empty:

            records = (
                cat_to_upsert[["idCat", "name"]]
                .drop_duplicates()
                .assign(isActive=True)
                .to_dict("records")
            )

            batch_size = 5000
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                try:
                    #session.bulk_insert_mappings(Historique_Voyage, batch)
                    #session.commit()
                    stmt = mysql_insert(Categorie).values(batch)

                    stmt = stmt.on_duplicate_key_update(
                        name=stmt.inserted.name,
                        isActive=True
                    )

                    session.execute(stmt)
                    print(f"Insertion réussie categories : {len(batch)} lignes (batch {i//batch_size + 1}).")
                except Exception as e:
                    session.rollback()
                    print(f"Erreur lors de l'insertion du batch {i//batch_size + 1} : {e}")



        # soft delete
        if not cat_rmv.empty:

            ids = cat_rmv["idCat"].dropna().tolist()

            session.query(Categorie)\
                .filter(Categorie.idCat.in_(ids))\
                .update(
                    {"isActive": False},
                    synchronize_session=False
                )

        session.commit()

    print(
        f"Catégories -> "
        f"new:{len(cat_new)} "
        f"upt:{len(cat_upt)} "
        f"rmv:{len(cat_rmv)}"
    )

def upsert_pois(poi_new, poi_upt, poi_rmv):

    poi_to_upsert = pd.concat(
        [poi_new, poi_upt],
        ignore_index=True
    )

    with Session() as session:

        if not poi_to_upsert.empty:

            poi_unique = poi_to_upsert.drop_duplicates(
                subset="fsq_place_id"
            )
            poi_unique = poi_unique.where(pd.notnull(poi_unique), None)
            records = []

            for _, row in poi_unique.iterrows():

                records.append({
                    "idFsq": row["fsq_place_id"],
                    "name": row.get("name_cur", row.get("name")),
                    "idCity": 1,
                    "address": row.get("address_cur", row.get("address")),
                    "latitudePoi": row.get("latitude"),
                    "longitudePoi": row.get("longitude"),
                    "tel": row.get("tel_cur", row.get("tel")),
                    "website": row.get("website_cur", row.get("website")),
                    "postcode": str(
                        row.get(
                            "postcode_cur",
                            row.get("postcode", "")
                        )
                    ),
                    "isActive": True,
                })

            records = [
                {
                    k: (None if pd.isna(v) else v)
                    for k, v in rec.items()
                }
                for rec in records
            ]

            batch_size = 5000
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                try:
                    #session.bulk_insert_mappings(Poi_Categorie, batch)
                    #session.commit()
                    stmt = mysql_insert(Poi).values(batch)

                    stmt = stmt.on_duplicate_key_update(
                        name=stmt.inserted.name,
                        address=stmt.inserted.address,
                        latitudePoi=stmt.inserted.latitudePoi,
                        longitudePoi=stmt.inserted.longitudePoi,
                        tel=stmt.inserted.tel,
                        website=stmt.inserted.website,
                        postcode=stmt.inserted.postcode,
                        isActive=True,
                    )

                    session.execute(stmt)
                    print(f"Insertion réussi poi : {len(batch)} lignes (batch {i//batch_size + 1}).")
                except Exception as e:
                    session.rollback()
                    print(f"Erreur lors de l'insertion du batch {i//batch_size + 1} : {e}")




        # soft delete
        if not poi_rmv.empty:

            ids = (
                poi_rmv["idFsq"]
                .dropna()
                .tolist()
            )

            session.query(Poi)\
                .filter(Poi.idFsq.in_(ids))\
                .update(
                    {"isActive": False},
                    synchronize_session=False
                )

        session.commit()

    print(
        f"POI -> "
        f"new:{len(poi_new)} "
        f"upt:{len(poi_upt)} "
        f"rmv:{len(poi_rmv)}"
    )

def upsert_poi_categories(poi_new, poi_upt):

    poi_to_process = pd.concat(
        [poi_new, poi_upt],
        ignore_index=True
    )
    poi_to_process = poi_to_process.drop_duplicates(subset=["fsq_place_id", "idCat"])

    if poi_to_process.empty:
        return

    with Session() as session:

        fsq_to_idpoi = {
            p.idFsq: p.idPoi
            for p in session.query(
                Poi.idFsq,
                Poi.idPoi
            ).all()
        }


        fsq_ids = (
            poi_to_process["fsq_place_id"]
            .dropna()
            .unique()
            .tolist()
        )

        poi_ids = [
            fsq_to_idpoi[x]
            for x in fsq_ids
            if x in fsq_to_idpoi
        ]

        if poi_ids:

            session.query(Poi_Categorie)\
                .filter(
                    Poi_Categorie.idPoi.in_(poi_ids)
                )\
                .delete(
                    synchronize_session=False
                )

        # recréer relations
        rows = []

        # check categorie manquantes
        valid_cats = {
            c[0]
            for c in session.query(Categorie.idCat).all()
        }

        for _, row in poi_to_process.iterrows():

            fsq_id = row["fsq_place_id"]
            cat_id = row["idCat"]

            if fsq_id not in fsq_to_idpoi:
                continue
            if cat_id not in valid_cats:
                continue

            rows.append({
                "idPoi": fsq_to_idpoi[fsq_id],
                "idCat": row["idCat"]
            })
        rows= list({(r["idPoi"], r["idCat"]): r for r in rows}.values())



        invalid = poi_to_process[
            ~poi_to_process["idCat"].isin(valid_cats)
        ]

        print("Catégories manquantes :", invalid["idCat"].unique())
        print("Nombre :", len(invalid))
        #insertions des relations
        if rows:
            batch_size = 5000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                try:
                    session.bulk_insert_mappings(Poi_Categorie, batch)
                    session.commit()
                    print(f"Insertion réussie relation poi_cat : {len(batch)} lignes (batch {i//batch_size + 1}).")
                except Exception as e:
                    session.rollback()
                    print(f"Erreur lors de l'insertion du batch {i//batch_size + 1} : {e}")


        session.commit()

    print(
        f"Poi_Categorie -> "
        f"{len(rows)} relations"
    )


def set_isActive_categories():
    with Session() as session:
        # Catégories actives sans aucun POI lié
        cat_without_poi = (
            session.query(Categorie.idCat)
            .outerjoin(Poi_Categorie, Poi_Categorie.idCat == Categorie.idCat)
            .filter(Poi_Categorie.idCat.is_(None))
            .filter(Categorie.isActive == True)
            .all()
        )

        ids = [c.idCat for c in cat_without_poi]

        if not ids:
            print("Aucune catégorie à désactiver.")
            return

        batch_size = 5000
        total = 0
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            try:
                session.query(Categorie)\
                    .filter(Categorie.idCat.in_(batch))\
                    .update({"isActive": False}, synchronize_session=False)
                session.commit()
                total += len(batch)
                print(f"Désactivation Categorie réussie : {len(batch)} catégories (batch {i//batch_size + 1}).")
            except Exception as e:
                session.rollback()
                print(f"Erreur lors du batch {i//batch_size + 1} : {e}")

        print(f"Catégories désactivées (sans POI) : {total}")   


def update_version(source, id_snapshot, last_date):
    with Session() as session:
        stmt = mysql_insert(Version).values(
            source=source,
            idSnapshot=str(id_snapshot),
            dateLastCheck=last_date,
        )

        session.execute(stmt)
        session.commit()



if __name__ == "__main__":


    poi_cur, id_snapshot_place, last_date_poi = compare_version_poi()
    cat_cur, id_snapshot_cat = data_cat()

    if poi_cur is None:
        print("Pas de mise à jour nécessaire.")
    else:
        poi_bd  = get_poi_bd()
        cat_bd  = get_cat_bd()

        cat_new, cat_upt, cat_rmv = compare_cat(cat_cur, cat_bd)
        poi_new, poi_upt, poi_rmv = compare_poi(poi_cur, poi_bd)


        upsert_categories(cat_new, cat_upt, cat_rmv)
        upsert_pois(poi_new, poi_upt, poi_rmv)
        upsert_poi_categories(poi_new, poi_upt)
        set_isActive_categories()
        
        update_version("place", id_snapshot_place, last_date_poi)
        update_version("categorie", id_snapshot_cat, datetime.now())
  
  
    