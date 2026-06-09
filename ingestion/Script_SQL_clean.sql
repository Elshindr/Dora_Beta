DELETE FROM categorie
WHERE idCat NOT IN (
    SELECT DISTINCT pc.idCat
    FROM poi_categorie pc
);