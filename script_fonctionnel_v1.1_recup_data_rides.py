# -*- coding: utf-8 -*-
"""
Created on Mon Nov 24 22:18:15 2025
récupérer les stats de trajets; V2 fonctionnelle
@author: Marius R-D
"""
import requests
import pandas as pd
import ast
from concurrent.futures import ThreadPoolExecutor
import time
import os

def get_bike_stats(bike_id):
    url = f"https://tdqr.ovh/api/rides/bike/{bike_id}"
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            return response.json()["data"]
        else:
            return None
    except Exception as e:
        print(f"Erreur pour le vélo {bike_id} : {e}")
        return None

def main():
    try:
        # Lire les bike_id déjà enregistrés dans bike_ids.csv
        if not os.path.exists("bike_ids.csv"):
            print("Le fichier bike_ids.csv n'existe pas. Veuillez d'abord exécuter le script de collecte des identifiants.")
            return

        existing_df_bikes = pd.read_csv("bike_ids.csv")
        bike_ids = existing_df_bikes["bike_id"].tolist()
        print(f"Nombre de vélos à traiter : {len(bike_ids)}")

        # Lire les rides déjà enregistrés dans bike_stats.csv
        existing_ride_ids = set()
        if os.path.exists("bike_stats.csv"):
            existing_df_stats = pd.read_csv("bike_stats.csv")
            for _, row in existing_df_stats.iterrows():
                if row["stats"] != "[]":
                    try:
                        rides = ast.literal_eval(row["stats"])
                        for ride in rides:
                            existing_ride_ids.add(ride["id"])
                    except (ValueError, SyntaxError):
                        # Ignorer les lignes malformées
                        continue

        bike_stats_list = []
        new_ride_count = 0

        with ThreadPoolExecutor(max_workers=40) as executor:
            # Récupérer les statistiques en parallèle
            stats = list(executor.map(get_bike_stats, bike_ids))
            for bike_id, stat in zip(bike_ids, stats):
                if stat is not None and len(stat) > 0:  # Ignorer les vélos sans ride
                    # Filtrer les rides déjà enregistrés
                    new_rides = [ride for ride in stat if ride["id"] not in existing_ride_ids]
                    if new_rides:
                        new_ride_count += len(new_rides)
                        bike_stats_list.append({
                            "bike_id": bike_id,
                            "stats": new_rides
                        })

            time.sleep(0.1)  # Pause pour éviter de surcharger le serveur

        # Ajouter les nouvelles rides au DataFrame existant (s'il existe)
        if os.path.exists("bike_stats.csv"):
            df = existing_df_stats.copy()
            # Mettre à jour les rides pour chaque vélo
            for entry in bike_stats_list:
                bike_id = entry["bike_id"]
                new_rides = entry["stats"]
                # Trouver l'index du vélo dans le DataFrame existant
                idx = df[df["bike_id"] == bike_id].index
                if not idx.empty:
                    try:
                        existing_rides = ast.literal_eval(df.at[idx[0], "stats"])
                    except (ValueError, SyntaxError):
                        existing_rides = []
                    existing_rides.extend(new_rides)
                    df.at[idx[0], "stats"] = existing_rides
                else:
                    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
        else:
            df = pd.DataFrame(bike_stats_list)

        print(f"Nombre total de vélos avec statistiques : {len(df)}")
        print(f"Nombre de nouvelles rides ajoutées : {new_ride_count}")
        df.to_csv("bike_stats.csv", index=False)
        print("Les statistiques ont été sauvegardées dans bike_stats.csv.")

    except Exception as e:
        print(f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    main()
