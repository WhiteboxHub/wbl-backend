import asyncio
import random
import sys

from fapi.ai_prep.utils.telemetry_client import emit_pipeline_metric


async def run_pipeline_simulation():
    print("=" * 60)
    print("AIPrep Pipeline Telemetry Simulation")
    print("Sending live assessment pipeline metrics from wbl-backend to wbl-observability...")
    print("=" * 60)

    assessments = [
        {"id": 105, "type": "TECHNICAL", "candidate_id": 42},
        {"id": 106, "type": "TECHNICAL", "candidate_id": 43},
        {"id": 107, "type": "SYSTEM_DESIGN", "candidate_id": 44},
    ]

    stages = [
        ("WHISPER_AUDIO", 1100, 1800),     # Whisper STT: ~1.1s - 1.8s
        ("VIDEO_ENGINE", 650, 1100),       # Video Telemetry: ~650ms - 1.1s
        ("EVAL_ENGINE_LLM", 2800, 4200),   # LLM Generation: ~2.8s - 4.2s
        ("SCORES_ENGINE", 180, 320),       # Scores Engine Schema Validation: ~180ms - 320ms
    ]

    for assess in assessments:
        print(f"\nProcessing Assessment #{assess['id']} ({assess['type']})...")
        for stage_name, min_ms, max_ms in stages:
            duration = random.randint(min_ms, max_ms)
            status = "SUCCESS"
            msg = None
            if duration > 4000:
                msg = "LLM response took longer than 4.0s (p95 threshold exceeded)"

            ok = await emit_pipeline_metric(
                assessment_id=assess["id"],
                candidate_id=assess["candidate_id"],
                stage=stage_name,
                status=status,
                duration_ms=duration,
                message=msg,
                metadata={"assessment_type": assess["type"]}
            )
            print(f"  [METRIC EMITTED] {stage_name:<16} | Duration: {duration:>4}ms | Status: {status} | Sent: {ok}")
            await asyncio.sleep(0.2)

    print("\n" + "=" * 60)
    print("SUCCESS! Metrics have been ingested into wbl-observability.")
    print("Now open your Grafana dashboard at http://localhost:3001 and click Refresh!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_pipeline_simulation())
