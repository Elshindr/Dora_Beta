
import L from "leaflet";
import "leaflet-routing-machine/dist/leaflet-routing-machine.css";
import "leaflet-routing-machine";
import { useMap } from "react-leaflet";

import { useEffect, useRef } from 'react';


L.Marker.prototype.options.icon = L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const RoutingMachine = ({ waypoints, mode }) => {
    const map = useMap();
    const routingControlRef = useRef(null);

    useEffect(() => {
        // Nettoyer le contrôle précédent s'il existe
        if (routingControlRef.current) {
            map.removeControl(routingControlRef.current);
        }

        // Créer un nouveau contrôle de routage
        if (waypoints.length > 0) {
            routingControlRef.current = L.Routing.control({
                waypoints: waypoints.map(wp => L.latLng(wp[0], wp[1])),
                routeWhileDragging: true,
                show: false,
                addWaypoints: false,
                lineOptions: {
                    styles: [{ color: '#3388ff', weight: 5 }]
                },
                profile: mode,
                language: 'fr',
                showAlternatives: true,
            }).addTo(map);
        }

        // Nettoyer à la destruction du composant
        return () => {
            if (routingControlRef.current) {
                map.removeControl(routingControlRef.current);
            }
        };
    }, [waypoints, map]);

    return null;
};

export default RoutingMachine;