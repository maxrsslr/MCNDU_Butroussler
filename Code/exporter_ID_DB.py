# -*- coding: utf-8 -*-
"""
Script pour exporter en une fois les IDs des vélos depuis la base de données AWS DynamoDB et l'enregistrer en csv.
"""

# Importer les packages utiles
import boto3
import pandas as pd

# Configuration clés AWS (clés ont été enlevées ici pour des raisons de sécurité)
AWS_ACCESS_KEY_ID = "XXXXXXXXXXXXXXXXXXXXXXXXXXxx"
AWS_SECRET_ACCESS_KEY = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
REGION = "eu-north-1"

# Configurer les inputs et outputs
TABLE_NAME = "VelibBikeIds"
OUTPUT_FILE = "bikes_id_final.csv"

# Connexion à la base de données DynamoDB
dynamodb = boto3.resource(
    "dynamodb",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=REGION
)

table = dynamodb.Table(TABLE_NAME)

# Scan complet
items = []

response = table.scan()
items.extend(response["Items"])

while "LastEvaluatedKey" in response:
    response = table.scan(
        ExclusiveStartKey=response["LastEvaluatedKey"]
    )
    items.extend(response["Items"])

print(f"✅ {len(items)} lignes récupérées")

# Transformation en dataframe puis export en csv en local
df = pd.DataFrame(items)
# df = df.iloc[:, 1:] effacer "last seen column" si nécessaire
df.to_csv("bike_id_final_last_seen.csv", index=False, encoding="utf-8")


