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

faker = Faker("fr_FR")

# === Paramètres ===
nb_users = 1000      # nombre d’utilisateurs fictifs


# Supprimer les anciens avis
cursor.execute("DELETE FROM user")
conx.commit()
print("Anciens user supprimés.")



# Génération et insertion

lstUser= list()

for _ in range(nb_users):

    name = faker.first_name()
    lstUser.append((_, name))


cursor.executemany("""
    INSERT INTO user (idUser, name)
    VALUES (%s,%s)
""", lstUser)

conx.commit()
cursor.close()
conx.close()

print(f"user fictifs générés et insérés avec succès !")