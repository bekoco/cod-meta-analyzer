# Étape 3 — Indicateurs et analyses de la méta

**Fichiers :** [`sql/03_kpi.sql`](../sql/03_kpi.sql) (définitions) ·
[`sql/exploration/03_kpi.sql`](../sql/exploration/03_kpi.sql) (affichage)

## Règles

- **Un jeu = une saison** : on ne compare jamais les statistiques de deux jeux entre elles (armes,
  cartes et règles changent).
- **Un ratio global = somme / somme** : le K/D d'un joueur sur la saison, c'est ses kills totaux divisés
  par ses morts totales, pas la moyenne de ses K/D par partie (une partie à 3/1 ne pèse pas autant
  qu'une à 30/10).
- **Seuils** : 100 parties minimum pour classer un joueur (25 en Infinite Warfare, un seul tournoi),
  20 séries pour une équipe (5 en Infinite Warfare). Seules les séries complètes comptent.

## Résultats

### La méta des armes

| Jeu | Armes dominantes (part des joueurs) |
|---|---|
| Infinite Warfare | KBAR-32 40 %, Erad 30 %, NV4 30 % |
| WWII | PPSh-41 56 %, STG-44 28 % |
| Black Ops 4 | Maddox RFB 45 %, Saug 9mm 32 %, ICR-7 20 % |

Chaque arme dominante a un **taux de victoire d'environ 50 %** : tout le monde la joue, elle ne départage
donc personne. La méta est une contrainte commune, pas un avantage.

**Évolution** : en Black Ops 4, le Maddox RFB passe de 50 % (janvier) à 35 % (championnat), où le Saug 9mm
le dépasse. En WWII, le FG 42, joué à 46 % au premier tournoi (Dallas), tombe à 4 % puis disparaît ;
cause probable : une mise à jour d'équilibrage du jeu (hypothèse non vérifiée dans les données).

### Ce qui fait gagner

Méthode : pour chaque partie, on compare les deux équipes sur un indicateur, puis on mesure la part des
parties gagnées par l'équipe qui le domine. 50 % = l'indicateur ne dit rien.

| Mode | Indicateur | Black Ops 4 | WWII |
|---|---|---:|---:|
| Search & Destroy | Plus d'éliminations | 92 % | 93 % |
| Search & Destroy | Plus de premiers kills de manche | 67 % | 72 % |
| Hardpoint | Plus de temps dans la zone | 92 % | 95 % |
| Control | Plus de captures de zone | 78 % | — |

**Premiers kills en Search & Destroy** : au-delà de 70 % des premiers kills d'une partie, une équipe gagne
78 à 87 % du temps ; sous 30 %, 13 à 22 %.

**Prudence** : ce sont des corrélations (gagner fait aussi faire plus d'éliminations), et en Hardpoint le
score *est* le temps dans la zone : le lien y est presque automatique.

### Joueurs et équipes

- Meilleurs K/D : Dashy (1,27 en Black Ops 4, 1,21 en WWII), Formal (1,44 en Infinite Warfare, 80 % de victoires).
- Meilleures équipes (séries gagnées) : 100 Thieves 79 % et eUnited 76 % en Black Ops 4 ; Rise Nation 72 % en WWII.
