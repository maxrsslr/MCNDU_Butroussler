# -*- coding: utf-8 -*-
"""
Script permettant le calcul des itinéraires 
"""
import json
import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString
from collections import defaultdict
from tqdm import tqdm
import pickle
import os
import psutil
import uuid

#chargement des données
base_dir = "/Users/XXXXX/XXXXXX/Tradd 22/MCDNU/Fichiers" #A adapter
stations_file = f"{base_dir}/velib-emplacement-des-stations.json"
trajets_file = f"{base_dir}/stats_bike_82259_noel.json" 
output_files = {
    'scenario1': {
        'routes': f"{base_dir}/velib_routes_scenario1.geojson",
        'segments': f"{base_dir}/velib_segments_scenario1.geojson",
        'checkpoint': f"{base_dir}/routes_checkpoint_scenario1.pkl"
    },
    'scenario2': {
        'routes': f"{base_dir}/velib_routes_scenario2.geojson",
        'segments': f"{base_dir}/velib_segments_scenario2.geojson",
        'checkpoint': f"{base_dir}/routes_checkpoint_scenario2.pkl"
    },
    'scenario3': {
        'routes': f"{base_dir}/velib_routes_scenario3.geojson",
        'segments': f"{base_dir}/velib_segments_scenario3.geojson",
        'checkpoint': f"{base_dir}/routes_checkpoint_scenario3.pkl"
    }
}

graph_cache_file = f"{base_dir}/graph_cache.pkl"
nodes_cache_file = f"{base_dir}/station_nodes_cache.pkl"

# Paramètres de calcul des trajets
MIN_TRIP_COUNT = 1
DEBUG_MODE = False  
DEBUG_SAMPLE_SIZE = 1000

print("="*70)
print("CALCUL ITINÉRAIRES VÉLIB - VERSION MULTI-SCÉNARIOS")
print("="*70)

#affichage de la RAM utilisée pour ce script
def print_memory_usage():
    mem = psutil.virtual_memory()
    print(f"RAM : {mem.used/1e9:.1f}/{mem.total/1e9:.1f} GB ({mem.percent:.1f}%)")

#%%
# ÉTAPE 1 : Chargement des données

print("\n[1/9] Chargement des données...")
print_memory_usage()

with open(stations_file, 'r', encoding='utf-8') as f:
    stations_data = json.load(f)

with open(trajets_file, 'r', encoding='utf-8') as f:
    trajets_data = json.load(f)

# Harmoniser les IDs et créer un index des trajets 
trajets_index = {}  
for bike in trajets_data:
    for stat in bike['stats']:
        if stat.get('start_station_id'):
            stat['start_station_id'] = stat['start_station_id'].replace('station_', '')
        if stat.get('end_station_id'):
            stat['end_station_id'] = stat['end_station_id'].replace('station_', '')
        
        # Indexer les trajets complétés
        if stat.get('status') == 'completed' and stat.get('end_station_id'):
            key = (stat['start_station_id'], stat['end_station_id'])
            if key not in trajets_index:
                trajets_index[key] = []
            trajets_index[key].append(stat)

print(f" {len(trajets_index)} paires de stations avec trajets")
print_memory_usage()

#%%
# ÉTAPE 2 : Extraction coordonnées stations


print("\n[2/9] Extraction des coordonnées des stations...")

stations_coords = {}
for s in stations_data:
    code = str(s.get("stationcode"))
    coords = s.get("coordonnees_geo", {})
    lon, lat = coords.get("lon"), coords.get("lat")
    if code and lon is not None and lat is not None:
        stations_coords[code] = (lon, lat)

print(f" {len(stations_coords)} stations chargées")

#%%
# ÉTAPE 3 : Extraction paires uniques

print("\n[3/9] Analyse des trajets...")

