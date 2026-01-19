import collections
import time
from typing import Dict, Optional, Tuple, Any

import numpy as np
import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent  # dossier models/

class LiveHMMRecognizer:
    """
    Fenêtre glissante -> normalisation -> scores HMM -> décision.
    Retourne None si "no move".
    """

    def __init__(
        self,
        window_size: int = 60,
        step_size: int = 3,
        num_features: int = 9,
        scaler_path: str = "models/scaler.joblib",
        models_path: str = "models/hmm_models.joblib",
        # --- NO MOVE gate ---
        activity_threshold: float = 10,   # à ajuster
        # --- décision HMM ---
        min_margin: float = 8.0,            # best - second_best (à ajuster)
        # --- anti-spam ---
        cooldown_ms: int = 700,             # à ajuster
        debug: bool = True
    ):
        self.window_size = window_size
        self.step_size = step_size
        self.num_features = num_features

        self.window_buffer = collections.deque(maxlen=window_size)
        self.new_sample_counter = 0

        self.scaler = joblib.load(BASE_DIR / "models/scaler.joblib")
        self.models = joblib.load(BASE_DIR / "models/hmm_models.joblib")

        self.activity_threshold = activity_threshold
        self.min_margin = min_margin
        self.cooldown_ms = cooldown_ms

        self._last_emit_ts = 0.0
        self._last_label = None

        self.debug = debug

        print(
            f"[Recognizer] Loaded scaler={scaler_path} models={models_path} ({len(self.models)} classes)")

    def add_sample(self, sample_9d: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        sample_9d: shape (9,)
        Retour:
          - None si pas de décision (fenêtre pas prête ou no-move ou incertain)
          - dict sinon: {label, scores, margin, activity}
        """
        if sample_9d.shape != (self.num_features,):
            return None

        self.window_buffer.append(sample_9d)
        self.new_sample_counter += 1

        if len(self.window_buffer) < self.window_size:
            if self.debug:
                print(
                    f"[HMM] Buffering... {len(self.window_buffer)}/{self.window_size}")
            return None

        if self.new_sample_counter < self.step_size:
            return None

        self.new_sample_counter = 0
        window = np.array(self.window_buffer)  # (T,9)

        # 1) NO MOVE gate
        activity = self._activity(window)
        if activity < self.activity_threshold:
            if self.debug:
                print(
                    f"[HMM] NO MOVE (activity={activity:.4f} < {self.activity_threshold})")
            return None

        # 2) Normalisation
        window_norm = self.scaler.transform(window)

        # 3) Scores HMM
        scores = {}
        for label, model in self.models.items():
            try:
                scores[label] = float(model.score(window_norm))
            except Exception:
                scores[label] = float("-inf")

        # Debug
        if self.debug:
            print("[HMM] Scores:")
            for k, v in scores.items():
                print(f"   {k:10s}: {v:8.2f}")

        # 4) Décision: best + margin
        best_label, best_score = max(scores.items(), key=lambda kv: kv[1])
        second_best = sorted(scores.values(), reverse=True)[
            1] if len(scores) > 1 else float("-inf")
        margin = best_score - second_best

        if margin < self.min_margin:
            if self.debug:
                print(
                    f"[HMM] UNCERTAIN (margin={margin:.2f} < {self.min_margin})")
            return None

        # 5) Cooldown + anti-spam (évite de répéter)
        now_ms = time.time() * 1000.0
        if (now_ms - self._last_emit_ts) < self.cooldown_ms and best_label == self._last_label:
            return None

        self._last_emit_ts = now_ms
        self._last_label = best_label

        if self.debug:
            print(
                f"[HMM] ✅ RECOGNIZED: {best_label} | margin={margin:.2f} | activity={activity:.2f}")

        return {
            "label": best_label,
            "scores": scores,
            "margin": margin,
            "activity": activity,
        }

    @staticmethod
    def _activity(window: np.ndarray) -> float:
        """
        Mesure simple: variabilité sur acc + gyro.
        window: (T,9) = [ax ay az gx gy gz alpha beta gamma]
        """
        acc = window[:, 0:3]
        gyro = window[:, 3:6]

        acc_norm = np.linalg.norm(acc, axis=1)
        gyro_norm = np.linalg.norm(gyro, axis=1)

        # std(acc) + petite pondération std(gyro)
        return float(np.std(acc_norm) + 0.15 * np.std(gyro_norm))
