-- Étape 1 : exploration des données brutes (explications : etapes/01-exploration.md)
-- Lancer : uv run python -m pipeline.db run sql/exploration/01_exploration.sql

-- Q1 : volume par jeu
SELECT game, count(*) AS lignes, count(DISTINCT "match id") AS parties, count(DISTINCT "series id") AS series,
       count(DISTINCT player) AS joueurs, count(DISTINCT team) AS equipes
FROM raw.player_game GROUP BY game ORDER BY min(source_file);

-- Q2 : combien de lignes par partie ? (attendu : 8, deux équipes de 4)
SELECT lignes_par_partie, count(*) AS parties
FROM (SELECT "match id", count(*) AS lignes_par_partie FROM raw.player_game GROUP BY 1) t
GROUP BY 1 ORDER BY 1;

-- Q3 : modes de jeu par titre
SELECT game, mode, count(DISTINCT "match id") AS parties
FROM raw.player_game GROUP BY 1, 2 ORDER BY 1, 3 DESC;

-- Q4 : valeurs de « win? » et équipes gagnantes par partie
SELECT "win?", count(*) FROM raw.player_game GROUP BY 1;
SELECT gagnantes, count(*) AS parties FROM (
    SELECT "match id", count(DISTINCT team) FILTER (WHERE "win?" = 'W') AS gagnantes FROM raw.player_game GROUP BY 1
) t GROUP BY 1 ORDER BY 1;

-- Q5 : formats des colonnes numériques (exemples)
SELECT "accuracy (%)", "k/d", "duration (s)", "hill time (s)", "end time" FROM raw.player_game WHERE game = 'WWII' LIMIT 3;

-- Q6 : noms d'équipe proches (même nom en minuscules, sans espaces)
SELECT lower(regexp_replace(team, '[^A-Za-z0-9]', '', 'g')) AS cle, array_agg(DISTINCT team) AS variantes
FROM raw.player_game GROUP BY 1 HAVING count(DISTINCT team) > 1 ORDER BY 1;

-- Q7 : joueurs dont le pseudo change de casse
SELECT lower(player) AS cle, array_agg(DISTINCT player) AS variantes
FROM raw.player_game GROUP BY 1 HAVING count(DISTINCT player) > 1 ORDER BY 1 LIMIT 15;

-- Q8 : armes préférées les plus fréquentes par jeu
SELECT game, "fave weapon", count(*) AS lignes
FROM (SELECT game, "fave weapon", row_number() OVER (PARTITION BY game ORDER BY count(*) DESC) AS rang
      FROM raw.player_game GROUP BY 1, 2) t
JOIN raw.player_game USING (game, "fave weapon")
WHERE rang <= 4 GROUP BY 1, 2 ORDER BY 1, 3 DESC;
