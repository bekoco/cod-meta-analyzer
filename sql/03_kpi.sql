-- Étape 3 : indicateurs et analyses de la méta (explications : etapes/03-kpi.md)
--
-- Des vues (recalculées à chaque lecture) dans le schéma kpi.
-- Règles :
--   * un jeu = une saison : on ne compare jamais des statistiques de jeux différents entre elles ;
--   * un ratio global se calcule comme somme / somme (K/D global = kills totaux / morts totales),
--     jamais comme moyenne de ratios (un 3/1 et un 30/10 ne pèsent pas pareil) ;
--   * les égalités (6 parties) sont exclues des taux de victoire.

CREATE SCHEMA IF NOT EXISTS kpi;

-- ── 1. La méta des armes ───────────────────────────────────────────────────────
-- Part d'utilisation : sur 100 « joueur × partie », combien ont cette arme comme arme principale.
CREATE OR REPLACE VIEW kpi.meta_armes AS
WITH base AS (
    SELECT jeu, mode, arme_preferee AS arme, count(*) AS utilisations,
           sum(kills) AS kills, sum(deaths) AS deaths, sum(duree_s) AS duree_s,
           count(*) FILTER (WHERE resultat = 'V') AS victoires,
           count(*) FILTER (WHERE resultat IN ('V', 'D')) AS parties_decidees
    FROM core.fait_joueur_partie
    WHERE arme_preferee IS NOT NULL
    GROUP BY jeu, mode, arme_preferee
)
SELECT jeu, mode, arme, utilisations,
       round(100.0 * utilisations / sum(utilisations) OVER (PARTITION BY jeu, mode), 1) AS part_pct,
       round(kills::numeric / nullif(deaths, 0), 2) AS kd,
       round(kills * 600.0 / nullif(duree_s, 0), 2) AS kills_10min,
       round(100.0 * victoires / nullif(parties_decidees, 0), 1) AS taux_victoire_pct
FROM base;

-- Évolution de la part des armes d'un tournoi à l'autre (les mises à jour du jeu changent la méta)
CREATE OR REPLACE VIEW kpi.meta_armes_evolution AS
SELECT t.jeu, t.date_fin, t.tournoi, f.arme_preferee AS arme,
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY t.tournoi_id), 1) AS part_pct
FROM core.fait_joueur_partie f
JOIN core.dim_tournoi t USING (tournoi_id)
WHERE f.arme_preferee IS NOT NULL
GROUP BY t.jeu, t.date_fin, t.tournoi, t.tournoi_id, f.arme_preferee;

-- ── 2. Les modes de jeu ────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW kpi.modes AS
SELECT jeu, mode,
       count(DISTINCT match_id) AS parties,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY duree_s)::numeric / 60, 1) AS duree_mediane_min,
       round(sum(kills) * 600.0 / sum(duree_s), 2) AS kills_10min_par_joueur,
       round(100.0 * sum(headshots) / nullif(sum(kills), 0), 1) AS part_headshots_pct
FROM core.fait_joueur_partie
GROUP BY jeu, mode;

-- ── 3. Ce qui fait gagner : « l'équipe qui domine X gagne-t-elle ? » ───────────
-- Pour chaque partie décidée, on compare les deux équipes sur un indicateur.
-- Taux = part des parties gagnées par l'équipe qui a la plus grosse valeur (les égalités sur
-- l'indicateur sont écartées). 50 % = l'indicateur ne dit rien ; 100 % = il décide tout.
CREATE OR REPLACE VIEW kpi.facteurs_victoire AS
WITH duel AS (
    SELECT a.jeu, a.mode, a.resultat,
           a.kills - b.kills                                   AS d_kills,
           a.hp_temps_zone_s - b.hp_temps_zone_s               AS d_temps_zone,
           a.snd_premiers_kills - b.snd_premiers_kills         AS d_premiers_kills,
           a.ctrl_captures - b.ctrl_captures                   AS d_captures
    FROM core.fait_equipe_partie a
    JOIN core.fait_equipe_partie b ON b.match_id = a.match_id AND b.equipe = a.adversaire
    WHERE a.resultat IN ('V', 'D')
),
indicateurs AS (
    SELECT jeu, mode, 'Plus d''éliminations' AS facteur, d_kills AS d, resultat FROM duel
    UNION ALL SELECT jeu, mode, 'Plus de temps dans la zone', d_temps_zone, resultat FROM duel WHERE mode = 'Hardpoint'
    UNION ALL SELECT jeu, mode, 'Plus de premiers kills (manches)', d_premiers_kills, resultat FROM duel WHERE mode = 'Search & Destroy'
    UNION ALL SELECT jeu, mode, 'Plus de captures de zone', d_captures, resultat FROM duel WHERE mode = 'Control'
)
SELECT jeu, mode, facteur,
       count(*) FILTER (WHERE d > 0) AS parties,
       round(100.0 * count(*) FILTER (WHERE d > 0 AND resultat = 'V') / nullif(count(*) FILTER (WHERE d > 0), 0), 1)
           AS taux_victoire_pct
