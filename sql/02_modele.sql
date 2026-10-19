-- Étape 2b : modèle en étoile (explications : etapes/02-modele.md)
--
-- Trois tables de faits, chacune à son grain :
--   core.fait_joueur_partie   1 ligne = 1 joueur dans 1 partie
--   core.fait_equipe_partie   1 ligne = 1 équipe dans 1 partie
--   core.fait_serie           1 ligne = 1 série (un match au meilleur des 5 parties)
-- et des dimensions : tournoi, carte, équipe, joueur.

CREATE SCHEMA IF NOT EXISTS core;

-- ── Dimensions ─────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS core.dim_tournoi CASCADE;
CREATE TABLE core.dim_tournoi AS
SELECT source_file AS tournoi_id, min(tournoi) AS tournoi, min(jeu) AS jeu, min(date_fin_tournoi) AS date_fin,
       CASE WHEN min(tournoi) LIKE '%Pro League%' THEN 'Pro League' ELSE 'Open / LAN' END AS format,
       count(DISTINCT match_id) AS parties
FROM stg.player_game
GROUP BY source_file;

DROP TABLE IF EXISTS core.dim_carte CASCADE;
CREATE TABLE core.dim_carte AS
SELECT DISTINCT jeu || '|' || carte AS carte_id, jeu, carte FROM stg.player_game;

DROP TABLE IF EXISTS core.dim_equipe CASCADE;
CREATE TABLE core.dim_equipe AS
SELECT equipe, count(DISTINCT match_id) AS parties, min(date_fin_tournoi) AS premiere_apparition,
       max(date_fin_tournoi) AS derniere_apparition
FROM stg.player_game GROUP BY equipe;

DROP TABLE IF EXISTS core.dim_joueur CASCADE;
CREATE TABLE core.dim_joueur AS
SELECT joueur, count(DISTINCT match_id) AS parties, count(DISTINCT jeu) AS jeux,
       -- l'équipe la plus récente du joueur (les transferts sont fréquents)
       (array_agg(equipe ORDER BY fin_partie_utc DESC))[1] AS derniere_equipe
FROM stg.player_game GROUP BY joueur;

-- ── Faits : joueur × partie ────────────────────────────────────────────────────
DROP TABLE IF EXISTS core.fait_joueur_partie CASCADE;
CREATE TABLE core.fait_joueur_partie AS
SELECT
    p.match_id, p.serie_id, p.source_file AS tournoi_id, p.jeu, p.mode, p.jeu || '|' || p.carte AS carte_id,
    p.fin_partie_utc, p.duree_s, p.equipe, p.joueur, r.resultat,
    p.kills, p.deaths, p.assists, p.headshots, p.hits, p.shots, p.degats,
    -- Ratios recalculés à partir des comptages (les valeurs publiées sont arrondies)
    p.kills::numeric / nullif(p.deaths, 0)                       AS kd,
    p.kills * 600.0 / nullif(p.duree_s, 0)                       AS kills_10min,
    p.hits::numeric / nullif(p.shots, 0)                         AS precision,
    p.arme_preferee,
    p.hp_temps_zone_s, p.hp_captures, p.hp_defenses,
    p.snd_manches, p.snd_premiers_kills, p.snd_premieres_morts, p.snd_poses_bombe, p.snd_desamorcages,
    p.ctrl_captures
FROM stg.player_game p
JOIN stg.resultat_equipe r USING (match_id, equipe);

-- ── Faits : équipe × partie ────────────────────────────────────────────────────
DROP TABLE IF EXISTS core.fait_equipe_partie CASCADE;
CREATE TABLE core.fait_equipe_partie AS
SELECT
    f.match_id, min(f.serie_id) AS serie_id, min(f.tournoi_id) AS tournoi_id, min(f.jeu) AS jeu,
    min(f.mode) AS mode, min(f.carte_id) AS carte_id, min(f.fin_partie_utc) AS fin_partie_utc,
    min(f.duree_s) AS duree_s, f.equipe, min(r.adversaire) AS adversaire,
    min(r.score) AS score, min(r.score_adversaire) AS score_adversaire, min(r.resultat) AS resultat,
    bool_or(r.resultat_deduit) AS resultat_deduit,
    count(*) AS joueurs,
    sum(f.kills) AS kills, sum(f.deaths) AS deaths,
    sum(f.hp_temps_zone_s) AS hp_temps_zone_s,
    sum(f.snd_premiers_kills) AS snd_premiers_kills,
    max(f.snd_manches) AS snd_manches,
    sum(f.snd_poses_bombe) AS snd_poses_bombe,
    sum(f.ctrl_captures) AS ctrl_captures
FROM core.fait_joueur_partie f
JOIN stg.resultat_equipe r USING (match_id, equipe)
GROUP BY f.match_id, f.equipe;

-- ── Faits : série ──────────────────────────────────────────────────────────────
-- Une série oppose deux équipes au meilleur des 5 parties : la première à 3 victoires gagne.
DROP TABLE IF EXISTS core.fait_serie CASCADE;
CREATE TABLE core.fait_serie AS
WITH bilan AS (
    SELECT serie_id, min(tournoi_id) AS tournoi_id, min(jeu) AS jeu, equipe,
           count(*) FILTER (WHERE resultat = 'V') AS victoires, count(*) AS parties,
           min(fin_partie_utc) AS debut
    FROM core.fait_equipe_partie GROUP BY serie_id, equipe
)
SELECT
    a.serie_id, a.tournoi_id, a.jeu, a.debut,
    a.equipe AS equipe_a, b.equipe AS equipe_b, a.victoires AS victoires_a, b.victoires AS victoires_b,
    a.parties,
    CASE WHEN a.victoires > b.victoires THEN a.equipe WHEN b.victoires > a.victoires THEN b.equipe END AS vainqueur,
    -- Complète si une équipe a atteint 3 victoires ; sinon des parties manquent (pertes de données)
    greatest(a.victoires, b.victoires) >= 3 AS complete
FROM bilan a JOIN bilan b ON b.serie_id = a.serie_id AND a.equipe < b.equipe;
