import os
from dotenv import load_dotenv
from pathlib import Path
import sqlalchemy
from sqlalchemy import create_engine, text
from ORM import Base, Categorie, Ville, Poi,Poi_Categorie, User,Avis, Historique_Voyage, Version
from pyiceberg.catalog import load_catalog
from sqlalchemy.orm import sessionmaker
from pyiceberg.expressions import And, NotIn, IsNull, NotNull
import numpy as np
import pandas as pd
from faker import Faker
import random
from tqdm import tqdm
from datetime import datetime, timedelta

# === Config MySQL ===
load_dotenv(Path(".dev.env"))

API = os.getenv("API")
host = os.getenv("MYSQL_HOST")
user = os.getenv("MYSQL_USER")
pwd = os.getenv("MYSQL_PASSWORD")
db = os.getenv("MYSQL_DB")
port = 3306


"""idSnapShotPlace = None
idSnapShotCategorie = None
lastDatePoi= None"""

def get_engine():
    engine = create_engine(f"mysql+mysqlconnector://{user}:{pwd}@{host}:{port}/{db}")
    return engine

def connect_mysql_test(engine):
    try:

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1

    except Exception as e:
        print(f"Erreur de connexion a la base de données mysql: {str(e)}")
        return False


def base_create(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def data_categorie():
    df_cat = None
    idSnapShotCategorie = None
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
        df_cat = table.scan(
            selected_fields=selected_columns, 
            row_filter=And(
            NotNull("category_name"),
            NotIn("category_name", excluded_values)
        )
        ).to_pandas()

        idSnapShotCategorie = table.current_snapshot().snapshot_id
        print(idSnapShotCategorie)
        #df_cat = df_cat.drop_duplicates(subset=["category_name"])
        print("nombre de categorie brute:"+str(df_cat["category_name"].size))



    except Exception as e:
        print("Erreur dans data_categorie:" + str(e))
    finally:
        return df_cat, idSnapShotCategorie


def send_city(engine):

    print("ville")
    ville = Ville(cp=75000, name="Paris", region="Île-de-France", departement="Paris")

    # Preparer la session pour l'envoi 
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        session.add(ville)
        session.commit()
        print(f"Insertion City réussie : 1 lignes insérée.")
    except Exception as e:
        session.rollback()
        print(f"Erreur lors de l'insertion City : {e}")
    finally:
        session.close()



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
        "date_refreshed"
    ]


    print("Chargement de la table poi")
    table = catalog.load_table('datasets.places_os')
    old = table.metadata.snapshots[-5].snapshot_id #TODO: a supprimer 4855572603108190307
    print("snapshot:"+str(old))
    print("Table chargée ! Transformation en DataFrame")

    df_plc = table.scan(
            snapshot_id=old, #TODO:Test pour les maj à supprimer, force la récupération d'un ancien snapshot du catalogue
            selected_fields=selected_columns,
            row_filter=(
            "(latitude IS NOT NULL) AND "
            "(longitude IS NOT NULL) AND "
            "(country = 'FR') AND "
            "(postcode LIKE '75%') AND"
            #"(locality = 'Paris' OR locality = 'PARIS') AND "
            "(region IS NOT NULL) AND "
            "(address IS NOT NULL) AND "
            "(date_closed IS NULL)"
            
        )#, limit=1000
    ).to_pandas()

    lastDatePoi = df_plc["date_refreshed"].max()
    idSnapShotPlace= old #TODO:table.current_snapshot().snapshot_id

    print(lastDatePoi)
    print(idSnapShotPlace)

    return df_plc, lastDatePoi, idSnapShotPlace


def data_filter_categorie(df_cat, df_plc):

    all_categories = set()

    for categories in df_plc['fsq_category_ids']:
        if isinstance(categories, (list, np.ndarray)):
            all_categories.update(str(x) for x in categories)
        elif categories is not None:
            all_categories.add(str(categories))

    df_cat["category_id"] = df_cat["category_id"].astype(str)
    print("Nb catégories utilisées :", len(all_categories))
    df_cat_filt = df_cat[
        df_cat["category_id"].isin(all_categories)
    ]

    print(
        "nombre de cat apres filtre:",
        len(df_cat_filt)
    )

    return df_cat_filt


def send_cat(df_cat, engine):
    df_cat.rename(
        columns={"category_id": "idCat", "category_name": "name"}, inplace=True
    )
    data_to_insert = df_cat.to_dict(orient="records")

    # Preparer la session pour l'envoi en bulk
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        session.bulk_insert_mappings(Categorie, data_to_insert)
        session.commit()
        print(
            f"Insertion Categorie réussie : {len(data_to_insert)} lignes insérées."
        )
    except Exception as e:
        session.rollback()
        print(f"Erreur lors de l'insertion Categorie : {e}")
    finally:
        session.close()


