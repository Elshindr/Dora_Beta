import pymysql
# se rendre au dossier C:\wamp64\apps\phpmyadmin5.2.0

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

try:
    conx = pymysql.connect(
        host=host, 
        user=user, 
        password=pwd, 
        database=db, 
        port=port
    )
    print("Connexion ok")
    
    # Test simple
    with open('Script_SQL_Database_Dora.sql', 'r', encoding='utf-8') as script:
        cursor = conx.cursor()
        lst_instructions = script.read().split(';')
        
        for instruction in lst_instructions:
            cursor.execute(instruction)
            print("commande ok:", instruction)
        
        
    conx.close()
    
except Exception as e:
    print(f"Erreur : {e}")