"""
TransferLens Worker CLI
=======================

Command-line interface for running worker jobs.

Usage:
    python -m worker.cli <command> [options]

Commands:
    ingest:demo                    Load demo seed data
    features:build                 Build feature tables
    model:train                    Train prediction model
    predict:run                    Generate predictions
    signals:derive                 Derive signals from user events
    daily:run                      Run daily pipeline

Examples:
    python -m worker.cli ingest:demo --force
    python -m worker.cli features:build --as-of 2025-01-15T00:00:00
    python -m worker.cli model:train --horizon 90
    python -m worker.cli predict:run --horizon 90
    python -m worker.cli signals:derive --window 24h
    python -m worker.cli daily:run
"""

import click
from datetime import datetime
from typing import Optional

from rich.console import Console

console = Console()


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse datetime string in ISO format."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise click.BadParameter(f"Invalid datetime format: {value}. Use ISO format (YYYY-MM-DDTHH:MM:SS)")


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """TransferLens Worker - Background job runner for transfer intelligence."""
    pass


# =============================================================================
# INGEST COMMANDS
# =============================================================================

@cli.command("ingest:demo")
@click.option("--force", is_flag=True, help="Force reload even if data exists")
def cmd_ingest_demo(force: bool):
    """Load or refresh demo seed data (idempotent)."""
    from worker.jobs.ingest import run_demo_ingest
    
    console.print("\n[bold]TransferLens Worker - Demo Ingestion[/bold]\n")
    run_demo_ingest(force=force)


# =============================================================================
# FEATURE COMMANDS
# =============================================================================

@cli.command("features:build")
@click.option("--as-of", type=str, default=None, help="Build features as of timestamp (ISO format)")
def cmd_features_build(as_of: Optional[str]):
    """Build feature tables for (player, club) candidates."""
    from worker.jobs.features import run_feature_build
    
    console.print("\n[bold]TransferLens Worker - Feature Build[/bold]\n")
    as_of_dt = parse_datetime(as_of)
    run_feature_build(as_of=as_of_dt)


# =============================================================================
# MODEL COMMANDS
# =============================================================================

@cli.command("model:train")
@click.option("--as-of", type=str, default=None, help="Training data cutoff timestamp (ISO format)")
@click.option("--horizon", type=int, default=90, help="Prediction horizon in days (30, 90, 180)")
@click.option("--model-type", type=click.Choice(["logistic", "gradient_boosting"]), default="logistic", help="Model type")
@click.option("--lookback", type=int, default=730, help="Days of historical data to use")
def cmd_model_train(as_of: Optional[str], horizon: int, model_type: str, lookback: int):
    """Train a transfer prediction model."""
    from worker.jobs.train import run_model_train
    
    console.print("\n[bold]TransferLens Worker - Model Training[/bold]\n")
    as_of_dt = parse_datetime(as_of)
    run_model_train(as_of=as_of_dt, horizon_days=horizon, model_type=model_type, lookback_days=lookback)


