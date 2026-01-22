"""
Model Evaluation Job
====================

Produces comprehensive model evaluation including:
- AUC-ROC and AUC-PR
- Calibration analysis (slope, intercept, reliability diagram)
- Backtest by season
- Stores results in model_evaluations table

Run with: python -m worker.cli model:evaluate --model-version <version> --horizon 90

CRITICAL: All evaluations respect time-travel. We only use data that would
have been available at prediction time.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from uuid import uuid4, UUID
from decimal import Decimal

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from sklearn.metrics import (
    roc_auc_score, average_precision_score, accuracy_score,
    precision_score, recall_score, f1_score, log_loss, brier_score_loss,
    confusion_matrix, precision_recall_curve, roc_curve
)
from sklearn.calibration import calibration_curve
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.database import get_sync_session
from worker.config import settings
from worker.jobs.train import load_model_artifact, get_latest_model, FEATURE_COLUMNS
from worker.jobs.features import build_feature_vector
from worker.time_guards import (
    validate_training_label_time_travel,
    TimeTravelViolationError,
    DataLeakageError,
)

console = Console()


# =============================================================================
# CALIBRATION METRICS
# =============================================================================

def compute_calibration_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10
) -> Dict[str, Any]:
    """
    Compute calibration metrics.
    
    Returns:
        Dict with calibration slope, intercept, and binned values
    """
    # Calibration curve
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy='uniform')
    
    # Linear fit for calibration slope/intercept
    # Perfect calibration: slope=1, intercept=0
    if len(prob_pred) >= 2:
        slope, intercept = np.polyfit(prob_pred, prob_true, 1)
    else:
        slope, intercept = 1.0, 0.0
    
    # Binned calibration data
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)
    
    calibration_bins = {}
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            calibration_bins[f"bin_{i}"] = {
                "range": [float(bins[i]), float(bins[i+1])],
                "predicted_mean": float(y_prob[mask].mean()),
                "actual_mean": float(y_true[mask].mean()),
                "count": int(mask.sum()),
            }
    
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "bins": calibration_bins,
        "prob_true": prob_true.tolist(),
        "prob_pred": prob_pred.tolist(),
    }


def compute_threshold_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    thresholds: List[float] = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
) -> Dict[str, Dict[str, float]]:
    """
    Compute precision/recall/F1 at different probability thresholds.
    """
    results = {}
    
    for thresh in thresholds:
        y_pred = (y_prob >= thresh).astype(int)
        
        # Handle edge case where all predictions are 0 or 1
        if y_pred.sum() == 0:
            precision = 0.0
            recall = 0.0
            f1 = 0.0
        else:
            precision = precision_score(y_true, y_pred, zero_division=0)
            recall = recall_score(y_true, y_pred, zero_division=0)
            f1 = f1_score(y_true, y_pred, zero_division=0)
        
        results[f"threshold_{thresh}"] = {
            "threshold": thresh,
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "predicted_positive": int(y_pred.sum()),
            "actual_positive": int(y_true.sum()),
        }
    
    return results


# =============================================================================
# BACKTEST BY SEASON
# =============================================================================

def get_season_windows(
    start_date: datetime,
    end_date: datetime,
) -> List[Dict[str, Any]]:
    """
    Generate season windows for backtesting.
    
    Football seasons typically run Aug 1 to Jul 31.
    """
    seasons = []
    
    # Start from August of the start year
    year = start_date.year
    if start_date.month < 8:
        year -= 1
    
    while True:
        season_start = datetime(year, 8, 1)
        season_end = datetime(year + 1, 7, 31, 23, 59, 59)
        
        if season_start > end_date:
            break
        
        # Only include seasons that overlap with our date range
        actual_start = max(season_start, start_date)
        actual_end = min(season_end, end_date)
        
        if actual_start < actual_end:
            seasons.append({
                "name": f"{year}-{str(year+1)[-2:]}",
                "start": actual_start,
                "end": actual_end,
            })
        
        year += 1
    
    return seasons


def run_backtest_for_window(
    session: Session,
    model_artifact: Dict[str, Any],
    window_start: datetime,
    window_end: datetime,
    horizon_days: int,
) -> Dict[str, Any]:
    """
    Run backtest for a specific time window.
    
    CRITICAL: Respects time-travel. For each transfer in the window,
    we build features as of (transfer_date - horizon_days) and check
    if the model would have predicted it.
    """
    model = model_artifact["model"]
    imputer = model_artifact["imputer"]
    scaler = model_artifact["scaler"]
    feature_names = model_artifact["feature_names"]
    
    # Get transfers in window
    transfers = session.execute(
        text("""
            SELECT 
                t.player_id,
                t.from_club_id,
                t.to_club_id,
                t.transfer_date
            FROM transfer_events t
            WHERE t.transfer_date BETWEEN :start AND :end
            AND t.is_superseded = false
            AND t.transfer_type IN ('permanent', 'loan', 'loan_with_option')
            AND t.from_club_id IS NOT NULL
        """),
        {"start": window_start, "end": window_end}
    ).fetchall()
    
    if len(transfers) == 0:
        return {
            "n_samples": 0,
            "n_positive": 0,
            "auc_roc": None,
            "message": "No transfers in window",
        }
    
    y_true = []
    y_prob = []
    
    # Get all clubs for negative sampling
    all_clubs = session.execute(
        text("SELECT id FROM clubs WHERE is_active = true")
    ).scalars().all()
    
    import random
    
    for transfer in transfers:
        # Build features as of (transfer_date - horizon_days)
        feature_date = datetime.combine(
            transfer.transfer_date - timedelta(days=horizon_days),
            datetime.min.time()
        )
        
        # POSITIVE: actual transfer destination
        features = build_feature_vector(
            session,
            transfer.player_id,
            transfer.from_club_id,
            transfer.to_club_id,
            feature_date
        )
        
        # Convert to array
        X = np.array([[features.get(f, 0) or 0 for f in feature_names]])
        X_imputed = imputer.transform(X)
        X_scaled = scaler.transform(X_imputed)
        prob = model.predict_proba(X_scaled)[0, 1]
        
        y_true.append(1)
        y_prob.append(prob)
        
        # NEGATIVE: random non-destination clubs
        negative_clubs = random.sample(
            [c for c in all_clubs if c != transfer.to_club_id and c != transfer.from_club_id],
            min(2, len(all_clubs) - 2)
        )
        
        for neg_club in negative_clubs:
            features = build_feature_vector(
                session,
                transfer.player_id,
                transfer.from_club_id,
                neg_club,
                feature_date
            )
            
            X = np.array([[features.get(f, 0) or 0 for f in feature_names]])
            X_imputed = imputer.transform(X)
            X_scaled = scaler.transform(X_imputed)
            prob = model.predict_proba(X_scaled)[0, 1]
            
            y_true.append(0)
            y_prob.append(prob)
    
    y_true = np.array(y_true)
    y_prob = np.array(y_prob)
    
    # Compute metrics
    if len(np.unique(y_true)) < 2:
        auc_roc = None
    else:
        auc_roc = roc_auc_score(y_true, y_prob)
    
    return {
        "n_samples": len(y_true),
        "n_positive": int(y_true.sum()),
        "n_negative": int(len(y_true) - y_true.sum()),
        "auc_roc": float(auc_roc) if auc_roc else None,
        "mean_prob_positive": float(y_prob[y_true == 1].mean()) if y_true.sum() > 0 else None,
        "mean_prob_negative": float(y_prob[y_true == 0].mean()) if (y_true == 0).sum() > 0 else None,
    }


# =============================================================================
# MAIN EVALUATION FUNCTION
# =============================================================================

def run_model_evaluate(
    model_version: Optional[str] = None,
    horizon_days: int = 90,
    lookback_days: int = 730,
    save_to_db: bool = True,
) -> Dict[str, Any]:
    """
    Run comprehensive model evaluation.
    
    Args:
        model_version: Specific version to evaluate (or None for latest)
        horizon_days: Prediction horizon
        lookback_days: How far back to evaluate
        save_to_db: Whether to save results to model_evaluations table
        
    Returns:
        Dict with all evaluation metrics
    """
    start_time = datetime.utcnow()
    
    console.print(f"[bold blue]📊 Running Model Evaluation[/bold blue]")
    console.print(f"  • Horizon: {horizon_days} days")
    console.print(f"  • Lookback: {lookback_days} days")
    
    results = {
        "horizon_days": horizon_days,
        "lookback_days": lookback_days,
        "evaluation_start": start_time.isoformat(),
        "status": "started",
    }
    
    with get_sync_session() as session:
        # Load model
        model_name = f"transfer_xgb_{horizon_days}d"
        
        if model_version:
            model_info = session.execute(
                text("""
                    SELECT id, model_version, artifact_path
                    FROM model_versions
                    WHERE model_name = :name AND model_version = :version
                """),
                {"name": model_name, "version": model_version}
            ).first()
        else:
            model_info = session.execute(
                text("""
                    SELECT id, model_version, artifact_path
                    FROM model_versions
                    WHERE model_name = :name
                    AND status IN ('completed', 'deployed')
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"name": model_name}
            ).first()
        
        if not model_info:
            console.print(f"[red]No model found for {model_name}[/red]")
            results["status"] = "failed"
            results["error"] = f"No model found for {model_name}"
            return results
        
        console.print(f"  • Model version: {model_info.model_version}")
        
        try:
            artifact = load_model_artifact(model_info.artifact_path)
        except Exception as e:
            console.print(f"[red]Failed to load model artifact: {e}[/red]")
            results["status"] = "failed"
            results["error"] = str(e)
            return results
        
        results["model_version_id"] = str(model_info.id)
        results["model_version"] = model_info.model_version
        
        # Build evaluation dataset
        console.print("\n[bold]Building evaluation dataset...[/bold]")
        
        eval_end = datetime.utcnow()
        eval_start = eval_end - timedelta(days=lookback_days)
        
        # Build evaluation data (similar to training data)
        from worker.jobs.features import build_training_features
        
        eval_df = build_training_features(
            session, 
            as_of=eval_end,
            lookback_days=lookback_days,
            horizon_days=horizon_days,
            validate_time_travel=True,
        )
        
        if len(eval_df) < 10:
            console.print("[red]Insufficient evaluation data[/red]")
            results["status"] = "failed"
            results["error"] = f"Insufficient data: {len(eval_df)} samples"
            return results
        
        # Prepare features
        model = artifact["model"]
        imputer = artifact["imputer"]
        scaler = artifact["scaler"]
        feature_names = artifact["feature_names"]
        
        # Extract features that exist in both model and data
        available_features = [f for f in feature_names if f in eval_df.columns]
        missing_features = [f for f in feature_names if f not in eval_df.columns]
        
        if missing_features:
            console.print(f"[yellow]Missing features (using 0): {missing_features}[/yellow]")
            for f in missing_features:
                eval_df[f] = 0
        
        X = eval_df[feature_names].values
        y = eval_df["label"].values
        
        # Apply preprocessing
        X_imputed = imputer.transform(X)
        X_scaled = scaler.transform(X_imputed)
        
        # Generate predictions
        console.print("\n[bold]Generating predictions...[/bold]")
        y_prob = model.predict_proba(X_scaled)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        
        # Compute metrics
        console.print("\n[bold]Computing metrics...[/bold]")
        
        # Core metrics
        metrics = {
            "auc_roc": roc_auc_score(y, y_prob) if len(np.unique(y)) > 1 else None,
            "auc_pr": average_precision_score(y, y_prob) if len(np.unique(y)) > 1 else None,
            "accuracy": accuracy_score(y, y_pred),
            "precision": precision_score(y, y_pred, zero_division=0),
            "recall": recall_score(y, y_pred, zero_division=0),
            "f1": f1_score(y, y_pred, zero_division=0),
            "log_loss": log_loss(y, y_prob) if len(np.unique(y)) > 1 else None,
            "brier_score": brier_score_loss(y, y_prob),
        }
        
        # Calibration
        console.print("  Computing calibration metrics...")
        calibration = compute_calibration_metrics(y, y_prob)
        
        # Threshold metrics
        console.print("  Computing threshold metrics...")
        threshold_metrics = compute_threshold_metrics(y, y_prob)
        
        # Confusion matrix
        cm = confusion_matrix(y, y_pred)
        confusion = {
            "true_negative": int(cm[0, 0]),
            "false_positive": int(cm[0, 1]),
            "false_negative": int(cm[1, 0]),
            "true_positive": int(cm[1, 1]),
        }
        
        # Backtest by season
        console.print("\n[bold]Running backtest by season...[/bold]")
        seasons = get_season_windows(eval_start, eval_end)
        backtest_results = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Backtesting...", total=len(seasons))
            
            for season in seasons:
                progress.update(task, description=f"Backtesting {season['name']}...")
                
                season_result = run_backtest_for_window(
                    session,
                    artifact,
                    season["start"],
                    season["end"],
                    horizon_days,
                )
                season_result["season"] = season["name"]
                season_result["start"] = season["start"].isoformat()
                season_result["end"] = season["end"].isoformat()
                backtest_results.append(season_result)
                
                progress.update(task, advance=1)
        
        # Compile results
        results.update({
            "evaluation_start": eval_start.isoformat(),
            "evaluation_end": eval_end.isoformat(),
            "total_predictions": len(y),
            "total_positives": int(y.sum()),
            "total_negatives": int(len(y) - y.sum()),
            "metrics": metrics,
            "calibration": calibration,
            "threshold_metrics": threshold_metrics,
            "confusion_matrix": confusion,
            "backtest_by_season": backtest_results,
            "status": "completed",
        })
        
        # Display results
        display_evaluation_results(results)
        
        # Save to database
        if save_to_db:
            console.print("\n[bold]Saving evaluation to database...[/bold]")
            eval_id = save_evaluation_to_db(session, results)
            results["evaluation_id"] = eval_id
            console.print(f"  Saved as evaluation ID: {eval_id}")
        
        end_time = datetime.utcnow()
        results["evaluation_duration_seconds"] = (end_time - start_time).total_seconds()
        
        console.print("\n[bold green]✅ Evaluation complete![/bold green]")
    
    return results


