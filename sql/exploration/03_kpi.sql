-- Étape 3 : afficher les indicateurs (explications : etapes/03-kpi.md)
-- Lancer : uv run python -m pipeline.db run sql/exploration/03_kpi.sql

-- 1. Méta des armes : les 4 armes les plus utilisées par jeu et mode
SELECT jeu, mode, arme, utilisations, part_pct, kd, kills_10min, taux_victoire_pct
FROM (SELECT *, row_number() OVER (PARTITION BY jeu, mode ORDER BY utilisations DESC) AS rang FROM kpi.meta_armes) t
WHERE rang <= 3 ORDER BY jeu, mode, rang;
-- 2. Modes de jeu
SELECT * FROM kpi.modes ORDER BY jeu, mode;
-- 3. Facteurs de victoire
SELECT * FROM kpi.facteurs_victoire ORDER BY jeu, mode, taux_victoire_pct DESC;
-- 3b. Search & Destroy : part des premiers kills et victoire
SELECT * FROM kpi.snd_premiers_kills ORDER BY jeu, part_premiers_kills;
-- 5. Meilleurs joueurs par jeu (K/D)
SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY jeu ORDER BY kd DESC) AS rang FROM kpi.joueurs) t WHERE rang <= 5 ORDER BY jeu, rang;
-- 6. Meilleures équipes par jeu (au moins 20 séries)
SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY jeu ORDER BY taux_victoire_series_pct DESC NULLS LAST) AS rang FROM kpi.equipes WHERE series >= 20) t WHERE rang <= 5 ORDER BY jeu, rang;
