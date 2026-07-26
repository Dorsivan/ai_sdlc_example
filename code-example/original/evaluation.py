import os
import sys
from typing import Iterable

from openai import OpenAI
import mlflow
from mlflow.entities import AssessmentSource, AssessmentSourceType
from mlflow.genai.datasets import create_dataset, get_dataset
from mlflow.genai import scorer
from mlflow.genai.scorers import Correctness, Safety
from main import call_the_model_completions


MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-oss-20b")
MODEL_URL = os.getenv("MODEL_URL", "http://a5b3148f0995c48088e0800feaa2c651-1539933567.us-east-2.elb.amazonaws.com/demo-llm/gpt-oss-20b/v1")
SYSTEM_PROMPT = "You are an assistant that receives questions from a user using a terminal. As such, you answers are displayed in the terminal, and are expected to be mostly short, concise and not use formats like .md"


def create_dataset_in_mlflow():
    # Create a new dataset
    dataset = create_dataset(
        name="terminal_questions",
        experiment_id=["1"],  # Link to experiments
        tags={"version": "1.0", "team": "ml-platform", "status": "active"},
    )

    print(f"Created dataset: {dataset.dataset_id}")

    # Add records with inputs and expectations (ground truth)
    new_records = [
        {
            "inputs": {"question": "What is Age of Empires 4?"},
            "expectations": {
                "expected_response": "It is an RTS game"
            },
        },
        {
            "inputs": {"question": "What color is a cucumber?"},
            "expectations": {
                "expected_response": ("It is green")
            },
        },
        {
            "inputs": {"question": "Name a song by The Killers"},
            "expectations": {
                "expected_response": ("Mr. Brightside")
            },
        },
    ]

    dataset.merge_records(new_records)

    return dataset


def predict_fn(question: str) -> str:
    client = OpenAI(base_url=MODEL_URL)
    return call_the_model_completions(client, question)


@scorer
def is_concise(outputs: str) -> bool:
    return len(outputs.split()) <= 5

mlflow.set_tracking_uri("https://mlflow-route-mlflow.apps.ocp.wnk5d.sandbox1583.opentlc.com")
mlflow.set_experiment("Demo Project - gpt-oss-20b")

# os.environ["AZURE_API_BASE"] = os.getenv("MODEL_URL", "http://a5b3148f0995c48088e0800feaa2c651-1539933567.us-east-2.elb.amazonaws.com/demo-llm/gpt-oss-20b/v1")
# os.environ["AZURE_API_KEY"] = "doesn't-matter"
os.environ["OPENAI_API_BASE"] = os.getenv("MODEL_URL", "http://a5b3148f0995c48088e0800feaa2c651-1539933567.us-east-2.elb.amazonaws.com/demo-llm/gpt-oss-20b/v1")
# os.environ["OPENAI_DEPLOYMENT_NAME"] = "gpt-oss-20b"
# os.environ["OPENAI_API_VERSION"] = "gpt-oss-20b"


scorers = [
    # Correctness(model="azure:/gpt-oss-20b"),
    # Safety(model="azure:/gpt-oss-20b"),
    is_concise
]

# eval_dataset = get_dataset(dataset_id="d-854f453766ba49ddaaa94fef8cfb205d")

eval_dataset = create_dataset_in_mlflow()

print(eval_dataset.name)

results = mlflow.genai.evaluate(
    data=eval_dataset,
    predict_fn=predict_fn,
    scorers=scorers
)


