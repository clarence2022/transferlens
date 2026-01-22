"""
Model Training Job
==================

Trains a baseline transfer prediction model.
- Uses logistic regression or gradient boosting
- Ensures no data leakage (only signals before transfer_date)
- Saves model artifact and registers in model_versions table

Run with: python -m worker.cli model:train --as-of <timestamp> --horizon 90
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    classification_report, confusion_matrix
)
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.database import get_sync_session
from worker.config import settings
from worker.jobs.features import build_training_features, ALL_FEATURES

console = Console()


# =============================================================================
# FEATURE COLUMNS (must match features.py output)
# =============================================================================

FEATURE_COLUMNS = [
    # Player features
    "market_value",
    "contract_months_remaining",
    "goals_last_10",
    "assists_last_10",
    "minutes_last_5",
    "social_mention_velocity",
    "user_attention_velocity",
    "age",
    "position_encoded",
    
    # From club features
    "from_club_tier",
    "from_club_league_position",
    "from_club_points_per_game",
    "from_club_net_spend_12m",
    
    # To club features
    "to_club_tier",
    "to_club_league_position",
    "to_club_points_per_game",
    "to_club_net_spend_12m",
    
    # Pair features
    "same_country",
    "same_league",
    "tier_difference",
    "user_destination_cooccurrence",
]


def generate_model_version() -> str:
    """Generate a unique model version string."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"v{timestamp}"


def prepare_features(df: pd.DataFrame, feature_columns: List[str]) -> Tuple[np.ndarray, List[str]]:
    """
    Prepare feature matrix from dataframe.
    Handles missing values and returns column names.
    """
    # Select only columns that exist in the dataframe
    available_cols = [c for c in feature_columns if c in df.columns]
    missing_cols = [c for c in feature_columns if c not in df.columns]
    
    if missing_cols:
        console.print(f"[yellow]Missing columns (will use 0): {missing_cols}[/yellow]")
        for col in missing_cols:
            df[col] = 0
        available_cols = feature_columns
    
    X = df[available_cols].values
    return X, available_cols


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    model_type: str = "logistic"
) -> Tuple[Any, Any, Any]:
    """
    Train a model with preprocessing pipeline.
    
    Returns:
        model, imputer, scaler
    """
    # Impute missing values
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X_train)
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)
    
    # Train model
    if model_type == "logistic":
        model = LogisticRegression(
            max_iter=1000,
            random_state=settings.random_state,
            class_weight="balanced",
        )
    else:
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            random_state=settings.random_state,
        )
    
    model.fit(X_scaled, y_train)
    
    return model, imputer, scaler


def evaluate_model(
    model: Any,
    imputer: Any,
    scaler: Any,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: List[str]
) -> Dict[str, Any]:
    """Evaluate model and compute metrics."""
    X_imputed = imputer.transform(X_test)
    X_scaled = scaler.transform(X_imputed)
    
    y_pred = model.predict(X_scaled)
    y_prob = model.predict_proba(X_scaled)[:, 1]
    
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "auc_roc": roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else 0,
    }
    
    return metrics


def get_feature_importances(
    model: Any,
    feature_names: List[str]
) -> Dict[str, float]:
    """Extract feature importances from model."""
    importances = {}
    
    if hasattr(model, "coef_"):
        # Logistic regression - use absolute coefficients
        coefs = np.abs(model.coef_[0])
        total = coefs.sum()
        if total > 0:
            for name, coef in zip(feature_names, coefs):
                importances[name] = round(coef / total, 4)
    elif hasattr(model, "feature_importances_"):
        # Tree-based models
        for name, imp in zip(feature_names, model.feature_importances_):
            importances[name] = round(imp, 4)
    
    # Sort by importance
    importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))
    
    return importances


