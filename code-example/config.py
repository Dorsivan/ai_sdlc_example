import os

import mlflow


# App model
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2-5-0-5b-instruct")
MODEL_URL = os.getenv("MODEL_URL", "http://ae8a9def8616e4e2381163e0b4d76aca-772845044.us-east-1.elb.amazonaws.com/nutrient-example/baseline-model/v1")

# Judge / reflection model (for LLM-as-judge scorers and prompt optimization)
JUDGE_MODEL_NAME = os.getenv("JUDGE_MODEL_NAME", "gpt-oss-20b")
JUDGE_MODEL_URL = os.getenv("JUDGE_MODEL_URL", "http://a5b3148f0995c48088e0800feaa2c651-1539933567.us-east-2.elb.amazonaws.com/demo-llm/gpt-oss-20b/v1")

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "https://mlflow-route-mlflow.apps.ocp.wnk5d.sandbox1583.opentlc.com")
EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT", "Demo Project - gpt-oss-20b")

PROMPT_NAME = "terminal-prompt"

os.environ["OPENAI_API_KEY"] = "doesn't-matter"


def setup_mlflow():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)
