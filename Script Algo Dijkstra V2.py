#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Dec 29 20:49:21 2025

@author: titou
"""

import json
import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString
from collections import defaultdict

#je charge les fichiers
base_dir = "/Users/titou/Documents/Tradd 22/MCDNU/Fichiers"
stations_file = f"{base_dir}/velib-emplacement-des-stations.json"
trajets_file = f"{base_dir}/bike_stats_allege.json"
output_routes = f"{base_dir}/velib_routes.geojson"
output_segments = f"{base_dir}/velib_segments.geojson"

#je charge les données
def load_and_harmonize_data(stations_file, trajets_file):
    with open(stations_file, 'r', encoding='utf-8') as f:
        stations_data = json.load(f)

    with open(trajets_file, 'r', encoding='utf-8') as f:
        trajets_data = json.load(f)

    # Harmoniser les identifiants des stations
    for bike in trajets_data:
        for stat in bike['stats']:
            if stat['start_station_id']:
                stat['start_station_id'] = stat['start_station_id'].replace('station_', '')
            if stat['end_station_id']:
                stat['end_station_id'] = stat['end_station_id'].replace('station_', '')

    return stations_data, trajets_data

stations_data, trajets_data = load_and_harmonize_data(stations_file, trajets_file)

#%%
# 3. Extraire les coordonnées des stations
stations_coords = {}
for s in stations_data:
    code = s.get("stationcode")
    coords = s.get("coordonnees_geo", {})
    lon = coords.get("lon")
    lat = coords.get("lat")
    if code and lon is not None and lat is not None:
        stations_coords[str(code)] = (lon, lat)

print(f"{len(stations_coords)} stations chargées.")

#%%
# 4. Télécharger le graphe routier pour la zone demandée
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

print("Téléchargement du graphe OSM pour la zone demandée...")
G = ox.graph_from_place(place, network_type="bike")
print(f"Graphe téléchargé : {len(G.nodes)} nœuds - {len(G.edges)} arêtes")

#%%
# 5. Calculer les itinéraires entre toutes les stations
routes = []
for start_code, start_coords in stations_coords.items():
    for end_code, end_coords in stations_coords.items():
        if start_code == end_code:
            continue

        try:
            orig_node = ox.distance.nearest_nodes(G, start_coords[0], start_coords[1])
            dest_node = ox.distance.nearest_nodes(G, end_coords[0], end_coords[1])
            path = nx.shortest_path(G, orig_node, dest_node, weight="length")

            points = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in path]
            line = LineString(points)

            routes.append({
                "geometry": line,
                "start_station": start_code,
                "end_station": end_code,
                "length": nx.shortest_path_length(G, orig_node, dest_node, weight="length")
            })

        except Exception as e:
            print(f"Erreur entre {start_code} et {end_code} : {e}")
            continue

print(f"{len(routes)} itinéraires calculés.")

#%%
#Etape 5 bis : pondération des pistes cyclables pour les favorisers

routes = []

# On crée d'abord un poids personnalisé pour chaque tronçon
for u, v, k, data in G.edges(keys=True, data=True):
    length = data.get("length", 1)  # longueur du tronçon en mètres

    # pondération selon la piste cyclable
    cycleway = data.get("cycleway", "")
    if cycleway in ["track", "lane"]:   # piste dédiée
        factor = 0.5                    # favorisée
    elif cycleway in [""]:  # pas de piste
        factor = 2.0                     # pénalisée
    else:
        factor = 1.0                     # neutre

    data["bike_weight"] = length * factor


print("Poids vélo personnalisés appliqués au graphe.")

# Boucle sur toutes les paires de stations
for start_code, start_coords in stations_coords.items():
    for end_code, end_coords in stations_coords.items():
        if start_code == end_code:
            continue

        try:
            # trouver le nœud le plus proche de la station
            orig_node = ox.distance.nearest_nodes(G, start_coords[0], start_coords[1])
            dest_node = ox.distance.nearest_nodes(G, end_coords[0], end_coords[1])

            # calcul du chemin pondéré selon bike_weight
            path = nx.shortest_path(G, orig_node, dest_node, weight="bike_weight")

            # créer un LineString pour visualisation
            points = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in path]
            line = LineString(points)

            # ajouter à la liste des routes
            routes.append({
                "geometry": line,
                "start_station": start_code,
                "end_station": end_code,
                "length": nx.shortest_path_length(G, orig_node, dest_node, weight="bike_weight")
            })

        except Exception as e:
            print(f"Erreur entre {start_code} et {end_code} : {e}")
            continue

print(f"{len(routes)} itinéraires calculés avec pondération vélo.")

#%%
# 6. Créer un GeoDataFrame pour les itinéraires
gdf_routes = gpd.GeoDataFrame(routes, crs="EPSG:4326")
gdf_routes.to_file(output_routes, driver="GeoJSON")
print(f"Fichier des itinéraires écrit : {output_routes}")

#%%
# 7. Associer les trajets réels aux itinéraires
all_rides = []
for bike in trajets_data:
    bike_id = bike.get("bike_id")
    for stat in bike.get("stats", []):
        if stat.get("status") != "completed":
            continue
        if not stat.get("end_station_id"):
            continue

        all_rides.append({
            "bike_id": bike_id,
            "ride_id": stat.get("id"),
            "start_station_id": stat.get("start_station_id"),
            "end_station_id": stat.get("end_station_id"),
            "start_time": stat.get("start_time"),
            "end_time": stat.get("end_time"),
        })

print(f"{len(all_rides)} trajets complétés trouvés.")

# 8. Créer un GeoDataFrame pour les trajets
gdf_rides = gpd.GeoDataFrame(all_rides)
gdf_rides["geometry"] = gdf_rides.apply(
    lambda row: LineString([
        stations_coords[row["start_station_id"]],
        stations_coords[row["end_station_id"]]
    ]) if row["start_station_id"] in stations_coords and row["end_station_id"] in stations_coords else None,
    axis=1
)
gdf_rides = gdf_rides.dropna(subset=["geometry"])
gdf_rides.set_crs("EPSG:4326", inplace=True)
gdf_rides.to_file(f"{base_dir}/velib_trajets.geojson", driver="GeoJSON")
print(f"Fichier des trajets écrits : {base_dir}/velib_trajets.geojson")

#%%
# 9. Segmenter et compter les passages
segment_counts = defaultdict(int)
for route in routes:
    line = route["geometry"]
    for i in range(len(line.coords) - 1):
        segment = (line.coords[i], line.coords[i + 1])
        segment_counts[segment] += 1

# 10. Créer un GeoDataFrame pour les segments
segments = []
for segment, count in segment_counts.items():
    start, end = segment
    line = LineString([start, end])
    segments.append({
        "geometry": line,
        "count": count
    })

gdf_segments = gpd.GeoDataFrame(segments, crs="EPSG:4326")
gdf_segments.to_file(output_segments, driver="GeoJSON")
print(f"Fichier des segments écrit : {output_segments}")
