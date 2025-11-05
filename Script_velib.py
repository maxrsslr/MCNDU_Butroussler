import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import time

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
        stations = get_stations()
        print(f"Nombre de stations récupérées : {len(stations)}")

        bike_stats_list = []

        with ThreadPoolExecutor(max_workers=70) as executor:  # Réduire le nombre de threads
            for station in stations:
                station_id = station["id"]
                bikes = get_bikes_for_station(station_id)
                bike_ids = [bike["id"] for bike in bikes]

                # Récupérer les statistiques en parallèle
                stats = list(executor.map(get_bike_stats, bike_ids))

                for bike_id, stat in zip(bike_ids, stats):
                    if stat is not None:
                        bike_stats_list.append({
                            "station_id": station_id,
                            "bike_id": bike_id,
                            "stats": stat
                        })

                time.sleep(0.1)  # Pause pour éviter de surcharger le serveur

        df = pd.DataFrame(bike_stats_list)
        print(f"Nombre total de vélos traités : {len(df)}")
        df.to_csv("bike_stats.csv", index=False)
        print("Les statistiques ont été sauvegardées dans bike_stats.csv.")

    except Exception as e:
        print(f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    main()
