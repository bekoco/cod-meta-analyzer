"""Tableau de bord HTML interactif, généré à partir des vues SQL (schéma kpi).

Un seul fichier (docs/index.html), lisible dans n'importe quel navigateur et publiable
sur GitHub Pages. Les graphiques sont interactifs (survol, zoom, légende cliquable).

Usage : uv run python -m pipeline.dashboard   (après  uv run python -m pipeline.db build)
"""

import html
import sys
from datetime import date
from decimal import Decimal

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pipeline.db import ROOT, connect

OUT = ROOT / "docs" / "index.html"
JEUX = ["Infinite Warfare", "WWII", "Black Ops 4"]  # ordre chronologique des saisons
ANNEE = {"Infinite Warfare": "2017", "WWII": "2018", "Black Ops 4": "2019"}
# Palette catégorielle validée (contraste et daltonisme), couleurs dans un ordre fixe
COULEURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
COULEUR_JEU = dict(zip(JEUX, COULEURS))
ENCRE, ENCRE_2, GRILLE = "#1d1d1b", "#5b5a56", "#e6e5e1"


def q(sql: str) -> pd.DataFrame:
    with connect() as con:
        cur = con.execute(sql)
        df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    # PostgreSQL renvoie les « numeric » en Decimal : on les convertit en nombres flottants
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, Decimal)).any():
            df[c] = df[c].astype(float)
    return df


def style(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color=ENCRE),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        separators=", ",  # virgule décimale, espace pour les milliers
        legend=dict(orientation="h", y=1.08, x=0, title=None),
        hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(gridcolor=GRILLE, zeroline=False, linecolor=GRILLE)
    fig.update_yaxes(gridcolor=GRILLE, zeroline=False, linecolor=GRILLE)
    return fig


def to_html(fig: go.Figure) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False, "responsive": True})


# ── Graphiques ─────────────────────────────────────────────────────────────────
def fig_meta() -> go.Figure:
    df = q("""
        SELECT jeu, arme, round(100.0 * sum(utilisations) / sum(sum(utilisations)) OVER (PARTITION BY jeu), 1) AS part
        FROM kpi.meta_armes GROUP BY jeu, arme""")
    fig = make_subplots(rows=1, cols=3, subplot_titles=[f"{j} ({ANNEE[j]})" for j in JEUX], horizontal_spacing=0.12)
    for i, jeu in enumerate(JEUX, start=1):
        d = df[(df.jeu == jeu) & (df.part >= 1)].nlargest(5, "part").sort_values("part")
        fig.add_bar(x=d.part, y=d.arme, orientation="h", marker_color=COULEUR_JEU[jeu], showlegend=False,
                    text=[f"{v:.0f} %" for v in d.part], textposition="outside", cliponaxis=False,
                    hovertemplate="%{y} : %{x:.1f} % des joueurs<extra></extra>", row=1, col=i)
    fig.update_xaxes(range=[0, 75], ticksuffix=" %", showticklabels=False, showgrid=False)
    for a in fig.layout.annotations:
        a.font = dict(size=14, color=ENCRE)
    return style(fig, 300)