def display_evaluation_results(results: Dict[str, Any]) -> None:
    """Display evaluation results in a nice format."""
    
    # Core metrics table
    metrics_table = Table(title="Core Metrics")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="green")
    
    metrics = results.get("metrics", {})
    for metric, value in metrics.items():
        if value is not None:
            metrics_table.add_row(metric, f"{value:.4f}")
        else:
            metrics_table.add_row(metric, "N/A")
    
    console.print(metrics_table)
    
    # Calibration
    calibration = results.get("calibration", {})
    if calibration:
        console.print(f"\n[bold]Calibration:[/bold]")
        console.print(f"  Slope: {calibration.get('slope', 'N/A'):.4f} (ideal: 1.0)")
        console.print(f"  Intercept: {calibration.get('intercept', 'N/A'):.4f} (ideal: 0.0)")
    
    # Backtest by season
    backtest = results.get("backtest_by_season", [])
    if backtest:
        backtest_table = Table(title="Backtest by Season")
        backtest_table.add_column("Season", style="cyan")
        backtest_table.add_column("Samples", style="white")
        backtest_table.add_column("Positives", style="white")
        backtest_table.add_column("AUC-ROC", style="green")
        
        for season in backtest:
            auc = season.get("auc_roc")
            auc_str = f"{auc:.4f}" if auc else "N/A"
            backtest_table.add_row(
                season.get("season", "N/A"),
                str(season.get("n_samples", 0)),
                str(season.get("n_positive", 0)),
                auc_str,
            )
        
        console.print(backtest_table)