pair_counts = defaultdict(int)
for bike in trajets_data:
    for stat in bike.get('stats', []):
        if stat.get('status') == 'completed' and stat.get('end_station_id'):
            start = stat.get('start_station_id')
            end = stat.get('end_station_id')
            
            if start in stations_coords and end in stations_coords and start != end:
                pair_counts[(start, end)] += 1

if DEBUG_MODE:
    print(f"MODE DEBUG : échantillonnage de {DEBUG_SAMPLE_SIZE} paires")
    import random
    all_pairs = list(pair_counts.items())
    random.shuffle(all_pairs)
    pair_counts = dict(all_pairs[:DEBUG_SAMPLE_SIZE])

pair_counts = {k: v for k, v in pair_counts.items() if v >= MIN_TRIP_COUNT}
unique_pairs = list(pair_counts.keys())

print(f" {len(unique_pairs)} paires uniques (≥{MIN_TRIP_COUNT} trajets)")
print(f" {sum(pair_counts.values())} trajets totaux")
print(f" Temps estimé : {len(unique_pairs) * 3 * 0.3 / 60:.0f}-{len(unique_pairs) * 3 * 0.5 / 60:.0f} min (3 scénarios)")

print_memory_usage()

#%%
# ÉTAPE 4 : Chargement graphe OSM (AVEC CACHE)

print("\n[4/9] Chargement du graphe routier...")

#téléchargement des zones nécessaires à notre analyse
place = [
    "Paris, France",
    "Val-de-marne, France",
    "Seine-Saint-Denis, France",
    "Hauts-de-Seine, France"
    "Argenteuil, France",
    "Houilles, France",
    "Carrières-sur-Seine, France",
    "Bezons, France"
]

if os.path.exists(graph_cache_file):
    print("  → Chargement depuis le cache...")
    with open(graph_cache_file, 'rb') as f:
        G = pickle.load(f)
    print(f" Graphe chargé : {len(G.nodes):,} nœuds, {len(G.edges):,} arêtes")
else:
    print("  → Téléchargement depuis OpenStreetMap")
    G = ox.graph_from_place(place, network_type="bike")
    print(f"  → Graphe téléchargé : {len(G.nodes):,} nœuds, {len(G.edges):,} arêtes")
    
    print("  → Extraction du composant principal...")
    G = ox.truncate.largest_component(G, strongly=True)
    print(f"  → Graphe traité : {len(G.nodes):,} nœuds, {len(G.edges):,} arêtes")
    
    print("  → Sauvegarde du cache...")
    with open(graph_cache_file, 'wb') as f:
        pickle.dump(G, f)
    print(f"Cache sauvegardé")

print_memory_usage()

#%%
# ÉTAPE 4bis : Pré-calcul des nœuds OSM (AVEC CACHE)

print("\n[4bis/9] Pré-calcul des nœuds OSM pour chaque station...")

if os.path.exists(nodes_cache_file):
    print("  → Chargement depuis le cache...")
    with open(nodes_cache_file, 'rb') as f:
        station_nodes = pickle.load(f)
    print(f"{len(station_nodes)} nœuds chargés")
else:
    station_nodes = {}
    for code, coords in tqdm(stations_coords.items(), desc="Calcul nœuds"):
        try:
            station_nodes[code] = ox.distance.nearest_nodes(G, coords[0], coords[1])
        except Exception as e:
            print(f"  ⚠️  Station {code} : {e}")
    
    with open(nodes_cache_file, 'wb') as f:
        pickle.dump(station_nodes, f)
    print(f"{len(station_nodes)} nœuds calculés et sauvegardés")

#%%
# ÉTAPE 5 : DÉFINITION DES SCÉNARIOS (PONDÉRATIONS)

print("\n[5/9] Configuration des scénarios de calcul...")

# SCÉNARIO 1 : PLUS COURT CHEMIN (référence, sans pondération, package OSMnx simple)
def apply_scenario1_weights(G):
    for u, v, k, data in G.edges(keys=True, data=True):
        data['weighted_length'] = data.get('length', 1)
    return "Plus court chemin (distance uniquement)"

