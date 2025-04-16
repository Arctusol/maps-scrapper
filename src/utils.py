import re
import logging
import math # Needed for bounding box calculation
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

# Regex pour extraire lat, lng, et zoom/radius de la partie '@'
# Ex: @48.8582602,2.2944965,17z ou @48.8678444,2.2874891,17453m
GEO_REGEX = re.compile(r'@(-?\d+\.\d+),(-?\d+\.\d+),(\d+(\.\d+)?)(z|m)?')

# Regex pour extraire le mot-clé de la partie /search/
SEARCH_REGEX = re.compile(r'/search/([^/@]+)')

def estimate_radius_from_zoom(zoom_level: float) -> int:
    """
    Estime approximativement un rayon de recherche en mètres basé sur le niveau de zoom Google Maps.
    Ceci est très approximatif et peut nécessiter des ajustements.
    Source approximative : https://wiki.openstreetmap.org/wiki/Zoom_levels
    """
    # Échelle approximative (mètres par pixel à l'équateur) pour différents niveaux de zoom
    # zoom_scales = { 10: 152, 11: 76, 12: 38, 13: 19, 14: 9.5, 15: 4.7, 16: 2.4, 17: 1.2, 18: 0.6, 19: 0.3, 20: 0.15 }
    # On peut utiliser une formule simplifiée ou une correspondance plus directe.
    # Pour simplifier, utilisons une estimation basée sur l'expérience :
    # Zoom 17z (rue) -> ~500m radius?
    # Zoom 15z (quartier) -> ~2000m radius?
    # Zoom 13z (petite ville) -> ~5000m radius?
    # Zoom 11z (ville) -> ~15000m radius?
    if zoom_level >= 17:
        return 1000 # Rayon plus petit pour zoom élevé
    elif zoom_level >= 15:
        return 2500
    elif zoom_level >= 13:
        return 5000
    elif zoom_level >= 11:
        return 15000
    else:
        return 50000 # Rayon large par défaut pour faible zoom

