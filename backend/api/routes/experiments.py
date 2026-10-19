"""
ProvenanceLab — Experiment API Routes
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.api.schemas.models import RunExperimentRequest, RunExperimentResponse
from backend.carriers.factory import get_carrier
from backend.experiments.runner import ExperimentPipeline

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post("/run", response_model=RunExperimentResponse)
async def run_experiment_endpoint(req: RunExperimentRequest):
    """Run a reproducible survival experiment with real carrier inference and model fitting."""
    try:
        carrier = get_carrier(req.carrier)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load carrier '{req.carrier}': {e}")

    try:
        pipeline = ExperimentPipeline(carrier=carrier)
        df, summary = pipeline.run_survival_experiment(
            experiment_id=req.experiment_id,
        )
        return RunExperimentResponse(
            success=True,
            experiment_id=req.experiment_id,
            total_trials=summary["total_trials"],
            decodable_rate=summary["decodable_rate"],
            carrier=summary["carrier"],
            p_H1_mle=summary.get("p_H1_mle"),
            test_ece=summary.get("test_ece"),
            csv_path=summary["csv_path"],
            message="Experiment completed successfully.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Experiment run failed: {e}")


@router.get("")
@router.get("/list")
async def list_experiments():
    """List all completed experiment result summaries."""
    results_dir = "experiments/results"
    if not os.path.exists(results_dir):
        return {"experiments": []}

    files = [f for f in os.listdir(results_dir) if f.endswith("_summary.json")]
    summaries = []
    import json
    for f in sorted(files, reverse=True):
        try:
            with open(os.path.join(results_dir, f), "r", encoding="utf-8") as fp:
                summaries.append(json.load(fp))
        except Exception:
            continue
    return {"experiments": summaries}
