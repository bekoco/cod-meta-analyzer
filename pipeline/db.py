"""Base PostgreSQL locale et exécution des fichiers SQL.

Commandes :
  uv run python -m pipeline.db init             crée le cluster PostgreSQL local (une seule fois)
  uv run python -m pipeline.db start | stop     démarre / arrête le serveur
  uv run python -m pipeline.db load             charge les CSV bruts dans le schéma raw
  uv run python -m pipeline.db build            exécute sql/NN_*.sql puis les contrôles
  uv run python -m pipeline.db run f.sql        exécute un fichier et affiche chaque résultat

Par défaut, un PostgreSQL portable (dossier PGBIN) tourne dans .postgres/ sur le port 5433.
Pour utiliser un autre serveur (ex. Docker), définir DATABASE_URL.
"""

import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
RAW_DIR = ROOT / "data" / "raw"
PGDATA = ROOT / ".postgres"
PGBIN = Path(os.environ.get("PGBIN", Path.home() / ".local" / "pgsql" / "bin"))
PORT = 5433
DB = "cod"
URL = os.environ.get("DATABASE_URL", f"postgresql://postgres@localhost:{PORT}/{DB}")


# ── Serveur local ───────────────────────────────────────────────────────────────
def pg(tool: str, *args: str) -> None:
    subprocess.run([str(PGBIN / tool), *args], check=True)


def init() -> None:
    # Authentification « trust » limitée à la machine : base locale de travail, pas de mot de passe
    pg("initdb.exe", "-D", str(PGDATA), "-U", "postgres", "-A", "trust", "-E", "UTF8", "--locale=C")
    start()
    pg("createdb.exe", "-h", "localhost", "-p", str(PORT), "-U", "postgres", DB)


def start() -> None:
    # Sorties détachées : sinon, sous Windows, le serveur hérite de celles du terminal
    # et la commande ne rend jamais la main
    subprocess.run([str(PGBIN / "pg_ctl.exe"), "-D", str(PGDATA), "-o", f"-p {PORT} -c listen_addresses=localhost",
                    "-l", str(PGDATA / "server.log"), "-w", "start"],
                   check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"PostgreSQL démarré sur le port {PORT}")


def stop() -> None:
    pg("pg_ctl.exe", "-D", str(PGDATA), "-w", "stop")


def connect() -> psycopg.Connection:
    return psycopg.connect(URL, autocommit=True)


# ── Chargement brut ─────────────────────────────────────────────────────────────
def load() -> None:
    """Charge les 18 CSV tels quels (tout en texte) dans raw.player_game.

    Les colonnes changent selon le jeu : la table brute a l'union de toutes les colonnes,
    et une colonne absente d'un fichier reste vide. Aucune conversion ici : c'est le rôle du SQL.
    """
    manifest = {f["file"]: f for f in json.loads((RAW_DIR / "source.json").read_text(encoding="utf-8"))["files"]}
    headers = {}
    for name in manifest:
        with open(RAW_DIR / name, encoding="utf-8", newline="") as fh:
            headers[name] = next(csv.reader(fh))
    columns = list(dict.fromkeys(c for h in headers.values() for c in h))

    with connect() as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        con.execute("DROP TABLE IF EXISTS raw.player_game")
        cols_sql = ", ".join(f'"{c}" text' for c in columns)
        con.execute(f"CREATE TABLE raw.player_game (source_file text, game text, event text, {cols_sql})")
        total = 0
        for name, meta in manifest.items():
            buf = io.StringIO()
            writer = csv.writer(buf)
            with open(RAW_DIR / name, encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    writer.writerow([name, meta["game"], meta["event"], *(row.get(c, "") for c in columns)])
                    total += 1
            target = ", ".join(['source_file', 'game', 'event', *(f'"{c}"' for c in columns)])
            with con.cursor().copy(f"COPY raw.player_game ({target}) FROM STDIN WITH (FORMAT csv)") as cp:
                cp.write(buf.getvalue())
        print(f"raw.player_game : {total} lignes, {len(columns)} colonnes")


# ── Exécution du SQL ────────────────────────────────────────────────────────────
def statements(path: Path) -> list[str]:
    """Une requête se termine par « ; » en fin de ligne (commentaires « -- » ignorés)."""
    result, current = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        current.append(line)
        if line.split("--", 1)[0].rstrip().endswith(";"):
            result.append("\n".join(current))
            current = []
    result.append("\n".join(current))
    has_code = lambda s: any(l.split("--", 1)[0].strip() for l in s.splitlines())
    return [s.strip() for s in result if has_code(s)]


def label(stmt: str) -> str:
    comments = [l.strip() for l in stmt.splitlines() if l.strip().startswith("--")]
    return comments[-1] if comments else stmt.splitlines()[0]


def show(cur: psycopg.Cursor, max_rows: int = 30) -> None:
    if cur.description is None:
        return
    names = [d.name for d in cur.description]
    rows = cur.fetchall()
    fmt = lambda v: "" if v is None else (f"{v:,.2f}".replace(",", " ") if isinstance(v, float) else str(v))
    table = [names] + [[fmt(v) for v in r] for r in rows[:max_rows]]
    widths = [min(max(len(r[i]) for r in table), 45) for i in range(len(names))]
    for j, r in enumerate(table):
        print("  ".join(v[:45].ljust(w) for v, w in zip(r, widths)))
        if j == 0:
            print("  ".join("-" * w for w in widths))
    if len(rows) > max_rows:
        print(f"… {len(rows) - max_rows} lignes de plus")


def run(path: Path) -> None:
    with connect() as con:
        for stmt in statements(path):
            print(f"\n{label(stmt)[:100]}")
            show(con.execute(stmt))


def build() -> None:
    with connect() as con:
        for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
            print(path.name)
            for stmt in statements(path):
                con.execute(stmt)
        cur = con.execute("SELECT controle, ecart, ecart = 0 AS ok FROM controles")
        show(cur, max_rows=100)
        failed = con.execute("SELECT count(*) FROM controles WHERE ecart <> 0").fetchone()[0]
    if failed:
        sys.exit(f"{failed} contrôle(s) en échec : base construite mais à ne pas utiliser")
    print("Base à jour")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    match sys.argv[1:]:
        case ["init"]: init()
        case ["start"]: start()
        case ["stop"]: stop()
        case ["load"]: load()
        case ["build"]: build()
        case ["run", file]: run(Path(file))
        case _: sys.exit(__doc__)
