# -*- coding: utf-8 -*-
import os
import requests
import boto3
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration du logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Variables d'environnement (à configurer dans Lambda)
STATIONS_URL = os.getenv("STATIONS_URL", "https://tdqr.ovh/api/stations")
BIKES_URL_TEMPLATE = os.getenv("BIKES_URL_TEMPLATE", "https://tdqr.ovh/api/bikes/station/{station_id}")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "VelibBikeIds")
USER_AGENT_STRING = os.getenv("USER_AGENT_STRING", "VelibCollector_Academic_Project (https://github.com/maxrsslr/MCNDU_Butroussler)")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 40))  

# Vérifier que les variables d'environnement sont définies
logger.info(f"STATIONS_URL: {STATIONS_URL}")
logger.info(f"BIKES_URL_TEMPLATE: {BIKES_URL_TEMPLATE}")
logger.info(f"DYNAMODB_TABLE: {DYNAMODB_TABLE}")
logger.info(f"USER_AGENT_STRING: {USER_AGENT_STRING}")
logger.info(f"MAX_WORKERS: {MAX_WORKERS}")

# Initialiser DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE)

def get_stations():
    try:
        logger.info("Récupération des stations...")
        headers = {"User-Agent": USER_AGENT_STRING}
        with requests.Session() as session:
            response = session.get(STATIONS_URL, headers=headers, timeout=50)
            logger.info(f"Statut de la réponse : {response.status_code}")
            if response.status_code == 200:
                return response.json()["data"]
            else:
                raise Exception(f"Erreur lors de la récupération des stations : {response.status_code}")
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stations : {e}")
        return []

def get_bikes_for_station(session, station_id):
    url = BIKES_URL_TEMPLATE.format(station_id=station_id)
    try:
        headers = {"User-Agent": USER_AGENT_STRING}
        response = session.get(url, headers=headers, timeout=50)
        if response.status_code == 200:
            return response.json()["data"]
        else:
            logger.warning(f"Statut {response.status_code} pour la station {station_id}")
            return []
    except Exception as e:
        logger.warning(f"Erreur pour la station {station_id} : {e}")
        return []

def save_bike_ids_to_dynamodb(bike_ids):
    try:
        with table.batch_writer() as batch:
            for bike_id in bike_ids:
                batch.put_item(
                    Item={
                        'bike_id': str(bike_id),
                        'last_seen': datetime.now().isoformat()
                    }
                )
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde dans DynamoDB : {e}")
        
def count_dynamodb_items():
    try:
        response = table.scan(Select='COUNT')
        item_count = response['Count']
        logger.info(f"Nombre total d'objets dans DynamoDB : {item_count}")
        return item_count
    except Exception as e:
        logger.error(f"Erreur lors du comptage des objets : {e}")
        return 0

def lambda_handler(event, context):
    try:
        # Récupérer les stations
        stations = get_stations()
        logger.info(f"Nombre de stations récupérées : {len(stations)}")

        # Utiliser une session HTTP persistante
        with requests.Session() as session:
            new_bike_ids = set()

            # Récupérer les vélos en parallèle
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(get_bikes_for_station, session, station["id"]): station["id"] for station in stations}
                for future in as_completed(futures):
                    station_id = futures[future]
                    try:
                        bikes = future.result()
                        bike_ids = [bike["id"] for bike in bikes]
                        new_bike_ids.update(bike_ids)
                    except Exception as e:
                        logger.error(f"Erreur lors du traitement de la station {station_id} : {e}")

            logger.info(f"Nombre total de vélos uniques : {len(new_bike_ids)}")
            save_bike_ids_to_dynamodb(new_bike_ids)
            item_count = count_dynamodb_items()  # Compter les objets après sauvegarde
            logger.info(f"Nombre total d'objets dans DynamoDB après sauvegarde : {item_count}")
            logger.info("Fin de l'exécution de la fonction Lambda.")
            return {
                'statusCode': 200,
                'body': f"Collecte terminée. {len(new_bike_ids)} vélos traités. Total dans DB : {item_count}."
            }
    except Exception as e:
        logger.error(f"Erreur principale : {e}")
        return {
            'statusCode': 500,
            'body': f"Erreur lors de l'exécution : {str(e)}"
        }
