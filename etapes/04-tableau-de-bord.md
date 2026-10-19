# Étape 4 — Le tableau de bord

**Fichier :** [`pipeline/dashboard.py`](../pipeline/dashboard.py) → [`docs/index.html`](../docs/index.html)

## Le choix : une page HTML générée en Python

Le script lit les vues SQL du schéma `kpi`, construit les graphiques avec **Plotly** et écrit **un seul
fichier HTML** (58 Ko). Avantages : il s'ouvre dans n'importe quel navigateur, sans logiciel ni compte ;
il peut être publié gratuitement (GitHub Pages) ; les graphiques sont interactifs (survol, zoom, légende
cliquable).

## Le contenu

1. Les chiffres clés (parties, séries, joueurs, tournois).
2. Les armes dominantes par jeu.
3. L'évolution de la méta d'un tournoi à l'autre (WWII et Black Ops 4).
4. Premiers kills et victoire en Search & Destroy.
5. Les facteurs de victoire selon le mode.
6. Les 10 meilleurs joueurs et les meilleures équipes, par jeu (onglets).
7. Méthode et limites.

Chaque section pose une question et donne la lecture du graphique en une phrase.

## Les choix de conception

| Choix | Pourquoi |
|---|---|
| Une couleur par jeu, dans un ordre fixe | Le même jeu a la même couleur sur toute la page |
| Étiquettes au bout des courbes plutôt qu'une légende | Plus rapide à lire avec 3 séries ; les étiquettes trop proches sont écartées automatiquement |
| Une arme absente d'un tournoi vaut 0 %, pas « vide » | Sinon la courbe relie deux points en sautant le tournoi, ce qui ment |
| Ligne « 50 % : pile ou face » | Donne la référence : en dessous ou au-dessus du hasard |
| Mentions de prudence dans le texte | Symétrie du graphique Search & Destroy, Hardpoint presque automatique, corrélation ≠ causalité |
| Virgule décimale, espace pour les milliers | Format français |
