# NutriTrack — First Adoption of AI (v2)

---

## Basic AI Usage

NutriComp is happy to announce first usage of AI! The code now also allows the users the upload a picture, it then sends this picture to a model, alongside a basic prompt, explaining the role of the model, and requesting it to return whatever foods it believes it had found.

## What Was Added?

The main change now resides in the model directory, where we now have an LLMInferenceService object described in a yaml file. This file will deploy a <PLACEHOLDER> model, that is able to receive communication from the application.

It also adds an integration to the model in the application code, mainly:

```
    completion = client.chat.completions.create(
        model="Qwen2.5-VL-7B-Instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT
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
```

Which shows what communication with an Open-AI compatible endpoint looks like.

---

## Running this version

```bash
cd nutrient-example/v1-no_model
oc apply -f model/llm-infra.yaml
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn
uvicorn app:app --reload
```

Open [http://localhost:8000](http://localhost:8000) and you have the full app.
