"""
TransferLens Worker Jobs
========================

Individual job modules:
- ingest: Demo data loading
- features: Feature building
- train: Model training
- predict: Prediction generation
- signals: Signal derivation from user events
- evaluate: Model evaluation with backtest
- candidates: Destination candidate generation
"""

from worker.jobs.ingest import run_demo_ingest
from worker.jobs.features import run_feature_build
from worker.jobs.train import run_model_train
from worker.jobs.predict import run_predictions
from worker.jobs.signals import run_signal_derivation
from worker.jobs.evaluate import run_model_evaluate
from worker.jobs.candidates import run_candidate_generation, generate_candidates_for_player

__all__ = [
    "run_demo_ingest",
    "run_feature_build",
    "run_model_train",
    "run_predictions",
    "run_signal_derivation",
    "run_model_evaluate",
    "run_candidate_generation",
    "generate_candidates_for_player",
]
