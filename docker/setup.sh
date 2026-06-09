#!/bin/bash

echo "======================================"
echo "  Pipeline CI/CD - API Sentiment Test"
echo "======================================"

# Création des répertoires
echo "Création de la structure de répertoires"
mkdir -p tests logs

# Nettoyage des anciens containers et images
echo "Nettoyage des anciens containers"
sudo docker compose down --remove-orphans
sudo docker system prune -f


# Construction des images de test
echo "Construction des images"
sudo docker compose up

# Nettoyage final
sudo docker compose down

echo "Pipeline terminé avec succès!"