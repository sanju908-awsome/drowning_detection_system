"""Fail-closed temporal classifier loader: no model means not assessed."""

from pathlib import Path
from typing import Any

from .features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION


class RiskClassifier:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.model: Any = None
        self.reason = "No validated temporal classifier is configured."
        if model_path.is_file():
            try:
                import joblib
                artifact = joblib.load(model_path)
                if artifact.get("schema_version") != FEATURE_SCHEMA_VERSION or tuple(artifact.get("feature_names", ())) != FEATURE_NAMES:
                    self.reason = "Classifier feature schema does not match this application."
                elif artifact.get("model") is None:
                    self.reason = "Classifier artifact has no model."
                else:
                    self.model = artifact["model"]
                    self.reason = ""
            except Exception as exc:
                self.reason = f"Classifier could not be loaded: {type(exc).__name__}."

    @property
    def ready(self) -> bool:
        return self.model is not None

    def predict(self, features: dict[str, float]) -> dict[str, Any]:
        if not self.ready:
            return {"state": "UNASSESSED", "score": None, "reason": self.reason}
        vector = [[features[name] for name in FEATURE_NAMES]]
        probabilities = self.model.predict_proba(vector)[0]
        classes = list(self.model.classes_)
        idx = int(probabilities.argmax())
        label = str(classes[idx]).upper()
        allowed = {"SAFE", "WARNING", "EMERGENCY"}
        if label not in allowed:
            return {"state": "UNASSESSED", "score": None, "reason": "Classifier returned an unsupported risk label."}
        return {"state": label, "score": float(probabilities[idx]), "reason": None}
