from sqlalchemy.orm import declarative_base
from sqlalchemy import UniqueConstraint, Column, Integer, String,  Date, CheckConstraint,ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import DOUBLE
Base = declarative_base()


class User(Base):
    __tablename__ = "user"
    idUser = Column(Integer, primary_key=True)
    name = Column(String(20), nullable=False)


class Ville(Base):
    __tablename__="ville"
    idCity=Column(Integer, primary_key=True, autoincrement=True)
    cp=Column(String(250), nullable=False)
    name=Column(String(250), nullable=False)
    region=Column(String(250), nullable=False)
    departement=Column(String(250), nullable=False)


class Poi(Base):
    __tablename__ = "poi"
    idPoi = Column(Integer, autoincrement=True, primary_key=True)
    idFsq = Column(String(250),unique=True)
    name = Column(String(250), nullable=False)
    idCity = Column(Integer, ForeignKey(Ville.idCity), nullable=False)
    address = Column(String(250))
    latitudePoi = Column(DOUBLE,nullable=False)
    longitudePoi = Column(DOUBLE,nullable=False)
    tel = Column(String(250), nullable=True)
    website = Column(String(250), nullable=True)
    postcode = Column(String(250), nullable=True)
    isActive=Column(Boolean, default=True)
    rel_city_poi = relationship("Ville")


class Avis(Base):
    __tablename__ = "avis"
    idTip = Column(String(250), primary_key=True)
    content = Column(String(250), nullable=False)
    dateCreated = Column(Date, nullable=False)
    idPoi = Column(Integer,  ForeignKey(Poi.idPoi), nullable=False)
    idUser = Column(Integer, ForeignKey(User.idUser), nullable=False)
    note = Column(
        Integer, CheckConstraint("note BETWEEN 1 AND 5")
    )
    isActive=Column(Boolean, default=True)
    rel_poi_avis = relationship("Poi") 
    rel_user_avis = relationship("User")


class Categorie(Base):
    __tablename__="categorie"
    idCat = Column(String(250), primary_key=True)
    name= Column(String(250), nullable=False)
    #idFsq = Column(Integer, nullable=True)
    isActive=Column(Boolean, default=True)


class Poi_Categorie(Base):
    __tablename__="poi_categorie"
    idPoiCat=Column(Integer, primary_key=True, autoincrement=True)
    idCat=Column(String(250),ForeignKey(Categorie.idCat), nullable=False)
    idPoi=Column(Integer, ForeignKey(Poi.idPoi), nullable=False)
    rel_cat_poicat = relationship("Categorie")
    rel_poi_poicat=relationship("Poi")

    __table_args__ = (
        UniqueConstraint(
            "idPoi",
            "idCat",
            name="uk_poi_cat"
        ),
    )
    

class Historique_Voyage(Base):
    __tablename__="historique_voyage"
    idHistorique = Column(Integer, primary_key=True, autoincrement=True)
    idUser=Column(Integer, ForeignKey(User.idUser), nullable=False)
    idPoi=Column(Integer, ForeignKey(Poi.idPoi), nullable=False)
    dateVisite=Column(Date, nullable=False)
    rel_user_hist=relationship("User")
    rel_poi_hist=relationship("Poi")


class Version(Base):
    __tablename__="version"
    idVersion = Column(Integer, primary_key=True, autoincrement=True)
    source=Column(String(20))
    idSnapshot= Column(String(250))
    dateLastCheck = Column(Date)