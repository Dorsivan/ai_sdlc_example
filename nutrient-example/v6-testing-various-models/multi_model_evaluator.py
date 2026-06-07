#!/usr/bin/env python3
"""
Multi-model evaluator for testing multiple models sequentially.
Orchestrates deployment, evaluation, and cleanup for each model.
Results tracked in MLflow with parent/child Run structure.
"""

import os
import sys
import json
import argparse
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import shutil
import tempfile
import yaml

import mlflow


class MultiModelEvaluator:
    def __init__(
        self,
        models_config_path: str,
        app_dir: str,
        namespace: str = "nutrient-example",
        dry_run: bool = False,
        skip_cleanup: bool = False,
    ):
        self.models_config_path = models_config_path
        self.app_dir = Path(app_dir)
        self.namespace = namespace
        self.dry_run = dry_run
        self.skip_cleanup = skip_cleanup
        self.models = []
        self.parent_run_id = None

    def load_models_config(self) -> None:
        """Load models.json configuration"""
        with open(self.models_config_path, "r") as f:
            config = json.load(f)
        self.models = config.get("models", [])
        print(f"Loaded {len(self.models)} models from {self.models_config_path}")

    def update_yaml_file(self, yaml_path: str, model_config: Dict[str, Any]) -> str:
        """
        Update YAML file with model-specific values.
        Returns path to updated temporary file.
        """
        with open(yaml_path, "r") as f:
            content = f.read()

        # Replace placeholders with model-specific values
        content = content.replace("${MODEL_ID}", model_config["hf_endpoint"])
        content = content.replace("${MODEL_NAME}", model_config["model_name_in_api"])
        content = content.replace("${PVC_NAME}", model_config["pvc_name"])
        content = content.replace("${VLLM_ARGS}", model_config["vllm_args"])

        # Create temporary file with updated content
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        )
        temp_file.write(content)
        temp_file.close()

        return temp_file.name

    def deploy_model_to_openshift(self, model_config: Dict[str, Any]) -> bool:
        """
        Deploy model to OpenShift using kubectl.
        Returns True if successful.
        """
        try:
            model_dir = self.app_dir / "model"
            yaml_files = ["model-pvc.yaml", "downloader_job.yaml", "llm-infra.yaml"]

            for yaml_file in yaml_files:
                yaml_path = model_dir / yaml_file
                if not yaml_path.exists():
                    print(f"Warning: {yaml_path} not found")
                    continue

                temp_yaml = self.update_yaml_file(str(yaml_path), model_config)

                try:
                    if not self.dry_run:
                        result = subprocess.run(
                            ["kubectl", "apply", "-f", temp_yaml, "-n", self.namespace],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if result.returncode != 0:
                            print(f"Error deploying {yaml_file}: {result.stderr}")
                            return False
                    else:
                        print(f"[DRY-RUN] Would deploy: {yaml_file}")

                finally:
                    os.unlink(temp_yaml)

            return True
        except Exception as e:
            print(f"Error deploying model: {e}")
            return False

    def wait_for_model_ready(
        self, model_config: Dict[str, Any], timeout: int = 300
    ) -> bool:
        """
        Wait for model to be ready by checking service status.
        Returns True if ready, False if timeout.
        """
        if self.dry_run:
            print("[DRY-RUN] Would wait for model to be ready")
            return True

        try:
            service_name = model_config["service_name"]
            start_time = time.time()

            while time.time() - start_time < timeout:
                result = subprocess.run(
                    [
                        "kubectl",
                        "get",
                        "llminferenceservice",
                        service_name,
                        "-n",
                        self.namespace,
                        "-o",
                        "json",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    service_info = json.loads(result.stdout)
                    conditions = service_info.get("status", {}).get("conditions", [])
                    if any(c.get("type") == "Ready" and c.get("status") == "True" for c in conditions):
                        print(f"Model {model_config['id']} is ready")
                        return True

                print(f"Waiting for model {model_config['id']}... ({int(time.time() - start_time)}s)")
                time.sleep(10)

            print(f"Timeout waiting for model {model_config['id']} to be ready")
            return False

        except Exception as e:
            print(f"Error checking model readiness: {e}")
            return False

    def run_evaluation_for_model(self, model_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run evaluation.py for the current model.
        Returns evaluation results.
        """
        try:
            # Get model endpoint (would be set via environment or service)
            model_url = os.getenv(
                "MODEL_URL",
                f"http://{model_config['service_name']}.{self.namespace}.svc.cluster.local:8000/v1",
            )

            env = os.environ.copy()
            env["OPENAI_MODEL"] = model_config["model_name_in_api"]
            env["MODEL_URL"] = model_url

            if not self.dry_run:
                result = subprocess.run(
                    ["python", "evaluation.py"],
                    cwd=str(self.app_dir),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )

                if result.returncode != 0:
                    print(f"Evaluation failed: {result.stderr}")
                    mlflow.log_text(result.stderr, "evaluation_error.log")
                    return {"error": "Evaluation failed", "stderr": result.stderr}

                # Parse evaluation results (would be logged by evaluation.py to MLflow)
                return {"status": "success", "stdout": result.stdout}
            else:
                print(f"[DRY-RUN] Would run evaluation for {model_config['id']}")
                return {"status": "dry_run"}

        except subprocess.TimeoutExpired:
            print(f"Evaluation timeout for {model_config['id']}")
            return {"error": "Timeout"}
        except Exception as e:
            print(f"Error running evaluation: {e}")
            return {"error": str(e)}

    def cleanup_model_deployment(self, model_config: Dict[str, Any]) -> bool:
        """
        Clean up model deployment from OpenShift.
        Returns True if successful.
        """
        if self.skip_cleanup:
            print(f"Skipping cleanup for {model_config['id']} (--skip-cleanup)")
            return True

        if self.dry_run:
            print(f"[DRY-RUN] Would cleanup deployment for {model_config['id']}")
            return True

        try:
            pvc_name = model_config["pvc_name"]
            service_name = model_config["service_name"]

            # Delete LLMInferenceService
            subprocess.run(
                [
                    "kubectl",
                    "delete",
                    "llminferenceservice",
                    service_name,
                    "-n",
                    self.namespace,
                ],
                capture_output=True,
                timeout=30,
            )

            # Delete downloader job
            subprocess.run(
                ["kubectl", "delete", "job", "-l", f"model={model_config['id']}", "-n", self.namespace],
                capture_output=True,
                timeout=30,
            )

            # Delete PVC
            subprocess.run(
                ["kubectl", "delete", "pvc", pvc_name, "-n", self.namespace],
                capture_output=True,
                timeout=30,
            )

            print(f"Cleaned up deployment for {model_config['id']}")
            return True

        except subprocess.TimeoutExpired:
            print(f"Warning: Timeout during cleanup for {model_config['id']}")
            return False
        except Exception as e:
            print(f"Warning: Error during cleanup: {e}")
            return False

    def setup_parent_run(self) -> str:
        """
        Create parent MLflow Run for all models.
        Returns parent run ID.
        """
        model_names = [m["id"] for m in self.models]

        with mlflow.start_run():
            mlflow.log_param("models_to_test", ",".join(model_names))
            mlflow.log_param("total_models", len(self.models))
            mlflow.log_param("namespace", self.namespace)

            parent_run_id = mlflow.active_run().info.run_id
            print(f"Created parent MLflow Run: {parent_run_id}")
            return parent_run_id

    def evaluate_model(self, model_config: Dict[str, Any]) -> bool:
        """
        Complete evaluation workflow for a single model.
        Returns True if successful.
        """
        model_id = model_config["id"]
        print(f"\n{'='*60}")
        print(f"Evaluating model: {model_id} ({model_config['display_name']})")
        print(f"{'='*60}")

        with mlflow.start_run():
            try:
                mlflow.log_param("model_id", model_id)
                mlflow.log_param("hf_endpoint", model_config["hf_endpoint"])
                mlflow.log_param("pvc_name", model_config["pvc_name"])

                # Step 1: Deploy
                print(f"[1/4] Deploying model...")
                if not self.deploy_model_to_openshift(model_config):
                    mlflow.log_param("status", "deployment_failed")
                    print("Deployment failed, skipping to next model")
                    return False

                # Step 2: Wait for readiness
                print(f"[2/4] Waiting for model to be ready...")
                if not self.wait_for_model_ready(model_config):
                    mlflow.log_param("status", "readiness_timeout")
                    print("Model readiness timeout, skipping to next model")
                    return False

                # Step 3: Run evaluation
                print(f"[3/4] Running evaluation...")
                eval_result = self.run_evaluation_for_model(model_config)
                if "error" in eval_result:
                    mlflow.log_param("status", "evaluation_failed")
                    print("Evaluation failed, but continuing cleanup")
                else:
                    mlflow.log_param("status", "success")

                # Step 4: Cleanup
                print(f"[4/4] Cleaning up...")
                self.cleanup_model_deployment(model_config)

                print(f"Model {model_id} evaluation completed")
                return "error" not in eval_result

            except Exception as e:
                print(f"Unexpected error evaluating {model_id}: {e}")
                mlflow.log_param("status", f"error: {str(e)}")
                return False

    def run_all_evaluations(self) -> Dict[str, Any]:
        """
        Run evaluations for all models.
        Returns summary of results.
        """
        self.load_models_config()

        results = {
            "total_models": len(self.models),
            "successful": 0,
            "failed": 0,
            "model_results": [],
        }

        for model_config in self.models:
            success = self.evaluate_model(model_config)
            results["model_results"].append(
                {
                    "model_id": model_config["id"],
                    "display_name": model_config["display_name"],
                    "success": success,
                }
            )
            if success:
                results["successful"] += 1
            else:
                results["failed"] += 1

        # Log summary
        mlflow.log_dict(results, "evaluation_summary.json")
        print(f"\n{'='*60}")
        print("EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total models: {results['total_models']}")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
        for model_result in results["model_results"]:
            status = "✓" if model_result["success"] else "✗"
            print(
                f"  {status} {model_result['model_id']}: {model_result['display_name']}"
            )

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Test multiple models sequentially with MLflow tracking"
    )
    parser.add_argument(
        "--models-config",
        default="models.json",
        help="Path to models.json configuration file",
    )
    parser.add_argument(
        "--app-dir", default=".", help="Path to app directory with evaluation.py"
    )
    parser.add_argument(
        "--namespace",
        default="nutrient-example",
        help="OpenShift namespace for deployments",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without deploying",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Keep model deployments after evaluation",
    )
    parser.add_argument(
        "--mlflow-uri",
        help="MLflow tracking URI (uses env var MLFLOW_URL if not set)",
    )
    parser.add_argument(
        "--mlflow-experiment",
        default="Nutrition Tracker - Multi-Model",
        help="MLflow experiment name",
    )

    args = parser.parse_args()

    # Setup MLflow
    mlflow_uri = args.mlflow_uri or os.getenv(
        "MLFLOW_URL", "http://localhost:5000"
    )
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment(args.mlflow_experiment)

    # Run evaluations
    evaluator = MultiModelEvaluator(
        models_config_path=args.models_config,
        app_dir=args.app_dir,
        namespace=args.namespace,
        dry_run=args.dry_run,
        skip_cleanup=args.skip_cleanup,
    )

    results = evaluator.run_all_evaluations()

    # Exit with appropriate code
    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