def send_poi(df_plc, engine):
    df_plc.rename(
        columns={"fsq_place_id": "idFsq", "latitude": "latitudePoi", "longitude":"longitudePoi"}, inplace=True
    )
    df_plc = df_plc.fillna(value=np.nan).replace({np.nan: None}) #
    df_plc["idCity"] = 1 # on a que paris pour le moment 
    data_to_insert = df_plc.drop(columns=["fsq_category_ids"]).to_dict(orient="records")

    # Preparer la session pour l'envoi en bulk par bulck de 5000 (environ  poi)
    Session = sessionmaker(bind=engine)
    session = Session()

    batch_size = 5000
    for i in range(0, len(data_to_insert), batch_size):
        batch = data_to_insert[i:i + batch_size]
        try:
            session.bulk_insert_mappings(Poi, batch)
            session.commit()
            print(f"Insertion réussie poi: {len(batch)} lignes (batch {i//batch_size + 1}).")
        except Exception as e:
            session.rollback()
            print(f"Erreur lors de l'insertion du batch {i//batch_size + 1} : {e}")

        
    session.close() 


def send_rel_poi_cat(df_cat, df_plc, engine):
    print("relation poi_cat")

    # Récupérer le mapping idFsq:idPoi
    with engine.connect() as conn:
        mapping = pd.read_sql("SELECT idPoi, idFsq FROM poi", conn)
        
    fsq_to_idpoi = dict(zip(mapping["idFsq"], mapping["idPoi"]))

    df_rel = (
        df_plc[["idFsq", "fsq_category_ids"]]
        .explode("fsq_category_ids")
        .rename(columns={"fsq_category_ids": "idCat"})
        .dropna(subset=["idCat"])
        .reset_index(drop=True)
    )

    # Remplacer idFsq par idPoi 
    df_rel["idPoi"] = df_rel["idFsq"].map(fsq_to_idpoi)
    df_rel = df_rel.drop(columns=["idFsq"]).dropna(subset=["idPoi"])
    df_rel["idPoi"] = df_rel["idPoi"].astype(int)

    # ne garder que les catégories existantes
    valid_categories = set(df_cat["idCat"])

    df_rel = df_rel[df_rel["idCat"].isin(valid_categories)]

    print(f"Relations à insérer : {len(df_rel)}")

    data_to_insert = df_rel.to_dict(orient="records")
    Session = sessionmaker(bind=engine)
    session = Session()

    batch_size = 5000
    for i in range(0, len(data_to_insert), batch_size):
        batch = data_to_insert[i:i + batch_size]
        try:
            with engine.connect() as conn:
                cats_db = pd.read_sql("SELECT idCat FROM categorie", conn)

            cats_db = set(cats_db["idCat"])

            missing = set(df_rel["idCat"]) - cats_db

            print("Nombre de catégories manquantes :", len(missing))
            print("Exemples :", list(missing)[:20])
            session.bulk_insert_mappings(Poi_Categorie, batch)
            session.commit()
            print(f"Insertion réussie rel_poi_cat: {len(batch)} lignes (batch {i//batch_size + 1}).")
        except Exception as e:
            session.rollback()
            print(f"Erreur lors de l'insertion du batch {i//batch_size + 1} : {e}")

    session.close()


def send_user(engine):

    faker = Faker("fr_FR")
    nb_users = 1000      # nombre d’utilisateurs fictifs

    lstUser= list()
    for _ in range(nb_users):
        user = User(name=faker.first_name())
        lstUser.append(user)

    # Preparer la session pour l'envoi en bulk
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        session.add_all(lstUser)
        session.commit()
        print(
            f"Insertion Users réussie : {len(lstUser)} lignes insérées."
        )
    except Exception as e:
        session.rollback()
        print(f"Erreur lors de l'insertion User : {e}")
    finally:
        session.close()


