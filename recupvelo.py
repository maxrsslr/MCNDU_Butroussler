# -*- coding: utf-8 -*-
"""
Created on Fri Nov 21 11:16:36 2025
@author: Marius R-D
"""
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import time
import os

def get_stations():
    url = "https://tdqr.ovh/api/stations"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()["data"]
    else:
        raise Exception(f"Erreur lors de la récupération des stations : {response.status_code}")

def get_bikes_for_station(station_id):
    url = f"https://tdqr.ovh/api/bikes/station/{station_id}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()["data"]
        else:
            return []
    except Exception as e:
        print(f"Erreur pour la station {station_id} : {e}")
        return []

def main():
    try:
        # Lire le fichier CSV existant pour récupérer les bike_id déjà enregistrés
        existing_bike_ids = set()
        if os.path.exists("bike_ids.csv"):
            existing_df = pd.read_csv("bike_ids.csv")
            existing_bike_ids = set(existing_df["bike_id"])

        stations = get_stations()
        print(f"Nombre de stations récupérées : {len(stations)}")

        new_bike_ids = []
        new_bike_count = 0

        with ThreadPoolExecutor(max_workers=40) as executor:
            for station in stations:
                station_id = station["id"]
                bikes = get_bikes_for_station(station_id)
                bike_ids = [bike["id"] for bike in bikes]
                for bike_id in bike_ids:
                    if bike_id not in existing_bike_ids:
                        new_bike_ids.append(bike_id)
                        new_bike_count += 1
                time.sleep(0.1)  # Pause pour éviter de surcharger le serveur

        # Créer un DataFrame avec uniquement les nouveaux bike_id
        df_new = pd.DataFrame({"bike_id": new_bike_ids})

        # Ajouter les nouveaux bike_id au DataFrame existant (s'il existe)
        if os.path.exists("bike_ids.csv"):
            df = pd.concat([existing_df, df_new], ignore_index=True)
        else:
            df = df_new

        print(f"Nombre total de vélos enregistrés : {len(df)}")
        print(f"Nombre de nouveaux vélos ajoutés : {new_bike_count}")
        df.to_csv("bike_ids.csv", index=False)
        print("Les identifiants des vélos ont été sauvegardés dans bike_ids.csv.")

    except Exception as e:
        print(f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    main()
