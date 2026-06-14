"""Model registry with latency tracking and least-requests selection.

Benchmarked latencies (single trial, short prompt ~10 tok output):
  Model                          Total(s)  TTFT(ms)  tok/s   Tier
  Llama 3.2 3B                   1.76      339       57.3    fast
  Llama 4 Maverick 17B-128e      2.82      315       70.7    fast
  Llama 3.1 70B                  15.37     486       13.0    capable
  Llama 3.3 70B                  22.98     1014      8.6     capable
  DeepSeek V4 Flash              ~495      queued    -       unreliable
  DeepSeek V4 Pro                timeout   -         -       unreliable
"""
import threading
import time
from typing import Optional


class ModelInfo:
    def __init__(self, model_id: str, label: str, tier: str, weight: float = 1.0):
        self.model_id = model_id
        self.label = label
        self.tier = tier  # "fast", "capable", "unreliable"
        self.weight = weight  # lower = preferred
        self.request_count = 0
        self.error_count = 0
        self.last_latency_s = 0.0
        self.avg_latency_s = 0.0

    def record_request(self, latency_s: float, success: bool = True):
        self.request_count += 1
        if not success:
            self.error_count += 1
        self.last_latency_s = latency_s
        # Rolling average
        self.avg_latency_s = self.avg_latency_s * 0.9 + latency_s * 0.1

    @property
    def score(self) -> float:
        """Lower is better for selection."""
        base = self.weight
        usage_penalty = self.request_count * 0.1
        error_penalty = self.error_count * 2.0
        latency_penalty = self.avg_latency_s * 0.05
        return base + usage_penalty + error_penalty + latency_penalty


class ModelRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._models: dict[str, ModelInfo] = {}
        self._init_models()

    def _init_models(self):
        # Fast/small models - good for simple tasks (classifier, flag_detector)
        self.register("meta/llama-3.2-3b-instruct", "Llama 3.2 3B", "fast", weight=2.0)
        self.register("meta/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick 17B", "fast", weight=1.0)
        self.register("meta/llama-3.1-8b-instruct", "Llama 3.1 8B", "fast", weight=1.5)

        # Capable models - for complex reasoning
        self.register("meta/llama-3.1-70b-instruct", "Llama 3.1 70B", "capable", weight=1.0)

        # Unreliable/slow on this API tier
        self.register("deepseek-ai/deepseek-v4-flash", "DeepSeek V4 Flash", "unreliable", weight=10.0)
        self.register("deepseek-ai/deepseek-v4-pro", "DeepSeek V4 Pro", "unreliable", weight=10.0)

    def register(self, model_id: str, label: str, tier: str, weight: float = 1.0):
        self._models[model_id] = ModelInfo(model_id, label, tier, weight)

    def select_model(self, tier: str = "capable") -> str:
        """Select the model with lowest score within the given tier(s)."""
        with self._lock:
            candidates = [m for m in self._models.values() if m.tier == tier or tier == "any"]
            if not candidates:
                candidates = list(self._models.values())
            candidates.sort(key=lambda m: m.score)
            return candidates[0].model_id

    def select_best_for_role(self, role: str) -> str:
        """Select appropriate model based on agent role."""
        if role in ("classifier", "flag_detector", "difficulty_estimator"):
            return self.select_model("fast")
        return self.select_model("capable")

    def record(self, model_id: str, latency_s: float, success: bool = True):
        with self._lock:
            model = self._models.get(model_id)
            if model:
                model.record_request(latency_s, success)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                mid: {
                    "label": m.label,
                    "tier": m.tier,
                    "requests": m.request_count,
                    "errors": m.error_count,
                    "avg_latency_s": round(m.avg_latency_s, 3),
                    "score": round(m.score, 3),
                }
                for mid, m in sorted(self._models.items(), key=lambda x: x[1].score)
            }


model_registry = ModelRegistry()
