# -*- coding: utf-8 -*-
"""
Created on Thu Dec  4 16:25:48 2025

@author: Marius R-D
FONCTIONNEL V2.2 POUR LE TRAITEMENT DES RIDES, optimisé pour libérer de la mémoire de stockage
Latence: ~2mn30
Lecture des bike_id depuis CSV, sortie en JSON.
Exclut les rides "ongoing".
Applique les arrondis demandés et supprime "created_at".
Gère les valeurs None pour les champs numériques.
"""
import requests
import json
import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Optional
import time
from datetime import datetime

# Constantes
BIKE_IDS_CSV = "bike_ids.csv"
STATS_FILE = "bike_stats.json"
MAX_WORKERS = 60  # Ajuste selon la tolérance du serveur
REQUEST_TIMEOUT = 30
MAX_RETRIES = 2

def load_bike_ids() -> List[str]:
    """Charge la liste des bike_id depuis un fichier CSV."""
    if not os.path.exists(BIKE_IDS_CSV):
        raise FileNotFoundError(f"Fichier {BIKE_IDS_CSV} introuvable.")
    with open(BIKE_IDS_CSV, "r") as f:
        reader = csv.DictReader(f)
        return [row["bike_id"] for row in reader]

def load_existing_ride_ids() -> Set[str]:
    """Charge les ride_id déjà enregistrés."""
    if not os.path.exists(STATS_FILE):
        return set()
    with open(STATS_FILE, "r") as f:
        data = json.load(f)
        return {ride["id"] for bike in data for ride in bike["stats"]}

def round_ride_data(ride: Dict) -> Dict:
    """Applique les arrondis et supprime created_at. Gère les valeurs None."""
    if "start_time" in ride and ride["start_time"]:
        dt = datetime.fromisoformat(ride["start_time"].replace("Z", "+00:00"))
        ride["start_time"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if "end_time" in ride and ride["end_time"]:
        dt = datetime.fromisoformat(ride["end_time"].replace("Z", "+00:00"))
        ride["end_time"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if "duration_minutes" in ride and ride["duration_minutes"] is not None:
        ride["duration_minutes"] = round(float(ride["duration_minutes"]), 2)
    if "distance_meters" in ride and ride["distance_meters"] is not None:
        ride["distance_meters"] = round(float(ride["distance_meters"]), 1)
    if "average_speed_kmh" in ride and ride["average_speed_kmh"] is not None:
        ride["average_speed_kmh"] = round(float(ride["average_speed_kmh"]), 3)
    ride.pop("created_at", None)
    return ride

def get_bike_stats(bike_id: str) -> Optional[List[Dict]]:
    """Récupère et nettoie les stats pour un vélo."""
    url = f"https://tdqr.ovh/api/rides/bike/{bike_id}"
    for _ in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                rides = response.json()["data"]
                return [round_ride_data(r) for r in rides]
            elif response.status_code == 429:
                time.sleep(1)  # Rate limit, attendre
            else:
                return None
        except Exception as e:
            print(f"Erreur pour {bike_id}: {e}")
            time.sleep(0.5)
    return None

def main():
    try:
        # Chargement des données existantes
        bike_ids = load_bike_ids()
        existing_ride_ids = load_existing_ride_ids()
        print(f"Vélos à traiter: {len(bike_ids)}")

        # Récupération des nouvelles rides
        new_bike_stats = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(get_bike_stats, bike_id): bike_id for bike_id in bike_ids}
            for future in as_completed(futures):
                bike_id = futures[future]
                stat = future.result()
                if stat:
                    # Filtre: on exclut les rides "ongoing" et celles déjà enregistrées
                    new_rides = [
                        ride for ride in stat
                        if ride["id"] not in existing_ride_ids
                        and ride.get("status") != "ongoing"
                    ]
                    if new_rides:
                        new_bike_stats.append({"bike_id": bike_id, "stats": new_rides})

        # Mise à jour du fichier JSON
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r") as f:
                data = json.load(f)
            # Fusion des données
            bike_id_to_stats = {bike["bike_id"]: bike["stats"] for bike in data}
            for entry in new_bike_stats:
                bike_id = entry["bike_id"]
                if bike_id in bike_id_to_stats:
                    bike_id_to_stats[bike_id].extend(entry["stats"])
                else:
                    bike_id_to_stats[bike_id] = entry["stats"]
            data = [{"bike_id": bike_id, "stats": stats} for bike_id, stats in bike_id_to_stats.items()]
        else:
            data = new_bike_stats

        # Sauvegarde
        with open(STATS_FILE, "w") as f:
            json.dump(data, f, indent=2)

        print(f"Nouveaux trajets ajoutés: {sum(len(bike['stats']) for bike in new_bike_stats)}")
        print(f"Fichier sauvegardé: {STATS_FILE}")

    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    start = time.time()
    main()
    print(f"Temps d'exécution: {time.time() - start:.2f} secondes")