def fig_evolution() -> go.Figure:
    df = q("SELECT jeu, date_fin, tournoi, arme, part_pct FROM kpi.meta_armes_evolution ORDER BY date_fin")
    jeux = ["WWII", "Black Ops 4"]  # Infinite Warfare : un seul tournoi, pas d'évolution
    fig = make_subplots(rows=1, cols=2, subplot_titles=[f"{j} ({ANNEE[j]})" for j in jeux],
                        shared_yaxes=True, horizontal_spacing=0.06)
    for i, jeu in enumerate(jeux, start=1):
        d = df[df.jeu == jeu]
        tournois = d.drop_duplicates("tournoi").sort_values("date_fin").tournoi.tolist()
        top = d.groupby("arme").part_pct.mean().nlargest(3).index
        # Écarter les étiquettes de fin de courbe trop proches (moins de 5 points d'écart)
        fins = {a: float(d[d.arme == a].set_index("tournoi").part_pct.reindex(tournois, fill_value=0).iloc[-1]) for a in top}
        decalage, precedent = {}, None
        for a in sorted(fins, key=fins.get, reverse=True):
            decalage[a] = 0 if precedent is None or fins[precedent] - fins[a] >= 5 else decalage[precedent] - 16
            precedent = a
        for k, arme in enumerate(top):
            # Une arme absente d'un tournoi y pèse 0 %, ce n'est pas une valeur manquante
            s = d[d.arme == arme].set_index("tournoi").part_pct.reindex(tournois, fill_value=0)
            fig.add_scatter(x=tournois, y=s.values, name=arme, mode="lines+markers", showlegend=False,
                            line=dict(width=2, color=COULEURS[k]), marker=dict(size=8),
                            hovertemplate="%{x}<br>" + arme + " : %{y:.1f} %<extra></extra>", row=1, col=i)
            # Étiquette directe au bout de la courbe, à la place d'une légende
            fig.add_annotation(x=tournois[-1], y=float(s.values[-1]), text=f"<b>{arme}</b>", xanchor="left",
                               xshift=8, yshift=decalage[arme] + (8 if decalage[arme] == 0 and any(v < 0 for v in decalage.values()) else 0),
                               showarrow=False, font=dict(size=12, color=COULEURS[k]), row=1, col=i)
    fig.update_yaxes(ticksuffix=" %", range=[0, 70])
    fig.update_xaxes(tickangle=-35, tickfont=dict(size=11))
    for a in fig.layout.annotations[:2]:
        a.font = dict(size=14, color=ENCRE)
    fig.update_layout(margin=dict(r=90))
    style(fig, 440)
    fig.update_layout(margin=dict(l=10, r=95, t=30, b=10))
    return fig


def fig_snd() -> go.Figure:
    df = q("SELECT jeu, part_premiers_kills, parties, taux_victoire_pct FROM kpi.snd_premiers_kills")
    ordre = ["< 30 %", "30-45 %", "45-55 %", "55-70 %", "> 70 %"]
    fig = go.Figure()
    for jeu in JEUX:
        d = df[df.jeu == jeu].set_index("part_premiers_kills").reindex(ordre)
        fig.add_bar(x=ordre, y=d.taux_victoire_pct, name=f"{jeu} ({ANNEE[jeu]})", marker_color=COULEUR_JEU[jeu],
                    customdata=d.parties, hovertemplate="%{x} des premiers kills : %{y:.0f} % de victoires"
                                                        "<br>%{customdata} parties<extra></extra>")
    fig.add_hline(y=50, line_dash="dot", line_color=ENCRE_2, annotation_text="50 % : pile ou face",
                  annotation_position="top left", annotation_font_color=ENCRE_2)
    fig.update_yaxes(ticksuffix=" %", range=[0, 100], title="Taux de victoire")
    fig.update_xaxes(title="Part des premiers kills de la partie prise par l'équipe")
    fig.update_layout(barmode="group", bargap=0.25)
    return style(fig, 380)


def fig_facteurs() -> go.Figure:
    df = q("SELECT jeu, mode, facteur, parties, taux_victoire_pct FROM kpi.facteurs_victoire")
    df["etiquette"] = df["mode"] + " · " + df["facteur"].str.replace("Plus d'", "", regex=False) \
        .str.replace("Plus de ", "", regex=False).str.capitalize()
    ordre = (df.groupby("etiquette").taux_victoire_pct.mean().sort_values().index.tolist())
    fig = go.Figure()
    for jeu in JEUX:
        d = df[df.jeu == jeu].set_index("etiquette").reindex(ordre)
        fig.add_bar(y=ordre, x=d.taux_victoire_pct, orientation="h", name=f"{jeu} ({ANNEE[jeu]})",
                    marker_color=COULEUR_JEU[jeu], customdata=d.parties,
                    hovertemplate="%{y}<br>L'équipe qui domine gagne %{x:.0f} % du temps"
                                  "<br>%{customdata} parties<extra></extra>")
    fig.add_vline(x=50, line_dash="dot", line_color=ENCRE_2)
    fig.update_xaxes(ticksuffix=" %", range=[40, 100])
    fig.update_layout(barmode="group", bargap=0.3)
    return style(fig, 460)


