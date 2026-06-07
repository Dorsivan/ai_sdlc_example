"""
Example of what a prompt with embedded images would look like.
This demonstrates how you could include visual few-shot examples directly in the prompt.
"""

PROMPT_WITH_EMBEDDED_IMAGES = """You are helping a nutrition tracker analyze a meal photo.

AVAILABLE FOODS:
- banana: yellow fruit, curved shape, typically 120g
- yogurt: white creamy dairy product
- apple: round fruit, red or green skin, typically 150g
- chicken_breast: white/light meat, grilled or cooked
- rice: white grain, cooked
- broccoli: green florets, tree-like appearance
- carrot: orange vegetable, elongated
- spinach: green leafy vegetable

INSTRUCTIONS:
- Analyze the meal photo and identify foods from the AVAILABLE FOODS list only.
- For each food identified, provide: food_id, estimated_grams, and confidence (0-1).
- Return ONLY valid JSON. No markdown or explanation.

JSON FORMAT:
{
  "items": [
    {"food_id": "food_id", "estimated_grams": 100, "confidence": 0.95, "reason": "brief description"},
    {"food_id": "food_id2", "estimated_grams": 150, "confidence": 0.85, "reason": "brief description"}
  ]
}

VISUAL EXAMPLES WITH EXPECTED OUTPUT:

Example 1: Banana and Yogurt
[IMAGE: base64_encoded_banana_yogurt_image_1]
Output: {"items": [{"food_id": "banana", "estimated_grams": 120, "confidence": 0.95, "reason": "yellow curved fruit visible"}, {"food_id": "yogurt", "estimated_grams": 150, "confidence": 0.90, "reason": "white creamy substance in bowl"}]}

Example 2: Red Apple
[IMAGE: base64_encoded_apple_image_1]
Output: {"items": [{"food_id": "apple", "estimated_grams": 150, "confidence": 0.98, "reason": "round red fruit, clearly visible"}]}

Example 3: Grilled Chicken and Rice
[IMAGE: base64_encoded_chicken_rice_image_1]
Output: {"items": [{"food_id": "chicken_breast", "estimated_grams": 150, "confidence": 0.92, "reason": "light colored cooked meat"}, {"food_id": "rice", "estimated_grams": 200, "confidence": 0.88, "reason": "white grain pattern"}]}

Example 4: Vegetable Salad
[IMAGE: base64_encoded_vegetables_image_1]
Output: {"items": [{"food_id": "broccoli", "estimated_grams": 100, "confidence": 0.94, "reason": "green florets visible"}, {"food_id": "carrot", "estimated_grams": 80, "confidence": 0.90, "reason": "orange pieces"}, {"food_id": "spinach", "estimated_grams": 50, "confidence": 0.85, "reason": "green leafy base"}]}
"""


# How you would construct this programmatically:

import base64
from pathlib import Path

def build_prompt_with_images(example_images_dir: str = "few_shot_examples"):
    """
    Build a prompt with actual images embedded as base64.

    Expected directory structure:
    few_shot_examples/
    ├── banana_yogurt.jpg
    ├── apple.jpg
    ├── chicken_rice.jpg
    └── vegetables.jpg
    """

    BASE_PROMPT = """You are helping a nutrition tracker analyze a meal photo.

AVAILABLE FOODS:
- banana: yellow fruit, curved shape
- yogurt: white creamy dairy product
- apple: round fruit
- chicken_breast: white/light meat
- rice: white grain, cooked
- broccoli: green florets
- carrot: orange vegetable
- spinach: green leafy vegetable

[... instructions and format specification ...]

VISUAL EXAMPLES:

Example 1: Banana and Yogurt"""

    examples = [
        {
            "name": "Banana and Yogurt",
            "image_path": "banana_yogurt.jpg",
            "expected_output": '{"items": [{"food_id": "banana", "estimated_grams": 120, "confidence": 0.95, "reason": "yellow curved fruit"}, {"food_id": "yogurt", "estimated_grams": 150, "confidence": 0.90, "reason": "white creamy substance"}]}'
        },
        {
            "name": "Red Apple",
            "image_path": "apple.jpg",
            "expected_output": '{"items": [{"food_id": "apple", "estimated_grams": 150, "confidence": 0.98, "reason": "round red fruit"}]}'
        },
        {
            "name": "Grilled Chicken and Rice",
            "image_path": "chicken_rice.jpg",
            "expected_output": '{"items": [{"food_id": "chicken_breast", "estimated_grams": 150, "confidence": 0.92, "reason": "light cooked meat"}, {"food_id": "rice", "estimated_grams": 200, "confidence": 0.88, "reason": "white grains"}]}'
        },
        {
            "name": "Vegetable Salad",
            "image_path": "vegetables.jpg",
            "expected_output": '{"items": [{"food_id": "broccoli", "estimated_grams": 100, "confidence": 0.94}, {"food_id": "carrot", "estimated_grams": 80, "confidence": 0.90}, {"food_id": "spinach", "estimated_grams": 50, "confidence": 0.85}]}'
        }
    ]

    prompt = BASE_PROMPT + "\n"

    for i, example in enumerate(examples, 1):
        image_file = Path(example_images_dir) / example["image_path"]

        # Read image and encode to base64
        if image_file.exists():
            with open(image_file, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")

            # Add to prompt with embedded image
            prompt += f"""
Example {i}: {example['name']}
[IMAGE: data:image/jpeg;base64,{image_base64}]
Expected Output: {example['expected_output']}
"""
        else:
            prompt += f"""
Example {i}: {example['name']}
[IMAGE_PATH: {example['image_path']} - file not found]
Expected Output: {example['expected_output']}
"""

    return prompt


# Usage in the app would look like:
# def register_system_prompt_with_images():
#     prompt_with_images = build_prompt_with_images("few_shot_examples")
#     prompt = mlflow.genai.register_prompt(
#         name="meal-analysis-prompt-visual",
#         template=prompt_with_images,
#     )
#     return prompt
