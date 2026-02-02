# -*- coding: utf-8 -*-
"""
AWS Lambda function pour collecter les trajets des vélos Vélib'.
Lecture des bike_id depuis un fichier CSV stocké dans S3, sauvegarde des données en JSON dans S3.
"""

# Importer packages nécessaires
import json
import os
import boto3
import requests
import csv
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Optional
import time
from datetime import datetime

# Variables d'environnement (à configurer aussi dans Lambda)
S3_BUCKET = os.environ.get('S3_BUCKET', 'data-velib')
S3_BIKE_IDS_KEY = os.environ.get('S3_BIKE_IDS_KEY', 'bikes_id_final.csv')
S3_STATS_KEY = os.environ.get('S3_STATS_KEY', 'bike_stats.json')
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', 60))
REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 30))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', 2))

# Initialiser le client S3
s3 = boto3.client('s3')

# Fonction pour charger la liste des identifiants de vélo depuis un fichier CSV stocké dans S3
def load_bike_ids() -> List[str]:
    """Charge la liste des bike_id depuis un fichier CSV stocké dans S3."""
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_BIKE_IDS_KEY)
        csv_content = response['Body'].read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        bike_ids = [row["bike_id"] for row in reader]
        print(f"Vélos à traiter: {len(bike_ids)}")
        return bike_ids
    except Exception as e:
        print(f"Erreur lors de la récupération des bike_id depuis S3: {e}")
        raise
# Fonction pour charger la liste des trajets déjà enregistrés dans S3. Cela résulte de l'architecture des données où les derniers 1 à 10 trajets sont présents pour chaque bike_id lors d'une requête
def load_existing_ride_ids() -> Set[str]:
    """Charge les ride_id déjà enregistrés depuis un fichier JSON stocké dans S3."""
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_STATS_KEY)
        json_content = response['Body'].read().decode('utf-8')
        data = json.loads(json_content)
        return {ride["id"] for bike in data for ride in bike["stats"]}
    except s3.exceptions.NoSuchKey:
        return set()
    except Exception as e:
        print(f"Erreur lors de la récupération des trajets existants depuis S3: {e}")
        return set()
    
# Fonction pour arrondir les nombres et supprimer les choses inutiles afin d'optimiser le stockage. 
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

# Fonction qui extraie et nettoie les stats pour un identifiant de vélo
def get_bike_stats(bike_id: str) -> Optional[List[Dict]]:
    """Récupère et nettoie les stats pour un vélo."""
    url = f"https://tdqr.ovh/api/rides/bike/{bike_id}"
  # définition d'un user agent unique
    headers = {
        "User-Agent": "VelibCollector_Academic_Project (https://github.com/maxrsslr/MCNDU_Butroussler)"
    }
    for _ in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                rides = response.json()["data"]
                return [round_ride_data(r) for r in rides]
            elif response.status_code == 429:
                time.sleep(1)  # Rate limit, attendre
            else:
                print(f"Erreur {response.status_code} pour {bike_id}: {response.text}")
                return None
        except Exception as e:
            print(f"Erreur pour {bike_id}: {e}")
            time.sleep(0.5)
    return None

# Fonction qui permet de sauvegarder les données dans un fichier JSON dans S3
def save_stats_to_s3(data: List[Dict]):
    """Sauvegarde les données en JSON dans S3."""
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=S3_STATS_KEY,
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
        print(f"Fichier sauvegardé dans S3: {S3_STATS_KEY}")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde dans S3: {e}")
        raise

# Fonction pour tout exécuter
def lambda_handler(event, context):
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

        # Mise à jour des données
        if new_bike_stats:
            try:
                response = s3.get_object(Bucket=S3_BUCKET, Key=S3_STATS_KEY)
                json_content = response['Body'].read().decode('utf-8')
                data = json.loads(json_content)
            except s3.exceptions.NoSuchKey:
                data = []

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

        # Sauvegarde dans S3
        save_stats_to_s3(data)

        print(f"Nouveaux trajets ajoutés: {sum(len(bike['stats']) for bike in new_bike_stats)}")
        return {
            'statusCode': 200,
            'body': json.dumps('Collecte terminée avec succès!')
        }
    except Exception as e:
        print(f"Erreur: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Erreur: {e}')
        }
