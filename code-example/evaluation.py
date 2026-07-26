#!/usr/bin/env python3
import os

from openai import OpenAI
import mlflow
from mlflow.genai.datasets import create_dataset, get_dataset
from mlflow.genai import scorer
from mlflow.genai.scorers import Correctness, Safety, RelevanceToQuery
from mlflow.genai.judges import make_judge

from config import (
    setup_mlflow, MODEL_NAME, MODEL_URL,
    JUDGE_MODEL_NAME, JUDGE_MODEL_URL,
)


DATASET_NAME = "terminal_questions_v2"


def create_evaluation_dataset():
    dataset = create_dataset(
        name=DATASET_NAME,
        tags={
            "version": "2.0",
            "domain": "general-knowledge",
            "team": "ml-platform",
            "status": "active",
        },
    )

    records = [
        {
            "inputs": {"question": "What is Age of Empires 4?"},
            "expectations": {"expected_response": "A real-time strategy game developed by Relic Entertainment"},
        },
        {
            "inputs": {"question": "What color is a cucumber?"},
            "expectations": {"expected_response": "Green"},
        },
        {
            "inputs": {"question": "Name a song by The Killers"},
            "expectations": {"expected_response": "Mr. Brightside"},
        },
        {
            "inputs": {"question": "What is Kubernetes?"},
            "expectations": {"expected_response": "An open-source container orchestration platform"},
        },
        {
            "inputs": {"question": "What does API stand for?"},
            "expectations": {"expected_response": "Application Programming Interface"},
        },
        {
            "inputs": {"question": "Who painted the Mona Lisa?"},
            "expectations": {"expected_response": "Leonardo da Vinci"},
        },
        {
            "inputs": {"question": "What is the capital of Japan?"},
            "expectations": {"expected_response": "Tokyo"},
        },
        {
            "inputs": {"question": "What is a Dockerfile?"},
            "expectations": {"expected_response": "A text file with instructions to build a Docker container image"},
        },
        {
            "inputs": {"question": "How many bits in a byte?"},
            "expectations": {"expected_response": "8"},
        },
        {
            "inputs": {"question": "What programming language is MLflow written in?"},
            "expectations": {"expected_response": "Python"},
        },
    ]

    dataset.merge_records(records)
    print(f"Created dataset '{DATASET_NAME}' with {len(records)} records")
    return dataset


def predict_fn(question: str) -> str:
    client = OpenAI(base_url=MODEL_URL)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are an assistant that receives questions from a user using a terminal. "
                           "Your answers are displayed in the terminal, and are expected to be mostly short, "
                           "concise and not use formats like .md",
            },
            {"role": "user", "content": question},
        ],
    )
    return response.choices[0].message.content


# --- Custom Code Scorers ---

@scorer
def is_concise(outputs: str) -> bool:
    return len(outputs.split()) <= 50


@scorer
def is_well_formatted(outputs: str) -> bool:
    markdown_indicators = ["##", "**", "```", "| ", "---"]
    return not any(indicator in outputs for indicator in markdown_indicators)


@scorer
def has_answer(outputs: str) -> bool:
    refusal_phrases = [
        "i don't know", "i cannot", "i'm not sure",
        "i am not able", "as an ai", "i'm unable",
    ]
    lower = outputs.lower()
    return not any(phrase in lower for phrase in refusal_phrases)


# --- Custom LLM Judge ---

def create_terminal_friendly_judge():
    os.environ["OPENAI_API_BASE"] = JUDGE_MODEL_URL
    judge_model_uri = f"openai:/{JUDGE_MODEL_NAME}"

    return make_judge(
        name="terminal_friendly",
        model=judge_model_uri,
        description="Evaluates if a response is appropriate for terminal display",
        instructions=(
            "Evaluate whether the following response is appropriate for display in a terminal. "
            "A terminal-friendly response should be:\n"
            "- Concise (not overly verbose)\n"
            "- Free of markdown formatting (no headers, bold, tables, code blocks)\n"
            "- Direct and to the point\n"
            "- Not excessively long (ideally under 100 words)\n\n"
            "Question: {{ inputs }}\n"
            "Response: {{ outputs }}\n\n"
            "Is this response terminal-friendly?"
        ),
        feedback_value_type=bool,
    )


def run_evaluation(dataset):
    os.environ["OPENAI_API_BASE"] = JUDGE_MODEL_URL
    judge_model_uri = f"openai:/{JUDGE_MODEL_NAME}"

    all_scorers = [
        # Code-based scorers
        is_concise,
        is_well_formatted,
        has_answer,
        # Built-in LLM-as-judge scorers
        Correctness(model=judge_model_uri),
        Safety(model=judge_model_uri),
        RelevanceToQuery(model=judge_model_uri),
        # Custom LLM judge
        create_terminal_friendly_judge(),
    ]

    print(f"\nRunning evaluation with {len(all_scorers)} scorers...")
    print(f"Judge model: {JUDGE_MODEL_NAME} at {JUDGE_MODEL_URL}")

    results = mlflow.genai.evaluate(
        data=dataset,
        predict_fn=predict_fn,
        scorers=all_scorers,
    )

    print("\n=== Evaluation Results ===")
    print(results.tables[0] if results.tables else "No results table available")
    return results


def manage_dataset():
    datasets = mlflow.genai.search_datasets()
    print(f"\nFound {len(datasets)} datasets:")
    for ds in datasets:
        print(f"  - {ds.name} (id: {ds.dataset_id})")

    mlflow.genai.set_dataset_tags(
        dataset_id=datasets[0].dataset_id if datasets else None,
        tags={"last_eval_run": "latest", "reviewed": "true"},
    )


def main():
    setup_mlflow()

    print("=== Evaluation Pipeline ===\n")

    # Step 1: Create or get dataset
    dataset = create_evaluation_dataset()

    # Step 2: Run evaluation with all scorers
    results = run_evaluation(dataset)

    # Step 3: Dataset management
    # manage_dataset()

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
