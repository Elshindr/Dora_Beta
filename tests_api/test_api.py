import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


sys.path.append(str(Path(__file__).parent.parent))


from api import app


@pytest.fixture
def client():
    return TestClient(app)

# =========================================================
# ==================== HEALTH CHECK =======================
# =========================================================
def test_health(client):  # Utilise la fixture client
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# =========================================================
# ===================== /api/pois =========================
# =========================================================

def test_list_pois(client):
    response = client.get("/api/pois")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Vérifie la structure d'un POI
    assert "idPoi" in data[0]
    assert "name" in data[0]


def test_list_pois_pagination(client):
    response = client.get("/api/pois?limit=5&offset=0")
    assert response.status_code == 200
    assert len(response.json()) <= 5


# =========================================================
# =================== /api/poi/{id} ===================
# =======================================================

def test_get_poi_trouve(client):
    # Récupère d'abord un vrai id depuis la liste
    pois = client.get("/api/pois?limit=1").json()
    poi_id = pois[0]["idPoi"]

    response = client.get(f"/api/poi/{poi_id}")
    assert response.status_code == 200
    assert response.json()["idPoi"] == poi_id


def test_get_poi_non_trouve(client):
    response = client.get("/api/poi/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "POI non trouvé"


# =========================================================
# ================ /api/categories ========================
# =========================================================

def test_list_categories(client):
    response = client.get("/api/categories")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "idCat" in data[0]
    assert "name" in data[0]


# =========================================================
# =================== /api/cats ===========================
# =========================================================

def test_get_cats(client):
    response = client.get("/api/cats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert "idCat" in data[0]
    assert "name" in data[0]


# =========================================================
# ================== /api/search ==========================
# =========================================================

def test_search_poi(client):
    response = client.get("/api/search?q=Paris")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_search_trop_court(client):
    response = client.get("/api/search?q=a")
    assert response.status_code == 422  # Validation FastAPI


# =========================================================
# ============= /api/poisbycats/{idCat} ===================
# =========================================================

def test_get_pois_by_cat(client):
    # Récupère d'abord une vraie catégorie
    cats = client.get("/api/cats").json()
    id_cat = cats[0]["idCat"]

    response = client.get(f"/api/poisbycats/{id_cat}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "idPoi" in data[0]
        assert "namePoi" in data[0]


# =========================================================
# ========= /api/user/{user_id}/history ===================
# =========================================================

def test_user_history(client):
    response = client.get("/api/user/1/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# =========================================================
# ============= /api/recommend_from_selection =============
# =========================================================

def test_recommend_from_selection(client):
    # Récupère de vrais ids de POIs
    pois = client.get("/api/pois?limit=3").json()
    poi_ids = [p["idPoi"] for p in pois]

    payload = {"selected_pois": poi_ids, "user_id": 1}
    response = client.post("/api/recommend_from_selection", json=payload)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_recommend_liste_vide(client):
    payload = {"selected_pois": [], "user_id": 1}
    response = client.post("/api/recommend_from_selection", json=payload)
    assert response.status_code == 200
    assert response.json() == []


# =========================================================
# ================= /api/poi_by_ids =======================
# =========================================================

def test_poi_by_ids(client):
    pois = client.get("/api/pois?limit=3").json()
    poi_ids = [p["idPoi"] for p in pois]

    response = client.post("/api/poi_by_ids", json={"lstPois": poi_ids})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_poi_by_ids_vide(client):
    response = client.post("/api/poi_by_ids", json={"lstPois": []})
    assert response.status_code == 200
    assert response.json() == []


# =========================================================
# ========== /api/avisbypoi/{idPoi} =======================
# =========================================================

def test_avis_by_poi(client):
    pois = client.get("/api/pois?limit=1").json()
    poi_id = pois[0]["idPoi"]

    response = client.get(f"/api/avisbypoi/{poi_id}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)