def send_avis(engine):

    faker = Faker("fr_FR")
    nb_users = 1000   # nombre d’utilisateurs fictifs
    avis_par_poi = 5  # nombre d’avis par POI


    # Récupérer tous les POI et User en base
    Session = sessionmaker(bind=engine)
    session = Session()
    lstPois = session.query(Poi).all()
    lstUsers = session.query(User).all()
    #print(lstPois)

    # Dictionnaire de templates pour les avis
    templates = {
        1: [
            "Nul, j'ai vraiment passé un moment horrible.",
            "Beaucoup trop cher pour ce que c'est. Je ne comprends pas la note.",
            "Comment c'est possible de faire les choses aussi mal!",
            "À fuir. Je n'y remettrais plus jamais les pieds",
            "Mauvais, nul!!!"
        ],
        2: [
            "Inintéressant au possible.",
            "Ne vaut vraiment pas le coup",
            "On peut faire vraiment mieux",
            "Passer votre chemin",
            "Ça ne vaut pas le prix et le temps perdu"
        ],
        3: [
            "C'était pas trop mal",
            "On peut faire mieux, mais ça va",
            "Ça avait bien commencé, mais au final je ne reviendrais plus",
            "Un peu cher, mais on passe un bon moment",
            "Moyen"
        ],
        4: [
            "J'ai passé un bon moment, je reviendrais",
            "Propre, courtois et pas trop cher",
            "Je recommande!!",
            "RAS le service est correct",
            "Bon rapport qualité/prix"
        ],
        5: [
            "C'était super!",
            "Une pépite!!!! Et pas cher pour le service!",
            "J'ai passé un incroyable moment.",
            "Je recommande vivement! Le service est parfait!",
            "J'ai adoré le personnel, vraiment sympathique!"
        ]
    }

    # Génération
    lstAvis = []
    for poi in lstPois:
        for _ in range(avis_par_poi):
            idTip = faker.uuid4()
            dateCreated = faker.date_time_this_year()
            note = random.randint(1, 5)
            avisNb = random.randint(1, 5) 
            content = templates[note][avisNb - 1]   
            idUser = random.choice(lstUsers).idUser

            lstAvis.append({
                "idTip": idTip,
                "content": content,
                "dateCreated": dateCreated,
                "idPoi": poi.idPoi,
                "note": note,
                "idUser": idUser
            })
    

    batch_size = 5000
    for i in range(0, len(lstAvis), batch_size):
        batch = lstAvis[i:i + batch_size]
        try:
            session.bulk_insert_mappings(Avis, batch)
            session.commit()
            print(f"Insertion réussie avis : {len(batch)} lignes (batch {i//batch_size + 1}).")
        except Exception as e:
            session.rollback()
            print(f"Erreur lors de l'insertion du batch {i//batch_size + 1} : {e}")

    session.close()



def send_historique(engine):

    Session = sessionmaker(bind=engine)
    session = Session()

    lstPois = session.query(Poi.idPoi).all()
    lstUsers = session.query(User.idUser).distinct()

    historique = []
    nb_visites_par_user= 50

    for user in tqdm(lstUsers, desc="Génération historique"):
        # Pour chaque utilisateur, choisir des POI au hasard sans doublon
        visited_pois = random.sample(lstPois, min(nb_visites_par_user, len(lstPois)))
        for poi in visited_pois:
            # Date aléatoire dans les 365 derniers jours
            random_days = random.randint(0, 365)
            date_visite = datetime.now() - timedelta(days=random_days)
            historique.append({"idUser":user.idUser,"idPoi": poi.idPoi, "dateVisite":date_visite})

    print(len(historique))

    batch_size = 5000
    for i in range(0, len(historique), batch_size):
        batch = historique[i:i + batch_size]
        try:
            session.bulk_insert_mappings(Historique_Voyage, batch)
            session.commit()
            print(f"Insertion réussie historique : {len(batch)} lignes (batch {i//batch_size + 1}).")
        except Exception as e:
            session.rollback()
            print(f"Erreur lors de l'insertion du batch {i//batch_size + 1} : {e}")

    session.close()



def send_version(idSnapShotCategorie, idSnapShotPlace, lastDatePoi,engine):

    print(idSnapShotPlace)
    lstVersion = []
    lstVersion.append(Version(source="categorie", idSnapshot=idSnapShotCategorie, dateLastCheck=datetime.now()))
    lstVersion.append(Version(source="place", idSnapshot=idSnapShotPlace, dateLastCheck= lastDatePoi))

    # Preparer la session pour l'envoi en bulk
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        session.add_all(lstVersion)
        session.commit()
        print(
            f"Insertion Version réussie : {len(lstVersion)} lignes insérées."
        )
    except Exception as e:
        session.rollback()
        print(f"Erreur lors de l'insertion Version : {e}")
    finally:
        session.close()



if __name__ == "__main__":

    print("host:" + str(host))
    print("user:" + str(user))

    engine = get_engine()
    connect_mysql_test(engine)
    base_create(engine)

    # Recuperer les données et les nettoyer
    df_cat, idSnapShotCategorie = data_categorie()
    df_plc, lastDatePoi, idSnapShotPlace = data_poi()
    df_cat = data_filter_categorie(df_cat, df_plc)

    
    # Envoyer les données
    send_city(engine)
    send_cat(df_cat,engine)
    send_poi(df_plc,engine)
    send_rel_poi_cat(df_cat, df_plc,engine)

    send_user(engine)
    send_avis(engine)
    send_historique(engine)

    # Versionning data
    send_version(idSnapShotCategorie, idSnapShotPlace, lastDatePoi,engine)

