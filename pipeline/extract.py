"""Extraction : données officielles de la Call of Duty World League (Activision).

Activision a publié en 2017-2019 les données complètes de ses tournois (dépôt GitHub
« Activision/cwl-data », licence BSD 3-Clause), captées en direct sur les consoles des LAN,
puis nettoyées et validées. Le dépôt d'origine n'est plus en ligne ; on lit une copie
conforme (fork) figée au dernier commit de l'auteur de la publication, le 28 août 2019.

Usage : uv run python -m pipeline.extract
"""

import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MIRROR = "whiki/cwl-data"
COMMIT = "5b7eb907"  # « the *last* data », Justin Shacklette (Activision), 2019-08-28
BASE = f"https://raw.githubusercontent.com/{MIRROR}/{COMMIT}/data"

# Un fichier par tournoi. Le jeu change chaque saison : on le note pour ne pas mélanger.
EVENTS = {
    "data-2017-08-13-champs.csv": ("Infinite Warfare", "CWL Champs 2017"),
    "data-2017-12-10-dallas.csv": ("WWII", "CWL Dallas"),
    "data-2018-01-14-neworleans.csv": ("WWII", "CWL New Orleans"),
    "data-2018-03-11-atlanta.csv": ("WWII", "CWL Atlanta"),
    "data-2018-04-01-birmingham.csv": ("WWII", "CWL Birmingham"),
    "data-2018-04-08-proleague1.csv": ("WWII", "CWL Pro League Stage 1"),
    "data-2018-04-19-relegation.csv": ("WWII", "CWL Pro League Relegation"),
    "data-2018-04-22-seattle.csv": ("WWII", "CWL Seattle"),
    "data-2018-06-17-anaheim.csv": ("WWII", "CWL Anaheim 2018"),
    "data-2018-07-29-proleague2.csv": ("WWII", "CWL Pro League Stage 2"),
    "data-2018-08-19-champs.csv": ("WWII", "CWL Champs 2018"),
    "data-2019-01-20-proleague-qual.csv": ("Black Ops 4", "CWL Pro League Qualifier"),
    "data-2019-03-17-fortworth.csv": ("Black Ops 4", "CWL Fort Worth"),
    "data-2019-05-05-london.csv": ("Black Ops 4", "CWL London"),
    "data-2019-06-16-anaheim.csv": ("Black Ops 4", "CWL Anaheim 2019"),
    "data-2019-07-05-proleague.csv": ("Black Ops 4", "CWL Pro League 2019"),
    "data-2019-07-21-proleague-finals.csv": ("Black Ops 4", "CWL Pro League Finals"),
    "data-2019-08-18-champs.csv": ("Black Ops 4", "CWL Champs 2019"),
}

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def download(name: str) -> bytes:
    with urllib.request.urlopen(f"{BASE}/{name}", timeout=60) as resp:
        return resp.read()


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, (game, event) in EVENTS.items():
        content = download(name)
        (RAW_DIR / name).write_bytes(content)
        rows = content.count(b"\n") - 1
        manifest.append({"file": name, "game": game, "event": event, "rows": rows,
                         "sha256": hashlib.sha256(content).hexdigest()})
        print(f"{name:<40} {rows:>6} lignes  {game}")
    (RAW_DIR / "README-activision.md").write_bytes(download("README.md"))

    # Traçabilité : d'où viennent les fichiers, quand, et leur empreinte
    (RAW_DIR / "source.json").write_text(json.dumps({
        "publisher": "Activision — Call of Duty World League data release",
        "original_repository": "https://github.com/Activision/cwl-data (hors ligne)",
        "mirror": f"https://github.com/{MIRROR}", "commit": COMMIT,
        "licence": "BSD 3-Clause",
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": manifest,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(manifest)} fichiers, {sum(f['rows'] for f in manifest)} lignes -> {RAW_DIR}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
