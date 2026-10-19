# Étape 2 — Nettoyage, modèle et contrôles

**Fichiers :** [`sql/01_staging.sql`](../sql/01_staging.sql) · [`sql/02_modele.sql`](../sql/02_modele.sql) ·
[`sql/09_controles.sql`](../sql/09_controles.sql)

## Trois couches dans PostgreSQL

| Schéma | Rôle |
|---|---|
| `raw` | Les CSV **tels quels**, tout en texte. On ne corrige rien ici : on peut toujours revenir à la source. |
| `stg` | Le **staging** : conversion des types, noms en français, corrections tracées. Même grain que la source. |
| `core` | Le **modèle** : dimensions et tables de faits, prêtes pour l'analyse. |
| `kpi` | Les **indicateurs** (étape 3). |

Les schémas sont des « dossiers » dans la base : ils séparent les étapes du traitement.

## Les règles de nettoyage

- **Conversion tolérante** : une fonction `stg.num()` transforme « 652.0 », « 27.2% » ou une chaîne vide
  en nombre (ou `NULL`), au lieu de faire échouer tout le chargement.
- **Règle 1** : une partie sans gagnant publié mais avec des scores différents → le score décide.
- **Règle 2** : scores égaux → égalité (`N`), exclue des taux de victoire.
- **Règle 3** : un même club écrit de deux façons → un seul nom. Repérés en cherchant les noms différents qui
  alignent **les mêmes joueurs** : Team EnVyUs / Team Envy (renommage en 2018), Complexity / Complexity Gaming,
  Luminosity / Luminosity Gaming, ExcelerateGG / Excelerate. En revanche, un effectif racheté par un autre
  club (Midnight → UYU, Gen.G → Team Space…) n'est **pas** fusionné : ce sont deux organisations.

## Le modèle

| Table | 1 ligne = | Lignes |
|---|---|---:|
| `core.fait_joueur_partie` | un joueur dans une partie | 44 552 |
| `core.fait_equipe_partie` | une équipe dans une partie | 10 182 |
| `core.fait_serie` | une série (deux équipes, au meilleur des 5 parties) | 1 319 |
| `core.dim_tournoi` | un tournoi | 18 |
| `core.dim_carte` | une carte d'un jeu | — |
| `core.dim_equipe` | une équipe | 99 |
| `core.dim_joueur` | un joueur | 273 |

Pourquoi trois tables de faits ? Parce que les questions n'ont pas le même grain : « quel joueur a le
meilleur K/D ? » se calcule par joueur, « l'équipe qui prend plus de premiers kills gagne-t-elle ? » par
équipe, et « quelle équipe gagne le plus de séries ? » par série. Les ratios (K/D, kills par 10 minutes,
précision) sont **recalculés** à partir des comptages, plutôt que repris arrondis de la source.

## Les contrôles

10 tests rejoués à chaque build, par exemple : aucune ligne perdue, 2 équipes par partie, effectif conforme
au jeu (5 en Black Ops 4, 4 sinon), résultats cohérents (une victoire face à une défaite), et **le K/D
recalculé retombe sur le K/D publié par Activision**.

Le contrôle « une série oppose exactement deux équipes » a échoué au premier essai : la même équipe
apparaissait sous deux noms dans une série (« Team EnVyUs » à la partie 1, « Team Envy » ensuite). C'est
ce qui a fait découvrir la règle 3.