def save_model_artifact(
    model: Any,
    imputer: Any,
    scaler: Any,
    feature_names: List[str],
    model_version: str,
    horizon_days: int
) -> str:
    """Save model artifacts to disk."""
    model_dir = settings.model_storage_path / f"transfer_xgb_{horizon_days}d"
    model_dir.mkdir(parents=True, exist_ok=True)
    
    artifact_path = model_dir / f"{model_version}.joblib"
    
    artifact = {
        "model": model,
        "imputer": imputer,
        "scaler": scaler,
        "feature_names": feature_names,
        "model_version": model_version,
        "horizon_days": horizon_days,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    joblib.dump(artifact, artifact_path)
    
    return str(artifact_path)


def load_model_artifact(artifact_path: str) -> Dict[str, Any]:
    """Load model artifact from disk."""
    return joblib.load(artifact_path)


def register_model_version(
    session: Session,
    model_name: str,
    model_version: str,
    horizon_days: int,
    training_as_of: datetime,
    training_samples: int,
    positive_samples: int,
    negative_samples: int,
    feature_count: int,
    features_used: List[str],
    metrics: Dict[str, float],
    feature_importances: Dict[str, float],
    artifact_path: str,
    status: str = "completed"
) -> str:
    """Register a model version in the database."""
    model_id = uuid4()
    
    session.execute(
        text("""
            INSERT INTO model_versions (
                id, model_name, model_version, horizon_days, training_as_of,
                training_samples, positive_samples, negative_samples, feature_count,
                features_used, metrics, feature_importances, artifact_path,
                status, completed_at
            ) VALUES (
                :id, :model_name, :model_version, :horizon_days, :training_as_of,
                :training_samples, :positive_samples, :negative_samples, :feature_count,
                :features_used, :metrics, :feature_importances, :artifact_path,
                :status, :completed_at
            )
        """),
        {
            "id": model_id,
            "model_name": model_name,
            "model_version": model_version,
            "horizon_days": horizon_days,
            "training_as_of": training_as_of,
            "training_samples": training_samples,
            "positive_samples": positive_samples,
            "negative_samples": negative_samples,
            "feature_count": feature_count,
            "features_used": json.dumps(features_used),
            "metrics": json.dumps(metrics),
            "feature_importances": json.dumps(feature_importances),
            "artifact_path": artifact_path,
            "status": status,
            "completed_at": datetime.utcnow(),
        }
    )
    session.commit()
    
    return str(model_id)


def run_model_train(
    as_of: Optional[datetime] = None,
    horizon_days: int = 90,
    model_type: str = "logistic",
    lookback_days: int = 730
) -> Dict[str, Any]:
    """
    Train a transfer prediction model.
    
    Args:
        as_of: Timestamp for training data cutoff (defaults to now)
        horizon_days: Prediction horizon in days (30, 90, 180)
        model_type: "logistic" or "gradient_boosting"
        lookback_days: How far back to look for training data
        
    Returns:
        dict with training results
    """
    if as_of is None:
        as_of = datetime.utcnow()
    
    model_version = generate_model_version()
    model_name = f"transfer_xgb_{horizon_days}d"
    
    console.print(f"[bold blue]🤖 Training model: {model_name}[/bold blue]")
    console.print(f"  • Version: {model_version}")
    console.print(f"  • Horizon: {horizon_days} days")
    console.print(f"  • As of: {as_of.isoformat()}")
    console.print(f"  • Model type: {model_type}")
    
    results = {
        "model_name": model_name,
        "model_version": model_version,
        "horizon_days": horizon_days,
        "as_of": as_of.isoformat(),
        "status": "started",
    }
    
    with get_sync_session() as session:
        try:
            # Build training data
            console.print("\n[bold]Building training data...[/bold]")
            df = build_training_features(session, as_of, lookback_days, horizon_days)
            
            if len(df) < settings.min_training_samples:
                console.print(f"[red]Insufficient training data: {len(df)} samples[/red]")
                results["status"] = "failed"
                results["error"] = f"Insufficient training data: {len(df)} samples"
                return results
            
            # Prepare features
            console.print("\n[bold]Preparing features...[/bold]")
            X, feature_names = prepare_features(df, FEATURE_COLUMNS)
            y = df["label"].values
            
            console.print(f"  • Feature matrix shape: {X.shape}")
            console.print(f"  • Positive samples: {y.sum()}")
            console.print(f"  • Negative samples: {len(y) - y.sum()}")
            
            # Train/test split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=settings.test_size,
                random_state=settings.random_state,
                stratify=y
            )
            
            console.print(f"  • Train size: {len(X_train)}")
            console.print(f"  • Test size: {len(X_test)}")
            
            # Train model
            console.print("\n[bold]Training model...[/bold]")
            model, imputer, scaler = train_model(X_train, y_train, model_type)
            
            # Evaluate
            console.print("\n[bold]Evaluating model...[/bold]")
            metrics = evaluate_model(model, imputer, scaler, X_test, y_test, feature_names)
            
            # Display metrics
            metrics_table = Table(title="Model Metrics")
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", style="green")
            
            for metric, value in metrics.items():
                metrics_table.add_row(metric, f"{value:.4f}")
            
            console.print(metrics_table)
            
            # Get feature importances
            feature_importances = get_feature_importances(model, feature_names)
            
            # Display top features
            console.print("\n[bold]Top 10 Feature Importances:[/bold]")
            for i, (feat, imp) in enumerate(list(feature_importances.items())[:10]):
                console.print(f"  {i+1}. {feat}: {imp:.4f}")
            
            # Save model artifact
            console.print("\n[bold]Saving model artifact...[/bold]")
            artifact_path = save_model_artifact(
                model, imputer, scaler, feature_names, model_version, horizon_days
            )
            console.print(f"  Saved to: {artifact_path}")
            
            # Register in database
            console.print("\n[bold]Registering model version...[/bold]")
            model_id = register_model_version(
                session,
                model_name=model_name,
                model_version=model_version,
                horizon_days=horizon_days,
                training_as_of=as_of,
                training_samples=len(df),
                positive_samples=int(y.sum()),
                negative_samples=int(len(y) - y.sum()),
                feature_count=len(feature_names),
                features_used=feature_names,
                metrics=metrics,
                feature_importances=feature_importances,
                artifact_path=artifact_path,
            )
            console.print(f"  Model ID: {model_id}")
            
            results["status"] = "completed"
            results["model_id"] = model_id
            results["artifact_path"] = artifact_path
            results["metrics"] = metrics
            results["feature_importances"] = feature_importances
            results["training_samples"] = len(df)
            
            console.print("\n[bold green]✅ Model training complete![/bold green]")
            
        except Exception as e:
            console.print(f"[red]Training failed: {e}[/red]")
            results["status"] = "failed"
            results["error"] = str(e)
            raise
    
    return results


def get_latest_model(session: Session, model_name: str, horizon_days: int) -> Optional[Dict[str, Any]]:
    """Get the latest deployed or completed model for a given horizon."""
    result = session.execute(
        text("""
            SELECT id, model_version, artifact_path, metrics, feature_importances, features_used
            FROM model_versions
            WHERE model_name = :model_name
            AND horizon_days = :horizon_days
            AND status IN ('completed', 'deployed')
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"model_name": model_name, "horizon_days": horizon_days}
    ).first()
    
    if result:
        return {
            "id": str(result.id),
            "model_version": result.model_version,
            "artifact_path": result.artifact_path,
            "metrics": json.loads(result.metrics) if result.metrics else {},
            "feature_importances": json.loads(result.feature_importances) if result.feature_importances else {},
            "features_used": json.loads(result.features_used) if result.features_used else [],
        }
    return None