# ── Tableaux ───────────────────────────────────────────────────────────────────
def fmt(v, dec=1, suffix=""):
    if pd.isna(v):
        return "—"
    return f"{v:,.{dec}f}".replace(",", " ").replace(".", ",") + suffix


def table_joueurs(jeu: str) -> str:
    df = q(f"""SELECT joueur, equipe, parties, kd, kills_10min, taux_victoire_pct, snd_premier_kill_par_manche_pct
               FROM kpi.joueurs WHERE jeu = '{jeu}' ORDER BY kd DESC LIMIT 10""")
    rows = "".join(
        f"<tr><td>{i}</td><td><b>{html.escape(r.joueur)}</b></td><td>{html.escape(r.equipe)}</td>"
        f"<td class=n>{r.parties}</td><td class=n>{fmt(r.kd, 2)}</td><td class=n>{fmt(r.kills_10min)}</td>"
        f"<td class=n>{fmt(r.taux_victoire_pct, 0, ' %')}</td><td class=n>{fmt(r.snd_premier_kill_par_manche_pct, 1, ' %')}</td></tr>"
        for i, r in enumerate(df.itertuples(), start=1))
    return ("<table><thead><tr><th>#</th><th>Joueur</th><th>Équipe</th><th class=n>Parties</th><th class=n>K/D</th>"
            "<th class=n>Kills / 10 min</th><th class=n>Victoires</th><th class=n>1<sup>er</sup> kill S&amp;D</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>")


def table_equipes(jeu: str, min_series: int) -> str:
    df = q(f"""SELECT equipe, series, taux_victoire_series_pct, parties, taux_victoire_parties_pct
               FROM kpi.equipes WHERE jeu = '{jeu}' AND series >= {min_series}
               ORDER BY taux_victoire_series_pct DESC, series DESC LIMIT 8""")
    rows = "".join(
        f"<tr><td>{i}</td><td><b>{html.escape(r.equipe)}</b></td><td class=n>{r.series}</td>"
        f"<td class=n>{fmt(r.taux_victoire_series_pct, 0, ' %')}</td><td class=n>{r.parties}</td>"
        f"<td class=n>{fmt(r.taux_victoire_parties_pct, 0, ' %')}</td></tr>"
        for i, r in enumerate(df.itertuples(), start=1))
    return ("<table><thead><tr><th>#</th><th>Équipe</th><th class=n>Séries</th><th class=n>Séries gagnées</th>"
            f"<th class=n>Parties</th><th class=n>Parties gagnées</th></tr></thead><tbody>{rows}</tbody></table>")


def onglets(prefix: str, contenus: dict[str, str]) -> str:
    boutons = "".join(f'<button role="tab" aria-selected="{str(i == 0).lower()}" data-target="{prefix}-{i}">{html.escape(t)}</button>'
                      for i, t in enumerate(contenus))
    panneaux = "".join(f'<div role="tabpanel" id="{prefix}-{i}"{" hidden" if i else ""}>{c}</div>'
                       for i, c in enumerate(contenus.values()))
    return f'<div class="onglets"><div role="tablist">{boutons}</div>{panneaux}</div>'


# ── Page ───────────────────────────────────────────────────────────────────────
def chiffres() -> dict:
    r = q("""SELECT count(DISTINCT match_id) AS parties, count(DISTINCT joueur) AS joueurs,
                    count(DISTINCT tournoi_id) AS tournois, count(*) AS lignes FROM core.fait_joueur_partie""").iloc[0]
    s = q("SELECT count(*) AS series FROM core.fait_serie").iloc[0]
    return {"parties": int(r.parties), "joueurs": int(r.joueurs), "tournois": int(r.tournois),
            "lignes": int(r.lignes), "series": int(s.series)}


