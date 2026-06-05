from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_WEIGHTS = {
    "sharpness": 0.35,
    "brightness": 0.20,
    "keypoints": 0.25,
    "dynamic_range": 0.10,
    "clipping_penalty": 0.05,
    "redundancy_penalty": 0.05,
}


def robust_normalize(values, p_low: float = 5, p_high: float = 95):
    series = pd.Series(values, dtype="float64")
    result = pd.Series(0.0, index=series.index, dtype="float64")
    valid = series.replace([np.inf, -np.inf], np.nan).dropna()

    if valid.empty:
        return result

    low = float(np.percentile(valid, p_low))
    high = float(np.percentile(valid, p_high))
    if np.isclose(high, low):
        result.loc[valid.index] = 1.0
        return result

    normalized = (series - low) / (high - low)
    return normalized.clip(0.0, 1.0).fillna(0.0)


def compute_brightness_score(brightness):
    values = pd.Series(brightness, dtype="float64")
    score = 1.0 - (values - 0.5).abs() / 0.5
    return score.clip(0.0, 1.0).fillna(0.0)


def compute_quality_scores(df: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    scored = df.copy()

    scored["sharpness_score"] = robust_normalize(scored["sharpness"])
    scored["brightness_score"] = compute_brightness_score(scored["brightness"])
    scored["keypoint_score"] = robust_normalize(scored["keypoints_orb"])
    scored["dynamic_range_score"] = robust_normalize(scored["dynamic_range"])
    scored["clipping_penalty"] = scored["clipping"].astype(float).clip(0.0, 1.0).fillna(0.0)
    scored["redundancy_penalty"] = (
        scored["redundancy_ssim_to_prev"].astype(float).clip(0.0, 1.0).fillna(0.0)
    )

    scored["quality_score"] = (
        weights["sharpness"] * scored["sharpness_score"]
        + weights["brightness"] * scored["brightness_score"]
        + weights["keypoints"] * scored["keypoint_score"]
        + weights["dynamic_range"] * scored["dynamic_range_score"]
        - weights["clipping_penalty"] * scored["clipping_penalty"]
        - weights["redundancy_penalty"] * scored["redundancy_penalty"]
    ).clip(0.0, 1.0)

    return scored
