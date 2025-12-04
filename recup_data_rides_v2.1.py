# -*- coding: utf-8 -*-
"""
Created on Thu Dec  4 16:25:48 2025

@author: Marius R-D
FONCTIONNEL V2.1 POUR LE TRAITEMENT DES RIDES, excluant les ongoing rides
Latence: ~2mn30
Lecture des bike_id depuis CSV, sortie en JSON.

"""
import requests
import json
import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Optional
import time

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

def get_bike_stats(bike_id: str) -> Optional[List[Dict]]:
    """Récupère les stats pour un vélo, avec gestion des erreurs et réessais."""
    url = f"https://tdqr.ovh/api/rides/bike/{bike_id}"
    for _ in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.json()["data"]
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