@cli.command("model:list")
def cmd_model_list():
    """List all trained models."""
    from worker.database import get_sync_session
    from sqlalchemy import text
    from rich.table import Table
    
    console.print("\n[bold]TransferLens Worker - Model List[/bold]\n")
    
    with get_sync_session() as session:
        models = session.execute(
            text("""
                SELECT model_name, model_version, horizon_days, status, 
                       training_samples, created_at, metrics
                FROM model_versions
                ORDER BY created_at DESC
                LIMIT 20
            """)
        ).fetchall()
        
        if not models:
            console.print("[yellow]No models found.[/yellow]")
            return
        
        table = Table(title="Trained Models")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Horizon", justify="right")
        table.add_column("Status")
        table.add_column("Samples", justify="right")
        table.add_column("Created")
        
        for m in models:
            status_style = {
                "completed": "green",
                "deployed": "bold green",
                "failed": "red",
                "training": "yellow",
            }.get(m.status, "")
            
            table.add_row(
                m.model_name,
                m.model_version,
                str(m.horizon_days),
                f"[{status_style}]{m.status}[/]",
                str(m.training_samples),
                m.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        
        console.print(table)


@cli.command("model:evaluate")
@click.option("--model-version", type=str, default=None, help="Model version to evaluate (or latest)")
@click.option("--horizon", type=int, default=90, help="Prediction horizon in days")
@click.option("--lookback", type=int, default=730, help="Days of data to evaluate over")
@click.option("--no-save", is_flag=True, help="Don't save results to database")
def cmd_model_evaluate(model_version: Optional[str], horizon: int, lookback: int, no_save: bool):
    """
    Evaluate model with AUC, calibration, and backtest by season.
    
    Produces comprehensive evaluation report including:
    - AUC-ROC and AUC-PR
    - Calibration metrics (slope, intercept)
    - Backtest performance by season
    - Threshold-based precision/recall
    
    Results are stored in model_evaluations table.
    """
    from worker.jobs.evaluate import run_model_evaluate
    
    console.print("\n[bold]TransferLens Worker - Model Evaluation[/bold]\n")
    run_model_evaluate(
        model_version=model_version,
        horizon_days=horizon,
        lookback_days=lookback,
        save_to_db=not no_save,
    )


# =============================================================================
# PREDICT COMMANDS
# =============================================================================

@cli.command("predict:run")
@click.option("--as-of", type=str, default=None, help="Prediction timestamp (ISO format)")
@click.option("--horizon", type=int, default=90, help="Prediction horizon in days (30, 90, 180)")
@click.option("--max-candidates", type=int, default=10, help="Max candidate clubs per player")
def cmd_predict_run(as_of: Optional[str], horizon: int, max_candidates: int):
    """Generate prediction snapshots for all players."""
    from worker.jobs.predict import run_predictions
    
    console.print("\n[bold]TransferLens Worker - Prediction Generation[/bold]\n")
    as_of_dt = parse_datetime(as_of)
    run_predictions(as_of=as_of_dt, horizon_days=horizon, max_predictions_per_player=max_candidates)


@cli.command("predict:player")
@click.argument("player_id")
@click.option("--horizon", type=int, default=90, help="Prediction horizon in days")
def cmd_predict_player(player_id: str, horizon: int):
    """Generate predictions for a single player (for testing)."""
    from worker.jobs.predict import run_predictions_for_player
    from rich.table import Table
    
    console.print(f"\n[bold]Predictions for player {player_id}[/bold]\n")
    
    predictions = run_predictions_for_player(player_id, horizon_days=horizon)
    
    if not predictions:
        console.print("[yellow]No predictions generated.[/yellow]")
        return
    
    table = Table(title=f"Top Destinations ({horizon}d horizon)")
    table.add_column("Rank", justify="right")
    table.add_column("Club", style="cyan")
    table.add_column("Probability", justify="right", style="green")
    
    for i, pred in enumerate(predictions[:10], 1):
        table.add_row(
            str(i),
            pred["to_club_name"] or pred["to_club_id"][:8],
            f"{pred['probability']:.1%}",
        )
    
    console.print(table)


# =============================================================================
# SIGNAL COMMANDS
# =============================================================================

@cli.command("signals:derive")
@click.option("--window", type=str, default="24h", help="Time window (e.g., 24h, 7d)")
@click.option("--as-of", type=str, default=None, help="Derivation timestamp (ISO format)")
def cmd_signals_derive(window: str, as_of: Optional[str]):
    """Derive user signals from user events."""
    from worker.jobs.signals import run_signal_derivation
    
    console.print("\n[bold]TransferLens Worker - Signal Derivation[/bold]\n")
    as_of_dt = parse_datetime(as_of)
    run_signal_derivation(window=window, as_of=as_of_dt)


# =============================================================================
# CANDIDATE COMMANDS
# =============================================================================

@cli.command("candidates:generate")
@click.option("--as-of", type=str, default=None, help="Generation timestamp (ISO format)")
@click.option("--horizon", type=int, default=90, help="Prediction horizon in days")
@click.option("--player-id", type=str, default=None, help="Generate for specific player only")
def cmd_candidates_generate(as_of: Optional[str], horizon: int, player_id: Optional[str]):
    """
    Generate candidate destination sets for players.
    
    Sources:
    - League: Top clubs from same/major leagues
    - Social: Clubs with social co-mention spikes
    - User attention: Clubs with user cooccurrence signals
    - Constraint-fit: Clubs matching position need + affordability
    - Random: Calibration samples
    
    Results stored in candidate_sets table.
    """
    from worker.jobs.candidates import run_candidate_generation
    
    console.print("\n[bold]TransferLens Worker - Candidate Generation[/bold]\n")
    as_of_dt = parse_datetime(as_of)
    
    player_ids = [player_id] if player_id else None
    run_candidate_generation(as_of=as_of_dt, horizon_days=horizon, player_ids=player_ids)


@cli.command("candidates:show")
@click.argument("player_id")
@click.option("--as-of", type=str, default=None, help="Show candidates as of timestamp")
@click.option("--horizon", type=int, default=90, help="Prediction horizon")
def cmd_candidates_show(player_id: str, as_of: Optional[str], horizon: int):
    """Show candidate destinations for a specific player."""
    from worker.database import get_sync_session
    from worker.jobs.candidates import generate_candidates_for_player
    from rich.table import Table
    from uuid import UUID
    from datetime import datetime
    
    console.print(f"\n[bold]Candidates for player {player_id}[/bold]\n")
    
    as_of_dt = parse_datetime(as_of) or datetime.utcnow()
    
    with get_sync_session() as session:
        result = generate_candidates_for_player(
            session, UUID(player_id), as_of_dt, horizon, save_to_db=False
        )
        
        if "error" in result:
            console.print(f"[red]Error: {result['error']}[/red]")
            return
        
        # Player info
        ctx = result.get("player_context", {})
        console.print(f"[cyan]Player:[/cyan] {ctx.get('name', 'Unknown')}")
        console.print(f"[cyan]Club:[/cyan] {ctx.get('club', 'Unknown')}")
        console.print(f"[cyan]Position:[/cyan] {ctx.get('position', 'Unknown')}")
        console.print(f"[cyan]Age:[/cyan] {ctx.get('age', 'Unknown')}")
        console.print(f"[cyan]Market Value:[/cyan] €{(ctx.get('market_value') or 0)/1e6:.1f}M")
        console.print()
        
        # Candidates table
        table = Table(title=f"Candidate Destinations ({result['total_candidates']} total)")
        table.add_column("#", justify="right", width=3)
        table.add_column("Club", style="cyan", width=20)
        table.add_column("Source", width=15)
        table.add_column("Score", justify="right", width=6)
        table.add_column("Reason", width=35)
        
        # Get club names
        from sqlalchemy import text
        club_ids = [c["club_id"] for c in result["candidates"]]
        if club_ids:
            clubs = session.execute(
                text("SELECT id, name FROM clubs WHERE id = ANY(:ids)"),
                {"ids": [UUID(c) for c in club_ids]}
            ).fetchall()
            club_names = {str(c.id): c.name for c in clubs}
        else:
            club_names = {}
        
        for i, c in enumerate(result["candidates"], 1):
            club_name = club_names.get(c["club_id"], c["club_id"][:8])
            source_style = {
                "league": "green",
                "social": "magenta",
                "user_attention": "blue",
                "constraint_fit": "yellow",
                "random": "dim",
            }.get(c["source"], "")
            
            table.add_row(
                str(i),
                club_name,
                f"[{source_style}]{c['source']}[/]",
                f"{c['score']:.2f}",
                c["reason"][:35],
            )
        
        console.print(table)
        
        # Source summary
        console.print("\n[bold]By Source:[/bold]")
        for source, count in result["source_counts"].items():
            console.print(f"  • {source}: {count}")


@cli.command("candidates:audit")
@click.option("--as-of", type=str, default=None, help="Audit candidates as of timestamp")
@click.option("--limit", type=int, default=20, help="Number of records to show")
def cmd_candidates_audit(as_of: Optional[str], limit: int):
    """Audit stored candidate sets."""
    from worker.database import get_sync_session
    from sqlalchemy import text
    from rich.table import Table
    
    console.print("\n[bold]Candidate Sets Audit[/bold]\n")
    
    with get_sync_session() as session:
        query = """
            SELECT cs.id, cs.as_of, cs.horizon_days,
                   p.name as player_name,
                   c.name as club_name,
                   cs.total_candidates,
                   cs.league_candidates,
                   cs.social_candidates,
                   cs.user_attention_candidates,
                   cs.constraint_fit_candidates,
                   cs.random_candidates,
                   cs.created_at
            FROM candidate_sets cs
            JOIN players p ON cs.player_id = p.id
            LEFT JOIN clubs c ON cs.from_club_id = c.id
        """
        
        if as_of:
            as_of_dt = parse_datetime(as_of)
            query += " WHERE cs.as_of = :as_of"
            params = {"as_of": as_of_dt, "limit": limit}
        else:
            params = {"limit": limit}
        
        query += " ORDER BY cs.created_at DESC LIMIT :limit"
        
        records = session.execute(text(query), params).fetchall()
        
        if not records:
            console.print("[yellow]No candidate sets found.[/yellow]")
            return
        
        table = Table(title="Recent Candidate Sets")
        table.add_column("Player", style="cyan", width=18)
        table.add_column("Club", width=12)
        table.add_column("As Of", width=12)
        table.add_column("Total", justify="right", width=5)
        table.add_column("League", justify="right", width=6)
        table.add_column("Social", justify="right", width=6)
        table.add_column("User", justify="right", width=5)
        table.add_column("Fit", justify="right", width=4)
        table.add_column("Rand", justify="right", width=4)
        
        for r in records:
            table.add_row(
                r.player_name[:18],
                (r.club_name or "")[:12],
                r.as_of.strftime("%Y-%m-%d"),
                str(r.total_candidates),
                str(r.league_candidates),
                str(r.social_candidates),
                str(r.user_attention_candidates),
                str(r.constraint_fit_candidates),
                str(r.random_candidates),
            )
        
        console.print(table)


# =============================================================================
# DAILY RUN COMMAND
# =============================================================================

@cli.command("daily:run")
@click.option("--horizon", type=int, default=90, help="Prediction horizon in days")
@click.option("--skip-signals", is_flag=True, help="Skip signal derivation")
@click.option("--skip-candidates", is_flag=True, help="Skip candidate generation")
@click.option("--skip-features", is_flag=True, help="Skip feature building")
@click.option("--skip-predictions", is_flag=True, help="Skip prediction generation")
def cmd_daily_run(horizon: int, skip_signals: bool, skip_candidates: bool, skip_features: bool, skip_predictions: bool):
    """
    Run the daily pipeline:
    1. Derive signals from user events (24h window)
    2. Generate candidate destination sets
    3. Build feature tables
    4. Generate prediction snapshots
    """
    from datetime import datetime
    from worker.jobs.signals import run_signal_derivation
    from worker.jobs.candidates import run_candidate_generation
    from worker.jobs.features import run_feature_build
    from worker.jobs.predict import run_predictions
    
    console.print("\n[bold]TransferLens Worker - Daily Run[/bold]")
    console.print(f"Started at: {datetime.utcnow().isoformat()}\n")
    
    as_of = datetime.utcnow()
    
    # Step 1: Derive signals
    if not skip_signals:
        console.print("\n" + "=" * 60)
        console.print("[bold]STEP 1: Deriving signals from user events[/bold]")
        console.print("=" * 60)
        try:
            run_signal_derivation(window="24h", as_of=as_of)
        except Exception as e:
            console.print(f"[red]Signal derivation failed: {e}[/red]")
    else:
        console.print("\n[yellow]Skipping signal derivation[/yellow]")
    
    # Step 2: Generate candidate sets
    if not skip_candidates:
        console.print("\n" + "=" * 60)
        console.print("[bold]STEP 2: Generating candidate destination sets[/bold]")
        console.print("=" * 60)
        try:
            run_candidate_generation(as_of=as_of, horizon_days=horizon)
        except Exception as e:
            console.print(f"[red]Candidate generation failed: {e}[/red]")
    else:
        console.print("\n[yellow]Skipping candidate generation[/yellow]")
    
    # Step 3: Build features
    if not skip_features:
        console.print("\n" + "=" * 60)
        console.print("[bold]STEP 3: Building feature tables[/bold]")
        console.print("=" * 60)
        try:
            run_feature_build(as_of=as_of)
        except Exception as e:
            console.print(f"[red]Feature build failed: {e}[/red]")
    else:
        console.print("\n[yellow]Skipping feature building[/yellow]")
    
    # Step 4: Generate predictions
    if not skip_predictions:
        console.print("\n" + "=" * 60)
        console.print("[bold]STEP 4: Generating predictions[/bold]")
        console.print("=" * 60)
        try:
            run_predictions(as_of=as_of, horizon_days=horizon)
        except Exception as e:
            console.print(f"[red]Prediction generation failed: {e}[/red]")
    else:
        console.print("\n[yellow]Skipping prediction generation[/yellow]")
    
    console.print("\n" + "=" * 60)
    console.print(f"[bold green]Daily run complete![/bold green]")
    console.print(f"Finished at: {datetime.utcnow().isoformat()}")
    console.print("=" * 60)


# =============================================================================
# UTILITY COMMANDS
# =============================================================================

@cli.command("db:check")
def cmd_db_check():
    """Check database connection."""
    from worker.database import check_database_connection
    
    console.print("\n[bold]Checking database connection...[/bold]")
    
    if check_database_connection():
        console.print("[green]✅ Database connection successful![/green]")
    else:
        console.print("[red]❌ Database connection failed![/red]")


@cli.command("refresh:views")
def cmd_refresh_views():
    """Refresh materialized views."""
    from worker.database import get_sync_session
    from sqlalchemy import text
    
    console.print("\n[bold]Refreshing materialized views...[/bold]")
    
    with get_sync_session() as session:
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY player_market_view"))
            session.commit()
            console.print("[green]✅ Refreshed player_market_view[/green]")
        except Exception as e:
            try:
                session.execute(text("REFRESH MATERIALIZED VIEW player_market_view"))
                session.commit()
                console.print("[green]✅ Refreshed player_market_view (non-concurrent)[/green]")
            except Exception as e2:
                console.print(f"[red]❌ Failed to refresh view: {e2}[/red]")


if __name__ == "__main__":
    cli()
