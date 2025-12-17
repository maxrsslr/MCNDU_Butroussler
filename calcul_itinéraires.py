# -*- coding: utf-8 -*-
"""
Created on Wed Dec 17 14:46:20 2025

@author: titou
"""

import json
from pathlib import Path

import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString


stations_file = Path(r"C:\Users\titou\OneDrive\Documents\ENPC\Tradd 1\Mobilités connectées\velib-disponibilite-en-temps-reel.json")
trips_file    = Path(r"C:\Users\titou\OneDrive\Documents\ENPC\Tradd 1\Mobilités connectées\bike_stats_allege.json")
output_file   = Path(r"C:\Users\titou\OneDrive\Documents\ENPC\Tradd 1\Mobilités connectées\velib_itineraires_TOUS.gpkg")

#%%
# ------------------------------------------------------------
# 1) Stations: stationcode -> (lon, lat)
# ------------------------------------------------------------
with stations_file.open(encoding="utf-8") as f:
    stations_data = json.load(f)

stations_coords = {}
for s in stations_data:
    code = s.get("stationcode")
    coords = s.get("coordonnees_geo") or {}
    lon = coords.get("lon")
    lat = coords.get("lat")
    if code and lon is not None and lat is not None:
        stations_coords[str(code)] = (float(lon), float(lat))

print(f"{len(stations_coords)} stations chargées.")

#%%
# ------------------------------------------------------------
# 2) Trajets: on garde tout
# ------------------------------------------------------------
with trips_file.open(encoding="utf-8") as f:
    trips_data = json.load(f)

rides = []
for bike in trips_data:
    bike_id = bike.get("bike_id")
    for stat in bike.get("stats", []):
        if stat.get("status") != "completed":
            continue
        if not stat.get("start_station_id") or not stat.get("end_station_id"):
            continue

        rides.append({
            "ride_id": stat.get("id"),
            "bike_id": bike_id,
            "start_station_id": stat.get("start_station_id"),
            "end_station_id": stat.get("end_station_id"),
            "start_time": stat.get("start_time"),
            "end_time": stat.get("end_time"),
        })

print(f"{len(rides)} trajets sélectionnés (TOUS, completed).")

#%%
# ------------------------------------------------------------
# 3) Graphe OSM en mode vélo
# ------------------------------------------------------------
place = [
    "Paris, France",
    "Hauts-de-Seine, France",
    "Seine-Saint-Denis, France",
    "Val-de-Marne, France",
    "Argenteuil, Val-d'Oise, France"
]

print("Téléchargement du graphe OSM en mode vélo...")
G = ox.graph_from_place(place, network_type="bike")
print("Graphe :", len(G.nodes), "nœuds -", len(G.edges), "arêtes")

#%%
# ------------------------------------------------------------
# 4) Itinéraires + densité (comptage par edge OSM)
# ------------------------------------------------------------
routes_geom = []
routes_attr = []

edge_counts = {}  # (u,v,key) -> count

for r in rides:
    start_code = r["start_station_id"].replace("station_", "")
    end_code   = r["end_station_id"].replace("station_", "")

    if start_code not in stations_coords or end_code not in stations_coords:
        continue

    start_lon, start_lat = stations_coords[start_code]
    end_lon, end_lat     = stations_coords[end_code]

    try:
        orig = ox.distance.nearest_nodes(G, start_lon, start_lat)
        dest = ox.distance.nearest_nodes(G, end_lon, end_lat)

        # plus court chemin (distance) sur réseau vélo
        path = nx.shortest_path(G, orig, dest, weight="length")

        # géométrie (ligne) du trajet
        pts = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in path]
        line = LineString(pts)

        # dates/heures (UTC)
        dt_start_utc = pd.to_datetime(r["start_time"], errors="coerce", utc=True)
        dt_end_utc   = pd.to_datetime(r["end_time"], errors="coerce", utc=True)

        # optionnel: heure locale Paris (pratique pour analyses horaires)
        dt_start_paris = dt_start_utc.tz_convert("Europe/Paris") if pd.notnull(dt_start_utc) else pd.NaT
        dt_end_paris   = dt_end_utc.tz_convert("Europe/Paris") if pd.notnull(dt_end_utc) else pd.NaT

        routes_geom.append(line)
        routes_attr.append({
            "ride_id": r["ride_id"],
            "bike_id": r["bike_id"],
            "start_station": start_code,
            "end_station": end_code,

            "start_time_raw": r["start_time"],
            "end_time_raw": r["end_time"],

            "departure_utc": dt_start_utc,
            "arrival_utc": dt_end_utc,

            "departure_paris": dt_start_paris,
            "arrival_paris": dt_end_paris,

            "departure_hour": int(dt_start_paris.hour) if pd.notnull(dt_start_paris) else None,
            "arrival_hour": int(dt_end_paris.hour) if pd.notnull(dt_end_paris) else None,
        })

        # densité: compter chaque edge parcouru
        for u, v in zip(path[:-1], path[1:]):
            data = G.get_edge_data(u, v)
            if not data:
                continue
            # MultiDiGraph : choisir l'edge le plus court entre u et v
            best_key = min(data, key=lambda k: data[k].get("length", float("inf")))
            edge_id = (u, v, best_key)
            edge_counts[edge_id] = edge_counts.get(edge_id, 0) + 1

    except Exception as e:
        # tu peux imprimer e si tu veux debug
        continue

print(f"{len(routes_geom)} itinéraires calculés.")

#%%
# ------------------------------------------------------------
# 5) Export GeoPackage : itinéraires + densité
# ------------------------------------------------------------
if not routes_geom:
    raise RuntimeError("Aucun itinéraire n'a été calculé.")

gdf_routes = gpd.GeoDataFrame(routes_attr, geometry=routes_geom, crs="EPSG:4326")
gdf_routes.to_file(output_file, layer="itineraires_velib", driver="GPKG")
print("Layer écrit: itineraires_velib")

# reconstruire un GDF d'edges avec compteur
rows = []
for (u, v, k), cnt in edge_counts.items():
    ed = G.get_edge_data(u, v, k)
    if not ed:
        continue

    geom = ed.get("geometry")
    if geom is None:
        geom = LineString([(G.nodes[u]["x"], G.nodes[u]["y"]),
                           (G.nodes[v]["x"], G.nodes[v]["y"])])

    rows.append({
        "u": u,
        "v": v,
        "key": k,
        "count": cnt,
        "name": ed.get("name"),
        "highway": ed.get("highway"),
        "length_m": ed.get("length"),
        "geometry": geom
    })

gdf_density = gpd.GeoDataFrame(rows, crs="EPSG:4326")
gdf_density.to_file(output_file, layer="densite_passages", driver="GPKG")
print("Layer écrit: densite_passages")

print(f"✅ GeoPackage final : {output_file}")
