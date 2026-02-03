# -*- coding: utf-8 -*-
"""
Created on Tue Feb  3 11:59:16 2026

@author: Maxence
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Configuration du style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")
plt.rcParams['font.size'] = 10

# ============================================================================
# CONFIGURATION - À ADAPTER
# ============================================================================
base_dir = "."  # Modifier selon votre chemin
stations_file = f"{base_dir}/velib-emplacement-des-stations.json"
trajets_file = f"{base_dir}/bike_stats_backup_02.01.2026.json"

# ============================================================================
# CHARGEMENT DES DONNÉES
# ============================================================================

# Charger les stations
with open(stations_file, 'r', encoding='utf-8') as f:
    stations_data = json.load(f)

stations_df = pd.DataFrame([
    {
        'station_code': str(s.get('stationcode')),
        'name': s.get('name'),
        'capacity': s.get('capacity'),
        'lon': s.get('coordonnees_geo', {}).get('lon'),
        'lat': s.get('coordonnees_geo', {}).get('lat')
    }
    for s in stations_data
])

print(f"\n {len(stations_df)} stations chargées")

# Créer un dictionnaire station_code -> nom pour recherche rapide
station_names = dict(zip(stations_df['station_code'], stations_df['name']))

# Charger les trajets (liste de vélos avec leurs stats)
with open(trajets_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"\n {len(data)} vélos chargés")

# Créer un DataFrame à partir de tous les trajets
rides = []
for bike in data:
    bike_id = bike.get('bike_id')
    for stat in bike.get('stats', []):
        rides.append({
            'bike_id': bike_id,
            'ride_id': stat.get('id'),
            'start_station_id': stat.get('start_station_id', '').replace('station_', ''),
            'end_station_id': stat.get('end_station_id', '').replace('station_', ''),
            'start_time': stat.get('start_time'),
            'end_time': stat.get('end_time'),
            'duration_minutes': stat.get('duration_minutes'),
            'distance_meters': stat.get('distance_meters'),
            'average_speed_kmh': stat.get('average_speed_kmh'),
            'ride_type': stat.get('ride_type'),
            'status': stat.get('status')
        })

df = pd.DataFrame(rides)
print(f" {len(df)} trajets extraits")

# Convertir les dates et ajuster au fuseau horaire de Paris
df['start_time'] = pd.to_datetime(df['start_time']).dt.tz_convert('Europe/Paris')
df['end_time'] = pd.to_datetime(df['end_time']).dt.tz_convert('Europe/Paris')

# Ajouter des colonnes dérivées
df['date'] = df['start_time'].dt.date
df['hour'] = df['start_time'].dt.hour
df['day_of_week'] = df['start_time'].dt.dayofweek
df['day_name'] = df['start_time'].dt.day_name()
df['is_weekend'] = df['day_of_week'].isin([5, 6])
df['is_boomerang'] = df['ride_type'] == 'boomerang'
df['distance_km'] = df['distance_meters'] / 1000

# Filtrer les trajets complétés valides
df = df[
    (df['status'] == 'completed') & 
    (df['duration_minutes'].notna()) &
    (df['duration_minutes'] > 0) &
    (df['duration_minutes'] < 300)
].copy()

print(f" {len(df)} trajets complétés valides")
print(f" Période: du {df['start_time'].min().date()} au {df['start_time'].max().date()}")

# Séparer trajets standard et boomerang
df_standard = df[~df['is_boomerang'] &
                 (df['distance_meters'] > 0 )].copy()
df_boomerang = df[df['is_boomerang']].copy()

print(f"\n   - Trajets standard: {len(df_standard)}")
print(f"   - Trajets boomerang: {len(df_boomerang)} ({len(df_boomerang)/len(df)*100:.1f}%)")

# ============================================================================
# STATISTIQUES GÉNÉRALES (SANS BOOMERANG)
# ============================================================================
print("\n" + "=" * 80)
print(" STATISTIQUES GÉNÉRALES (TRAJETS STANDARD UNIQUEMENT)")
print("=" * 80)

stats_summary = pd.DataFrame({
    'Métrique': ['Durée (min)', 'Distance (km)', 'Vitesse (km/h)'],
    'Moyenne': [
        df_standard['duration_minutes'].mean(),
        df_standard['distance_km'].mean(),
        df_standard[df_standard['average_speed_kmh'] > 0]['average_speed_kmh'].mean()
    ],
    'Médiane': [
        df_standard['duration_minutes'].median(),
        df_standard['distance_km'].median(),
        df_standard[df_standard['average_speed_kmh'] > 0]['average_speed_kmh'].median()
    ],
    'Min': [
        df_standard['duration_minutes'].min(),
        df_standard['distance_km'].min(),
        df_standard[df_standard['average_speed_kmh'] > 0]['average_speed_kmh'].min()
    ],
    'Max': [
        df_standard['duration_minutes'].max(),
        df_standard['distance_km'].max(),
        df_standard['average_speed_kmh'].max()
    ],
    'Écart-type': [
        df_standard['duration_minutes'].std(),
        df_standard['distance_km'].std(),
        df_standard[df_standard['average_speed_kmh'] > 0]['average_speed_kmh'].std()
    ]
})

print(stats_summary.to_string(index=False))

# ============================================================================
# ANALYSE TEMPORELLE
# ============================================================================
print("\n" + "=" * 80)
print("⏰ ANALYSE TEMPORELLE")
print("=" * 80)

# Trajets par jour de la semaine
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
trips_by_day = df_standard.groupby('day_name').size().reindex(days_order)

print("\n📅 Trajets par jour de la semaine:")
for day in days_order:
    count = trips_by_day.get(day, 0)
    jour_fr = {'Monday': 'Lundi', 'Tuesday': 'Mardi', 'Wednesday': 'Mercredi', 
               'Thursday': 'Jeudi', 'Friday': 'Vendredi', 'Saturday': 'Samedi', 
               'Sunday': 'Dimanche'}[day]
    print(f"  {jour_fr:10s}: {count:3d} trajets")

# Moyenne semaine vs weekend
weekday_avg = df_standard[~df_standard['is_weekend']].groupby('date').size().mean()
weekend_avg = df_standard[df_standard['is_weekend']].groupby('date').size().mean()
print(f"\n📊 Moyenne trajets/jour:")
print(f"  Lundi-Vendredi: {weekday_avg:.2f} trajets/jour")
print(f"  Weekend:        {weekend_avg:.2f} trajets/jour")

# ============================================================================
# ANALYSE DES STATIONS
# ============================================================================

## Top 15 stations avec le plus gd nb de départs par jour en moyenne

# Grouper par station de départ et date pour calculer le nombre de départs par jour
daily_departures = df_standard.groupby(['start_station_id', 'date']).size().reset_index(name='daily_departures')

# Calculer la moyenne des départs par jour pour chaque station
average_daily_departures = round(daily_departures.groupby('start_station_id')['daily_departures'].mean().reset_index())

# Trier les stations par ordre décroissant de la moyenne des départs par jour
average_daily_departures = average_daily_departures.sort_values(by='daily_departures', ascending=False)

# Afficher le top 10 des stations avec le plus grand nombre de départs par jour en moyenne
print("\n Top 10 stations avec le plus grand nombre de départs par jour en moyenne:")
for i, row in average_daily_departures.head(10).iterrows():
    station_name = station_names.get(row['start_station_id'], 'Inconnue')
    print(f"  {station_name[:50]:.<52} {row['daily_departures']:>5}")

## Top 10 stations avec le plus gb nombre d'arrivées par jour en moyenne

# Grouper par station d'arrivée et date pour calculer le nombre d'arrivées par jour
daily_arrivals = df_standard.groupby(['end_station_id', 'date']).size().reset_index(name='daily_arrivals')

# Calculer la moyenne des arrivées par jour pour chaque station
average_daily_arrivals = round(daily_arrivals.groupby('end_station_id')['daily_arrivals'].mean().reset_index())

# Trier les stations par ordre décroissant de la moyenne des arrivées par jour
average_daily_arrivals = average_daily_arrivals.sort_values(by='daily_arrivals', ascending=False)

# Afficher le top 15 des stations avec le plus grand nombre d'arrivées par jour en moyenne
print("\n Top 10 stations avec le plus grand nombre d'arrivées par jour en moyenne:")
for i, row in average_daily_arrivals.head(10).iterrows():
    station_name = station_names.get(row['end_station_id'], 'Inconnue')
    print(f"  {station_name[:50]:.<52} {row['daily_arrivals']:>5}")


## Top 10 stations avec le plus grand trafic par jour en moyenne
# Renommer les noms de colonnes
daily_departures.rename(columns={'start_station_id':'station_id'}, inplace = True)

daily_arrivals.rename(columns={'end_station_id':'station_id'}, inplace = True)

# Fusionner les deux DataFrames
total_traffic = pd.merge(daily_departures, daily_arrivals, on=['station_id','date'], how='outer').fillna(0)

# Additionner les comptes de départs et d'arrivées pour chaque station et chaque date
total_traffic['total_traffic'] = total_traffic['daily_departures'] + total_traffic['daily_arrivals']

# Calculer la moyenne par jour pour chaque station
average_daily_traffic = round(total_traffic.groupby('station_id')['total_traffic'].mean().reset_index())

# Trier les stations par ordre décroissant de la moyenne du trafic par jour
average_daily_traffic = average_daily_traffic.sort_values(by='total_traffic', ascending=False)

# Afficher le résultat
print("\nTop stations avec le plus grand trafic moyen par jour:")
for i, row in average_daily_traffic.head(10).iterrows():
    station_name = station_names.get(row['station_id'], 'Inconnue')
    print(f"  {station_name[:50]:.<52} {row['total_traffic']}")





# ============================================================================
# ANALYSE ORIGINE-DESTINATION
# ============================================================================
print("\n" + "=" * 80)
print("🗺️  TOP PAIRES ORIGINE-DESTINATION")
print("=" * 80)

od_matrix = df_standard.groupby(['start_station_id', 'end_station_id']).size().reset_index(name='trips')
od_matrix = od_matrix.sort_values('trips', ascending=False)

print("\n🔝 Top 15 paires O-D les plus fréquentes:")
for i, row in od_matrix.head(15).iterrows():
    start_name = station_names.get(row['start_station_id'], row['start_station_id'])[:40]
    end_name = station_names.get(row['end_station_id'], row['end_station_id'])[:40]
    print(f"{i+1:2d}. {start_name} → {end_name}")
    print(f"    ({row['trips']} trajets)")

# ============================================================================
# FONCTION D'ABRÉVIATION DES NOMS
# ============================================================================
def abbreviate_station(name, max_length=25):
    """Abrège intelligemment un nom de station"""
    if len(name) <= max_length:
        return name
    
    # Supprimer les mots communs
    common_words = ['Avenue', 'Boulevard', 'Rue', 'Place', 'Square', 'Quai', 'Pont']
    for word in common_words:
        name = name.replace(f'{word} ', '')
        name = name.replace(f' {word}', '')
    
    # Abréviations courantes
    abbreviations = {
        'Saint': 'St', 'Sainte': 'Ste', 'Général': 'Gal',
        'Maréchal': 'Mal', 'Président': 'Pdt',
        'République': 'Rép.', 'National': 'Nat.',
        'de la ': '', 'du ': '', 'des ': '', ' - ': '-',
    }
    for full, abbr in abbreviations.items():
        name = name.replace(full, abbr)
    
    if len(name) > max_length:
        name = name[:max_length-2] + '..'
    
    return name

# ============================================================================
# VISUALISATIONS
# ============================================================================
print("\n" + "=" * 80)
print("📊 GÉNÉRATION DES GRAPHIQUES...")
print("=" * 80)

# ============================================================================
# 1. Distribution de la distance des trajets
# ============================================================================
fig, ax = plt.subplots(figsize=(12, 6))
df_standard[df_standard['distance_meters'] > 0]['distance_meters'].hist(bins=50, edgecolor='black', alpha=1, color='cornflowerblue')
plt.axvline(df_standard['distance_meters'].mean(), color='red', linestyle='--', linewidth=2,
            label=f'Moyenne: {df_standard["distance_meters"].mean():.1f} m')
plt.axvline(df_standard['distance_meters'].median(), color='green', linestyle='--', linewidth=2,
            label=f'Médiane: {df_standard["distance_meters"].median():.1f} m')
plt.xticks(np.arange(0, 23000, 500), rotation=70)
plt.xlabel('Distance (m)', fontsize=12, fontweight='bold')
plt.ylabel('Nombre de trajets', fontsize=12, fontweight='bold')
plt.title('Distribution de la Distance des Trajets (sans boomerang)', fontsize=14, fontweight='bold')
plt.legend(fontsize=11)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('01_distribution_distance.png', dpi=300, bbox_inches='tight')
print("✅ Sauvegardé: 01_distribution_distance.png")

# ============================================================================
# 2. Trajets par jour de la semaine
# ============================================================================
fig, ax = plt.subplots(figsize=(12, 6))
days_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
colors = ['lightgreen']
# colors = ['#FF6B6B' if i >= 5 else '#4ECDC4' for i in range(7)]
bars = ax.bar(days_fr, trips_by_day.values, color=colors, alpha=1, width = 0.5)
ax.set_xlabel('Jour de la semaine', fontsize=12, fontweight='bold')
ax.set_ylabel('Nombre de trajets', fontsize=12, fontweight='bold')
ax.set_title('Nombre de Trajets par Jour de la Semaine', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, axis='y')

# Ajouter les valeurs sur les barres
# for bar in bars:
#     height = bar.get_height()
#     ax.text(bar.get_x() + bar.get_width()/2., height,
#             f'{int(height)}',
#             ha='center', va='bottom', fontweight='bold')

plt.tight_layout()
plt.savefig('02_trajets_par_jour.png', dpi=300, bbox_inches='tight')
print("✅ Sauvegardé: 02_trajets_par_jour.png")

# ============================================================================
# 3. Trajets par heure - Semaine vs Weekend
# ============================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))

# Semaine
weekday_hourly = df_standard[~df_standard['is_weekend']].groupby('hour').size()
hours = range(24)
weekday_counts = [weekday_hourly.get(h, 0) for h in hours]
ax1.bar(hours, weekday_counts, color='#4ECDC4', alpha=1)
ax1.set_xlabel('Heure de la journée (Paris)', fontsize=12, fontweight='bold')
ax1.set_ylabel('Nombre de trajets', fontsize=12, fontweight='bold')
ax1.set_title('Trajets par Heure - SEMAINE (Lundi-Vendredi)', fontsize=14, fontweight='bold')
ax1.set_xticks(hours)
ax1.set_xticklabels([f'{h:02d}h' for h in hours], rotation=45, ha='right')
ax1.grid(True, alpha=0.3, axis='y')

# Weekend
weekend_hourly = df_standard[df_standard['is_weekend']].groupby('hour').size()
weekend_counts = [weekend_hourly.get(h, 0) for h in hours]
ax2.bar(hours, weekend_counts, color='#FF6B6B', alpha=1)
ax2.set_xlabel('Heure de la journée (Paris)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Nombre de trajets', fontsize=12, fontweight='bold')
ax2.set_title('Trajets par Heure - WEEKEND (Samedi-Dimanche)', fontsize=14, fontweight='bold')
ax2.set_xticks(hours)
ax2.set_xticklabels([f'{h:02d}h' for h in hours], rotation=45, ha='right')
ax2.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('03_trajets_par_heure.png', dpi=300, bbox_inches='tight')
print("✅ Sauvegardé: 03_trajets_par_heure.png")

# ============================================================================
# 4. Top 6 stations les plus utilisées
# ============================================================================

# Ajouter une colonne pour les noms des stations dans le DataFrame average_daily_traffic
average_daily_traffic['name'] = average_daily_traffic['station_id'].map(station_names)
# Sélectionner les 6 premières stations
top6_stations = average_daily_traffic.head(6)
# Tracer le graphique
fig, ax = plt.subplots(figsize=(15, 8))
station_labels = [abbreviate_station(name, 35) for name in top6_stations['name']]
ax.barh(range(len(top6_stations)), top6_stations['total_traffic'].values[::-1],
        color='forestgreen', alpha=1, height = 0.5)
ax.set_yticks(range(len(top6_stations)))
ax.set_yticklabels(station_labels[::-1], fontsize=9)
ax.set_xlabel('Nombre d\'utilisations (départs + arrivées) en moyenne par jour', fontsize=12, fontweight='bold')
ax.set_title('Top 6 Stations les Plus Utilisées', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig('04_top_stations.png', dpi=300, bbox_inches='tight')
print("✅ Sauvegardé: 04_top_stations.png")



# ============================================================================
# 5. Top 20 paires Origine-Destination
# ============================================================================
fig, ax = plt.subplots(figsize=(15, 8))
top10_od = od_matrix.head(10)

od_labels = []
for _, row in top10_od.iterrows():
    start_name = station_names.get(row['start_station_id'], row['start_station_id'])
    end_name = station_names.get(row['end_station_id'], row['end_station_id'])
    start_abbr = abbreviate_station(start_name, 22)
    end_abbr = abbreviate_station(end_name, 22)
    od_labels.append(f"{start_abbr} → {end_abbr}")

ax.barh(range(len(top10_od)), top10_od['trips'].values[::-1], 
        color='purple', alpha=1, height = 0.5)
ax.set_yticks(range(len(top10_od)))
ax.set_yticklabels(od_labels[::-1], fontsize=8)
ax.set_xlabel('Nombre de trajets', fontsize=12, fontweight='bold')
ax.set_title('Top 10 Paires Origine-Destination', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig('05_top_od.png', dpi=300, bbox_inches='tight')
print("✅ Sauvegardé: 05_top_od.png")







