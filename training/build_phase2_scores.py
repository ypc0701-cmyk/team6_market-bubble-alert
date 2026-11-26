"""Build Phase 2 scores using Javier's evaluated serving decision."""

import re
import subprocess
from pathlib import Path

from validate_phase2_training import ROOT, DBT_BIN

REPORT = ROOT / "evaluation" / "output" / "report.md"

ALLOWED_MODELS = {
    "baseline_drawdown",
    "baseline_vol",
    "logistic",
    "boosted_trees",
}


def get_served_model():
    if not REPORT.exists():
        raise FileNotFoundError(f"Evaluation report not found: {REPORT}")

    text = REPORT.read_text(encoding="utf-8")

    match = re.search(
        r"Served model:\s*(baseline_drawdown|baseline_vol|logistic|boosted_trees)\b",
        text,
    )

    if not match:
        raise ValueError("No valid served-model decision found in report.md")

    model = match.group(1)

    if model not in ALLOWED_MODELS:
        raise ValueError(f"Invalid served model: {model}")

    return model


def main():
    model = get_served_model()
    print(f"Evaluation selected served model: {model}", flush=True)

    command = [
        str(DBT_BIN),
        "build",
        "--select", "model_scores",
        "--project-dir", str(ROOT / "dbt"),
        "--profiles-dir", str(Path.home() / ".dbt"),
        "--target", "dev",
        "--vars", f"phase2_served_model: {model}",
    ]

    subprocess.run(command, check=True, cwd=ROOT)

    print(f"Phase 2 scores built successfully using {model}.")


if __name__ == "__main__":
    main()