# SCÉNARIO 2 : Broach, J., Dill, J., & Gliebe, J. (2012). Where do cyclists ride? A route choice model developed with revealed preference GPS data. Transportation Research Part A: Policy and Practice, 46(10), 1730-1740. 
def apply_scenario2_weights(G):

    for u, v, k, data in G.edges(keys=True, data=True):
        base_length = data.get('length', 1)
        
        # Détecter piste cyclable
        has_cycleway = False
        if 'cycleway' in data and data['cycleway'] not in [None, 'no']:
            has_cycleway = True
        if 'cycleway:right' in data and data['cycleway:right'] not in [None, 'no']:
            has_cycleway = True
        if 'cycleway:left' in data and data['cycleway:left'] not in [None, 'no']:
            has_cycleway = True
        if 'highway' in data and data['highway'] in ['cycleway', 'path']:
            has_cycleway = True
        
        # Détecter route principale
        is_major_road = False
        if 'highway' in data and data['highway'] in ['primary', 'trunk', 'motorway']:
            is_major_road = True
        
        # Appliquer pondération
        if has_cycleway:
            data['weighted_length'] = base_length * 0.86  # Favoriser pistes de l'ordre de 16% pour les déplacements Domicile-Travail comme le dit l'article
        elif is_major_road:
            data['weighted_length'] = base_length * 1 
        else:
            data['weighted_length'] = base_length  
    
    return "Scénario 2"

# SCÉNARIO 3 : De Jong, T., Böcker, L., & Weber, C. (2023). Road infrastructures, spatial surroundings, and the demand and route choices for cycling: Evidence from a GPS-based mode detection study from Oslo, Norway. Environment and Planning B: Urban Analytics and City Science, 50(8), 2107-2124. Fitch, D. T., & Handy, 
def apply_scenario3_weights(G):
    for u, v, k, data in G.edges(keys=True, data=True):
        base_length = data.get('length', 1)
        
        # Détecter piste cyclable
        has_cycleway = False
        if 'cycleway' in data and data['cycleway'] not in [None, 'no']:
            has_cycleway = True
        if 'cycleway:right' in data and data['cycleway:right'] not in [None, 'no']:
            has_cycleway = True
        if 'cycleway:left' in data and data['cycleway:left'] not in [None, 'no']:
            has_cycleway = True
        if 'highway' in data and data['highway'] in ['cycleway', 'path']:
            has_cycleway = True
        
        # Détecter route principale
        is_major_road = False
        if 'highway' in data and data['highway'] in ['primary', 'trunk', 'motorway']:
            is_major_road = True
        
        # Appliquer pondération
        if has_cycleway:
            data['weighted_length'] = base_length * 0.41  # Favoriser de 59% les pistes cyclables
        elif is_major_road:
            data['weighted_length'] = base_length * 1 
        else:
            data['weighted_length'] = base_length  
    
    return "Scénario 3"

# Configuration des scénarios
SCENARIOS = {
    'scenario1': {
        'name': 'Scénario 1 : Plus court chemin',
        'description': 'Itinéraire le plus court en distance (OSM basique)',
        'apply_weights': apply_scenario1_weights
    },
    'scenario2': {
        'name': 'Scénario 2 : Favoriser pistes cyclables',
        'apply_weights': apply_scenario2_weights
    },
    'scenario3': {
        'name': 'Scénario 3 : Routes rapides',
        'apply_weights': apply_scenario3_weights
    }
}

print("3 scénarios configurés :")
for scenario_id, config in SCENARIOS.items():
    print(f"   • {config['name']}")

#%%
# ETAPE 6 : Création des statistiques

