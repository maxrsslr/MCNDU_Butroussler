# -*- coding: utf-8 -*-
"""
Created on Tue Nov 25 17:49:26 2025
SCRIPT RECUP VELO SNAPSHOT.3 (objectif de réduire la latence de 9 mn)
@author: Marius R-D
"""

# -*- coding: utf-8 -*-

import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

def get_stations():
    url = "https://tdqr.ovh/api/stations"
    with requests.Session() as session:
        response = session.get(url)
        if response.status_code == 200:
            return response.json()["data"]
        else:
            raise Exception(f"Erreur lors de la récupération des stations : {response.status_code}")

def get_bikes_for_station(session, station_id):
    url = f"https://tdqr.ovh/api/bikes/station/{station_id}"
    try:
        response = session.get(url, timeout=50)
        if response.status_code == 200:
            return response.json()["data"]
        else:
            return []
    except Exception as e:
        print(f"Erreur pour la station {station_id} : {e}")
        return []

def main():
    try:
        # Lire les bike_id déjà enregistrés dans bike_ids.csv
        existing_bike_ids = set()
        if os.path.exists("bike_ids.csv"):
            existing_df = pd.read_csv("bike_ids.csv")
            existing_bike_ids = set(existing_df["bike_id"])

        # Récupérer les stations
        stations = get_stations()
        print(f"Nombre de stations récupérées : {len(stations)}")

        # Utiliser une session HTTP persistante
        with requests.Session() as session:
            new_bike_ids = set()
            new_bike_count = 0

            # Paralléliser la récupération des vélos pour toutes les stations
            with ThreadPoolExecutor(max_workers=70) as executor:
                futures = {executor.submit(get_bikes_for_station, session, station["id"]): station["id"] for station in stations}

                for future in as_completed(futures):
                    station_id = futures[future]
                    try:
                        bikes = future.result()
                        bike_ids = [bike["id"] for bike in bikes]
                        for bike_id in bike_ids:
                            if bike_id not in existing_bike_ids and bike_id not in new_bike_ids:
                                new_bike_ids.add(bike_id)
                                new_bike_count += 1
                    except Exception as e:
                        print(f"Erreur lors du traitement de la station {station_id} : {e}")

        # Créer un DataFrame avec les nouveaux bike_id
        df_new = pd.DataFrame({"bike_id": list(new_bike_ids)})

        # Ajouter les nouveaux bike_id au DataFrame existant (s'il existe)
        if os.path.exists("bike_ids.csv"):
            df = pd.concat([existing_df, df_new], ignore_index=True)
        else:
            df = df_new

        # Supprimer les doublons éventuels
        df = df.drop_duplicates(subset=["bike_id"])

        print(f"Nombre total de vélos enregistrés : {len(df)}")
        print(f"Nombre de nouveaux vélos ajoutés : {new_bike_count}")
        df.to_csv("bike_ids.csv", index=False)
        print("Les identifiants des vélos ont été sauvegardés dans bike_ids.csv.")

    except Exception as e:
        print(f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    main()
