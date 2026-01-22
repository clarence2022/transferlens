"""
Prediction Generation Job
=========================

Generates prediction_snapshots for candidate destinations.
- Uses sophisticated candidate generation (league, social, user attention, constraint-fit)
- Stores probability + top drivers
- Candidates auditable via candidate_sets table

Run with: python -m worker.cli predict:run --as-of <timestamp> --horizon 90
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import uuid4

import numpy as np
import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.database import get_sync_session
from worker.config import settings
from worker.jobs.features import build_feature_vector, FEATURE_COLUMNS
from worker.jobs.candidates import get_candidates_for_prediction
from worker.jobs.train import (
    load_model_artifact, get_latest_model, prepare_features, FEATURE_COLUMNS
)

console = Console()


def generate_snapshot_id(player_id, to_club_id, horizon, as_of) -> str:
    """Generate unique snapshot ID."""
    player_short = str(player_id)[:8]
    to_short = str(to_club_id)[:8] if to_club_id else "ANY"
    ts = as_of.strftime("%Y%m%d%H%M%S")
    return f"SNAP-{player_short}-{to_short}-H{horizon}-{ts}"


def compute_driver_contributions(
    model: Any,
    feature_values: Dict[str, float],
    feature_names: List[str],
    feature_importances: Dict[str, float],
    top_n: int = 5
) -> Dict[str, float]:
    """
    Compute feature contributions to the prediction.
    
    For MVP, we use feature importance weighted by normalized feature values.
    This is a simplified approximation of SHAP values.
    """
    drivers = {}
    
    # Get feature values in order
    values = []
    for name in feature_names:
        val = feature_values.get(name, 0) or 0
        values.append(val)
    
    values = np.array(values)
    
    # Normalize values to [0, 1]
    if values.max() != values.min():
        normalized = (values - values.min()) / (values.max() - values.min())
    else:
        normalized = np.ones_like(values) * 0.5
    
    # Compute contribution as importance * normalized_value
    for i, name in enumerate(feature_names):
        importance = feature_importances.get(name, 0)
        contribution = importance * normalized[i]
        if contribution > 0:
            drivers[name] = round(contribution, 4)
    
    # Sort and return top N
    sorted_drivers = dict(sorted(drivers.items(), key=lambda x: x[1], reverse=True)[:top_n])
    
    # Normalize to sum to 1
    total = sum(sorted_drivers.values())
    if total > 0:
        sorted_drivers = {k: round(v / total, 4) for k, v in sorted_drivers.items()}
    
    return sorted_drivers


def run_predictions(
    as_of: Optional[datetime] = None,
    horizon_days: int = 90,
    max_predictions_per_player: int = 10
) -> Dict[str, Any]:
    """
    Generate prediction snapshots for all active players.
    
    Args:
        as_of: Timestamp for predictions (defaults to now)
        horizon_days: Prediction horizon in days (30, 90, 180)
        max_predictions_per_player: Max candidate destinations per player
        
    Returns:
        dict with prediction stats
    """
    if as_of is None:
        as_of = datetime.utcnow()
    
    model_name = f"transfer_xgb_{horizon_days}d"
    
    console.print(f"[bold blue]🔮 Generating predictions as of {as_of.isoformat()}...[/bold blue]")
    console.print(f"  • Horizon: {horizon_days} days")
    console.print(f"  • Model: {model_name}")
    
    stats = {
        "as_of": as_of.isoformat(),
        "horizon_days": horizon_days,
        "players_processed": 0,
        "predictions_created": 0,
        "errors": 0,
    }
    
    with get_sync_session() as session:
        # Load model
        model_info = get_latest_model(session, model_name, horizon_days)
        
        if not model_info:
            console.print(f"[yellow]No trained model found for {model_name}[/yellow]")
            console.print("[yellow]Using dummy predictions...[/yellow]")
            model_artifact = None
            feature_importances = {
                "contract_months_remaining": 0.25,
                "market_value": 0.20,
                "user_destination_cooccurrence": 0.15,
                "age": 0.10,
                "same_league": 0.10,
                "tier_difference": 0.10,
                "social_mention_velocity": 0.10,
            }
        else:
            console.print(f"  • Model version: {model_info['model_version']}")
            try:
                model_artifact = load_model_artifact(model_info['artifact_path'])
                feature_importances = model_info.get('feature_importances', {})
            except Exception as e:
                console.print(f"[yellow]Could not load model: {e}[/yellow]")
                model_artifact = None
                feature_importances = {}
        
        # Get all active players
        players = session.execute(
            text("""
                SELECT id, name, current_club_id
                FROM players
                WHERE is_active = true
                AND current_club_id IS NOT NULL
            """)
        ).fetchall()
        
        console.print(f"\nFound {len(players)} active players")
        
        # Calculate window dates
        window_start = as_of.date()
        window_end = as_of.date() + timedelta(days=horizon_days)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating predictions...", total=len(players))
            
            for player in players:
                try:
                    # Get candidate clubs using sophisticated candidate generation
                    # This uses: league top N, social co-mentions, user attention,
                    # constraint-fit (position need + affordability), and random negatives
                    candidates = get_candidates_for_prediction(
                        session,
                        player.id,
                        as_of,
                        horizon_days,
                    )
                    
                    # Limit to max predictions
                    candidates = candidates[:max_predictions_per_player]
                    
                    for to_club_id in candidates:
                        # Build feature vector
                        features = build_feature_vector(
                            session,
                            player.id,
                            player.current_club_id,
                            to_club_id,
                            as_of
                        )
                        
                        # Predict probability
                        if model_artifact:
                            # Use actual model
                            df = pd.DataFrame([features])
                            X, feature_names = prepare_features(df, FEATURE_COLUMNS)
                            
                            # Apply preprocessing
                            X_imputed = model_artifact['imputer'].transform(X)
                            X_scaled = model_artifact['scaler'].transform(X_imputed)
                            
                            # Predict
                            probability = float(model_artifact['model'].predict_proba(X_scaled)[0, 1])
                        else:
                            # Dummy prediction based on contract months
                            contract_months = features.get('contract_months_remaining', 24) or 24
                            market_value = features.get('market_value', 50000000) or 50000000
                            
                            # Simple heuristic
                            base_prob = 0.1
                            if contract_months < 12:
                                base_prob += 0.3
                            elif contract_months < 24:
                                base_prob += 0.15
                            
                            # Same league bonus
                            if features.get('same_league'):
                                base_prob += 0.05
                            
                            probability = min(0.95, base_prob + np.random.uniform(-0.05, 0.05))
                        
                        # Compute driver contributions
                        drivers = compute_driver_contributions(
                            model_artifact['model'] if model_artifact else None,
                            features,
                            list(features.keys()),
                            feature_importances
                        )
                        
                        # Generate snapshot ID
                        snapshot_id = generate_snapshot_id(player.id, to_club_id, horizon_days, as_of)
                        
                        # Insert prediction
                        session.execute(
                            text("""
                                INSERT INTO prediction_snapshots (
                                    id, snapshot_id, model_version, model_name,
                                    player_id, from_club_id, to_club_id,
                                    horizon_days, probability, drivers_json,
                                    features_json, as_of, window_start, window_end
                                ) VALUES (
                                    :id, :snapshot_id, :model_version, :model_name,
                                    :player_id, :from_club_id, :to_club_id,
                                    :horizon_days, :probability, :drivers_json,
                                    :features_json, :as_of, :window_start, :window_end
                                )
                                ON CONFLICT (snapshot_id) DO UPDATE SET
                                    probability = :probability,
                                    drivers_json = :drivers_json
                            """),
                            {
                                "id": uuid4(),
                                "snapshot_id": snapshot_id,
                                "model_version": model_info['model_version'] if model_info else "v0-demo",
                                "model_name": model_name,
                                "player_id": player.id,
                                "from_club_id": player.current_club_id,
                                "to_club_id": to_club_id,
                                "horizon_days": horizon_days,
                                "probability": round(probability, 4),
                                "drivers_json": json.dumps(drivers),
                                "features_json": json.dumps({k: float(v) if v is not None else None for k, v in features.items()}),
                                "as_of": as_of,
                                "window_start": window_start,
                                "window_end": window_end,
                            }
                        )
                        stats["predictions_created"] += 1
                    
                    stats["players_processed"] += 1
                    
                except Exception as e:
                    console.print(f"[red]Error for player {player.name}: {e}[/red]")
                    stats["errors"] += 1
                
                progress.update(task, advance=1)
        
        session.commit()
        
        # Refresh materialized view
        console.print("\n[bold]Refreshing materialized view...[/bold]")
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY player_market_view"))
            session.commit()
            console.print("  [green]Refreshed player_market_view[/green]")
        except Exception as e:
            try:
                session.execute(text("REFRESH MATERIALIZED VIEW player_market_view"))
                session.commit()
                console.print("  [green]Refreshed player_market_view[/green]")
            except Exception as e2:
                console.print(f"  [yellow]Could not refresh view: {e2}[/yellow]")
    
    console.print("\n[bold green]✅ Prediction generation complete![/bold green]")
    console.print(f"  • Players processed: {stats['players_processed']}")
    console.print(f"  • Predictions created: {stats['predictions_created']}")
    console.print(f"  • Errors: {stats['errors']}")
    
    return stats


def run_predictions_for_player(
    player_id: str,
    as_of: Optional[datetime] = None,
    horizon_days: int = 90
) -> List[Dict[str, Any]]:
    """
    Generate predictions for a single player (useful for testing).
    """
    if as_of is None:
        as_of = datetime.utcnow()
    
    predictions = []
    
    with get_sync_session() as session:
        # Get player info
        player = session.execute(
            text("SELECT id, name, current_club_id FROM players WHERE id = :id"),
            {"id": player_id}
        ).first()
        
        if not player:
            return []
        
        # Get candidates
        candidates = get_candidate_clubs(
            session, player.id, player.current_club_id, as_of, max_candidates=10
        )
        
        # Get club names
        for to_club_id in candidates:
            club_name = session.execute(
                text("SELECT name FROM clubs WHERE id = :id"),
                {"id": to_club_id}
            ).scalar()
            
            # Build features and predict (simplified)
            features = build_feature_vector(
                session, player.id, player.current_club_id, to_club_id, as_of
            )
            
            # Simple probability calculation
            contract_months = features.get('contract_months_remaining', 24) or 24
            base_prob = 0.1 + (24 - min(contract_months, 24)) * 0.02
            
            predictions.append({
                "to_club_id": str(to_club_id),
                "to_club_name": club_name,
                "probability": round(min(0.95, base_prob), 4),
                "features": features,
            })
    
    return sorted(predictions, key=lambda x: x['probability'], reverse=True)