CSS = """
:root{--encre:#1d1d1b;--encre2:#5b5a56;--fond:#fbfaf7;--carte:#ffffff;--trait:#e6e5e1;--accent:#2a78d6}
*{box-sizing:border-box}body{margin:0;background:var(--fond);color:var(--encre);font:16px/1.55 Inter,"Segoe UI",system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:40px 20px 80px}
header .sur{font:600 12px/1 ui-monospace,Consolas,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--encre2)}
h1{font-size:clamp(30px,5vw,46px);line-height:1.08;margin:12px 0 14px;letter-spacing:-.02em}
.chapo{font-size:18px;color:var(--encre2);max-width:760px;margin:0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:32px 0 8px}
.kpi{background:var(--carte);border:1px solid var(--trait);padding:16px 18px}
.kpi b{display:block;font-size:30px;letter-spacing:-.02em}.kpi span{font-size:13px;color:var(--encre2)}
section{background:var(--carte);border:1px solid var(--trait);padding:26px 26px 18px;margin-top:22px}
section h2{font-size:22px;margin:0 0 6px;letter-spacing:-.01em}
.lecture{color:var(--encre2);margin:0 0 10px;max-width:880px}
.lecture strong{color:var(--encre)}
table{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0 14px}
th,td{padding:8px 10px;border-bottom:1px solid var(--trait);text-align:left}th{font-size:12px;color:var(--encre2);font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.onglets [role=tablist]{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 4px}
.onglets button{font:inherit;font-size:14px;padding:6px 14px;border:1px solid var(--trait);background:var(--fond);cursor:pointer}
.onglets button[aria-selected=true]{background:var(--encre);color:#fff;border-color:var(--encre)}
.deux{display:grid;grid-template-columns:1fr 1fr;gap:22px}@media(max-width:820px){.deux{grid-template-columns:1fr}section{padding:20px 14px 10px}}
.note{font-size:14px;color:var(--encre2)}.note li{margin-bottom:6px}
footer{margin-top:28px;font-size:13px;color:var(--encre2)}a{color:var(--accent)}
"""

JS = """
document.querySelectorAll('.onglets').forEach(function(o){
  o.querySelectorAll('[role=tab]').forEach(function(b){
    b.addEventListener('click',function(){
      o.querySelectorAll('[role=tab]').forEach(function(x){x.setAttribute('aria-selected','false')});
      o.querySelectorAll('[role=tabpanel]').forEach(function(p){p.hidden=true});
      b.setAttribute('aria-selected','true');document.getElementById(b.dataset.target).hidden=false;
      window.dispatchEvent(new Event('resize'));
    });
  });
});
"""


def page() -> str:
    c = chiffres()
    nb = lambda n: f"{n:,}".replace(",", " ")
    joueurs = onglets("j", {f"{j} ({ANNEE[j]})": table_joueurs(j) for j in reversed(JEUX)})
    equipes = onglets("e", {f"{j} ({ANNEE[j]})": table_equipes(j, 20 if j != "Infinite Warfare" else 5)
                            for j in reversed(JEUX)})
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>COD Meta Analyzer</title>
<meta name="description" content="Analyse des données officielles de la Call of Duty World League 2017-2019 : méta des armes, facteurs de victoire, joueurs et équipes.">
<script src="https://cdn.plot.ly/plotly-3.0.1.min.js" charset="utf-8"></script>
<style>{CSS}</style></head><body><main>
<header>
  <div class="sur">Projet data · Call of Duty World League 2017-2019</div>
  <h1>COD Meta Analyzer</h1>
  <p class="chapo">Quelles armes dominent la compétition, qu'est-ce qui fait gagner une partie, et quels joueurs
  et équipes sortent du lot ? Analyse des données officielles publiées par Activision, chargées dans PostgreSQL
  et interrogées en SQL.</p>
</header>
<div class="kpis">
  <div class="kpi"><b>{nb(c['parties'])}</b><span>parties</span></div>
  <div class="kpi"><b>{nb(c['series'])}</b><span>séries (matchs en 5 parties)</span></div>
  <div class="kpi"><b>{nb(c['joueurs'])}</b><span>joueurs professionnels</span></div>
  <div class="kpi"><b>{c['tournois']}</b><span>tournois, 3 jeux</span></div>
  <div class="kpi"><b>{nb(c['lignes'])}</b><span>lignes joueur × partie</span></div>