def parse_google_maps_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Analyse une URL Google Maps pour extraire les coordonnées, le rayon/zoom et le mot-clé.

    Args:
        url: L'URL Google Maps à analyser.

    Returns:
        Un dictionnaire contenant 'latitude', 'longitude', 'radius_meters', 'keyword'
        ou None si l'URL ne peut pas être analysée correctement.
    """
    if not url:
        return None

    parsed_url = urlparse(url)
    path_segments = parsed_url.path.split('/')
    query_params = parse_qs(parsed_url.query)

    latitude, longitude, radius_meters, keyword = None, None, None, None

    # 1. Extraire Lat/Lng et Rayon/Zoom
    geo_match = GEO_REGEX.search(parsed_url.path)
    if geo_match:
        latitude = float(geo_match.group(1))
        longitude = float(geo_match.group(2))
        value = float(geo_match.group(3))
        unit = geo_match.group(5)

        if unit == 'm':
            radius_meters = int(value)
        elif unit == 'z':
            radius_meters = estimate_radius_from_zoom(value)
        else: # Si ni 'm' ni 'z' (ancien format?), estimer depuis la valeur comme si c'était un zoom
             radius_meters = estimate_radius_from_zoom(value)
        logger.info(f"URL Geo Info: Lat={latitude}, Lng={longitude}, Radius={radius_meters}m (estimated from {value}{unit or '?'})")
    else:
         logger.warning("Impossible d'extraire les informations géographiques '@lat,lng,zoom/radius' de l'URL.")
         # On pourrait essayer de chercher lat/lng dans les query params comme fallback, mais c'est moins fiable.

    # 2. Extraire le Mot-clé
    search_match = SEARCH_REGEX.search(parsed_url.path)
    if search_match:
        keyword = search_match.group(1).replace('+', ' ').strip()
        logger.info(f"URL Keyword (from path): '{keyword}'")
    else:
        # Essayer d'extraire depuis le paramètre 'q' (moins courant pour les recherches complexes)
        if 'q' in query_params:
            keyword = query_params['q'][0].strip()
            logger.info(f"URL Keyword (from 'q' param): '{keyword}'")
        else:
            # Essayer d'extraire depuis la partie 'data=' (méthode plus complexe et fragile)
            # Exemple: data=!3m1!1e3!4m5!2m4!5m2!4e7!6sgcid:french_restaurant!6e5
            # On cherche souvent après !6s ou similaire. C'est très dépendant de la version de GMaps.
            # Pour simplifier ici, on ne tente pas cette extraction complexe pour le moment.
            logger.warning("Impossible d'extraire le mot-clé depuis le chemin /search/ ou le paramètre 'q'.")

    # Retourner les résultats si on a au moins les coordonnées
    if latitude is not None and longitude is not None:
        return {
            "latitude": latitude,
            "longitude": longitude,
            "radius_meters": radius_meters,
            "keyword": keyword
        }
    else:
        return None # Analyse échouée si pas de coordonnées

def calculate_bounding_box(center_lat: float, center_lon: float, radius_meters: int) -> Optional[Dict[str, float]]:
    """
    Calcule une boîte englobante (bounding box) autour d'un point central donné et d'un rayon.

    Args:
        center_lat: Latitude du point central.
        center_lon: Longitude du point central.
        radius_meters: Rayon autour du centre en mètres.

    Returns:
        Un dictionnaire avec 'sw_lat', 'sw_lon', 'ne_lat', 'ne_lon' ou None si erreur.
    """
    if radius_meters <= 0:
        logger.error("Le rayon pour le calcul de la bounding box doit être positif.")
        return None

    # Conversion approximative: https://en.wikipedia.org/wiki/Geographic_coordinate_system#Length_of_a_degree
    # 1 degré de latitude ≈ 111,132 mètres (relativement constant)
    # 1 degré de longitude ≈ 111,320 * cos(latitude) mètres
    try:
        lat_rad = math.radians(center_lat)
        deg_lat_dist = 111132.0
        deg_lon_dist = 111320.0 * math.cos(lat_rad)

        if deg_lon_dist == 0: # Éviter division par zéro aux pôles
             logger.warning("Calcul de la longitude invalide près des pôles.")
             # Pourrait retourner une box très large ou None
             return None

        delta_lat = radius_meters / deg_lat_dist
        delta_lon = radius_meters / deg_lon_dist

        sw_lat = center_lat - delta_lat
        sw_lon = center_lon - delta_lon
        ne_lat = center_lat + delta_lat
        ne_lon = center_lon + delta_lon

        # S'assurer que les latitudes/longitudes restent dans les limites valides
        sw_lat = max(-90.0, sw_lat)
        ne_lat = min(90.0, ne_lat)
        # Pour la longitude, gérer le dépassement de +/- 180 n'est pas crucial ici
        # car on définit juste une zone de recherche.

        logger.info(f"Bounding box calculée: SW({sw_lat:.6f}, {sw_lon:.6f}), NE({ne_lat:.6f}, {ne_lon:.6f}) pour centre ({center_lat}, {center_lon}) et rayon {radius_meters}m")

        return {
            "sw_lat": sw_lat,
            "sw_lon": sw_lon,
            "ne_lat": ne_lat,
            "ne_lon": ne_lon
        }
    except Exception as e:
         logger.error(f"Erreur lors du calcul de la bounding box: {e}", exc_info=True)
         return None

if __name__ == '__main__':
    # Exemples de test
    test_urls = [
        "https://www.google.fr/maps/search/restaurant/@48.8678444,2.2874891,17453m/data=!3m1!1e3!4m5!2m4!5m2!4e7!6sgcid:french_restaurant!6e5?entry=ttu",
        "https://www.google.com/maps/search/pizza+near+eiffel+tower/@48.8583701,2.2944813,15z/data=!3m1!4b1",
        "https://www.google.com/maps/@48.8582602,2.2944965,17z", # Juste coordonnées et zoom
        "https://www.google.com/maps/place/Eiffel+Tower/@48.8583701,2.2922926,17z/data=!3m1!4b1!4m6!3m5!1s0x47e66e2964e34e2d:0x8ddca9ee380ef7e0!8m2!3d48.8583701!4d2.2944813!16zL20vMDI3NXI", # URL de lieu spécifique
        "https://www.google.com/maps/search/cafes/?q=cafes+near+me" # Utilise le param 'q'
    ]

    for url in test_urls:
        print(f"\nAnalysing URL: {url}")
        result = parse_google_maps_url(url)
        if result:
            print(f"  -> Result: {result}")
        else:
            print("  -> Failed to parse.")