"""
Demo Data Ingestion Job
=======================

Loads/refreshes demo seed data into Postgres (idempotent).
Run with: python -m worker.cli ingest:demo
"""

import random
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import uuid4

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.database import get_sync_session
from worker.config import settings

console = Console()


# =============================================================================
# DEMO DATA DEFINITIONS
# =============================================================================

COMPETITIONS_DATA = [
    {"name": "Premier League", "short_name": "PL", "country": "England", "tier": 1},
    {"name": "La Liga", "short_name": "LL", "country": "Spain", "tier": 1},
    {"name": "Bundesliga", "short_name": "BL", "country": "Germany", "tier": 1},
    {"name": "Serie A", "short_name": "SA", "country": "Italy", "tier": 1},
]

CLUBS_DATA = [
    {"name": "Manchester City", "short_name": "MCI", "country": "England", "city": "Manchester", "competition_idx": 0},
    {"name": "Arsenal", "short_name": "ARS", "country": "England", "city": "London", "competition_idx": 0},
    {"name": "Liverpool", "short_name": "LIV", "country": "England", "city": "Liverpool", "competition_idx": 0},
    {"name": "Chelsea", "short_name": "CHE", "country": "England", "city": "London", "competition_idx": 0},
    {"name": "Real Madrid", "short_name": "RMA", "country": "Spain", "city": "Madrid", "competition_idx": 1},
    {"name": "FC Barcelona", "short_name": "BAR", "country": "Spain", "city": "Barcelona", "competition_idx": 1},
    {"name": "Atletico Madrid", "short_name": "ATM", "country": "Spain", "city": "Madrid", "competition_idx": 1},
    {"name": "Bayern Munich", "short_name": "FCB", "country": "Germany", "city": "Munich", "competition_idx": 2},
    {"name": "Borussia Dortmund", "short_name": "BVB", "country": "Germany", "city": "Dortmund", "competition_idx": 2},
    {"name": "Juventus", "short_name": "JUV", "country": "Italy", "city": "Turin", "competition_idx": 3},
    {"name": "AC Milan", "short_name": "MIL", "country": "Italy", "city": "Milan", "competition_idx": 3},
    {"name": "Inter Milan", "short_name": "INT", "country": "Italy", "city": "Milan", "competition_idx": 3},
]

PLAYERS_DATA = [
    {"name": "Erling Haaland", "dob": "2000-07-21", "nationality": "Norway", "position": "ST", "club_idx": 0, "market_value": 180000000, "contract_months": 30},
    {"name": "Bukayo Saka", "dob": "2001-09-05", "nationality": "England", "position": "RW", "club_idx": 1, "market_value": 120000000, "contract_months": 30},
    {"name": "Jude Bellingham", "dob": "2003-06-29", "nationality": "England", "position": "CAM", "club_idx": 4, "market_value": 180000000, "contract_months": 54},
    {"name": "Lamine Yamal", "dob": "2007-07-13", "nationality": "Spain", "position": "RW", "club_idx": 5, "market_value": 150000000, "contract_months": 54},
    {"name": "Jamal Musiala", "dob": "2003-02-26", "nationality": "Germany", "position": "CAM", "club_idx": 7, "market_value": 130000000, "contract_months": 18},
    {"name": "Dusan Vlahovic", "dob": "2000-01-28", "nationality": "Serbia", "position": "ST", "club_idx": 9, "market_value": 80000000, "contract_months": 18},
    {"name": "Phil Foden", "dob": "2000-05-28", "nationality": "England", "position": "LW", "club_idx": 0, "market_value": 150000000, "contract_months": 36},
    {"name": "Martin Odegaard", "dob": "1998-12-17", "nationality": "Norway", "position": "CAM", "club_idx": 1, "market_value": 120000000, "contract_months": 42},
    {"name": "Vinicius Junior", "dob": "2000-07-12", "nationality": "Brazil", "position": "LW", "club_idx": 4, "market_value": 200000000, "contract_months": 30},
    {"name": "Pedri", "dob": "2002-11-25", "nationality": "Spain", "position": "CM", "club_idx": 5, "market_value": 100000000, "contract_months": 18},
    {"name": "Mohamed Salah", "dob": "1992-06-15", "nationality": "Egypt", "position": "RW", "club_idx": 2, "market_value": 70000000, "contract_months": 6},
    {"name": "Cole Palmer", "dob": "2002-05-06", "nationality": "England", "position": "CAM", "club_idx": 3, "market_value": 100000000, "contract_months": 48},
    {"name": "Florian Wirtz", "dob": "2003-05-03", "nationality": "Germany", "position": "CAM", "club_idx": 8, "market_value": 130000000, "contract_months": 24},
    {"name": "Rafael Leao", "dob": "1999-06-10", "nationality": "Portugal", "position": "LW", "club_idx": 10, "market_value": 90000000, "contract_months": 30},
    {"name": "Lautaro Martinez", "dob": "1997-08-22", "nationality": "Argentina", "position": "ST", "club_idx": 11, "market_value": 110000000, "contract_months": 36},
]


