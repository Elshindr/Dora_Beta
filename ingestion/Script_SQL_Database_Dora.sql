DROP TABLE IF EXISTS `poi`;
CREATE TABLE IF NOT EXISTS `poi` (
  `idFsq` varchar(250) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `idCity` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `idPoi` int NOT NULL AUTO_INCREMENT,
  `address` varchar(250) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `latitudePoi` double NOT NULL,
  `longitudePoi` double NOT NULL,
  PRIMARY KEY (`idPoi`),
  UNIQUE KEY `idFsq` (`idFsq`,`idPoi`),
  KEY `poi_ibfk_1` (`idCity`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS `avis`;
CREATE TABLE IF NOT EXISTS avis (
  idTip VARCHAR(250) PRIMARY KEY,
  content VARCHAR(250) NOT NULL,
  dateCreated DATETIME NOT NULL,
  idPoi INT NOT NULL,
  idUser INT NOT NULL,
  note INT CHECK (note BETWEEN 1 AND 5),
  FOREIGN KEY (idPoi) REFERENCES poi(idPoi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `categorie`;
CREATE TABLE IF NOT EXISTS `categorie` (
  `name` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `idCat` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `icoPrefix` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `icoSuffix` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `idFsq` int NOT NULL,
  PRIMARY KEY (`idCat`),
  UNIQUE KEY `idCat` (`idCat`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;





DROP TABLE IF EXISTS `poi_categorie`;
CREATE TABLE IF NOT EXISTS `poi_categorie` (
  `idPoiCat` int NOT NULL AUTO_INCREMENT,
  `idCat` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `idPoi` int NOT NULL,
  PRIMARY KEY (`idPoiCat`),
  UNIQUE KEY `idPoiCat` (`idPoiCat`),
  KEY `poi_categorie_ibfk_1` (`idCat`),
  KEY `poi_categorie_ibfk_2` (`idPoi`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `ville`;
CREATE TABLE IF NOT EXISTS `ville` (
  `cp` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `idCity` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `latitudeCity` double NOT NULL,
  `longitudeCity` double NOT NULL,
  `region` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `departement` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`idCity`),
  UNIQUE KEY `idCity` (`idCity`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



DROP TABLE IF EXISTS `user`;
CREATE TABLE IF NOT EXISTS `user` (
  `idUser` int NOT NULL,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`idUser`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `historique_voyage`;
CREATE TABLE IF NOT EXISTS `historique_voyage` (
  `idHistorique` int NOT NULL AUTO_INCREMENT,
  `idUser` int NOT NULL,
  `idPoi` int NOT NULL,
  `dateVisite` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`idHistorique`),
  UNIQUE KEY `unique_user_poi` (`idUser`,`idPoi`),
  KEY `idPoi` (`idPoi`)
) ENGINE=InnoDB AUTO_INCREMENT=49952 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE `avis`
  ADD CONSTRAINT `tip_poi` FOREIGN KEY (`idPoi`) REFERENCES `poi` (`idPoi`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `avis`
  ADD CONSTRAINT `tip_user` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`) ON DELETE RESTRICT ON UPDATE RESTRICT;


ALTER TABLE `poi`
  ADD CONSTRAINT `poi_ibfk_1` FOREIGN KEY (`idCity`) REFERENCES `ville` (`idCity`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `poi_categorie`
  ADD CONSTRAINT `poi_categorie_ibfk_1` FOREIGN KEY (`idCat`) REFERENCES `categorie` (`idCat`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `poi_categorie`
  ADD CONSTRAINT `poi_categorie_ibfk_2` FOREIGN KEY (`idPoi`) REFERENCES `poi` (`idPoi`) ON DELETE RESTRICT ON UPDATE RESTRICT;


ALTER TABLE `historique_voyage`
  ADD CONSTRAINT `historique_voyage_ibfk_1` FOREIGN KEY (`idUser`) REFERENCES `user` (`idUser`),
  ADD CONSTRAINT `historique_voyage_ibfk_2` FOREIGN KEY (`idPoi`) REFERENCES `poi` (`idPoi`);