</div>

<section><h2>Quelles armes dominent ?</h2>
<p class="lecture">Part des joueurs dont c'est l'arme principale, toutes parties confondues. Chaque saison a sa
<strong>méta</strong> : deux armes couvrent les trois quarts des choix. Pourtant, chaque arme dominante gagne
environ une partie sur deux : tout le monde la joue, elle ne départage donc personne.</p>
{to_html(fig_meta())}</section>

<section><h2>La méta bouge pendant la saison</h2>
<p class="lecture">En Black Ops 4, le <strong>Maddox RFB</strong> passe d'une arme sur deux à une sur trois, et le
<strong>Saug 9mm</strong> le dépasse au championnat. En WWII, le <strong>FG 42</strong>, joué à 46 % au premier
tournoi, disparaît presque ensuite (probablement une mise à jour d'équilibrage du jeu).</p>
{to_html(fig_evolution())}</section>

<section><h2>Search &amp; Destroy : le premier kill fait la différence</h2>
<p class="lecture">Dans ce mode, chaque manche se joue sans réapparition. L'équipe qui prend <strong>plus de 70 %
des premiers kills</strong> d'une partie la gagne <strong>78 à 87 %</strong> du temps, contre 13 à 22 % sous 30 %.
Chaque partie compte deux fois (une par équipe) : le graphique est donc symétrique, et la tranche 45-55 % vaut 50 % par
construction.</p>
{to_html(fig_snd())}</section>

<section><h2>Qu'est-ce qui fait gagner, selon le mode ?</h2>
<p class="lecture">Part des parties gagnées par l'équipe qui domine l'indicateur. 50 % : l'indicateur ne dit rien.
<strong>Attention</strong> : en Hardpoint, le score <em>est</em> le temps dans la zone, le lien est donc presque
automatique. Et ce sont des corrélations : gagner fait aussi faire plus d'éliminations.</p>
{to_html(fig_facteurs())}</section>

<section><h2>Les joueurs</h2>
<p class="lecture">Les 10 meilleurs ratios éliminations / morts (K/D global = kills totaux / morts totales), parmi
les joueurs avec au moins 100 parties dans la saison (25 pour Infinite Warfare, qui ne compte qu'un tournoi).</p>
{joueurs}</section>

<section><h2>Les équipes</h2>
<p class="lecture">Classement par part des séries gagnées (séries complètes seulement), parmi les équipes avec au
moins 20 séries (5 pour Infinite Warfare).</p>
{equipes}</section>

<section><h2>Méthode et limites</h2><ul class="note">
<li><strong>Données</strong> : publication officielle d'Activision (2017-2019), captée en direct sur les consoles
des tournois. 18 tournois, 3 jeux. Un jeu = une saison : on ne compare jamais deux jeux entre eux.</li>
<li><strong>Chaîne</strong> : CSV bruts → PostgreSQL (schéma raw) → nettoyage SQL (stg) → modèle en étoile (core)
→ indicateurs (kpi) → cette page, générée en Python. 10 contrôles qualité automatiques.</li>
<li><strong>Données manquantes</strong> documentées par Activision : environ 80 parties perdues à Birmingham 2018,
317 parties sur environ 400 au qualificatif 2019. 44 séries incomplètes sont exclues des classements d'équipes.</li>
<li><strong>Corrections</strong> : un même club écrit de deux façons (Team EnVyUs / Team Envy…) est fusionné ;
le gagnant d'une partie reconstituée à la main est déduit du score ; 6 égalités sont exclues des taux de victoire.</li>
<li>L'« arme préférée » est l'arme principale la plus utilisée par le joueur dans la partie (370 lignes sans arme).</li>
</ul></section>
<footer>Généré le {date.today().strftime('%d/%m/%Y')} · Pierre Bekono ·
<a href="https://github.com/bekoco/cod-meta-analyzer">code source</a></footer>
</main><script>{JS}</script></body></html>"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page(), encoding="utf-8")
    print(f"Tableau de bord : {OUT} ({OUT.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
