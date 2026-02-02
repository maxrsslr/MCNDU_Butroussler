# -*- coding: utf-8 -*-
"""
Created on Mon Dec 15 16:46:04 2025

@author: Maxence
"""

import boto3
import pandas as pd

# -----------------------
# CONFIG AWS (EN DUR)
# -----------------------
AWS_ACCESS_KEY_ID = "XXXXXXXXXXXXXXXXXXXXXXXXXXxx"
AWS_SECRET_ACCESS_KEY = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
REGION = "eu-north-1"


# -----------------------
# CONFIG
# -----------------------
TABLE_NAME = "VelibBikeIds"
OUTPUT_FILE = "bikes_id_final.csv"

# -----------------------
# CONNEXION DYNAMODB
# -----------------------
dynamodb = boto3.resource(
    "dynamodb",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=REGION
)

table = dynamodb.Table(TABLE_NAME)

# -----------------------
# SCAN COMPLET (PAGINÉ)
# -----------------------
items = []

response = table.scan()
items.extend(response["Items"])

while "LastEvaluatedKey" in response:
    response = table.scan(
        ExclusiveStartKey=response["LastEvaluatedKey"]
    )
    items.extend(response["Items"])

print(f"✅ {len(items)} lignes récupérées")

# -----------------------
# DATAFRAME + EXPORT CSV
# -----------------------
df = pd.DataFrame(items)
# df = df.iloc[:, 1:] get rid of "last seen column"
df.to_csv("bike_id_final_last_seen.csv", index=False, encoding="utf-8")

print(f"🎉 Export terminé : {OUTPUT_FILE}")