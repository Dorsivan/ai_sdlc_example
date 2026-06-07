from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import date
from typing import List, Dict, Any
import json
import uuid
import os
from fastapi.staticfiles import StaticFiles

import mlflow
from mlflow.entities import AssessmentSource, AssessmentSourceType


app = FastAPI(title="Simple Nutrition Backend")


DATA_DIR = Path("data")
FOODS_FILE = DATA_DIR / "foods.json"
REQUIREMENTS_FILE = DATA_DIR / "daily_requirements.json"
MEAL_LOG_FILE = DATA_DIR / "meal_log.json"

MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-oss-20b")
MODEL_URL = os.getenv("MODEL_URL", "http://a5b3148f0995c48088e0800feaa2c651-1539933567.us-east-2.elb.amazonaws.com/demo-llm/gpt-oss-20b/v1")
MLFLOW_URL = os.getenv("MLFLOW_URL", "http://localhost:5000")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "Nutrition Tracker")

BASE_SYSTEM_PROMPT = """You are helping a nutrition tracker analyze a meal photo.

AVAILABLE FOODS:
{available_foods}

INSTRUCTIONS:
- Analyze the meal photo and identify foods from the AVAILABLE FOODS list only.
- For each food identified, provide: food_id, estimated_grams, and confidence (0-1).
- Return ONLY valid JSON. No markdown or explanation.

JSON FORMAT:
{{
  "items": [
    {{"food_id": "food_id", "estimated_grams": 100, "confidence": 0.95, "reason": "brief description"}},
    {{"food_id": "food_id2", "estimated_grams": 150, "confidence": 0.85, "reason": "brief description"}}
  ]
}}

EXAMPLES:

Example 1: Breakfast with banana and yogurt
Input: Image of a banana (120g) and a cup of yogurt (150g)
Output: {{"items": [{{"food_id": "banana", "estimated_grams": 120, "confidence": 0.95, "reason": "yellow color and shape"}}, {{"food_id": "yogurt", "estimated_grams": 150, "confidence": 0.90, "reason": "white creamy substance in bowl"}}]}}

Example 2: Simple apple
Input: Image of a medium-sized red apple on a plate
Output: {{"items": [{{"food_id": "apple", "estimated_grams": 150, "confidence": 0.98, "reason": "recognizable red apple shape"}}]}}

Example 3: Chicken and rice
Input: Image of grilled chicken breast (150g) and white rice (200g)
Output: {{"items": [{{"food_id": "chicken_breast", "estimated_grams": 150, "confidence": 0.92, "reason": "grilled poultry appearance"}}, {{"food_id": "rice", "estimated_grams": 200, "confidence": 0.88, "reason": "white grain pattern"}}]}}

Example 4: Mixed vegetables
Input: Image of broccoli, carrots, and spinach salad
Output: {{"items": [{{"food_id": "broccoli", "estimated_grams": 100, "confidence": 0.94, "reason": "green florets visible"}}, {{"food_id": "carrot", "estimated_grams": 80, "confidence": 0.90, "reason": "orange vegetable pieces"}}, {{"food_id": "spinach", "estimated_grams": 50, "confidence": 0.85, "reason": "green leafy base"}}]}}
"""

os.environ["OPENAI_API_KEY"] = "doesn't-matter"


def get_available_foods_list():
    """Get formatted list of available foods from foods.json"""
    try:
        foods = read_json(FOODS_FILE)
        food_list = []
        for food_id, food_data in foods.items():
            food_list.append(f"- {food_id}: {food_data.get('name', food_id)}")
        return "\n".join(food_list)
    except:
        return "- No foods available"


def register_system_prompt():
    foods_list = get_available_foods_list()
    system_prompt = BASE_SYSTEM_PROMPT.format(available_foods=foods_list)
    prompt = mlflow.genai.register_prompt(
        name="meal-analysis-prompt",
        template=system_prompt,
    )
    return prompt


class MealItem(BaseModel):
    food_id: str = Field(..., example="banana")
    grams: float = Field(..., gt=0, example=120)


class MealCreate(BaseModel):
    meal_name: str = Field(..., example="Breakfast")
    eaten_on: date = Field(default_factory=date.today)
    items: List[MealItem]


def read_json(path: Path) -> Any:
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Missing file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_nutrients(target: Dict[str, float], source: Dict[str, float]) -> None:
    for nutrient, value in source.items():
        target[nutrient] = round(target.get(nutrient, 0) + value, 2)


def scale_nutrients(nutrients_per_100g: Dict[str, float], grams: float) -> Dict[str, float]:
    scale = grams / 100

    return {
        nutrient: round(value * scale, 2)
        for nutrient, value in nutrients_per_100g.items()
    }


@mlflow.trace(name="Calculate Meal", span_type="NUTRITION_CALCULATION", attributes={"operation": "meal_calculation"})
def calculate_meal(items: List[MealItem], foods: Dict[str, Any]) -> Dict[str, Any]:
    meal_total = {}
    item_details = []

    for item in items:
        if item.food_id not in foods:
            raise HTTPException(
                status_code=404,
                detail=f"Food '{item.food_id}' was not found in foods.json"
            )

        food = foods[item.food_id]
        nutrients = scale_nutrients(
            food["nutrients_per_100g"],
            item.grams
        )

        add_nutrients(meal_total, nutrients)

        item_details.append({
            "food_id": item.food_id,
            "name": food["name"],
            "grams": item.grams,
            "nutrients": nutrients
        })

    return {
        "items": item_details,
        "total_nutrients": meal_total
    }


