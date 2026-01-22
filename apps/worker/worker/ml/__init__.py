"""
Machine Learning Utilities
==========================

Common ML utilities for feature engineering and model evaluation.
"""

from typing import List, Dict, Any, Optional
import numpy as np


def normalize_features(features: Dict[str, float], feature_names: List[str]) -> np.ndarray:
    """Convert feature dict to normalized numpy array."""
    values = []
    for name in feature_names:
        val = features.get(name, 0)
        if val is None:
            val = 0
        values.append(float(val))
    return np.array(values)


def feature_dict_to_array(features: Dict[str, Any], columns: List[str]) -> np.ndarray:
    """Convert feature dict to array in specified column order."""
    result = []
    for col in columns:
        val = features.get(col, 0)
        if val is None:
            val = 0
        elif isinstance(val, bool):
            val = 1 if val else 0
        result.append(float(val))
    return np.array(result)


def compute_class_weights(y: np.ndarray) -> Dict[int, float]:
    """Compute class weights for imbalanced classification."""
    n_samples = len(y)
    n_classes = len(np.unique(y))
    
    weights = {}
    for cls in np.unique(y):
        n_cls = np.sum(y == cls)
        weights[int(cls)] = n_samples / (n_classes * n_cls)
    
    return weights
