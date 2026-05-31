from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import date
from typing import List, Dict, Any
import json
import uuid
from fastapi.staticfiles import StaticFiles


app = FastAPI(title="Simple Nutrition Backend")


DATA_DIR = Path("data")
FOODS_FILE = DATA_DIR / "foods.json"
REQUIREMENTS_FILE = DATA_DIR / "daily_requirements.json"
MEAL_LOG_FILE = DATA_DIR / "meal_log.json"


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
def list_foods():
    return read_json(FOODS_FILE)


@app.post("/meals")
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