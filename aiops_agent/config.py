"""Central configuration. All thresholds are fixed BEFORE running experiments."""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    # data / measurement
    step_s: int = 15              # one metric sample every 15 simulated seconds
    n_pre: int = 40               # samples before remediation
    n_post: int = 12              # samples after remediation
    baseline_points: int = 20     # first 20 samples = "normal" reference window
    # detection
    z_thresh: float = 6.0         # robust z-score threshold
    sustain: int = 4              # consecutive samples required (filters flapping spikes)
    # correlation
    corr_window_s: int = 120      # max time gap between linked alerts
    # RCA decision thresholds (confidence = relative support, NOT calibrated probability)
    conf_min: float = 0.60
    margin_min: float = 0.20
    # verification
    verify_points: int = 5        # last k post-action samples are compared
    resolved_ratio: float = 0.20  # residual deviation <=20% of incident deviation -> resolved
    unresolved_ratio: float = 0.70  # >=70% -> unresolved; in between -> inconclusive
    # simulated durations (seconds) used ONLY for simulated time-to-resolution
    action_duration_s: dict = field(default_factory=lambda: {
        "scale_out_replicas": 60, "restart_service": 90, "increase_db_pool_size": 30,
        "clear_cache": 20, "rollback_deployment": 120})
    mode: str = os.getenv("AIOPS_MODE", "simulate")   # only 'simulate' is implemented


CFG = Config()
