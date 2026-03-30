"""
Seed the leagues table with supported soccer leagues from the-odds-api.com.
Run once after setting up the database:

    python seed_leagues.py

Safe to re-run — skips any leagues already present.

Notes:
  - soccer_germany_bundesliga appears twice in source data — kept once as "Bundesliga"
  - soccer_spain_segunda_division appears twice in source data — kept once as "La Liga 2"
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal, engine, Base
from app.models import League

LEAGUES = [
    {"key": "soccer_belgium_first_div",                 "name": "Belgium First Div",                  "country": "Belgium"},
    {"key": "soccer_denmark_superliga",                 "name": "Denmark Superliga",                  "country": "Denmark"},
    {"key": "soccer_efl_champ",                         "name": "Championship",                       "country": "England"},
    {"key": "soccer_england_efl_cup",                   "name": "EFL Cup",                            "country": "England"},
    {"key": "soccer_england_league1",                   "name": "League 1",                           "country": "England"},
    {"key": "soccer_england_league2",                   "name": "League 2",                           "country": "England"},
    {"key": "soccer_epl",                               "name": "EPL",                                "country": "England"},
    {"key": "soccer_fa_cup",                            "name": "FA Cup",                             "country": "England"},
    {"key": "soccer_fifa_club_world_cup",               "name": "FIFA Club World Cup",                "country": "International"},
    {"key": "soccer_fifa_world_cup_qualifiers_europe",  "name": "FIFA World Cup Qualifiers - Europe", "country": "International"},
    {"key": "soccer_france_ligue_one",                  "name": "Ligue 1",                            "country": "France"},
    {"key": "soccer_germany_bundesliga",                "name": "Bundesliga",                         "country": "Germany"},
    {"key": "soccer_germany_bundesliga2",               "name": "Bundesliga 2",                       "country": "Germany"},
    {"key": "soccer_greece_super_league",               "name": "Super League",                       "country": "Greece"},
    {"key": "soccer_italy_serie_a",                     "name": "Serie A",                            "country": "Italy"},
    {"key": "soccer_italy_serie_b",                     "name": "Serie B",                            "country": "Italy"},
    {"key": "soccer_japan_j_league",                    "name": "J League",                           "country": "Japan"},
    {"key": "soccer_korea_kleague1",                    "name": "K League 1",                         "country": "South Korea"},
    {"key": "soccer_mexico_ligamx",                     "name": "Liga MX",                            "country": "Mexico"},
    {"key": "soccer_netherlands_eredivisie",            "name": "Dutch Eredivisie",                   "country": "Netherlands"},
    {"key": "soccer_norway_eliteserien",                "name": "Eliteserien",                        "country": "Norway"},
    {"key": "soccer_poland_ekstraklasa",                "name": "Ekstraklasa",                        "country": "Poland"},
    {"key": "soccer_portugal_primeira_liga",            "name": "Primeira Liga",                      "country": "Portugal"},
    {"key": "soccer_spain_la_liga",                     "name": "La Liga",                            "country": "Spain"},
    {"key": "soccer_spain_segunda_division",            "name": "La Liga 2",                          "country": "Spain"},
    {"key": "soccer_spl",                               "name": "Premiership",                        "country": "Scotland"},
    {"key": "soccer_sweden_allsvenskan",                "name": "Allsvenskan",                        "country": "Sweden"},
    {"key": "soccer_turkey_super_league",               "name": "Turkey Super League",                "country": "Turkey"},
    {"key": "soccer_uefa_champs_league",                "name": "UEFA Champions League",              "country": "Europe"},
    {"key": "soccer_uefa_europa_conference_league",     "name": "UEFA Europa Conference League",      "country": "Europe"},
    {"key": "soccer_uefa_europa_league",                "name": "UEFA Europa League",                 "country": "Europe"},
    {"key": "soccer_uefa_nations_league",               "name": "UEFA Nations League",                "country": "Europe"},
    {"key": "soccer_usa_mls",                           "name": "MLS",                                "country": "USA"},
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing_keys = {row.key for row in db.query(League.key).all()}
        to_insert = [l for l in LEAGUES if l["key"] not in existing_keys]

        if not to_insert:
            print("Nothing to seed — all leagues already present.")
            return

        for l in to_insert:
            db.add(League(name=l["name"], key=l["key"], country=l["country"]))

        db.commit()
        print(f"Seeded {len(to_insert)} league(s).")

        if existing_keys:
            print(f"Skipped {len(existing_keys)} already present.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
