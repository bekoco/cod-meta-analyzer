# Étape 1 — Trouver les données et les explorer

**Requêtes :** [`sql/exploration/01_exploration.sql`](../sql/exploration/01_exploration.sql)

## Trouver une source fiable

Il n'existe pas de jeu de données « CDL » officiel et téléchargeable. Les sites de statistiques
communautaires publient des tableaux web, sans licence claire. La meilleure source est la
**publication officielle d'Activision** : entre 2017 et 2019, l'éditeur a mis en ligne les données
complètes de ses tournois de la Call of Duty World League, « pour inspirer la recherche ».

Le dépôt d'origine (`Activision/cwl-data`) n'existe plus. Vérification de la provenance :

1. Une archive (Wayback Machine) du dépôt officiel confirme la liste des **18 fichiers** et la licence.
2. Des **forks** du dépôt subsistent ; leur dernier commit, « the *last* data » du 28 août 2019, est
   signé par l'auteur de la publication, et ils contiennent exactement les 18 fichiers de l'archive.
3. On lit cette version figée (commit `5b7eb907`) et on enregistre l'empreinte SHA-256 de chaque fichier.

Une autre copie trouvée en ligne (2016-2019) disait avoir « récupéré » les données hors publication
officielle, sans licence : écartée.

## Volume et grain

| Jeu | Lignes | Parties | Séries | Joueurs |
|---|---:|---:|---:|---:|
| Infinite Warfare (2017) | 2 384 | 298 | 82 | 128 |
| WWII (2018) | 23 048 | 2 881 | 444 | 166 |
| Black Ops 4 (2019) | 19 120 | 1 912 | 384 | 206 |

**Grain : 1 ligne = 1 joueur dans 1 partie.** 8 lignes par partie en Infinite Warfare et WWII (4 contre 4),
10 en Black Ops 4 (5 contre 5) : les données suivent les règles de chaque saison.

## Ce que l'exploration a révélé

| Constat | Ampleur | Traitement |
|---|---|---|
| Colonnes différentes selon le jeu (55, 66, 62) | 86 colonnes au total | Table brute avec l'union des colonnes, une colonne absente reste vide |
| Durées écrites « 266.0 » en Infinite Warfare | 2 384 lignes | Conversion tolérante (`stg.num`) |
| Précision écrite « 27.2% » | toutes les lignes | Le `%` est retiré à la conversion |
| Parties sans gagnant | 4 | 1 égalité (227-227), 1 partie touchée par une panne matérielle, 1 égalité en CTF, 1 partie reconstituée à la main sans gagnant renseigné |
| Identifiant de série réutilisé d'un tournoi à l'autre | 150 noms | Clé de série = tournoi + identifiant |
| Séries incomplètes (1 ou 2 parties) | 29 | Conséquence des pertes de données ; exclues des classements |
| Arme préférée vide | 370 lignes | `NULL` |
| Le même club sous deux noms | 4 cas | Voir l'étape 2 |

**Contrôle de cohérence :** dans 86 % des parties, le total des éliminations est exactement égal au
total des morts ; l'écart restant vient des suicides et des tirs fratricides.

La documentation d'Activision **liste elle-même les données perdues** (pannes, serveur de données
en panne à Atlanta, environ 80 parties perdues à Birmingham…) : elle est reprise dans les limites.
