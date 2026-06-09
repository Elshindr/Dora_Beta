from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
from typing import List, Dict, Tuple
import random
from haversine import haversine


def nearest_neighbor(pois: List[Dict], start_idx: int = 0) -> List[Dict]:
    """
    Algorithme du plus proche voisin pour optimiser l'ordre de visite
    """
    if not pois:
        return []
    
    unvisited = pois.copy()
    current = unvisited.pop(start_idx)
    route = [current]
    
    while unvisited:
        nearest_dist = float('inf')
        nearest_idx = 0
        
        for i, poi in enumerate(unvisited):
            dist = haversine(
                (current['lon'], current['lat']),
                (poi['lon'], poi['lat'])
            )
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = i
        
        current = unvisited.pop(nearest_idx)
        route.append(current)
    
    return route



def calculate_total_distance(route: List[Dict]) -> float:
    """
    Calcule la distance totale d'un itinéraire
    """
    if len(route) <= 1:
        return 0.0

    total = 0
    for i in range(len(route) - 1):
        total += haversine(
            (route[i]['lat'], route[i]['lon']),
            (route[i+1]['lat'], route[i+1]['lon'])
        )
    return total



def optimize_itinerary(
    start_date: str,
    end_date: str,
    pois: List[Dict],
    max_pois_per_day: int = None
) -> Dict:
    """
    Optimise la visite des POIs sur plusieurs jours.
    Si trop de POIs, ajoute automatiquement des jours supplémentaires avec un tag 'extra_day'.
    
    Args:
        start_date: Date de début (format 'YYYY-MM-DD')
        end_date: Date de fin (format 'YYYY-MM-DD')
        pois: Liste de POIs avec 'id', 'name', 'lat', 'lon'
        max_pois_per_day: Nombre max de POIs par jour (None = auto)
    
    Returns:
        Dictionnaire avec :
        - itinerary: Dict avec les jours et leurs POIs
        - has_extra_days: Boolean indiquant si des jours ont été ajoutés
        - extra_days_count: Nombre de jours supplémentaires
    """
    # Convertir les dates
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    # Calculer le nombre de jours initiaux
    num_days_initial = (end - start).days + 1
    
    if num_days_initial <= 0:
        raise ValueError("La date de fin doit être après la date de début")
    
    # Répartir les POIs sur les jours
    if max_pois_per_day is None:
        max_pois_per_day = len(pois) // num_days_initial + (1 if len(pois) % num_days_initial else 0)
    
    # Calculer le nombre de jours nécessaires
    num_days_needed = (len(pois) + max_pois_per_day - 1) // max_pois_per_day  # Division arrondie au supérieur
    
    # Déterminer s'il faut des jours supplémentaires
    extra_days_count = max(0, num_days_needed - num_days_initial)
    has_extra_days = extra_days_count > 0
    
    # Optimiser l'ordre global des POIs
    optimized_pois = nearest_neighbor(pois)
    
    # Répartir par jour
    itinerary = {}
    current_date = start
    day_index = 0
    
    for i in range(0, len(optimized_pois), max_pois_per_day):
        date_str = current_date.strftime('%Y-%m-%d')
        day_pois = optimized_pois[i:i+max_pois_per_day]
        
        # Déterminer si c'est un jour supplémentaire
        is_extra_day = current_date > end
        
        itinerary[date_str] = {
            'pois': day_pois,
            'distance_km': round(calculate_total_distance(day_pois), 2),
            'extra_day': is_extra_day,  # Tag pour le frontend
        }
        
        current_date += timedelta(days=1)
        day_index += 1
    

    return itinerary