@mlflow.trace(name="Get Daily Summary", span_type="NUTRITION_QUERY", attributes={"operation": "daily_summary"})
def get_daily_summary(day: str) -> Dict[str, Any]:
    logs = read_json(MEAL_LOG_FILE)
    requirements = read_json(REQUIREMENTS_FILE)

    day_meals = [
        meal for meal in logs
        if meal["eaten_on"] == day
    ]

    consumed = {}

    for meal in day_meals:
        add_nutrients(consumed, meal["total_nutrients"])

    comparison = {}

    for nutrient, required_amount in requirements.items():
        consumed_amount = consumed.get(nutrient, 0)
        remaining = round(required_amount - consumed_amount, 2)

        comparison[nutrient] = {
            "consumed": consumed_amount,
            "required": required_amount,
            "remaining": max(remaining, 0),
            "percentage": round((consumed_amount / required_amount) * 100, 1)
            if required_amount > 0 else None
        }

    return {
        "date": day,
        "meals": day_meals,
        "daily_totals": consumed,
        "daily_requirements": requirements,
        "comparison": comparison
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "message": "Nutrition backend is running"
    }


@app.get("/foods")
@mlflow.trace(name="List Foods", span_type="API_CALL", attributes={"endpoint": "/foods"})
def list_foods():
    return read_json(FOODS_FILE)


@app.post("/meals")
@mlflow.trace(name="Log Meal", span_type="API_CALL", attributes={"endpoint": "/meals"})
def log_meal(meal: MealCreate):
    foods = read_json(FOODS_FILE)
    logs = read_json(MEAL_LOG_FILE)

    calculated = calculate_meal(meal.items, foods)

    new_meal = {
        "id": str(uuid.uuid4()),
        "meal_name": meal.meal_name,
        "eaten_on": meal.eaten_on.isoformat(),
        "items": calculated["items"],
        "total_nutrients": calculated["total_nutrients"]
    }

    logs.append(new_meal)
    write_json(MEAL_LOG_FILE, logs)

    return {
        "message": "Meal logged successfully",
        "meal": new_meal,
        "daily_summary": get_daily_summary(meal.eaten_on.isoformat())
    }


@app.get("/summary/{day}")
@mlflow.trace(name="Daily Summary", span_type="API_CALL", attributes={"endpoint": "/summary"})
def daily_summary(day: str):
    return get_daily_summary(day)


@app.get("/logs")
def all_logs():
    return read_json(MEAL_LOG_FILE)


@app.delete("/logs")
def clear_logs():
    write_json(MEAL_LOG_FILE, [])
    return {
        "message": "All meal logs were cleared"
    }

app.mount("/", StaticFiles(directory="static", html=True), name="static")


import base64
import json
import os
from fastapi import UploadFile, File, HTTPException
from openai import OpenAI


vlm_client = OpenAI(
    api_key="EMPTY",
    base_url=os.getenv("VLM_BASE_URL", "http://localhost:8001/v1")
)

## new code for v3

mlflow.set_tracking_uri(MLFLOW_URL)
mlflow.set_experiment(MLFLOW_EXPERIMENT)
register_system_prompt()


@app.post("/analyze-meal-image")
@mlflow.trace(name="Analyze Image", span_type="LLM_CALL", attributes={"model": "Qwen2.5", "endpoint": "/analyze-meal-image"})
async def analyze_meal_image(file: UploadFile = File(...)):
    foods = read_json(FOODS_FILE)

    image_bytes = await file.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    mime_type = file.content_type or "image/jpeg"
    image_url = f"data:{mime_type};base64,{image_base64}"

    allowed_foods = [
        {
            "food_id": food_id,
            "name": food["name"]
        }
        for food_id, food in foods.items()
    ]

    completion = vlm_client.chat.completions.create(
        model="Qwen/Qwen2.5-VL-7B-Instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": mlflow.genai.load_prompt(name_or_uri="prompts:/meal-analysis-prompt@latest").format()
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ],
        temperature=0,
        max_tokens=700
    )

    raw_text = completion.choices[0].message.content

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Model did not return valid JSON",
                "raw_output": raw_text
            }
        )

    calculated_items = []

    for item in result.get("items", []):
        food_id = item.get("food_id")

        if food_id not in foods:
            continue

        estimated_grams = float(item.get("estimated_grams", 0))

        if estimated_grams <= 0:
            continue

        food = foods[food_id]

        nutrients = scale_nutrients(
            food["nutrients_per_100g"],
            estimated_grams
        )

        calculated_items.append({
            "food_id": food_id,
            "name": food["name"],
            "estimated_grams": estimated_grams,
            "confidence": item.get("confidence"),
            "reason": item.get("reason"),
            "nutrients": nutrients
        })

    total_nutrients = {}

    for item in calculated_items:
        add_nutrients(total_nutrients, item["nutrients"])

    return {
        "message": "Meal image analyzed",
        "items": calculated_items,
        "total_nutrients": total_nutrients,
        "note": "Ask the user to confirm or edit before logging."
    }