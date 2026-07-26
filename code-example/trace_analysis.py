#!/usr/bin/env python3
import mlflow
from mlflow.entities import AssessmentSource, AssessmentSourceType

from config import setup_mlflow


def search_recent_traces(max_results=10):
    traces_df = mlflow.search_traces(
        max_results=max_results,
    )
    print(f"Found {len(traces_df)} traces")
    return traces_df


def print_trace_summary(traces_df):
    print("\n=== Trace Summary ===\n")
    for _, row in traces_df.iterrows():
        trace_id = row.get("trace_id", "N/A")
        status = row.get("status", "N/A")
        timestamp = row.get("timestamp_ms", "N/A")
        request = str(row.get("request", ""))[:80]
        response = str(row.get("response", ""))[:80]

        print(f"Trace: {trace_id}")
        print(f"  Status: {status}")
        print(f"  Time: {timestamp}")
        print(f"  Request: {request}...")
        print(f"  Response: {response}...")
        print()


def add_expectation_to_trace(trace_id: str, expected: str):
    mlflow.log_expectation(
        trace_id=trace_id,
        name="expected_response",
        value=expected,
        source=AssessmentSource(
            source_type=AssessmentSourceType.HUMAN,
            source_id="reviewer",
        ),
    )
    print(f"Logged expectation on trace {trace_id}")


def override_feedback_on_trace(trace_id: str, assessment_id: str, new_value, rationale: str):
    mlflow.override_feedback(
        trace_id=trace_id,
        assessment_id=assessment_id,
        value=new_value,
        rationale=rationale,
        source=AssessmentSource(
            source_type=AssessmentSourceType.HUMAN,
            source_id="reviewer",
        ),
    )
    print(f"Overrode feedback {assessment_id} on trace {trace_id}")


def batch_tag_traces(trace_ids: list[str], tags: dict):
    for trace_id in trace_ids:
        for key, value in tags.items():
            mlflow.set_trace_tag(trace_id, key, value)
    print(f"Tagged {len(trace_ids)} traces with {tags}")


def main():
    setup_mlflow()

    print("=== Trace Analysis ===\n")

    # Step 1: Search recent traces
    traces_df = search_recent_traces(max_results=5)

    if traces_df.empty:
        print("No traces found. Run main.py first to generate traces.")
        return

    # Step 2: Print summary
    print_trace_summary(traces_df)

    # Step 3: Batch tag traces
    trace_ids = traces_df["trace_id"].tolist()
    batch_tag_traces(trace_ids, {"reviewed": "true", "batch": "analysis-run-1"})

    # Step 4: Add expectation to the most recent trace
    most_recent_trace_id = trace_ids[0]
    add_expectation_to_trace(most_recent_trace_id, "A concise, terminal-friendly answer")

    # Step 5: Override feedback (example — requires a real assessment_id)
    # To get an assessment_id, inspect the trace in the MLflow UI
    # or use mlflow.get_trace(trace_id) to find existing assessments
    #
    # trace = mlflow.get_trace(most_recent_trace_id)
    # if trace.info.assessments:
    #     assessment_id = trace.info.assessments[0].assessment_id
    #     override_feedback_on_trace(
    #         most_recent_trace_id,
    #         assessment_id,
    #         new_value=True,
    #         rationale="Reviewer corrected: response was actually helpful",
    #     )

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
