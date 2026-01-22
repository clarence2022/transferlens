#!/usr/bin/env python3
"""
TransferLens Seed Script
========================

Seeds the database with demo data:
- 4 competitions
- 2 seasons per competition
- 6 clubs
- 10 players
- 20 transfer_events
- 200 signal_events
- 100 prediction_snapshots
- Sample user_events and watchlists

Run with: python scripts/seed.py
"""

import asyncio
import random
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models
import sys
sys.path.insert(0, '/home/claude/transferlens/apps/api')

from app.models import (
    Competition, Season, Club, Player, TransferEvent, SignalEvent,
    PredictionSnapshot, UserEvent, Watchlist, WatchlistItem, DataCorrection,
    EntityType, SignalTypeEnum, TransferType, FeeType, UserEventType
)
from app.config import settings


# =============================================================================
# SEED DATA DEFINITIONS
# =============================================================================

COMPETITIONS_DATA = [
    {"name": "Premier League", "short_name": "PL", "country": "England", "tier": 1, "transfermarkt_id": "GB1"},
    {"name": "La Liga", "short_name": "LL", "country": "Spain", "tier": 1, "transfermarkt_id": "ES1"},
    {"name": "Bundesliga", "short_name": "BL", "country": "Germany", "tier": 1, "transfermarkt_id": "L1"},
    {"name": "Serie A", "short_name": "SA", "country": "Italy", "tier": 1, "transfermarkt_id": "IT1"},
]

CLUBS_DATA = [
    {"name": "Manchester City", "short_name": "MCI", "country": "England", "city": "Manchester", 
     "stadium": "Etihad Stadium", "stadium_capacity": 53400, "founded_year": 1880,
     "primary_color": "#6CABDD", "secondary_color": "#1C2C5B", "competition_idx": 0},
    {"name": "Arsenal", "short_name": "ARS", "country": "England", "city": "London",
     "stadium": "Emirates Stadium", "stadium_capacity": 60704, "founded_year": 1886,
     "primary_color": "#EF0107", "secondary_color": "#FFFFFF", "competition_idx": 0},
    {"name": "Real Madrid", "short_name": "RMA", "country": "Spain", "city": "Madrid",
     "stadium": "Santiago Bernabéu", "stadium_capacity": 81044, "founded_year": 1902,
     "primary_color": "#FFFFFF", "secondary_color": "#00529F", "competition_idx": 1},
    {"name": "FC Barcelona", "short_name": "BAR", "country": "Spain", "city": "Barcelona",
     "stadium": "Spotify Camp Nou", "stadium_capacity": 99354, "founded_year": 1899,
     "primary_color": "#A50044", "secondary_color": "#004D98", "competition_idx": 1},
    {"name": "Bayern Munich", "short_name": "FCB", "country": "Germany", "city": "Munich",
     "stadium": "Allianz Arena", "stadium_capacity": 75000, "founded_year": 1900,
     "primary_color": "#DC052D", "secondary_color": "#FFFFFF", "competition_idx": 2},
    {"name": "Juventus", "short_name": "JUV", "country": "Italy", "city": "Turin",
     "stadium": "Allianz Stadium", "stadium_capacity": 41507, "founded_year": 1897,
     "primary_color": "#000000", "secondary_color": "#FFFFFF", "competition_idx": 3},
]