def save_evaluation_to_db(session: Session, results: Dict[str, Any]) -> str:
    """Save evaluation results to model_evaluations table."""
    eval_id = uuid4()
    
    metrics = results.get("metrics", {})
    calibration = results.get("calibration", {})
    
    session.execute(
        text("""
            INSERT INTO model_evaluations (
                id, model_version_id, evaluation_type, evaluation_name,
                evaluation_start, evaluation_end, horizon_days,
                total_predictions, total_positives, total_negatives,
                auc_roc, auc_pr, accuracy, precision_score, recall_score, f1_score,
                log_loss, brier_score, calibration_slope, calibration_intercept,
                calibration_bins, confusion_matrix, threshold_metrics, backtest_windows,
                evaluation_duration_seconds
            ) VALUES (
                :id, :model_version_id, :evaluation_type, :evaluation_name,
                :evaluation_start, :evaluation_end, :horizon_days,
                :total_predictions, :total_positives, :total_negatives,
                :auc_roc, :auc_pr, :accuracy, :precision_score, :recall_score, :f1_score,
                :log_loss, :brier_score, :calibration_slope, :calibration_intercept,
                :calibration_bins, :confusion_matrix, :threshold_metrics, :backtest_windows,
                :evaluation_duration_seconds
            )
        """),
        {
            "id": eval_id,
            "model_version_id": UUID(results["model_version_id"]),
            "evaluation_type": "backtest",
            "evaluation_name": f"backtest_{results.get('lookback_days', 730)}d",
            "evaluation_start": datetime.fromisoformat(results["evaluation_start"]),
            "evaluation_end": datetime.fromisoformat(results["evaluation_end"]),
            "horizon_days": results["horizon_days"],
            "total_predictions": results["total_predictions"],
            "total_positives": results["total_positives"],
            "total_negatives": results["total_negatives"],
            "auc_roc": metrics.get("auc_roc"),
            "auc_pr": metrics.get("auc_pr"),
            "accuracy": metrics.get("accuracy"),
            "precision_score": metrics.get("precision"),
            "recall_score": metrics.get("recall"),
            "f1_score": metrics.get("f1"),
            "log_loss": metrics.get("log_loss"),
            "brier_score": metrics.get("brier_score"),
            "calibration_slope": calibration.get("slope"),
            "calibration_intercept": calibration.get("intercept"),
            "calibration_bins": json.dumps(calibration.get("bins", {})),
            "confusion_matrix": json.dumps(results.get("confusion_matrix", {})),
            "threshold_metrics": json.dumps(results.get("threshold_metrics", {})),
            "backtest_windows": json.dumps(results.get("backtest_by_season", [])),
            "evaluation_duration_seconds": results.get("evaluation_duration_seconds"),
        }
    )
    session.commit()
    
    return str(eval_id)
