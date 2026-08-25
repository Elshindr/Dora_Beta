import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import pandas as pd
from ORM import Base, Ville, Categorie, Poi, User, Poi, Historique_Voyage, Avis, Version
from base_creation import (
    base_create,
    connect_mysql_test,
    send_city,
    data_filter_categorie,
    send_cat,
    send_poi,
    send_historique,
    send_avis,
send_version
)
import numpy as np
from datetime import datetime, date
@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    Base.metadata.create_all(engine)

    yield engine

    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def session(test_engine):
    Session = sessionmaker(bind=test_engine)
    session = Session()

    yield session

    session.close()



def test_database_connection(test_engine, session):
    assert connect_mysql_test(test_engine) is True
    assert connect_mysql_test(None) is False


def test_base_create():
    engine = create_engine("sqlite:///:memory:")

    # Création des tables
    base_create(engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Vérifie que les tables SQLAlchemy existent
    expected_tables = set(Base.metadata.tables.keys())

    assert set(tables) == expected_tables

    engine.dispose()


def test_send_city(test_engine, session):
    send_city(test_engine)

    ville = session.query(Ville).first()

    assert ville is not None
    assert ville.name == "Paris"
    assert ville.cp == "75000"



def test_data_filter_categorie():
    df_cat = pd.DataFrame(
        {
            "category_id": ["1", "2", "3", "4"],
            "category_name": ["Monuments", "Restaurants", "Musées", "Cinéma"],
        }
    )

    df_plc = pd.DataFrame({"fsq_category_ids": [["1", "3"], ["3"], ["999"]]})

    result = data_filter_categorie(df_cat, df_plc)
    print(result["category_id"].dtype)
    assert result["category_id"].dtype == "string"
    assert len(result) == 2
    assert set(result["category_id"]) == {"1", "3"}


def test_send_cat(test_engine, session):
    df_cat = pd.DataFrame(
        {"category_id": ["1", "2"], "category_name": ["Monuments", "Musées"]}
    )

    send_cat(
        df_cat,
        test_engine,
    )

    categories = session.query(Categorie).all()

    assert len(categories) == 2
    assert categories[0].name in ["Monuments", "Musées"]
    assert categories[1].name in ["Monuments", "Musées"]


    with pytest.raises(Exception):
        insert_db(lstValues=lstHouse, session=session)


def test_send_poi(test_engine, session):
    df_poi = pd.DataFrame(
        {
            "fsq_place_id": ["fsq-1", "fsq-2"],
            "name": ["Tour Eiffel", "Louvre"],
            "latitude": [48.8584, 48.8606],
            "longitude": [2.2945, 2.3376],
            "address": ["Paris", "Paris"],
            "fsq_category_ids": [["1"], ["2"]],
        }
    )

    send_poi(df_poi, test_engine)



    pois = session.query(Poi).all()

    assert len(pois) == 2
    assert pois[0].idFsq in ["fsq-1", "fsq-2"]

   

def test_send_historique(test_engine, session):


    # 3 utilisateurs
    users = [
        User(name="Alice"),
        User(name="Bob"),
        User(name="Charlie"),
    ]

    # 4 POI
    pois = [
        Poi(
            idFsq="poi-1",
            name="Tour Eiffel",
            latitudePoi=48.8584,
            longitudePoi=2.2945,
            idCity=1,
        ),
        Poi(
            idFsq="poi-2",
            name="Louvre",
            latitudePoi=48.8606,
            longitudePoi=2.3376,
            idCity=1,
        ),
        Poi(
            idFsq="poi-3",
            name="Arc de Triomphe",
            latitudePoi=48.8738,
            longitudePoi=2.2950,
            idCity=1,
        ),
        Poi(
            idFsq="poi-4",
            name="Musée d'Orsay",
            latitudePoi=48.8600,
            longitudePoi=2.3266,
            idCity=1,
        ),
    ]

    session.add_all(users)
    session.add_all(pois)
    session.commit()



    # Exécute la fonction à tester
    send_historique(test_engine)

    # Vérification
    historiques = session.query(Historique_Voyage).all()

    assert len(historiques) == 12

 

def test_send_avis(test_engine, session):


    # Création de 2 utilisateurs
    users = [
        User(name="Alice"),
        User(name="Bob"),
    ]

    # Création de 3 POI
    pois = [
        Poi(
            idFsq="poi-1",
            name="Tour Eiffel",
            latitudePoi=48.8584,
            longitudePoi=2.2945,
            idCity=1,
        ),
        Poi(
            idFsq="poi-2",
            name="Louvre",
            latitudePoi=48.8606,
            longitudePoi=2.3376,
            idCity=1,
        ),
        Poi(
            idFsq="poi-3",
            name="Arc de Triomphe",
            latitudePoi=48.8738,
            longitudePoi=2.2950,
            idCity=1,
        ),
    ]

    session.add_all(users)
    session.add_all(pois)
    session.commit()

  

    # Exécution
    send_avis(test_engine)

    # Vérification
    avis = session.query(Avis).all()
    # 3 POI × 5 avis par POI
    assert len(avis) == 15

    assert all(avis_item.idPoi is not None for avis_item in avis)
    assert all(avis_item.idUser is not None for avis_item in avis)

    assert all(1 <= avis_item.note <= 5 for avis_item in avis)

    poi_ids = {avis_item.idPoi for avis_item in avis}
    user_ids = {avis_item.idUser for avis_item in avis}

    assert len(poi_ids) == 3
    assert len(user_ids) == 2


def test_send_version(test_engine, session):

    send_version(
        idSnapShotCategorie=123,
        idSnapShotPlace=456,
        lastDatePoi=datetime(2026, 8, 20, 0, 0),
        engine=test_engine,
    )


    versions = session.query(Version).all()

    assert len(versions) == 2

    assert versions[0].source == "categorie"
    assert versions[0].idSnapshot == "123"

    assert versions[1].source == "place"
    assert versions[1].idSnapshot == "456"
    assert versions[1].dateLastCheck ==  date(2026, 8, 20)

