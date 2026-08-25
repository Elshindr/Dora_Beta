import sqlite3


class FakeConnection:
    def __init__(self):
        self.conn = sqlite3.connect(
            ":memory:",
            check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row

        self._create_database()

    def _create_database(self):
        cursor = self.conn.cursor()

        cursor.executescript("""
            CREATE TABLE categorie (
                idCat INTEGER PRIMARY KEY,
                name TEXT,
                isActive INTEGER
            );

            CREATE TABLE poi (
                idPoi INTEGER PRIMARY KEY,
                idFsq TEXT,
                name TEXT,
                latitudePoi REAL,
                longitudePoi REAL,
                address TEXT,
                idCity INTEGER
            );

            CREATE TABLE poi_categorie (
                idPoi INTEGER,
                idCat INTEGER
            );

            CREATE TABLE avis (
                idTip TEXT,
                content TEXT,
                note INTEGER,
                idPoi INTEGER,
                idUser INTEGER
            );

            CREATE TABLE historique_voyage (
                idUser INTEGER,
                idPoi INTEGER,
                dateVisite TEXT
            );

            CREATE TABLE user (
                idUser INTEGER PRIMARY KEY,
                name TEXT
            );
        """)

        cursor.executemany(
            """
            INSERT INTO categorie (idCat, name, isActive)
            VALUES (?, ?, ?)
            """,
            [
                (1, "Monuments", 1),
                (2, "Musées", 1),
                (3, "Restaurants", 1),
            ]
        )

        cursor.executemany(
            """
            INSERT INTO poi
            (idPoi, idFsq, name, latitudePoi, longitudePoi, address, idCity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "fake-1", "Tour Eiffel", 48.8584, 2.2945, "Paris", 1),
                (2, "fake-2", "Louvre", 48.8606, 2.3376, "Paris", 1),
                (3, "fake-3", "Arc de Triomphe", 48.8738, 2.2950, "Paris", 1),
                (4, "fake-4", "Musée d'Orsay", 48.8600, 2.3266, "Paris", 1),
                (5, "fake-5", "Restaurant Paris", 48.8566, 2.3522, "Paris", 1),
            ]
        )

        cursor.executemany(
            """
            INSERT INTO poi_categorie (idPoi, idCat)
            VALUES (?, ?)
            """,
            [
                (1, 1),
                (2, 2),
                (3, 1),
                (4, 2),
                (5, 3),
            ]
        )

        cursor.execute(
            """
            INSERT INTO user (idUser, name)
            VALUES (1, 'Test User')
            """
        )

        cursor.executemany(
            """
            INSERT INTO avis
            (idTip, content, note, idPoi, idUser)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("avis-1", "Excellent", 5, 1, 1),
                ("avis-2", "Très bien", 4, 1, 1),
                ("avis-3", "Super musée", 5, 2, 1),
                ("avis-4", "Très intéressant", 4, 3, 1),
            ]
        )

        cursor.executemany(
            """
            INSERT INTO historique_voyage
            (idUser, idPoi, dateVisite)
            VALUES (?, ?, ?)
            """,
            [
                (1, 1, "2026-08-01"),
                (1, 2, "2026-08-02"),
                (1, 3, "2026-08-03"),
            ]
        )

        self.conn.commit()

    def cursor(self):
        return FakeCursor(self.conn.cursor())

    def close(self):
        """
        L'API appelle close() après chaque requête.

        On ne ferme PAS la connexion SQLite ici.
        Sinon le test suivant essaierait d'utiliser
        une base fermée.
        """
        pass

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def execute(self, query, params=None):
        query = query.replace("%s", "?")

        if params is None:
            return self.conn.execute(query)

        return self.conn.execute(query, params)

    def __getattr__(self, name):
        return getattr(self.conn, name)


class FakeCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        # Conversion des placeholders MySQL -> SQLite
        query = query.replace("%s", "?")

        if params is None:
            return self.cursor.execute(query)

        return self.cursor.execute(query, params)

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchone(self):
        return self.cursor.fetchone()

    @property
    def description(self):
        return self.cursor.description

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def close(self):
        self.cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def create_fake_db():
    return FakeConnection()