PLAYERS_DATA = [
    {"name": "Erling Haaland", "full_name": "Erling Braut Haaland", "dob": "2000-07-21",
     "nationality": "Norway", "position": "ST", "foot": "left", "height_cm": 195, "weight_kg": 88,
     "club_idx": 0, "shirt_number": 9, "contract_until": "2027-06-30", "market_value": 180000000},
    {"name": "Bukayo Saka", "full_name": "Bukayo Ayoyinka Saka", "dob": "2001-09-05",
     "nationality": "England", "position": "RW", "foot": "left", "height_cm": 178, "weight_kg": 72,
     "club_idx": 1, "shirt_number": 7, "contract_until": "2027-06-30", "market_value": 120000000},
    {"name": "Jude Bellingham", "full_name": "Jude Victor William Bellingham", "dob": "2003-06-29",
     "nationality": "England", "position": "CAM", "foot": "right", "height_cm": 186, "weight_kg": 75,
     "club_idx": 2, "shirt_number": 5, "contract_until": "2029-06-30", "market_value": 180000000},
    {"name": "Lamine Yamal", "full_name": "Lamine Yamal Nasraoui Ebana", "dob": "2007-07-13",
     "nationality": "Spain", "position": "RW", "foot": "left", "height_cm": 180, "weight_kg": 68,
     "club_idx": 3, "shirt_number": 19, "contract_until": "2026-06-30", "market_value": 150000000},
    {"name": "Jamal Musiala", "full_name": "Jamal Musiala", "dob": "2003-02-26",
     "nationality": "Germany", "secondary_nationality": "England", "position": "CAM", "foot": "right",
     "height_cm": 183, "weight_kg": 72, "club_idx": 4, "shirt_number": 42, "contract_until": "2026-06-30",
     "market_value": 130000000},
    {"name": "Dusan Vlahovic", "full_name": "Dušan Vlahović", "dob": "2000-01-28",
     "nationality": "Serbia", "position": "ST", "foot": "left", "height_cm": 190, "weight_kg": 80,
     "club_idx": 5, "shirt_number": 9, "contract_until": "2026-06-30", "market_value": 65000000},
    {"name": "Phil Foden", "full_name": "Philip Walter Foden", "dob": "2000-05-28",
     "nationality": "England", "position": "LW", "secondary_position": "CAM", "foot": "left",
     "height_cm": 171, "weight_kg": 69, "club_idx": 0, "shirt_number": 47, "contract_until": "2027-06-30",
     "market_value": 110000000},
    {"name": "Martin Odegaard", "full_name": "Martin Ødegaard", "dob": "1998-12-17",
     "nationality": "Norway", "position": "CAM", "foot": "left", "height_cm": 178, "weight_kg": 68,
     "club_idx": 1, "shirt_number": 8, "contract_until": "2028-06-30", "market_value": 100000000},
    {"name": "Vinicius Junior", "full_name": "Vinícius José Paixão de Oliveira Júnior", "dob": "2000-07-12",
     "nationality": "Brazil", "position": "LW", "foot": "right", "height_cm": 176, "weight_kg": 73,
     "club_idx": 2, "shirt_number": 7, "contract_until": "2027-06-30", "market_value": 200000000},
    {"name": "Pedri", "full_name": "Pedro González López", "dob": "2002-11-25",
     "nationality": "Spain", "position": "CM", "foot": "right", "height_cm": 174, "weight_kg": 63,
     "club_idx": 3, "shirt_number": 8, "contract_until": "2026-06-30", "market_value": 100000000},
]