def generate_event_id(transfer_date, player_id, from_club_id) -> str:
    """Generate unique event ID."""
    date_str = transfer_date.strftime("%Y%m%d")
    player_short = str(player_id)[:8]
    from_short = str(from_club_id)[:8] if from_club_id else "ORIGIN"
    return f"TL-{date_str}-{player_short}-{from_short}"


def generate_snapshot_id(player_id, to_club_id, horizon, as_of) -> str:
    """Generate unique snapshot ID."""
    player_short = str(player_id)[:8]
    to_short = str(to_club_id)[:8] if to_club_id else "ANY"
    ts = as_of.strftime("%Y%m%d%H%M%S")
    return f"SNAP-{player_short}-{to_short}-H{horizon}-{ts}"


def run_demo_ingest(force: bool = False) -> dict:
    """
    Load demo data into the database.
    
    This is idempotent - it will clear existing demo data and reload.
    
    Args:
        force: If True, skip confirmation prompts
        
    Returns:
        dict with counts of created records
    """
    console.print("[bold blue]🚀 Starting demo data ingestion...[/bold blue]")
    
    with get_sync_session() as session:
        # Check if data exists
        existing_count = session.execute(
            text("SELECT COUNT(*) FROM competitions")
        ).scalar()
        
        if existing_count > 0 and not force:
            console.print(f"[yellow]Found {existing_count} existing competitions.[/yellow]")
            console.print("[yellow]Use --force to clear and reload.[/yellow]")
        
        # Clear existing data (in reverse dependency order)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Clearing existing data...", total=None)
            
            session.execute(text("TRUNCATE TABLE prediction_snapshots CASCADE"))
            session.execute(text("TRUNCATE TABLE signal_events CASCADE"))
            session.execute(text("TRUNCATE TABLE transfer_events CASCADE"))
            session.execute(text("TRUNCATE TABLE user_events CASCADE"))
            session.execute(text("TRUNCATE TABLE watchlist_items CASCADE"))
            session.execute(text("TRUNCATE TABLE watchlists CASCADE"))
            session.execute(text("TRUNCATE TABLE players CASCADE"))
            session.execute(text("TRUNCATE TABLE clubs CASCADE"))
            session.execute(text("TRUNCATE TABLE seasons CASCADE"))
            session.execute(text("TRUNCATE TABLE competitions CASCADE"))
            session.commit()
            
            progress.update(task, description="[green]Cleared existing data[/green]")
        
        # Track created IDs
        competition_ids = []
        club_ids = []
        player_ids = []
        
        counts = {
            "competitions": 0,
            "clubs": 0,
            "players": 0,
            "transfers": 0,
            "signals": 0,
            "predictions": 0,
            "user_events": 0,
        }
        
        # Create competitions
        console.print("\n[bold]Creating competitions...[/bold]")
        for comp_data in COMPETITIONS_DATA:
            comp_id = uuid4()
            session.execute(
                text("""
                    INSERT INTO competitions (id, name, short_name, country, tier, is_active)
                    VALUES (:id, :name, :short_name, :country, :tier, true)
                """),
                {"id": comp_id, **comp_data}
            )
            competition_ids.append(comp_id)
            counts["competitions"] += 1
        session.commit()
        console.print(f"  Created {counts['competitions']} competitions")
        
        # Create clubs
        console.print("\n[bold]Creating clubs...[/bold]")
        for club_data in CLUBS_DATA:
            club_id = uuid4()
            comp_id = competition_ids[club_data["competition_idx"]]
            session.execute(
                text("""
                    INSERT INTO clubs (id, name, short_name, country, city, competition_id, is_active)
                    VALUES (:id, :name, :short_name, :country, :city, :competition_id, true)
                """),
                {
                    "id": club_id,
                    "name": club_data["name"],
                    "short_name": club_data["short_name"],
                    "country": club_data["country"],
                    "city": club_data["city"],
                    "competition_id": comp_id,
                }
            )
            club_ids.append(club_id)
            counts["clubs"] += 1
        session.commit()
        console.print(f"  Created {counts['clubs']} clubs")
        
        # Create players
        console.print("\n[bold]Creating players...[/bold]")
        now = datetime.utcnow()
        for player_data in PLAYERS_DATA:
            player_id = uuid4()
            club_id = club_ids[player_data["club_idx"]]
            contract_until = now.date() + timedelta(days=player_data["contract_months"] * 30)
            
            session.execute(
                text("""
                    INSERT INTO players (id, name, date_of_birth, nationality, position, 
                                        current_club_id, contract_until, is_active)
                    VALUES (:id, :name, :dob, :nationality, :position, :club_id, :contract_until, true)
                """),
                {
                    "id": player_id,
                    "name": player_data["name"],
                    "dob": date.fromisoformat(player_data["dob"]),
                    "nationality": player_data["nationality"],
                    "position": player_data["position"],
                    "club_id": club_id,
                    "contract_until": contract_until,
                }
            )
            player_ids.append((player_id, player_data))
            counts["players"] += 1
        session.commit()
        console.print(f"  Created {counts['players']} players")
        
        # Create historical transfers
        console.print("\n[bold]Creating transfer events...[/bold]")
        for i, (player_id, player_data) in enumerate(player_ids[:5]):
            # Create a historical transfer for first 5 players
            transfer_date = now.date() - timedelta(days=random.randint(180, 730))
            from_club_idx = random.choice([j for j in range(len(club_ids)) if j != player_data["club_idx"]])
            
            event_id = generate_event_id(transfer_date, player_id, club_ids[from_club_idx])
            fee = Decimal(str(random.randint(20, 100) * 1000000))
            
            session.execute(
                text("""
                    INSERT INTO transfer_events (
                        id, event_id, player_id, from_club_id, to_club_id,
                        transfer_type, transfer_date, fee_amount, fee_currency,
                        fee_amount_eur, fee_type, source, source_confidence, is_superseded
                    ) VALUES (
                        :id, :event_id, :player_id, :from_club_id, :to_club_id,
                        'permanent', :transfer_date, :fee, 'EUR',
                        :fee, 'confirmed', 'official', 1.0, false
                    )
                """),
                {
                    "id": uuid4(),
                    "event_id": event_id,
                    "player_id": player_id,
                    "from_club_id": club_ids[from_club_idx],
                    "to_club_id": club_ids[player_data["club_idx"]],
                    "transfer_date": transfer_date,
                    "fee": fee,
                }
            )
            counts["transfers"] += 1
        session.commit()
        console.print(f"  Created {counts['transfers']} transfers")
        
        # Create signals
        console.print("\n[bold]Creating signal events...[/bold]")
        signal_types = [
            ("market_value", "value_num"),
            ("contract_months_remaining", "value_num"),
            ("goals_last_10", "value_num"),
            ("assists_last_10", "value_num"),
            ("social_mention_velocity", "value_num"),
        ]
        
        for player_id, player_data in player_ids:
            for days_ago in [0, 7, 14, 30, 60, 90]:
                effective_from = now - timedelta(days=days_ago)
                
                for signal_type, value_col in signal_types:
                    if signal_type == "market_value":
                        value = Decimal(str(player_data["market_value"])) * Decimal(str(1 - days_ago * 0.001))
                    elif signal_type == "contract_months_remaining":
                        value = Decimal(str(max(0, player_data["contract_months"] - days_ago // 30)))
                    elif signal_type == "goals_last_10":
                        value = Decimal(str(random.randint(0, 8)))
                    elif signal_type == "assists_last_10":
                        value = Decimal(str(random.randint(0, 5)))
                    else:
                        value = Decimal(str(random.randint(10, 1000)))
                    
                    session.execute(
                        text(f"""
                            INSERT INTO signal_events (
                                id, entity_type, player_id, signal_type,
                                {value_col}, source, confidence, observed_at, effective_from
                            ) VALUES (
                                :id, 'player', :player_id, :signal_type,
                                :value, 'demo_seed', 0.9, :observed_at, :effective_from
                            )
                        """),
                        {
                            "id": uuid4(),
                            "player_id": player_id,
                            "signal_type": signal_type,
                            "value": value,
                            "observed_at": effective_from,
                            "effective_from": effective_from,
                        }
                    )
                    counts["signals"] += 1
        session.commit()
        console.print(f"  Created {counts['signals']} signals")
        
        # Create predictions
        console.print("\n[bold]Creating prediction snapshots...[/bold]")
        for player_id, player_data in player_ids:
            current_club_idx = player_data["club_idx"]
            
            # Generate predictions for 3 random destination clubs
            candidate_clubs = random.sample(
                [i for i in range(len(club_ids)) if i != current_club_idx],
                min(3, len(club_ids) - 1)
            )
            
            for to_club_idx in candidate_clubs:
                for horizon in [30, 90, 180]:
                    probability = Decimal(str(round(random.uniform(0.05, 0.45), 4)))
                    snapshot_id = generate_snapshot_id(player_id, club_ids[to_club_idx], horizon, now)
                    
                    session.execute(
                        text("""
                            INSERT INTO prediction_snapshots (
                                id, snapshot_id, model_version, model_name,
                                player_id, from_club_id, to_club_id,
                                horizon_days, probability, drivers_json,
                                as_of, window_start, window_end
                            ) VALUES (
                                :id, :snapshot_id, 'v1.0.0', 'demo_model',
                                :player_id, :from_club_id, :to_club_id,
                                :horizon, :probability, :drivers,
                                :as_of, :window_start, :window_end
                            )
                        """),
                        {
                            "id": uuid4(),
                            "snapshot_id": snapshot_id,
                            "player_id": player_id,
                            "from_club_id": club_ids[current_club_idx],
                            "to_club_id": club_ids[to_club_idx],
                            "horizon": horizon,
                            "probability": probability,
                            "drivers": '{"contract_months_remaining": 0.3, "market_value": 0.2, "club_interest": 0.15}',
                            "as_of": now,
                            "window_start": now.date(),
                            "window_end": now.date() + timedelta(days=horizon),
                        }
                    )
                    counts["predictions"] += 1
        session.commit()
        console.print(f"  Created {counts['predictions']} predictions")
        
        # Create user events
        console.print("\n[bold]Creating user events...[/bold]")
        event_types = ["player_view", "search", "page_view"]
        for _ in range(50):
            player_id, _ = random.choice(player_ids)
            occurred_at = now - timedelta(hours=random.randint(0, 72))
            
            session.execute(
                text("""
                    INSERT INTO user_events (
                        id, user_anon_id, session_id, event_type,
                        player_id, occurred_at, device_type
                    ) VALUES (
                        :id, :user_anon_id, :session_id, :event_type,
                        :player_id, :occurred_at, :device_type
                    )
                """),
                {
                    "id": uuid4(),
                    "user_anon_id": f"anon_{random.randint(1000, 9999)}",
                    "session_id": f"sess_{random.randint(10000, 99999)}",
                    "event_type": random.choice(event_types),
                    "player_id": player_id,
                    "occurred_at": occurred_at,
                    "device_type": random.choice(["desktop", "mobile", "tablet"]),
                }
            )
            counts["user_events"] += 1
        session.commit()
        console.print(f"  Created {counts['user_events']} user events")
        
        # Refresh materialized view
        console.print("\n[bold]Refreshing materialized view...[/bold]")
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW player_market_view"))
            session.commit()
            console.print("  [green]Refreshed player_market_view[/green]")
        except Exception as e:
            console.print(f"  [yellow]Could not refresh view: {e}[/yellow]")
        
        console.print("\n[bold green]✅ Demo data ingestion complete![/bold green]")
        console.print(f"\n[bold]Summary:[/bold]")
        for key, count in counts.items():
            console.print(f"  • {key}: {count}")
        
        return counts
