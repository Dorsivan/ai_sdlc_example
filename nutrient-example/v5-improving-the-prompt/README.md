# NutriTrack — First Adoption of AI (v2)

---

## Iterating Over The Prompt

The evaluation process is working correctly. Now we are required to start making changes, and watching the progress.
Since the model was not developed internally, the main method for us to improve the accuracy is by improving the prompt, and possibly updating the model itself.

## What Was Added?

MLflow can now be enabled as a part of RHOAI, you can access it in: <rhoai_url>/models
You can notice that the main functions in app.py now have a tracing header. Run the code, log into mlflow, and check out the new information!

---

## Running this version

```bash
enable mlflowoperator <PLACEHOLDER>
cd nutrient-example/v1-no_model
oc apply -f model/llm-infra.yaml
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn
uvicorn app:app --reload
```

Open [http://localhost:8000](http://localhost:8000) and you have the full app.
