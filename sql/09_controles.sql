-- Contrôles qualité, rejoués à chaque build (explications : etapes/02-modele.md)
-- Chaque ligne est un test ; le build échoue si un seul écart est différent de 0.

DROP VIEW IF EXISTS controles;
CREATE VIEW controles AS
SELECT 'Aucune ligne perdue entre raw et le modèle' AS controle,
       (SELECT count(*) FROM raw.player_game) - (SELECT count(*) FROM core.fait_joueur_partie) AS ecart
UNION ALL
SELECT 'Un joueur au plus une fois par partie',
       (SELECT count(*) - count(DISTINCT (match_id, joueur)) FROM core.fait_joueur_partie)
UNION ALL
SELECT 'Deux équipes par partie',
       (SELECT count(*) FROM (SELECT match_id FROM core.fait_equipe_partie GROUP BY 1 HAVING count(*) <> 2) t)
UNION ALL
SELECT 'Effectif par équipe conforme au jeu (5 en Black Ops 4, 4 sinon)',
       (SELECT count(*) FROM core.fait_equipe_partie
        WHERE joueurs <> CASE WHEN jeu = 'Black Ops 4' THEN 5 ELSE 4 END)
UNION ALL
SELECT 'Résultats cohérents : V face à D, ou N face à N',
       (SELECT count(*) FROM core.fait_equipe_partie a JOIN core.fait_equipe_partie b
          ON b.match_id = a.match_id AND b.equipe = a.adversaire
        WHERE (a.resultat, b.resultat) NOT IN (('V', 'D'), ('D', 'V'), ('N', 'N')))
UNION ALL
SELECT 'Le vainqueur a le meilleur score',
       (SELECT count(*) FROM core.fait_equipe_partie WHERE resultat = 'V' AND score < score_adversaire)
UNION ALL
SELECT 'Chaque partie a une durée positive',
       (SELECT count(*) FROM core.fait_equipe_partie WHERE duree_s IS NULL OR duree_s <= 0)
UNION ALL
SELECT 'Une série oppose exactement deux équipes',
       (SELECT count(*) FROM (SELECT serie_id FROM core.fait_equipe_partie GROUP BY 1
                              HAVING count(DISTINCT equipe) <> 2) t)
UNION ALL
SELECT 'Clés des dimensions présentes (tournoi, carte, équipe, joueur)',
       (SELECT count(*) FROM core.fait_joueur_partie f WHERE NOT EXISTS (SELECT 1 FROM core.dim_tournoi d WHERE d.tournoi_id = f.tournoi_id))
     + (SELECT count(*) FROM core.fait_joueur_partie f WHERE NOT EXISTS (SELECT 1 FROM core.dim_carte d WHERE d.carte_id = f.carte_id))
     + (SELECT count(*) FROM core.fait_joueur_partie f WHERE NOT EXISTS (SELECT 1 FROM core.dim_equipe d WHERE d.equipe = f.equipe))
     + (SELECT count(*) FROM core.fait_joueur_partie f WHERE NOT EXISTS (SELECT 1 FROM core.dim_joueur d WHERE d.joueur = f.joueur))
UNION ALL
SELECT 'Le K/D recalculé retombe sur le K/D publié (à l''arrondi près)',
       (SELECT count(*) FROM core.fait_joueur_partie f JOIN stg.player_game p USING (match_id, joueur)
        WHERE f.kd IS NOT NULL AND abs(round(f.kd, 2) - p.kd_publie) > 0.011);
