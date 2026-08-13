"""Shared feature preprocessing: missing-value indicators + imputation.

Fit ONLY on the training split (never validation/test) and reused as-is at
val/test/prediction time, exactly like a real deployment would work — the
imputer must not "see" future/held-out data either.

Per the project's data-quality requirement, missing values are never
silently treated as 0 when 0 has racing meaning (e.g. a win-rate feature):
every feature that has any missingness in the training data gets a
companion `<feature>__isnan` indicator column BEFORE imputation, so a model
can distinguish "true zero" from "unknown".
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class FeaturePreprocessor:
    feature_columns: list[str]
    medians_: dict[str, float] = field(default_factory=dict)
    indicator_columns_: list[str] = field(default_factory=list)
    fitted_: bool = False

    def fit(self, df: pd.DataFrame) -> "FeaturePreprocessor":
        for col in self.feature_columns:
            series = pd.to_numeric(df[col], errors="coerce")
            if series.isna().any():
                self.indicator_columns_.append(col)
            median = series.median()
            self.medians_[col] = float(median) if pd.notna(median) else 0.0
        self.fitted_ = True
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.fitted_:
            raise RuntimeError("FeaturePreprocessor.transform called before fit()")

        columns: dict[str, pd.Series] = {}
        for col in self.feature_columns:
            series = pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(np.nan, index=df.index)
            if col in self.indicator_columns_:
                columns[f"{col}__isnan"] = series.isna().astype(int)
            columns[col] = series.fillna(self.medians_.get(col, 0.0))
        return pd.DataFrame(columns, index=df.index)

    def output_columns(self) -> list[str]:
        cols: list[str] = []
        for col in self.feature_columns:
            if col in self.indicator_columns_:
                cols.append(f"{col}__isnan")
            cols.append(col)
        return cols

    def to_dict(self) -> dict:
        return {
            "feature_columns": self.feature_columns,
            "medians": self.medians_,
            "indicator_columns": self.indicator_columns_,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FeaturePreprocessor":
        return cls(
            feature_columns=data["feature_columns"],
            medians_=data["medians"],
            indicator_columns_=data["indicator_columns"],
            fitted_=True,
        )

    def missing_fraction(self, df: pd.DataFrame) -> pd.Series:
        """Per-row fraction of tracked features that were missing (NaN)
        BEFORE imputation — used as a ModelConfidence input."""
        sub = df[self.feature_columns].apply(pd.to_numeric, errors="coerce")
        return sub.isna().mean(axis=1)


@dataclass
class OutOfDistributionDetector:
    """Flags rows with an unusually large fraction of features sitting
    outside the [5th, 95th] percentile band observed in the training data —
    a simple, transparent proxy for "this runner looks unlike anything the
    model was trained on", used as a ModelConfidence input."""

    feature_columns: list[str]
    lower_: dict[str, float] = field(default_factory=dict)
    upper_: dict[str, float] = field(default_factory=dict)
    fitted_: bool = False

    def fit(self, df: pd.DataFrame) -> "OutOfDistributionDetector":
        for col in self.feature_columns:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) == 0:
                continue
            self.lower_[col] = float(series.quantile(0.05))
            self.upper_[col] = float(series.quantile(0.95))
        self.fitted_ = True
        return self

    def extreme_fraction(self, df: pd.DataFrame) -> pd.Series:
        if not self.fitted_:
            raise RuntimeError("OutOfDistributionDetector.extreme_fraction called before fit()")
        flag_columns: dict[str, pd.Series] = {}
        for col in self.feature_columns:
            if col not in self.lower_:
                continue
            series = pd.to_numeric(df[col], errors="coerce")
            flag_columns[col] = (series < self.lower_[col]) | (series > self.upper_[col])
        if not flag_columns:
            return pd.Series(0.0, index=df.index)
        flags = pd.DataFrame(flag_columns, index=df.index)
        return flags.mean(axis=1)

    def to_dict(self) -> dict:
        return {"feature_columns": self.feature_columns, "lower": self.lower_, "upper": self.upper_}

    @classmethod
    def from_dict(cls, data: dict) -> "OutOfDistributionDetector":
        return cls(feature_columns=data["feature_columns"], lower_=data["lower"], upper_=data["upper"], fitted_=True)