# Historical transfers (fictional but realistic)
TRANSFERS_DATA = [
    # Haaland to Man City (real)
    {"player_idx": 0, "from_club_idx": 4, "to_club_idx": 0, "type": TransferType.PERMANENT,
     "date": "2022-07-01", "fee": 60000000, "contract_years": 5},
    # Bellingham to Real Madrid (real)
    {"player_idx": 2, "from_club_idx": 4, "to_club_idx": 2, "type": TransferType.PERMANENT,
     "date": "2023-07-01", "fee": 103000000, "contract_years": 6},
    # Odegaard to Arsenal (real)
    {"player_idx": 7, "from_club_idx": 2, "to_club_idx": 1, "type": TransferType.PERMANENT,
     "date": "2021-08-20", "fee": 35000000, "contract_years": 5},
    # Vlahovic to Juventus (real)
    {"player_idx": 5, "from_club_idx": None, "to_club_idx": 5, "type": TransferType.PERMANENT,
     "date": "2022-01-28", "fee": 75000000, "contract_years": 4.5},
    # More fictional historical transfers
    {"player_idx": 6, "from_club_idx": None, "to_club_idx": 0, "type": TransferType.YOUTH_PROMOTION,
     "date": "2017-07-01", "fee": None, "contract_years": 3},
    {"player_idx": 1, "from_club_idx": None, "to_club_idx": 1, "type": TransferType.YOUTH_PROMOTION,
     "date": "2018-09-01", "fee": None, "contract_years": 3},
    {"player_idx": 8, "from_club_idx": None, "to_club_idx": 2, "type": TransferType.PERMANENT,
     "date": "2018-07-12", "fee": 45000000, "contract_years": 6},
    {"player_idx": 9, "from_club_idx": None, "to_club_idx": 3, "type": TransferType.YOUTH_PROMOTION,
     "date": "2020-09-01", "fee": None, "contract_years": 3},
    {"player_idx": 4, "from_club_idx": None, "to_club_idx": 4, "type": TransferType.PERMANENT,
     "date": "2019-07-01", "fee": 500000, "contract_years": 5},
    {"player_idx": 3, "from_club_idx": None, "to_club_idx": 3, "type": TransferType.YOUTH_PROMOTION,
     "date": "2023-04-29", "fee": None, "contract_years": 3},
    # Some loan deals
    {"player_idx": 7, "from_club_idx": 2, "to_club_idx": None, "type": TransferType.LOAN,
     "date": "2020-01-22", "fee": 0, "contract_years": 0.5, "loan": True},
    {"player_idx": 7, "from_club_idx": 2, "to_club_idx": 1, "type": TransferType.LOAN_WITH_OPTION,
     "date": "2021-01-22", "fee": 0, "contract_years": 0.5, "loan": True, "option_amount": 35000000},
    # Contract renewals shown as internal transfers
    {"player_idx": 0, "from_club_idx": 0, "to_club_idx": 0, "type": TransferType.PERMANENT,
     "date": "2024-01-01", "fee": None, "contract_years": 3, "notes": "Contract extension"},
    {"player_idx": 1, "from_club_idx": 1, "to_club_idx": 1, "type": TransferType.PERMANENT,
     "date": "2023-05-16", "fee": None, "contract_years": 4, "notes": "Contract extension"},
    {"player_idx": 6, "from_club_idx": 0, "to_club_idx": 0, "type": TransferType.PERMANENT,
     "date": "2024-04-04", "fee": None, "contract_years": 3, "notes": "Contract extension"},
    # More varied transfers
    {"player_idx": 4, "from_club_idx": 4, "to_club_idx": 4, "type": TransferType.PERMANENT,
     "date": "2023-07-01", "fee": None, "contract_years": 3, "notes": "Contract extension"},
    {"player_idx": 9, "from_club_idx": 3, "to_club_idx": 3, "type": TransferType.PERMANENT,
     "date": "2024-04-15", "fee": None, "contract_years": 4, "notes": "Contract extension"},
    {"player_idx": 8, "from_club_idx": 2, "to_club_idx": 2, "type": TransferType.PERMANENT,
     "date": "2024-09-01", "fee": None, "contract_years": 3, "notes": "Contract extension"},
    {"player_idx": 5, "from_club_idx": 5, "to_club_idx": 5, "type": TransferType.PERMANENT,
     "date": "2024-03-01", "fee": None, "contract_years": 2, "notes": "Contract extension"},
    {"player_idx": 3, "from_club_idx": 3, "to_club_idx": 3, "type": TransferType.PERMANENT,
     "date": "2024-10-01", "fee": None, "contract_years": 6, "notes": "Contract extension with €1B release clause"},
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_event_id(transfer_date: date, player_id: str, from_club_id: str | None) -> str:
    """Generate unique event ID: TL-YYYYMMDD-PLAYERID-FROMCLUBID"""
    date_str = transfer_date.strftime("%Y%m%d")
    player_short = str(player_id)[:8]
    from_short = str(from_club_id)[:8] if from_club_id else "ORIGIN"
    return f"TL-{date_str}-{player_short}-{from_short}"


def generate_snapshot_id(player_id: str, to_club_id: str | None, horizon: int, as_of: datetime) -> str:
    """Generate unique snapshot ID"""
    player_short = str(player_id)[:8]
    to_short = str(to_club_id)[:8] if to_club_id else "ANY"
    ts = as_of.strftime("%Y%m%d%H%M%S")
    return f"SNAP-{player_short}-{to_short}-H{horizon}-{ts}"


def random_datetime_between(start: datetime, end: datetime) -> datetime:
    """Generate random datetime between two dates"""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


# =============================================================================
# SEEDING FUNCTIONS
# =============================================================================

async def seed_competitions(session: AsyncSession) -> list[Competition]:
    """Seed competitions"""
    competitions = []
    for data in COMPETITIONS_DATA:
        comp = Competition(
            id=uuid.uuid4(),
            name=data["name"],
            short_name=data["short_name"],
            country=data["country"],
            tier=data["tier"],
            transfermarkt_id=data.get("transfermarkt_id"),
            competition_type="league",
            is_active=True
        )
        session.add(comp)
        competitions.append(comp)
    await session.flush()
    print(f"✓ Seeded {len(competitions)} competitions")
    return competitions


async def seed_seasons(session: AsyncSession, competitions: list[Competition]) -> list[Season]:
    """Seed seasons for each competition"""
    seasons = []
    for comp in competitions:
        # 2023-24 season
        s1 = Season(
            id=uuid.uuid4(),
            competition_id=comp.id,
            name="2023-24",
            start_date=date(2023, 8, 1),
            end_date=date(2024, 5, 31),
            is_current=False
        )
        # 2024-25 season (current)
        s2 = Season(
            id=uuid.uuid4(),
            competition_id=comp.id,
            name="2024-25",
            start_date=date(2024, 8, 1),
            end_date=date(2025, 5, 31),
            is_current=True
        )
        session.add(s1)
        session.add(s2)
        seasons.extend([s1, s2])
    await session.flush()
    print(f"✓ Seeded {len(seasons)} seasons")
    return seasons


async def seed_clubs(session: AsyncSession, competitions: list[Competition]) -> list[Club]:
    """Seed clubs"""
    clubs = []
    for data in CLUBS_DATA:
        club = Club(
            id=uuid.uuid4(),
            name=data["name"],
            short_name=data["short_name"],
            country=data["country"],
            city=data.get("city"),
            competition_id=competitions[data["competition_idx"]].id,
            stadium=data.get("stadium"),
            stadium_capacity=data.get("stadium_capacity"),
            founded_year=data.get("founded_year"),
            primary_color=data.get("primary_color"),
            secondary_color=data.get("secondary_color"),
            is_active=True
        )
        session.add(club)
        clubs.append(club)
    await session.flush()
    print(f"✓ Seeded {len(clubs)} clubs")
    return clubs


async def seed_players(session: AsyncSession, clubs: list[Club]) -> list[Player]:
    """Seed players"""
    players = []
    for data in PLAYERS_DATA:
        dob = datetime.strptime(data["dob"], "%Y-%m-%d").date() if data.get("dob") else None
        contract = datetime.strptime(data["contract_until"], "%Y-%m-%d").date() if data.get("contract_until") else None
        
        player = Player(
            id=uuid.uuid4(),
            name=data["name"],
            full_name=data.get("full_name"),
            date_of_birth=dob,
            nationality=data.get("nationality"),
            secondary_nationality=data.get("secondary_nationality"),
            position=data.get("position"),
            secondary_position=data.get("secondary_position"),
            foot=data.get("foot"),
            height_cm=data.get("height_cm"),
            weight_kg=data.get("weight_kg"),
            current_club_id=clubs[data["club_idx"]].id,
            shirt_number=data.get("shirt_number"),
            contract_until=contract,
            is_active=True
        )
        session.add(player)
        players.append(player)
    await session.flush()
    print(f"✓ Seeded {len(players)} players")
    return players


async def seed_transfers(session: AsyncSession, players: list[Player], clubs: list[Club]) -> list[TransferEvent]:
    """Seed 20 transfer events"""
    transfers = []
    
    for i, data in enumerate(TRANSFERS_DATA[:20]):
        player = players[data["player_idx"]]
        from_club = clubs[data["from_club_idx"]] if data.get("from_club_idx") is not None else None
        to_club = clubs[data["to_club_idx"]] if data.get("to_club_idx") is not None else clubs[0]  # Default
        transfer_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        
        # Calculate contract dates
        contract_years = Decimal(str(data.get("contract_years", 0)))
        contract_start = transfer_date
        contract_end = transfer_date + timedelta(days=int(float(contract_years) * 365)) if contract_years else None
        
        transfer = TransferEvent(
            id=uuid.uuid4(),
            event_id=generate_event_id(transfer_date, str(player.id), str(from_club.id) if from_club else None),
            player_id=player.id,
            from_club_id=from_club.id if from_club else None,
            to_club_id=to_club.id,
            transfer_type=data["type"],
            transfer_date=transfer_date,
            fee_amount=Decimal(str(data["fee"])) if data.get("fee") else None,
            fee_currency="EUR",
            fee_amount_eur=Decimal(str(data["fee"])) if data.get("fee") else None,
            fee_type=FeeType.CONFIRMED if data.get("fee") else FeeType.FREE,
            contract_start=contract_start,
            contract_end=contract_end,
            contract_years=contract_years if contract_years else None,
            loan_end_date=contract_end if data.get("loan") else None,
            option_to_buy=data.get("option_amount") is not None,
            option_to_buy_amount=Decimal(str(data["option_amount"])) if data.get("option_amount") else None,
            source="official" if data.get("fee") else "transfermarkt",
            source_confidence=Decimal("1.00"),
            notes=data.get("notes"),
            is_superseded=False
        )
        session.add(transfer)
        transfers.append(transfer)
    
    await session.flush()
    print(f"✓ Seeded {len(transfers)} transfer events")
    return transfers


async def seed_signals(session: AsyncSession, players: list[Player], clubs: list[Club]) -> list[SignalEvent]:
    """Seed 200 signal events"""
    signals = []
    signal_count = 0
    
    # Signal types to distribute
    player_signal_types = [
        (SignalTypeEnum.MARKET_VALUE, EntityType.PLAYER),
        (SignalTypeEnum.CONTRACT_MONTHS_REMAINING, EntityType.PLAYER),
        (SignalTypeEnum.WAGE_ESTIMATE, EntityType.PLAYER),
        (SignalTypeEnum.GOALS_LAST_10, EntityType.PLAYER),
        (SignalTypeEnum.ASSISTS_LAST_10, EntityType.PLAYER),
        (SignalTypeEnum.MINUTES_LAST_5, EntityType.PLAYER),
        (SignalTypeEnum.SOCIAL_MENTION_VELOCITY, EntityType.PLAYER),
        (SignalTypeEnum.SOCIAL_SENTIMENT, EntityType.PLAYER),
        (SignalTypeEnum.INJURIES_STATUS, EntityType.PLAYER),
        (SignalTypeEnum.USER_ATTENTION_VELOCITY, EntityType.PLAYER),
    ]
    
    club_signal_types = [
        (SignalTypeEnum.CLUB_LEAGUE_POSITION, EntityType.CLUB),
        (SignalTypeEnum.CLUB_POINTS_PER_GAME, EntityType.CLUB),
        (SignalTypeEnum.CLUB_NET_SPEND_12M, EntityType.CLUB),
    ]
    
    now = datetime.now()
    
    # Generate signals for each player (about 15-20 signals each = ~180 total)
    for player_data, player in zip(PLAYERS_DATA, players):
        for signal_type, entity_type in player_signal_types:
            # Generate 1-3 historical values per signal type
            num_signals = random.randint(1, 2)
            
            for j in range(num_signals):
                days_ago = j * 30 + random.randint(0, 14)  # Spread over time
                effective_from = now - timedelta(days=days_ago)
                observed_at = effective_from + timedelta(hours=random.randint(1, 12))
                
                # Generate appropriate values based on signal type
                value_num = None
                value_json = None
                value_text = None
                
                if signal_type == SignalTypeEnum.MARKET_VALUE:
                    # Fluctuate around the base market value
                    base_value = player_data.get("market_value", 50000000)
                    fluctuation = random.uniform(-0.1, 0.1)
                    value_num = Decimal(str(int(base_value * (1 + fluctuation))))
                elif signal_type == SignalTypeEnum.CONTRACT_MONTHS_REMAINING:
                    # Calculate months remaining
                    contract_until = datetime.strptime(player_data["contract_until"], "%Y-%m-%d")
                    months = max(0, (contract_until - effective_from).days // 30)
                    value_num = Decimal(str(months))
                elif signal_type == SignalTypeEnum.WAGE_ESTIMATE:
                    base_wage = player_data.get("market_value", 50000000) / 400  # Rough estimate
                    value_num = Decimal(str(int(base_wage * random.uniform(0.8, 1.2))))
                elif signal_type == SignalTypeEnum.GOALS_LAST_10:
                    value_num = Decimal(str(random.randint(0, 8)))
                elif signal_type == SignalTypeEnum.ASSISTS_LAST_10:
                    value_num = Decimal(str(random.randint(0, 6)))
                elif signal_type == SignalTypeEnum.MINUTES_LAST_5:
                    value_num = Decimal(str(random.randint(200, 450)))
                elif signal_type == SignalTypeEnum.SOCIAL_MENTION_VELOCITY:
                    value_num = Decimal(str(random.randint(100, 10000)))
                elif signal_type == SignalTypeEnum.SOCIAL_SENTIMENT:
                    value_num = Decimal(str(round(random.uniform(-1, 1), 2)))
                elif signal_type == SignalTypeEnum.INJURIES_STATUS:
                    value_text = random.choice(["fit", "fit", "fit", "minor_knock", "out_1_week"])
                elif signal_type == SignalTypeEnum.USER_ATTENTION_VELOCITY:
                    value_num = Decimal(str(random.randint(10, 500)))
                
                signal = SignalEvent(
                    id=uuid.uuid4(),
                    entity_type=entity_type,
                    player_id=player.id,
                    club_id=None,
                    signal_type=signal_type,
                    value_num=value_num,
                    value_text=value_text,
                    value_json=value_json,
                    source=random.choice(["transfermarkt", "sofascore", "twitter_api", "user_aggregation"]),
                    confidence=Decimal(str(round(random.uniform(0.7, 1.0), 2))),
                    observed_at=observed_at,
                    effective_from=effective_from,
                    effective_to=None if j == 0 else effective_from + timedelta(days=30),
                )
                session.add(signal)
                signals.append(signal)
                signal_count += 1
                
                if signal_count >= 200:
                    break
            if signal_count >= 200:
                break
        if signal_count >= 200:
            break
    
    # Add remaining club signals if we have room
    while signal_count < 200:
        for club in clubs:
            for signal_type, entity_type in club_signal_types:
                if signal_count >= 200:
                    break
                    
                days_ago = random.randint(0, 60)
                effective_from = now - timedelta(days=days_ago)
                observed_at = effective_from + timedelta(hours=random.randint(1, 12))
                
                value_num = None
                if signal_type == SignalTypeEnum.CLUB_LEAGUE_POSITION:
                    value_num = Decimal(str(random.randint(1, 20)))
                elif signal_type == SignalTypeEnum.CLUB_POINTS_PER_GAME:
                    value_num = Decimal(str(round(random.uniform(0.5, 2.8), 2)))
                elif signal_type == SignalTypeEnum.CLUB_NET_SPEND_12M:
                    value_num = Decimal(str(random.randint(-200000000, 300000000)))
                
                signal = SignalEvent(
                    id=uuid.uuid4(),
                    entity_type=entity_type,
                    player_id=None,
                    club_id=club.id,
                    signal_type=signal_type,
                    value_num=value_num,
                    source="transfermarkt",
                    confidence=Decimal("0.95"),
                    observed_at=observed_at,
                    effective_from=effective_from,
                )
                session.add(signal)
                signals.append(signal)
                signal_count += 1
            
            if signal_count >= 200:
                break
    
    await session.flush()
    print(f"✓ Seeded {len(signals)} signal events")
    return signals


async def seed_predictions(session: AsyncSession, players: list[Player], clubs: list[Club]) -> list[PredictionSnapshot]:
    """Seed 100 prediction snapshots"""
    predictions = []
    pred_count = 0
    horizons = [30, 90, 180]
    
    now = datetime.now()
    
    # Generate predictions for various player-destination pairs
    for player in players:
        # Each player gets predictions to 2-3 potential destinations
        potential_destinations = [c for c in clubs if c.id != player.current_club_id]
        destinations = random.sample(potential_destinations, min(3, len(potential_destinations)))
        
        # Also add "any move" prediction (to_club_id = None)
        destinations_with_none = destinations + [None]
        
        for to_club in destinations_with_none:
            for horizon in horizons:
                # Generate 1-2 historical snapshots
                num_snapshots = random.randint(1, 2)
                
                for j in range(num_snapshots):
                    days_ago = j * 7 + random.randint(0, 3)
                    as_of = now - timedelta(days=days_ago)
                    
                    # Base probability varies by player and destination
                    # Higher for players with expiring contracts
                    base_prob = random.uniform(0.05, 0.45)
                    
                    # Adjust based on horizon (longer = higher uncertainty)
                    horizon_factor = 1 + (horizon / 180) * 0.3
                    probability = min(0.95, base_prob * horizon_factor)
                    
                    # Generate realistic drivers
                    drivers = {
                        "contract_months_remaining": round(random.uniform(0.1, 0.4), 3),
                        "market_value_trend": round(random.uniform(-0.1, 0.2), 3),
                        "social_velocity": round(random.uniform(0.05, 0.15), 3),
                        "performance_score": round(random.uniform(0.05, 0.2), 3),
                        "club_financial_fit": round(random.uniform(0.05, 0.15), 3),
                    }
                    
                    window_start = as_of.date()
                    window_end = window_start + timedelta(days=horizon)
                    
                    snapshot = PredictionSnapshot(
                        id=uuid.uuid4(),
                        snapshot_id=generate_snapshot_id(
                            str(player.id), 
                            str(to_club.id) if to_club else None, 
                            horizon, 
                            as_of
                        ),
                        model_version="v1.2.0",
                        model_name="transfer_probability_xgb",
                        player_id=player.id,
                        from_club_id=player.current_club_id,
                        to_club_id=to_club.id if to_club else None,
                        horizon_days=horizon,
                        probability=Decimal(str(round(probability, 4))),
                        drivers_json=drivers,
                        as_of=as_of,
                        window_start=window_start,
                        window_end=window_end,
                    )
                    session.add(snapshot)
                    predictions.append(snapshot)
                    pred_count += 1
                    
                    if pred_count >= 100:
                        break
                if pred_count >= 100:
                    break
            if pred_count >= 100:
                break
        if pred_count >= 100:
            break
    
    await session.flush()
    print(f"✓ Seeded {len(predictions)} prediction snapshots")
    return predictions


async def seed_user_events(session: AsyncSession, players: list[Player], clubs: list[Club]) -> list[UserEvent]:
    """Seed sample user events"""
    events = []
    now = datetime.now()
    
    # Generate some user activity
    for _ in range(50):
        user_anon_id = f"anon_{uuid.uuid4().hex[:12]}"
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        
        # Random events
        for _ in range(random.randint(2, 8)):
            event_type = random.choice(list(UserEventType))
            player = random.choice(players) if random.random() > 0.3 else None
            club = random.choice(clubs) if random.random() > 0.5 else None
            
            event = UserEvent(
                id=uuid.uuid4(),
                user_anon_id=user_anon_id,
                session_id=session_id,
                event_type=event_type,
                player_id=player.id if player else None,
                club_id=club.id if club else None,
                occurred_at=now - timedelta(hours=random.randint(0, 168)),
                device_type=random.choice(["mobile", "desktop", "tablet"]),
                country_code=random.choice(["US", "GB", "DE", "ES", "FR", "IT", "BR"]),
            )
            session.add(event)
            events.append(event)
    
    await session.flush()
    print(f"✓ Seeded {len(events)} user events")
    return events


async def seed_watchlists(session: AsyncSession, players: list[Player]) -> tuple[list[Watchlist], list[WatchlistItem]]:
    """Seed sample watchlists"""
    watchlists = []
    items = []
    
    # Create a few demo watchlists
    demo_users = ["demo_user_1", "demo_user_2", "demo_user_3"]
    
    for user_id in demo_users:
        watchlist = Watchlist(
            id=uuid.uuid4(),
            user_id=user_id,
            name=f"{user_id}'s Transfer Watch",
            description="Tracking potential summer transfers",
            is_public=random.choice([True, False]),
            share_token=uuid.uuid4().hex[:16] if random.random() > 0.5 else None,
        )
        session.add(watchlist)
        watchlists.append(watchlist)
        
        # Add some players to watchlist
        watched_players = random.sample(players, random.randint(2, 5))
        for player in watched_players:
            item = WatchlistItem(
                id=uuid.uuid4(),
                watchlist_id=watchlist.id,
                player_id=player.id,
                notes=f"Watching {player.name}" if random.random() > 0.5 else None,
                alert_on_transfer=True,
                alert_on_probability_change=random.choice([True, False]),
                probability_threshold=Decimal("0.50") if random.random() > 0.5 else None,
            )
            session.add(item)
            items.append(item)
    
    await session.flush()
    print(f"✓ Seeded {len(watchlists)} watchlists with {len(items)} items")
    return watchlists, items


async def refresh_materialized_view(session: AsyncSession):
    """Refresh the player_market_view materialized view"""
    try:
        await session.execute(text("REFRESH MATERIALIZED VIEW player_market_view"))
        print("✓ Refreshed player_market_view materialized view")
    except Exception as e:
        print(f"⚠ Could not refresh materialized view (may not exist yet): {e}")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Main seed function"""
    print("\n" + "="*60)
    print("TransferLens Database Seeder")
    print("="*60 + "\n")
    
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Clear existing data (in reverse order of dependencies)
            print("Clearing existing data...")
            await session.execute(text("TRUNCATE TABLE data_corrections CASCADE"))
            await session.execute(text("TRUNCATE TABLE watchlist_items CASCADE"))
            await session.execute(text("TRUNCATE TABLE watchlists CASCADE"))
            await session.execute(text("TRUNCATE TABLE user_events CASCADE"))
            await session.execute(text("TRUNCATE TABLE prediction_snapshots CASCADE"))
            await session.execute(text("TRUNCATE TABLE signal_events CASCADE"))
            await session.execute(text("TRUNCATE TABLE transfer_events CASCADE"))
            await session.execute(text("TRUNCATE TABLE players CASCADE"))
            await session.execute(text("TRUNCATE TABLE clubs CASCADE"))
            await session.execute(text("TRUNCATE TABLE seasons CASCADE"))
            await session.execute(text("TRUNCATE TABLE competitions CASCADE"))
            print("✓ Cleared existing data\n")
            
            # Seed in order
            competitions = await seed_competitions(session)
            seasons = await seed_seasons(session, competitions)
            clubs = await seed_clubs(session, competitions)
            players = await seed_players(session, clubs)
            transfers = await seed_transfers(session, players, clubs)
            signals = await seed_signals(session, players, clubs)
            predictions = await seed_predictions(session, players, clubs)
            user_events = await seed_user_events(session, players, clubs)
            watchlists, watchlist_items = await seed_watchlists(session, players)
            
            # Commit all changes
            await session.commit()
            
            # Refresh materialized view
            await refresh_materialized_view(session)
            await session.commit()
            
            print("\n" + "="*60)
            print("Seeding Complete!")
            print("="*60)
            print(f"""
Summary:
  - {len(competitions)} competitions
  - {len(seasons)} seasons
  - {len(clubs)} clubs
  - {len(players)} players
  - {len(transfers)} transfer events
  - {len(signals)} signal events
  - {len(predictions)} prediction snapshots
  - {len(user_events)} user events
  - {len(watchlists)} watchlists with {len(watchlist_items)} items
""")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error during seeding: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