def calculate_route_with_scenario(start_code, end_code, scenario_id, trajets_list):
    """Calcule un itinéraire selon le scénario spécifié."""
    if start_code not in station_nodes or end_code not in station_nodes:
        return None

    try:
        orig_node = station_nodes[start_code]
        dest_node = station_nodes[end_code]

        # Calculer le plus court chemin avec la pondération du scénario
        path = nx.shortest_path(G, orig_node, dest_node, weight="weighted_length")
        points = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in path]
        line = LineString(points)
        
        # Calculer distances réelles et pondérées
        real_length = sum(G.edges[path[i], path[i+1], 0].get('length', 0) 
                         for i in range(len(path)-1))
        weighted_length = nx.shortest_path_length(G, orig_node, dest_node, weight="weighted_length")
        
        # Statistiques des segments (optionnel, pour analyses futures)
        total_segments = len(path) - 1
        
        # Statistiques agrégées des trajets réels
        trip_count = len(trajets_list)
        total_duration = sum(t.get('duration_minutes', 0) for t in trajets_list)
        total_distance = sum(t.get('distance_meters', 0) for t in trajets_list)
        speeds = [t.get('average_speed_kmh', 0) for t in trajets_list if t.get('average_speed_kmh')]
        
        route_data = {
            "route_id": str(uuid.uuid4()),  # ID unique de l'itinéraire
            "geometry": line,
            "start_station": start_code,
            "end_station": end_code,
            "scenario": scenario_id,
            "scenario_name": SCENARIOS[scenario_id]['name'],
            "trip_count": trip_count,
            
            # Métriques de l'itinéraire calculé
            "route_length_meters": real_length,
            "route_weighted_length": weighted_length,
            "route_segments_total": total_segments,
            
            # Statistiques agrégées des trajets réels
            "avg_duration_minutes": total_duration / trip_count if trip_count > 0 else None,
            "avg_distance_meters": total_distance / trip_count if trip_count > 0 else None,
            "avg_speed_kmh": sum(speeds) / len(speeds) if speeds else None,
            "min_speed_kmh": min(speeds) if speeds else None,
            "max_speed_kmh": max(speeds) if speeds else None,
            
            # Liste des IDs de trajets source
            "source_ride_ids": [t['id'] for t in trajets_list]
        }
        
        return route_data
        
    except Exception as e:
        print(f"  ⚠️  Erreur {start_code}→{end_code} ({scenario_id}): {e}")
        return None

#%%
# ETAPE 7 : Calcule des itinéraires selon les scénarios

print("\n[7/9] Calcul des itinéraires pour chaque scénario...")

for scenario_id, config in SCENARIOS.items():
    print(f"\n{'='*70}")
    print(f"🚴 {config['name']}")
    print(f"   {config['description']}")
    print(f"{'='*70}")
    
    # Appliquer la pondération du scénario
    scenario_desc = config['apply_weights'](G)
    print(f"   Pondération appliquée : {scenario_desc}")
    
    # Charger checkpoint si existe
    checkpoint_file = output_files[scenario_id]['checkpoint']
    if os.path.exists(checkpoint_file):
        print("📂 Checkpoint trouvé, chargement...")
        with open(checkpoint_file, 'rb') as f:
            routes = pickle.load(f)
        print(f"{len(routes)} itinéraires déjà calculés")
    else:
        routes = []
    
    # Calculer les routes manquantes
    already_computed = {(r['start_station'], r['end_station']) for r in routes}
    remaining_pairs = [(s, e) for s, e in unique_pairs if (s, e) not in already_computed]
    
    print(f"🚴 Calcul de {len(remaining_pairs)} itinéraires restants...")
    
    for i, (start_code, end_code) in enumerate(tqdm(remaining_pairs, desc=f"Calcul {scenario_id}")):
        # Récupérer tous les trajets pour cette paire
        trajets_list = trajets_index.get((start_code, end_code), [])
        
        result = calculate_route_with_scenario(start_code, end_code, scenario_id, trajets_list)
        if result:
            routes.append(result)
        
        # Checkpoint tous les 500
        if (i + 1) % 500 == 0:
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(routes, f)
            print(f"  💾 Checkpoint: {len(routes)} routes")
    
    # Sauvegarder checkpoint final
    with open(checkpoint_file, 'wb') as f:
        pickle.dump(routes, f)
    
    print(f"{len(routes)} itinéraires calculés pour '{scenario_id}'")
    
    # Sauvegarder GeoJSON
    output_file = output_files[scenario_id]['routes']
    gdf_routes = gpd.GeoDataFrame(routes, crs="EPSG:4326")
    gdf_routes.to_file(output_file, driver="GeoJSON")
    print(f"Fichier sauvegardé : {output_file}")
    
    # Supprimer checkpoint après succès
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)
        print(f"Checkpoint supprimé")
    
    # Libérer mémoire
    del routes, gdf_routes

