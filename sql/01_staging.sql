-- Étape 2a : staging — typage et nettoyage ligne à ligne (explications : etapes/02-modele.md)
--
-- Même grain que la source : une ligne par joueur et par partie.
-- Les CSV sont chargés en texte brut (schéma raw) ; ici on convertit, on normalise,
-- et on garde une trace de chaque correction.

CREATE SCHEMA IF NOT EXISTS stg;

-- Conversion tolérante : « 652.0 », « 27.2% », « » → nombre ou NULL
CREATE OR REPLACE FUNCTION stg.num(txt text) RETURNS numeric
LANGUAGE sql IMMUTABLE AS 'SELECT nullif(trim(replace(txt, ''%'', '''')), '''')::numeric';

-- Règle 3 : un même club écrit de deux façons → un seul nom (le plus récent).
-- Repérés en cherchant les noms différents qui alignent les mêmes joueurs. On ne fusionne PAS
-- un effectif racheté par un autre club (ex. Midnight → UYU) : ce sont deux organisations.
DROP TABLE IF EXISTS stg.alias_equipe CASCADE;
CREATE TABLE stg.alias_equipe (nom_publie text PRIMARY KEY, nom_retenu text NOT NULL);
INSERT INTO stg.alias_equipe VALUES
    ('Team EnVyUs', 'Team Envy'),           -- même club, renommé en 2018
    ('Complexity', 'Complexity Gaming'),
    ('Luminosity', 'Luminosity Gaming'),
    ('ExcelerateGG', 'Excelerate');

DROP TABLE IF EXISTS stg.player_game CASCADE;
CREATE TABLE stg.player_game AS
SELECT
    -- Où et quand : le tournoi (un fichier = un tournoi) et le jeu de la saison
    source_file,
    game                                             AS jeu,
    event                                            AS tournoi,
    to_date(substr(source_file, 6, 10), 'YYYY-MM-DD') AS date_fin_tournoi,
    "match id"                                       AS match_id,
    -- Un identifiant de série n'est unique qu'à l'intérieur d'un tournoi (ex. « champs-bracket-… »)
    source_file || '|' || "series id"                AS serie_id,
    "series id"                                      AS serie_nom,
    replace("end time", ' UTC', '')::timestamp       AS fin_partie_utc,
    stg.num("duration (s)")::int                     AS duree_s,
    mode,
    map                                              AS carte,
    coalesce(a.nom_retenu, r.team)                   AS equipe,
    r.team                                           AS equipe_publiee,
    player                                           AS joueur,
    "win?"                                           AS resultat_brut,
    stg.num(score)::int                              AS score_equipe,

    -- Statistiques de base (comptages)
    stg.num(kills)::int                              AS kills,
    stg.num(deaths)::int                             AS deaths,
    stg.num(assists)::int                            AS assists,
    stg.num(headshots)::int                          AS headshots,
    stg.num(suicides)::int                           AS suicides,
    stg.num("team kills")::int                       AS team_kills,
    stg.num(hits)::int                               AS hits,
    stg.num(shots)::int                              AS shots,
    stg.num("damage dealt")::int                     AS degats,           -- Black Ops 4 seulement

    -- Équipement : chaîne vide = non renseigné
    nullif(trim("fave weapon"), '')                  AS arme_preferee,

    -- Hardpoint
    stg.num("hill time (s)")::int                    AS hp_temps_zone_s,
    stg.num("hill captures")::int                    AS hp_captures,
    stg.num("hill defends")::int                     AS hp_defenses,
    -- Search & Destroy
    stg.num("snd rounds")::int                       AS snd_manches,
    stg.num("snd firstbloods")::int                  AS snd_premiers_kills,
    stg.num("snd firstdeaths")::int                  AS snd_premieres_morts,   -- WWII et BO4
    stg.num("bomb plants")::int                      AS snd_poses_bombe,
    stg.num("bomb defuses")::int                     AS snd_desamorcages,
    -- Control (Black Ops 4)
    stg.num("ctrl captures")::int                    AS ctrl_captures,

    -- Valeurs dérivées publiées, gardées pour contrôle (on les recalcule dans le modèle)
    stg.num("k/d")                                   AS kd_publie,
    stg.num("accuracy (%)")                          AS precision_publiee_pct
FROM raw.player_game r
LEFT JOIN stg.alias_equipe a ON a.nom_publie = r.team;

-- Résultat de chaque équipe dans chaque partie, avec les cas particuliers documentés par Activision
DROP TABLE IF EXISTS stg.resultat_equipe CASCADE;
CREATE TABLE stg.resultat_equipe AS
WITH equipes AS (
    SELECT match_id, equipe, max(score_equipe) AS score,
           bool_or(resultat_brut = 'W') AS gagnant_publie
    FROM stg.player_game
    GROUP BY match_id, equipe
),
parties AS (
    SELECT match_id, bool_or(gagnant_publie) AS a_un_gagnant FROM equipes GROUP BY match_id
)
SELECT
    e.match_id, e.equipe, e.score,
    o.equipe AS adversaire, o.score AS score_adversaire,
    CASE
        WHEN p.a_un_gagnant THEN CASE WHEN e.gagnant_publie THEN 'V' ELSE 'D' END
        -- Règle 1 : pas de gagnant publié mais scores différents → le score décide
        --          (partie reconstituée à la main, « missing-pro1-… »)
        WHEN e.score <> o.score THEN CASE WHEN e.score > o.score THEN 'V' ELSE 'D' END
        -- Règle 2 : scores égaux → égalité (dont la partie de 2017 touchée par une panne matérielle)
        ELSE 'N'
    END AS resultat,
    NOT p.a_un_gagnant AS resultat_deduit
FROM equipes e
JOIN equipes o ON o.match_id = e.match_id AND o.equipe <> e.equipe
JOIN parties p ON p.match_id = e.match_id;
