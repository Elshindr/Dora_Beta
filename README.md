# Dora

## Installation
- Créer une base de données MySQL
- Créer un compte Foursquare et récupérer la clé API
- Renseigner le fichier .env avec
```
MYSQL_HOST=
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DB=
API=
PATH_MODEL=
```

- Lancer le pipeline airflow depuis le dossier racine
``` 
docker compose -f docker-compose.airflox.yaml up --build
```
- Atteindre l'endpoint localhost:8080 pour atteindre Airflow
- Lancer le DAG "Create Database" pour initier la création de la base de données

- Lancer l'applicatif depuis le dossier racine
``` 
docker-compose up --build
```

ou

``` 
./docker/setup.sh
```
- Se rendre à localhost:3000 pour le front ReactJS
- Se rendre à localhost:5000/health pour  le back
- Se rendre à localhost:9090 pour Prometheus
- Se rendre à localhost:3001 pour Grafana



# Liste des sources de données
APIs externes et intégrations:
   - POIs:
      - [FourSquare](https://location.foursquare.com/developer/)
      - https://docs.foursquare.com/data-products/docs/categories
      - https://docs.foursquare.com/data-products/docs/access-fsq-os-places
              
   - Méteo:
      - [WeatherAPI](https://www.weatherapi.com/)


  

  



