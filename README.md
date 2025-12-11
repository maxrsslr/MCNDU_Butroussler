# RAPPORT:  Nouvelles données de mobilité : collecte et analyse, Projet (Code, Documentation)

*Décembre 2025*

*Titouan Butruille-Rio, Marius Roudil, Maxence Rössler*

*ENPC*

## Presentation (EN COURS DE REDACTION - PAS DEFINITIF)

# Contexte

En 2021, la mairie de Paris présente son plan 100% vélo qui prévoit l’aménagement de 1000 km de linéaire d’aménagement cyclable d’ici à 2026. Il s’inscrit dans un contexte d’augmentation de la fréquentation des rues de Paris à vélo. Par exemple, 1er janvier 2021, la mairie de Paris recensait 8,7% des actifs qui rendaient sur le lieu de travail à vélo (ce qui représente une augmentation de 4,5 points par rapport à 2015). 
Or il apparait que de bonnes infrastructures soient nécessaires pour promouvoir l’usage du vélo. Hull and O’Holleran (2014) montrent avec l’appui de nombreuses sources littéraires, que l’un des principaux facteurs déterminants d’utilisation du vélo en ville est la présence des infrastructures cyclables. Selon Emond et al (2019), cela est d’autant plus vrai pour les femmes, qui sont d’autant plus attachées à ces enjeux. Cette étude montre que les femmes sont particulièrement sensibles à la sécurité perçue vis-à-vis des automobilistes, et que leur confort de conduite constitue un facteur déterminant dans l’usage du vélo.  Rupi et al. (2023) confirment ces écarts en analysant des données GPS : les femmes tendent à éviter les itinéraires complexes ou jugés dangereux. Ces études soulignent que les préoccupations liées à la sécurité influencent fortement les choix de déplacement des femmes à vélo.

# Problématique

Ce projet vise à identifier les portions de voirie régulièrement empruntées par les usagers de Vélib’ et à les confronter à l’existence ou non d’aménagements cyclables. L’objectif est d’estimer les rues qui optimiseraient le maillage cyclable parisien en répondant aux trajets les plus courts et les plus fréquents des cyclistes.
En croisant les données de trajets avec les infrastructures existantes, il s’agirait de repérer les portions d’axe les plus utilisées. Nous pourrions ainsi identifier celles qui sont sécurisés, afin de proposer des priorités d’aménagement. 
Cette démarche soulève plusieurs enjeux méthodologiques : la difficulté d’identifier précisément les rues empruntées, les biais liés à l’évitement des zones peu sécurisées, ou encore la représentativité des usagers Vélib’ par rapport à l’ensemble des cyclistes parisiens.
L’analyse tiendra compte des itinéraires théoriques correspondant aux chemins les plus courts en jugeant que ce sont eux qui sont les plus efficaces (ce qui est bien-sûr débattable car d’autres facteurs rentrent en compte comme la topographie par exemple) mais aussi des données de fréquentation ou encore du profil socio-économique des utilisateurs. Le but est à la fin du projet, de pouvoir formuler des recommandations ciblées pour le développement de pistes cyclables adaptées à une partie de la réalité des déplacements des cyclistes. 

# Données 

Pour récupérer les données de déplacement des vélib’ (borne de départ et d’arrivée), nous nous baserons sur le site velibest (https://velibest.fr/) qui permet d’avoir des informations très précises sur les vélib'. L’API de ce site a été développée par Thomas de Queiros (https://tdqr.ovh/api/). Celle-ci extrait en temps réel les données de l’application Vélib’ et permet d’avoir de nombreuses variables que l’on peut exploiter, notamment les départs et les arrivées à chaque borne, le code de chaque vélo (qui est unique et identifié par un code exploitable). Un score est également calculé pour chaque vélo en prenant en compte divers indicateurs estimée par cette API comme par exemple le nombre de trajets boomerangs (c’est à dire le fait de reposer immédiatement son vélo après l’avoir décroché car celui-ci à un problème technique) la vitesse moyenne sur certains trajets mais aussi les notes que les utilisateurs laissent. 

# Methode 

Utilisation de divers services de Amazon Web Service (AWS):
- DynamoDB : base de données
- Lambda: requêtes automatisées à intervales réguliers
- Eventbridge: déclencheur d'événement 

## Contenus 

# Récupération des identifiants VELIB

Nous séparons donc notre phase de collecte de données en deux périodes étalées sur 1 mois. La première aura pour objectif d'effectuer uniquement les requêtes à chaque station des vélos actifs. En effectuant ces requêtes sur deux semaines, nous pensons obtenir la liste complète des vélos présents dans le système, en laissant le temps aux vélos potentiellement en maintenance lors de la première semaine de réintégrer le circuit. 

Cela a été fait utilisant les solutions proposées par Amazon Web Services (AWS). 

Trigger (Eventbridge): tous les jours toutes les 6 heures (00h,06h,12h,18h) durant 2 semaines (27/11-11/12) --> AWS Lambda: fonction de récupération des données pour chaque station via l'API), appelée par le trigger toutes les 6h --> DynamoDB: stockage des identifiants dans un base de données. 
11/12: 24'616 identifiants de vélos uniques. 
