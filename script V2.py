# -*- coding: utf-8 -*-
"""
Created on Tue Dec  9 20:20:03 2025

@author: titou
"""
#ATTENTION BESOIN DE FAIRE -pip install scikit-learn POUR FAIRE FONCTIONNER CE SCRIPT SINON IL NE SAIT PAS COMMENT AFFICHIER LES ITININERARIRES
import json
import random
from pathlib import Path

import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString


stations_file = Path(
    r"C:\Users\titou\OneDrive\Documents\ENPC\Tradd 1\Mobilités connectées\velib-disponibilite-en-temps-reel.json"
)


trips_file = Path(
    r"C:\Users\titou\OneDrive\Documents\ENPC\Tradd 1\Mobilités connectées\bike_stats_allege.json"
)

output_file = Path(
    r"C:\Users\titou\OneDrive\Documents\ENPC\Tradd 1\Mobilités connectées\velib_itineraires_10trajets.gpkg"
)

#%%

with stations_file.open(encoding="utf-8") as f:
    stations_data = json.load(f)

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
with trips_file.open(encoding="utf-8") as f:
    trips_data = json.load(f)

all_rides = []
for bike in trips_data:
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
#%%

n = min(10, len(all_rides))
rides = random.sample(all_rides, n)
print(f"{len(rides)} trajets sélectionnés au hasard.")
#%%


used_codes = set()

for r in rides:
    start_code = r["start_station_id"].replace("station_", "") if r["start_station_id"] else None
    end_code   = r["end_station_id"].replace("station_", "") if r["end_station_id"] else None

    if start_code in stations_coords:
        used_codes.add(start_code)
    if end_code in stations_coords:
        used_codes.add(end_code)

print("Stations utilisées dans les 10 trajets :", len(used_codes))

if not used_codes:
    raise ValueError("Aucune station trouvée pour les trajets sélectionnés.")

lats = []
lons = []
for code in used_codes:
    lon, lat = stations_coords[code]
    lats.append(lat)
    lons.append(lon)

# petite marge autour
margin = 0.01  # ≈ 1 km

north = max(lats) + margin
south = min(lats) - margin
east  = max(lons) + margin
west  = min(lons) - margin

# pour info
height_km = (north - south) * 111
width_km  = (east - west) * 73
print(f"BBOX trajets (approx) : {height_km:.1f} km x {width_km:.1f} km")
print("north:", north, "south:", south, "east:", east, "west:", west)

print("Téléchargement du graphe OSM (autour des 10 trajets)...")
print("Téléchargement du graphe OSM (Petite Couronne)...")

place = [
    "Paris, France",
    "Hauts-de-Seine, France",
    "Seine-Saint-Denis, France",
    "Val-de-Marne, France"
]

G = ox.graph_from_place(place, network_type="all")

print("Graphe téléchargé :", len(G.nodes), "nœuds -", len(G.edges), "arêtes")
print("Graphe téléchargé :", len(G.nodes), "nœuds -", len(G.edges), "arêtes")

#%%

geoms = []
attrs = []

for r in rides:
    start_code = r["start_station_id"].replace("station_", "") if r["start_station_id"] else None
    end_code   = r["end_station_id"].replace("station_", "") if r["end_station_id"] else None

    if start_code not in stations_coords or end_code not in stations_coords:
        print(f"Station manquante pour le trajet {r['ride_id']} → ignoré")
        continue

    start_lon, start_lat = stations_coords[start_code]
    end_lon, end_lat     = stations_coords[end_code]

    try:
       
        orig_node = ox.distance.nearest_nodes(G, start_lon, start_lat)
        dest_node = ox.distance.nearest_nodes(G, end_lon, end_lat)

        
        path = nx.shortest_path(G, orig_node, dest_node, weight="length")

        
        points = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in path]
        line = LineString(points)

        geoms.append(line)
        attrs.append({
            "ride_id": r["ride_id"],
            "bike_id": r["bike_id"],
            "start_station": start_code,
            "end_station": end_code,
            "start_time": r["start_time"],
            "end_time": r["end_time"],
        })

    except Exception as e:
        print(f"Erreur sur le trajet {r['ride_id']} : {e}")
        continue

print(f"{len(geoms)} itinéraires calculés.")

if geoms:
    gdf = gpd.GeoDataFrame(attrs, geometry=geoms, crs="EPSG:4326")
    gdf.to_file(output_file, layer="itineraires_velib", driver="GPKG")
    print(f"Fichier écrit : {output_file}")
else:
    print("Aucun itinéraire à exporter.")