FROM indicateurs
WHERE d IS NOT NULL
GROUP BY jeu, mode, facteur;

-- En Search & Destroy : plus on prend de premiers kills, plus on gagne ?
CREATE OR REPLACE VIEW kpi.snd_premiers_kills AS
SELECT jeu,
       CASE WHEN part < 0.3 THEN '< 30 %' WHEN part < 0.45 THEN '30-45 %' WHEN part <= 0.55 THEN '45-55 %'
            WHEN part <= 0.7 THEN '55-70 %' ELSE '> 70 %' END AS part_premiers_kills,
       count(*) AS parties,
       round(100.0 * count(*) FILTER (WHERE resultat = 'V') / count(*), 1) AS taux_victoire_pct
FROM (
    SELECT a.jeu, a.resultat,
           a.snd_premiers_kills::numeric / nullif(a.snd_premiers_kills + b.snd_premiers_kills, 0) AS part
    FROM core.fait_equipe_partie a
    JOIN core.fait_equipe_partie b ON b.match_id = a.match_id AND b.equipe = a.adversaire
    WHERE a.mode = 'Search & Destroy' AND a.resultat IN ('V', 'D')
) t
WHERE part IS NOT NULL
GROUP BY jeu, part_premiers_kills;

-- ── 4. Les cartes ──────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW kpi.cartes AS
SELECT c.jeu, c.carte, f.mode,
       count(DISTINCT f.match_id) AS parties,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY f.duree_s)::numeric / 60, 1) AS duree_mediane_min,
       round(sum(f.kills) * 600.0 / sum(f.duree_s), 2) AS kills_10min_par_joueur
FROM core.fait_joueur_partie f
JOIN core.dim_carte c USING (carte_id)
GROUP BY c.jeu, c.carte, f.mode;

-- ── 5. Les joueurs ─────────────────────────────────────────────────────────────
-- Seuil : au moins 100 parties dans le jeu, pour ne pas classer un joueur sur quelques matchs.
-- Infinite Warfare ne compte qu'un tournoi (298 parties) : seuil abaissé à 25 parties.
CREATE OR REPLACE VIEW kpi.joueurs AS
SELECT jeu, joueur,
       (array_agg(equipe ORDER BY fin_partie_utc DESC))[1] AS equipe,
       count(*) AS parties,
       round(sum(kills)::numeric / nullif(sum(deaths), 0), 2) AS kd,
       round(sum(kills) * 600.0 / sum(duree_s), 2) AS kills_10min,
       round(100.0 * count(*) FILTER (WHERE resultat = 'V') / nullif(count(*) FILTER (WHERE resultat IN ('V', 'D')), 0), 1)
           AS taux_victoire_pct,
       round(100.0 * sum(snd_premiers_kills) / nullif(sum(snd_manches) FILTER (WHERE mode = 'Search & Destroy'), 0), 1)
           AS snd_premier_kill_par_manche_pct,
       round(sum(hp_temps_zone_s) FILTER (WHERE mode = 'Hardpoint') * 600.0
             / nullif(sum(duree_s) FILTER (WHERE mode = 'Hardpoint'), 0), 1) AS hp_temps_zone_s_par_10min
FROM core.fait_joueur_partie
GROUP BY jeu, joueur
HAVING count(*) >= CASE WHEN jeu = 'Infinite Warfare' THEN 25 ELSE 100 END;

-- ── 6. Les équipes ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW kpi.equipes AS
WITH parties AS (
    SELECT jeu, equipe, count(*) AS parties,
           count(*) FILTER (WHERE resultat = 'V') AS victoires,
           count(*) FILTER (WHERE resultat IN ('V', 'D')) AS decidees
    FROM core.fait_equipe_partie GROUP BY jeu, equipe
),
series AS (
    SELECT jeu, equipe, count(*) AS series, count(*) FILTER (WHERE vainqueur = equipe) AS series_gagnees
    FROM (SELECT jeu, equipe_a AS equipe, vainqueur FROM core.fait_serie WHERE complete
          UNION ALL SELECT jeu, equipe_b, vainqueur FROM core.fait_serie WHERE complete) s
    GROUP BY jeu, equipe
)
SELECT p.jeu, p.equipe, p.parties,
       round(100.0 * p.victoires / nullif(p.decidees, 0), 1) AS taux_victoire_parties_pct,
       coalesce(s.series, 0) AS series,
       round(100.0 * s.series_gagnees / nullif(s.series, 0), 1) AS taux_victoire_series_pct
FROM parties p
LEFT JOIN series s USING (jeu, equipe);
