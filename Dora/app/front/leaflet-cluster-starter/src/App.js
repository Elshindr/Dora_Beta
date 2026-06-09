import { useState, useEffect } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import "leaflet-routing-machine/dist/leaflet-routing-machine.css";
import MarkerClusterGroup from '@changey/react-leaflet-markercluster';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { Rating } from 'react-simple-star-rating';
import "leaflet-routing-machine";
import Accordion from 'react-bootstrap/Accordion';
import Modal from 'react-bootstrap/Modal';
import RoutingMachine from './routing';
import './App.css';

const defaultIcon = L.icon({
    iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
    iconUrl: require('leaflet/dist/images/marker-icon.png'),
    shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const TRANSPORT_MODES = [
    { value: 'car', label: '🚗 Voiture' },
    { value: 'bicycle', label: '🚲 Vélo' },
    { value: 'foot', label: '🚶 À pied' },
];

function App() {
    const [pois, setPois] = useState([]);
    const [cats, setCats] = useState([]);
    const [filterCat, setFilteredCats] = useState([]);
    const [acts, setActs] = useState([]);
    const [checkedCats, setCheckedCats] = useState([]);
    const [recoms, setRecoms] = useState({});
    const [lstAvis, setLstAvis] = useState([]);
    const [waypoints, setWaypoints] = useState([]);
    const [startDate, setStart] = useState('');
    const [endDate, setEnd] = useState('');
    const [mode, setMode] = useState('car');
    const [nbEtape, setEtape] = useState(3);
    const [show, setShow] = useState(false);
    const [aiReco, setAiReco] = useState([]);
    const [dateError, setDateError] = useState('');

    useEffect(() => {
        fetch('http://localhost:5000/api/cats')
            .then(r => r.json())
            .then(data => { setCats(data); setFilteredCats(data); })
            .catch(console.error);
    }, []);

    function onChangeCheckbox(cat, isChecked) {
        if (isChecked) {
            setCheckedCats(prev => [...prev, cat.idCat]);
            fetch('http://localhost:5000/api/poisbycats/' + cat.idCat)
                .then(r => r.json())
                .then(data => {
                    const newPois = data.filter(p => !pois.some(e => e.idPoi === p.idPoi));
                    setPois(prev => [...prev, ...newPois]);
                })
                .catch(console.error);
        } else {
            setCheckedCats(prev => prev.filter(id => id !== cat.idCat));
            setPois(prev => prev.filter(p => p.nameCat !== cat.name));
        }
    }

    function onChangeSearch(term) {
        setFilteredCats(cats.filter(c => c.name.toLowerCase().includes(term.toLowerCase())));
    }

    async function onVoirAvis(idPoi) {
        setLstAvis([]);
        fetch('http://localhost:5000/api/avisbypoi/' + idPoi)
            .then(r => r.json())
            .then(setLstAvis)
            .catch(console.error);
    }

    function onAddActivity(poi) {
        if (!acts.some(a => a.idPoi === poi.idPoi))
            setActs(prev => [...prev, poi]);
    }

    function onDeleteActivity(idPoi) {
        setActs(prev => prev.filter(p => p.idPoi !== idPoi));
    }

    async function onRecommandationIA() {
        try {
            const lstPoi = acts.map(a => a.idPoi);
            const recoRes = await fetch('http://localhost:5000/api/recommend_from_selection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ selected_pois: lstPoi, user_id: 430 }),
            });
            const recoData = await recoRes.json();
            const poiRes = await fetch('http://localhost:5000/api/poi_by_ids', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lstPois: recoData.map(r => r.idPoi) }),
            });
            setAiReco(await poiRes.json());
            setShow(true);
        } catch (e) { console.error(e); }
    }

    function calculateRoute(lstPois) {
        const coords = lstPois.map(a => [a.lat, a.lon]);
        if (coords.length > 0) setWaypoints(coords, mode);
    }

    async function onRecommanderItineraire() {

        if (!startDate || !endDate) {
            setDateError("Les dates de début et de fin sont requises.");
            return;
        }
        if (new Date(endDate) <= new Date(startDate)) {
            setDateError("La date de fin doit être après la date de début.");
            return;
        }
        setDateError('');

        const lstPoi = acts.map(a => ({ id: a.idPoi, name: a.namePoi, lat: a.latitudePoi, lon: a.longitudePoi }));
        fetch('http://localhost:5000/api/optimize-itinerary/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_date: startDate, end_date: endDate, pois: lstPoi, max_pois_per_day: nbEtape }),
        })
            .then(r => r.json())
            .then(setRecoms)
            .catch(console.error);
    }

    return (
        <div className="app-root">

            {/* ── MAP ─────────────────────────────── */}
            <div className="map-col">
                <MapContainer center={[48.86, 2.33]} zoom={13} style={{ height: '100%', width: '100%' }}>
                    <TileLayer
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    />
                    <MarkerClusterGroup>
                        {pois.map(poi => (
                            <Marker key={poi.idPoi} position={[poi.latitudePoi, poi.longitudePoi]} icon={defaultIcon}>
                                <Popup>
                                    <div className="popup-card">
                                        <div className="popup-card-title">{poi.namePoi}</div>
                                        <div className="popup-card-cat">{poi.nameCat}</div>
                                        <div className="popup-card-address">{poi.address}</div>
                                        <div className="popup-card-footer">
                                            <Rating initialValue={parseInt(poi.note)} readonly size={16} fillColor="#fbbf24" emptyColor="#484f58" />
                                            <button className="btn-add-small" onClick={() => onAddActivity(poi)}>+</button>
                                        </div>
                                    </div>
                                </Popup>
                            </Marker>
                        ))}
                        <RoutingMachine waypoints={waypoints} />
                    </MarkerClusterGroup>
                </MapContainer>
            </div>

            {/* ── ACTIVITIES PANEL ────────────────── */}
            <div className="panel">
                {/* Category search */}
                <div className="panel-section">
                    <div className="section-title">Catégories</div>
                    <input
                        type="text"
                        className="search-input"
                        placeholder="Rechercher… ex: restaurant"
                        onChange={e => onChangeSearch(e.target.value)}
                        style={{ marginBottom: 12 }}
                    />
                    <div className="cat-list" style={{ maxHeight: 220, overflowY: 'auto' }}>
                        {filterCat.map(cat => (
                            <label key={cat.idCat} className={`cat-item ${checkedCats.includes(cat.idCat) ? 'checked' : ''}`} style={{ color: 'aliceblue' }}>
                                <input
                                    type="checkbox"
                                    checked={checkedCats.includes(cat.idCat)}
                                    onChange={e => onChangeCheckbox(cat, e.target.checked)}
                                />
                                {cat.name}
                            </label>
                        ))}
                    </div>
                </div>

                {/* Selected activities */}
                <div className="panel-section" style={{ borderBottom: 'none' }}>
                    <div className="section-title">Mes centres d'intérêt</div>
                </div>

                <div className="panel-scrollable">
                    {acts.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-state-icon">🗺️</div>
                            <p>Ajoutez des activités depuis la carte</p>
                        </div>
                    ) : (
                        <Accordion>
                            {acts.map(act => (
                                <Accordion.Item eventKey={'acc-' + act.idPoi} key={'acc-' + act.idPoi}>
                                    <div style={{ display: 'flex', alignItems: 'center' }}>
                                        <Accordion.Header style={{ flex: 1 }}>
                                            <span style={{ fontSize: 13, fontWeight: 500 }}>{act.namePoi}</span>
                                            <Rating initialValue={parseInt(act.note)} readonly size={14} fillColor="#fbbf24" emptyColor="#484f58" style={{ marginLeft: 8 }} />
                                        </Accordion.Header>
                                        <button
                                            className="btn-delete"
                                            onClick={e => { e.stopPropagation(); onDeleteActivity(act.idPoi); }}
                                            title="Retirer"
                                        >✕</button>
                                    </div>
                                    <Accordion.Collapse
                                        eventKey={'acc-' + act.idPoi}
                                        onEntered={() => onVoirAvis(act.idPoi)}
                                    >
                                        <Accordion.Body>
                                            <div className="carousel-custom">
                                                {lstAvis.length === 0 ? (
                                                    <div className="review-slide">
                                                        <p className="review-text" style={{ fontStyle: 'normal', color: 'var(--text-muted)' }}>Chargement des avis…</p>
                                                    </div>
                                                ) : lstAvis.map(avis => (
                                                    <div key={avis.idTip} className="review-slide">
                                                        <p className="review-text">"{avis.content}"</p>
                                                        <Rating initialValue={parseInt(avis.note)} readonly size={14} fillColor="#fbbf24" emptyColor="#484f58" />
                                                        <span className="badge-cat" style={{ marginTop: 6 }}>{act.nameCat}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </Accordion.Body>
                                    </Accordion.Collapse>
                                </Accordion.Item>
                            ))}
                        </Accordion>
                    )}
                </div>

                <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
                    <button className="btn-primary-custom" onClick={onRecommandationIA}>
                        ✨ Me recommander des activités
                    </button>
                </div>
            </div>

            {/* ── ITINERARY PANEL ─────────────────── */}
            <div className="panel">
                <div className="panel-section">
                    <div className="section-title">Mon itinéraire</div>
                    {dateError && (
                        <p style={{ color: 'var(--danger)', fontSize: 12, marginBottom: 10 }}>
                            ⚠️ {dateError}
                        </p>
                    )}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                        <span className="form-label-custom">Début</span>
                        <input type="date" className="form-control-custom" style={{ flex: 1 }}
                            onChange={e => setStart(e.target.value)} />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                        <span className="form-label-custom">Fin</span>
                        <input type="date" className="form-control-custom" style={{ flex: 1 }}
                            onChange={e => setEnd(e.target.value)} />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                        <span className="form-label-custom">Actes/jour</span>
                        <input type="number" className="form-control-custom" style={{ flex: 1 }}
                            placeholder="3" min="1" max="10"
                            onChange={e => setEtape(e.target.value)} />
                    </div>

                    <div className="transport-group" style={{ marginBottom: 14 }}>
                        {TRANSPORT_MODES.map(m => (
                            <label key={m.value} className={`transport-option ${mode === m.value ? 'active' : ''}`}>
                                <input type="radio" name="mode" value={m.value}
                                    checked={mode === m.value}
                                    onChange={e => setMode(e.target.value)} />
                                {m.label}
                            </label>
                        ))}
                    </div>

                    <button className="btn-primary-custom" onClick={onRecommanderItineraire} disabled={!startDate || !endDate}
                        style={{ opacity: (!startDate || !endDate) ? 0.4 : 1,cursor: (!startDate || !endDate) ? 'not-allowed' : 'pointer',}}>
                        🗓️ Calculer l'itinéraire
                    </button>
                </div>

                <div className="panel-scrollable">
                    {Object.keys(recoms).length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-state-icon">📅</div>
                            <p>Aucun itinéraire calculé</p>
                        </div>
                    ) : (
                        <Accordion>
                            {Object.keys(recoms).map(key => (
                                <Accordion.Item eventKey={'day-' + key} key={'day-' + key}>
                                    <Accordion.Header>
                                        <span className={`day-label ${recoms[key].extra_day ? 'extra' : ''}`}>{key}</span>
                                        <span className="day-distance" style={{ marginLeft: 'auto', marginRight: 12 }}>
                                            {recoms[key].distance_km} km
                                        </span>
                                    </Accordion.Header>
                                    <Accordion.Body>
                                        <div className="day-poi-list">
                                            {recoms[key].pois.map(act => (
                                                <div key={act.id} className="day-poi-item">{act.name}</div>
                                            ))}
                                        </div>
                                        <div style={{ padding: '8px 14px 14px' }}>
                                            <button className="btn-primary-custom" onClick={() => calculateRoute(recoms[key].pois)}>
                                                🗺️ Voir sur la carte
                                            </button>
                                        </div>
                                    </Accordion.Body>
                                </Accordion.Item>
                            ))}
                        </Accordion>
                    )}
                </div>
            </div>

            {/* ── AI RECO MODAL ───────────────────── */}
            <Modal show={show} onHide={() => setShow(false)} centered>
                <Modal.Header closeButton>
                    <Modal.Title>✨ Nos recommandations</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {aiReco.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-state-icon">⏳</div>
                            <p>Chargement…</p>
                        </div>
                    ) : aiReco.map(reco => (
                        <div key={reco.idPoi} className="reco-item">
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <div>
                                    <div className="reco-item-name">{reco.namePoi}</div>
                                    <div className="reco-item-cat">{reco.nameCat}</div>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <Rating initialValue={parseInt(reco.note)} readonly size={14} fillColor="#fbbf24" emptyColor="#484f58" />
                                    <button className="btn-add-small" onClick={() => onAddActivity(reco)}>+</button>
                                </div>
                            </div>
                        </div>
                    ))}
                </Modal.Body>
            </Modal>
        </div>
    );
}

export default App;