#%%
# ÉTAPE 8 : Calcul segments pour chaque scénario

print("\n[8/9] Calcul des segments de rue pour chaque scénario...")

for scenario_id in SCENARIOS.keys():
    print(f"\n🔧 Segments pour {SCENARIOS[scenario_id]['name']}...")
    
    # Recharger les routes
    routes_file = output_files[scenario_id]['routes']
    gdf_routes = gpd.read_file(routes_file)
    
    segment_data = defaultdict(lambda: {
        'count': 0,
        'route_ids': [],
        'scenario': scenario_id
    })
    
    for idx, route in tqdm(gdf_routes.iterrows(), total=len(gdf_routes), desc="Agrégation"):
        line = route["geometry"]
        trip_count = route["trip_count"]
        route_id = route["route_id"]
        
        for i in range(len(line.coords) - 1):
            segment = (line.coords[i], line.coords[i + 1])
            segment_data[segment]['count'] += trip_count
            segment_data[segment]['route_ids'].append(route_id)
    
    print(f"{len(segment_data)} segments uniques")
    
    # Créer GeoDataFrame segments avec IDs
    segments = []
    for segment, data in segment_data.items():
        start, end = segment
        line = LineString([start, end])
        segments.append({
            "segment_id": str(uuid.uuid4()),  # ID unique du segment
            "geometry": line,
            "passage_count": data['count'],
            "route_count": len(data['route_ids']),
            "scenario": scenario_id,
            "scenario_name": SCENARIOS[scenario_id]['name'],
            "source_route_ids": data['route_ids'][:100]  # Limiter pour éviter fichiers trop gros
        })
    
    gdf_segments = gpd.GeoDataFrame(segments, crs="EPSG:4326")
    segments_file = output_files[scenario_id]['segments']
    gdf_segments.to_file(segments_file, driver="GeoJSON")
    print(f"Fichier segments sauvegardé : {segments_file}")
    
    del gdf_routes, gdf_segments, segments

#%%
# STATISTIQUES FINALES : afficher dans la console Spyder

print("\n" + "="*70)
print("STATISTIQUES FINALES PAR SCÉNARIO")
print("="*70)

for scenario_id, config in SCENARIOS.items():
    print(f"\n🚴 {config['name']}:")
    
    routes_file = output_files[scenario_id]['routes']
    segments_file = output_files[scenario_id]['segments']
    
    gdf_routes = gpd.read_file(routes_file)
    gdf_segments = gpd.read_file(segments_file)
    
    print(f"   Itinéraires calculés    : {len(gdf_routes):,}")
    print(f"   Trajets totaux          : {gdf_routes['trip_count'].sum():,}")
    print(f"   Segments uniques        : {len(gdf_segments):,}")
    print(f"   Distance moy. itinéraire: {gdf_routes['route_length_meters'].mean():.0f}m")
    
    if len(gdf_segments) > 0:
        print(f"   Passage max/segment     : {gdf_segments['passage_count'].max():,}")

print("\n" + "="*70)
print_memory_usage()

print("\n TERMINÉ ! Fichiers générés :")
for scenario_id, config in SCENARIOS.items():
    print(f"\n{config['name']}:")
    print(f"  • {output_files[scenario_id]['routes']}")
    print(f"  • {output_files[scenario_id]['segments']}")
