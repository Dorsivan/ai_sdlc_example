# v6-testing-various-models

Multi-model evaluation framework for testing multiple LLM models sequentially with MLflow tracking.

## Overview

This version extends the nutrition tracking application to support testing multiple models in a single workflow. Each model is:
1. Deployed to OpenShift using KServe
2. Evaluated using the meal image analysis pipeline
3. Results tracked in MLflow with parent/child Run structure
4. Automatically cleaned up before the next model deploys

## Files

- **models.json** - Configuration file defining available models and their deployment parameters
- **multi_model_evaluator.py** - Orchestration script that manages the complete lifecycle
- **app.py** - FastAPI application (unchanged from v5)
- **evaluation.py** - Individual model evaluation logic (unchanged from v5)
- **model/** - OpenShift deployment manifests (YAML templates with placeholders)

## Models Configuration (models.json)

Each model entry includes:

```json
{
  "id": "unique-model-id",
  "hf_endpoint": "organization/model-name",  // HuggingFace model ID
  "display_name": "Human-friendly name",
  "pvc_name": "unique-pvc-name",            // Kubernetes PVC name
  "model_name_in_api": "api-model-id",      // Model name for OpenAI-compatible API
  "service_name": "baseline-model",         // Kubernetes service name
  "vllm_args": "--args --for --vllm"        // vLLM configuration flags
}
```

## Usage

### Prerequisites

1. OpenShift cluster with GPU nodes and KServe installed
2. MLflow server running and accessible
3. kubectl configured with access to the cluster
4. evaluation.py dependencies installed

### Basic Usage

```bash
# Test all models in models.json
python multi_model_evaluator.py --models-config models.json --app-dir .

# Dry-run to see what would happen
python multi_model_evaluator.py --models-config models.json --app-dir . --dry-run

# Keep deployments after evaluation (for debugging)
python multi_model_evaluator.py --models-config models.json --app-dir . --skip-cleanup

# Use specific MLflow server
python multi_model_evaluator.py --models-config models.json --mlflow-uri http://mlflow-server:5000
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--models-config` | `models.json` | Path to models configuration file |
| `--app-dir` | `.` | Path to application directory |
| `--namespace` | `nutrient-example` | OpenShift namespace for deployments |
| `--dry-run` | False | Show what would happen without deploying |
| `--skip-cleanup` | False | Keep model deployments after evaluation |
| `--mlflow-uri` | `MLFLOW_URL` env var or `http://localhost:5000` | MLflow tracking server |
| `--mlflow-experiment` | `Nutrition Tracker - Multi-Model` | MLflow experiment name |

## MLflow Tracking

### Run Structure

```
Parent Run (Multi-Model Evaluation)
├── params: models_to_test, total_models, namespace
├── artifacts: evaluation_summary.json
│
├── Child Run (Model 1)
│   ├── params: model_id, hf_endpoint, pvc_name, status
│   ├── metrics: meal_analysis_accuracy
│   └── artifacts: evaluation_results.json
│
└── Child Run (Model 2)
    ├── params: model_id, hf_endpoint, pvc_name, status
    ├── metrics: meal_analysis_accuracy
    └── artifacts: evaluation_results.json
```

Each child run is tagged with `model_type: "vllm"` and `parent_run_id: <parent_id>`.

## Workflow

For each model in models.json:

1. **Deployment Phase**
   - Create PersistentVolumeClaim with model-specific name
   - Deploy model downloader job to pull weights from HuggingFace
   - Deploy LLMInferenceService to OpenShift

2. **Readiness Phase**
   - Poll Kubernetes to verify LLMInferenceService is ready
   - Timeout after 5 minutes if not ready

3. **Evaluation Phase**
   - Run evaluation.py with model-specific MODEL_URL and MODEL_DEFAULT env vars
   - Evaluation script logs results to MLflow child run
   - Results include accuracy metrics and detailed per-image results

4. **Cleanup Phase**
   - Delete LLMInferenceService
   - Delete model downloader job
   - Delete PersistentVolumeClaim
   - On error: logs failure and continues to next model

## Error Handling

- **Deployment failures**: Logged to MLflow, skips to next model
- **Readiness timeouts**: Logged to MLflow, skips to next model
- **Evaluation failures**: Logs stderr to MLflow artifacts, still cleans up
- **Cleanup failures**: Warning logged but doesn't block next model evaluation

## YAML Templates

The model/*.yaml files use template variables that are replaced per-model:

- `${MODEL_ID}` → HuggingFace model endpoint (e.g., `Qwen/Qwen2.5-0.5B-Instruct`)
- `${MODEL_NAME}` → Model name in API (e.g., `qwen2-5-0-5b-instruct`)
- `${PVC_NAME}` → Unique PVC name per model
- `${VLLM_ARGS}` → vLLM configuration arguments

## Example

Add to models.json and run:

```json
{
  "id": "qwen-3b",
  "hf_endpoint": "Qwen/Qwen2.5-3B-Instruct",
  "display_name": "Qwen 2.5 3B",
  "pvc_name": "nutrient-model-qwen-3b",
  "model_name_in_api": "qwen2-5-3b-instruct",
  "service_name": "baseline-model",
  "vllm_args": "--disable-uvicorn-access-log --max-model-len=2000 --gpu-memory-utilization=0.8"
}
```

Then execute:
```bash
python multi_model_evaluator.py
```

Results will appear in MLflow under "Nutrition Tracker - Multi-Model" experiment.
