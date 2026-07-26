#!/usr/bin/env python3
import os

from openai import OpenAI
import mlflow
from mlflow.genai.optimize import GepaPromptOptimizer
from mlflow.genai.scorers import Correctness
from mlflow.genai.datasets import create_dataset, get_dataset

from config import (
    setup_mlflow, MODEL_NAME, MODEL_URL,
    JUDGE_MODEL_NAME, JUDGE_MODEL_URL, PROMPT_NAME,
)


SYSTEM_INSTRUCTIONS = "You answers are displayed in the terminal, and are expected to be mostly short, concise and not use formats like .md"


def register_initial_prompt():
    prompt = mlflow.genai.register_prompt(
        name=PROMPT_NAME,
        template="You are a {{role}} assistant. {{instructions}}",
        commit_message="Initial prompt with role and instructions variables",
        tags={
            "author": "mlflow-demo",
            "task": "terminal-qa",
        },
    )
    print(f"Registered prompt '{PROMPT_NAME}' version {prompt.version}")
    return prompt


def register_updated_prompt():
    prompt = mlflow.genai.register_prompt(
        name=PROMPT_NAME,
        template="You are a {{role}} assistant. {{instructions}} Always provide a direct answer first, then explain briefly if needed.",
        commit_message="Added instruction to provide direct answers first",
        tags={
            "author": "mlflow-demo",
            "task": "terminal-qa",
        },
    )
    print(f"Updated prompt '{PROMPT_NAME}' to version {prompt.version}")
    return prompt


def set_prompt_aliases(v1, v2):
    mlflow.genai.set_prompt_alias(PROMPT_NAME, "production", v1)
    mlflow.genai.set_prompt_alias(PROMPT_NAME, "development", v2)
    print(f"Set alias 'production' -> version {v1}")
    print(f"Set alias 'development' -> version {v2}")


def attach_model_config(version):
    mlflow.genai.set_prompt_model_config(
        PROMPT_NAME,
        version,
        {
            "model_name": MODEL_NAME,
            "temperature": 0.7,
            "max_tokens": 256,
        },
    )
    print(f"Attached model config to version {version}")


def tag_prompt():
    mlflow.genai.set_prompt_tag(PROMPT_NAME, "environment", "internal-cluster")
    mlflow.genai.set_prompt_tag(PROMPT_NAME, "status", "active")
    print("Tagged prompt with environment and status")


def search_all_prompts():
    prompts = mlflow.genai.search_prompts()
    print(f"\nFound {len(prompts)} registered prompts:")
    for p in prompts:
        print(f"  - {p.name}")


def optimize_prompt():
    print("\n--- Prompt Optimization ---")
    print("Running evolutionary prompt optimization with GepaPromptOptimizer...")
    print(f"Reflection model: {JUDGE_MODEL_NAME}")

    os.environ["OPENAI_API_BASE"] = JUDGE_MODEL_URL

    train_data = [
        {
            "inputs": {"question": "What is Linux?"},
            "expectations": {"expected_response": "An open-source operating system kernel"},
        },
        {
            "inputs": {"question": "What does CPU stand for?"},
            "expectations": {"expected_response": "Central Processing Unit"},
        },
        {
            "inputs": {"question": "What is Python?"},
            "expectations": {"expected_response": "A high-level programming language"},
        },
        {
            "inputs": {"question": "What is Docker?"},
            "expectations": {"expected_response": "A containerization platform"},
        },
    ]

    def predict_fn(question: str) -> str:
        client = OpenAI(base_url=MODEL_URL)
        prompt = mlflow.genai.load_prompt(f"prompts:/{PROMPT_NAME}@production")
        system_content = prompt.format(role="terminal", instructions=SYSTEM_INSTRUCTIONS)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": question},
            ],
        )
        return response.choices[0].message.content

    judge_model_uri = f"openai:/{JUDGE_MODEL_NAME}"

    result = mlflow.genai.optimize_prompts(
        predict_fn=predict_fn,
        train_data=train_data,
        prompt_uris=[f"prompts:/{PROMPT_NAME}@production"],
        optimizer=GepaPromptOptimizer(
            reflection_model=judge_model_uri,
            max_metric_calls=10,
        ),
        scorers=[Correctness(model=judge_model_uri)],
    )

    print(f"Optimization complete. Best prompt registered as new version.")

    # Point production alias to the optimized version
    latest = mlflow.genai.load_prompt(f"prompts:/{PROMPT_NAME}")
    mlflow.genai.set_prompt_alias(PROMPT_NAME, "production", latest.version)
    print(f"Updated 'production' alias to optimized version {latest.version}")

    return result


def main():
    setup_mlflow()

    print("=== Prompt Management Lifecycle ===\n")

    # Step 1: Register initial prompt
    v1 = register_initial_prompt()

    # Step 2: Register updated version
    v2 = register_updated_prompt()

    # Step 3: Set aliases
    set_prompt_aliases(v1.version, v2.version)

    # Step 4: Attach model config
    attach_model_config(v1.version)

    # Step 5: Tag prompt
    tag_prompt()

    # Step 6: Search all prompts
    search_all_prompts()

    # Step 7: Load and demonstrate format
    prompt = mlflow.genai.load_prompt(f"prompts:/{PROMPT_NAME}@production")
    rendered = prompt.format(role="terminal", instructions=SYSTEM_INSTRUCTIONS)
    print(f"\nRendered production prompt:\n  {rendered}")

    # Step 8: Optimize prompt (optional, requires judge model endpoint)
    # Uncomment to run prompt optimization with gpt-oss-20b
    # optimize_prompt()

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
