import pymysql
from faker import Faker
import random

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
# Connexion MySQL
conx = pymysql.connect(
    host=host,
    user=user,
    password=pwd,
    database=db,
    port=port
)
cursor = conx.cursor()


# Générateur de texte
faker = Faker("fr_FR")

# === Paramètres ===
nb_users = 1000           # nombre d’utilisateurs fictifs
avis_par_poi = 5          # nombre d’avis par POI

# Supprimer les anciens avis
cursor.execute("DELETE FROM avis")
conx.commit()
print("Anciens avis supprimés.")

# Récupérer tous les POI
cursor.execute("SELECT idPoi FROM poi")
pois = [row[0] for row in cursor.fetchall()]
print(f"{len(pois)} POI récupérés depuis MySQL")

# Génération et insertion
total_avis = 0
lstAvis = list()
for poi_id in pois:
    for _ in range(avis_par_poi):
        idTip = faker.uuid4()
        dateCreated = faker.date_time_this_year()
        note = random.randint(1, 5)
        avisNb = random.randint(1, 5)
        if note == 1:
            if avisNb == 1:
                content = "Nul, j'ai vraiment passé un moment horrible."
            if avisNb == 2:
                content = "Beaucoup trop cher pour ce que c'est. Je ne comprends pas la note."
            if avisNb == 3:
                content = "Comment c'est possible de de faire les choses aussi mal!"
            if avisNb == 4:
                content = "A fuir. Je n'y remettrais plus jamais les pieds"
            if avisNb == 5:
                content = "Mauvais, nul!!!"
        if note == 2:
            if avisNb == 1:
                content = "Inintéressant au  possible."
            if avisNb == 2:
                content = "Ne vaut vraiment pas le coup"
            if avisNb == 3:
                content = "On peut faire vraiment mieux"
            if avisNb == 4:
                content = "Passer votre chemin"
            if avisNb == 5:
                content = "ça ne vaut pas le prix et le temps perdu"
        if note == 3:
            if avisNb == 1:
                content = "C'était pas trop mal"
            if avisNb == 2:
                content = "On peux faire mieux, mais ça va"
            if avisNb == 3:
                content = "ça avait bien commencé, mais au final je ne reviendrais plus"
            if avisNb == 4:
                content = "Un peu cher, mais on passe un bon moment"
            if avisNb == 5:
                content = "Moyen"
        if note == 4:
            if avisNb == 1:
                content = "J'ai passé un bon moment, je reviendrais"
            if avisNb == 2:
                content = "Propre, courtois et pas trop cher"
            if avisNb == 3:
                content = "Je recommande!!"
            if avisNb == 4:
                content = "RAS le service est correct"
            if avisNb == 5:
                content = "Bon rapport qualité/prix"
        if note == 5:
            if avisNb == 1:
                content = "C'était super!"
            if avisNb == 2:
                content = "Une pépite!!!! Et pas cher pour le service!"
            if avisNb == 3:
                content = "J'ai passé un incroyable moment."
            if avisNb == 4:
                content = "Je recommande vivement! Le service est parfait!"
            if avisNb == 5:
                content = "J'ai adoré le personnel, vraiment sympathique!"
                
            
        idUser = random.randint(1, nb_users)
        

        lstAvis.append((idTip, content, dateCreated, poi_id, note, idUser))
        total_avis += 1

cursor.executemany("""
    INSERT INTO avis (idTip, content, dateCreated, idPoi, note, idUser)
    VALUES (%s, %s, %s, %s, %s, %s)"""
, lstAvis)
# Validation et fermeture
conx.commit()
cursor.close()
conx.close()

print(f"{total_avis} avis fictifs générés et insérés avec succès !")