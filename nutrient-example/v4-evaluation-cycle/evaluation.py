import os
import json
import requests
from pathlib import Path
from typing import Dict, List, Any
import base64

import mlflow
from mlflow.genai.datasets import create_dataset, get_dataset


MLFLOW_URL = os.getenv("MLFLOW_URL", "http://localhost:5000")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "Nutrition Tracker")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
ANALYZE_ENDPOINT = f"{API_BASE_URL}/analyze-meal-image"


def create_evaluation_dataset():
    """Create a dataset with meal images and ground truth data"""
    dataset = create_dataset(
        name="meal_images_evaluation",
        tags={"version": "1.0", "task": "meal-analysis", "status": "active"},
    )

    print(f"Created evaluation dataset: {dataset.dataset_id}")

    new_records = [
        {
            "inputs": {
                "image_path": "path/to/meal1.jpg",
                "image_base64": "base64_encoded_image_1"
            },
            "expectations": {
                "ground_truth_items": [
                    {"food_id": "banana", "estimated_grams": 120},
                    {"food_id": "yogurt", "estimated_grams": 150}
                ]
            },
        },
        {
            "inputs": {
                "image_path": "path/to/meal2.jpg",
                "image_base64": "base64_encoded_image_2"
            },
            "expectations": {
                "ground_truth_items": [
                    {"food_id": "apple", "estimated_grams": 150}
                ]
            },
        },
    ]

    dataset.merge_records(new_records)

    return dataset


def calculate_accuracy(predicted_items: List[Dict[str, Any]], ground_truth_items: List[Dict[str, Any]]) -> float:
    """Calculate accuracy by comparing predicted items to ground truth"""
    if not ground_truth_items:
        return 0.0

    matched = 0
    tolerance = 0.2

    for truth_item in ground_truth_items:
        truth_food_id = truth_item.get("food_id")
        truth_grams = truth_item.get("estimated_grams", 0)

        for pred_item in predicted_items:
            pred_food_id = pred_item.get("food_id")
            pred_grams = pred_item.get("estimated_grams", 0)

            if pred_food_id == truth_food_id:
                grams_diff_ratio = abs(pred_grams - truth_grams) / truth_grams if truth_grams > 0 else 0
                if grams_diff_ratio <= tolerance:
                    matched += 1
                break

    return matched / len(ground_truth_items)


def predict_fn(record: Dict[str, Any]) -> Dict[str, Any]:
    """Send image to the analyze endpoint and return predictions"""
    inputs = record.get("inputs", {})
    image_base64 = inputs.get("image_base64")

    if not image_base64:
        return {"items": [], "error": "No image provided"}

    image_bytes = base64.b64decode(image_base64)

    try:
        response = requests.post(
            ANALYZE_ENDPOINT,
            files={"file": ("meal.jpg", image_bytes, "image/jpeg")}
        )
        response.raise_for_status()
        result = response.json()
        return {
            "predicted_items": result.get("items", []),
            "total_nutrients": result.get("total_nutrients", {})
        }
    except Exception as e:
        return {"items": [], "error": str(e)}


@mlflow.trace(name="Evaluate Meal Analysis", span_type="EVALUATION")
def run_evaluation(dataset=None):
    """Run evaluation on the meal analysis model"""
    if dataset is None:
        dataset = create_evaluation_dataset()

    results = []
    accuracies = []

    for record in dataset.data:
        prediction = predict_fn(record)
        ground_truth = record.get("expectations", {}).get("ground_truth_items", [])
        predicted_items = prediction.get("predicted_items", [])

        accuracy = calculate_accuracy(predicted_items, ground_truth)
        accuracies.append(accuracy)

        results.append({
            "record_id": record.get("id"),
            "predicted_items": predicted_items,
            "ground_truth_items": ground_truth,
            "accuracy": accuracy
        })

    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0

    evaluation_result = {
        "total_records": len(results),
        "average_accuracy": avg_accuracy,
        "detailed_results": results
    }

    mlflow.log_metric("meal_analysis_accuracy", avg_accuracy)
    mlflow.log_dict(evaluation_result, "evaluation_results.json")

    print(f"\nEvaluation Results:")
    print(f"Total Records: {evaluation_result['total_records']}")
    print(f"Average Accuracy: {avg_accuracy * 100:.2f}%")

    return evaluation_result


if __name__ == "__main__":
    mlflow.set_tracking_uri(MLFLOW_URL)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    run_evaluation()
