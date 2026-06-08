# NutriTrack — First Adoption of AI (v2)

---

## Evaluation

Now that MLflow was integrated, NutriTrack wishes to improve the accuracy of the application. There are several ways to do that, and for now, they are focused on evaluation cycles.

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
