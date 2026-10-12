"""Conservative confirmation/hysteresis for raw Random Forest outputs."""


class RiskStateLogic:
    def __init__(self, min_observations: int = 30, min_probability: float = 0.7,
                 warning_frames: int = 5, emergency_frames: int = 3, clear_frames: int = 15):
        self.min_observations = min_observations
        self.min_probability = min_probability
        self.confirmations = {"WARNING": warning_frames, "EMERGENCY": emergency_frames, "SAFE": clear_frames}
        self.state = "UNASSESSED"
        self.pending = None
        self.pending_count = 0
        self.last_score = None

    def update(self, prediction: dict, observations: int) -> dict:
        raw_state, score = prediction.get("state"), prediction.get("score")
        if observations < self.min_observations:
            return {"state": "UNASSESSED", "score": None, "reason": "Insufficient track history."}
        if raw_state not in self.confirmations or score is None or score < self.min_probability:
            self.pending, self.pending_count = None, 0
            # Keep a confirmed alert active while evidence is uncertain. Do not call uncertainty safe.
            if self.state in {"WARNING", "EMERGENCY"}:
                return {"state": self.state, "score": self.last_score, "reason": "Alert held during uncertain evidence."}
            return {"state": "UNASSESSED", "score": None, "reason": "Model output did not pass the configured threshold."}

        self.last_score = float(score)
        if raw_state == self.state:
            self.pending, self.pending_count = None, 0
            return {"state": self.state, "score": self.last_score, "reason": None}
        if self.pending == raw_state:
            self.pending_count += 1
        else:
            self.pending, self.pending_count = raw_state, 1
        needed = self.confirmations[raw_state]
        if self.pending_count >= needed:
            self.state = raw_state
            self.pending, self.pending_count = None, 0
        elif self.state in {"WARNING", "EMERGENCY"}:
            # Do not reduce an active state until the new state has held long enough.
            pass
        else:
            return {"state": "UNASSESSED", "score": None, "reason": "Waiting for consecutive model evidence."}
        return {"state": self.state, "score": self.last_score, "reason": None}
