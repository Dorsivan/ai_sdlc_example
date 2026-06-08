# NutriTrack — First Adoption of AI (v2)

---

## Working Towards Improvement

While implementing AI into their system, NutriTrack still does not have proper monitoring and tracing for their applications. They have logs, sure, but users report of slower responses from the model, and they have no idea how much tokens they track. They would also like to improve their accuracy, and need a proper method of measuring it.

## MLflow

MLflow is a tool that helps you debug, evaluate and monitor your LLM applications, agents and models. It is officialy a part of Red Hat OpenShift AI (version 3.4 and onwards). With some basic additions to your code, it helps you get the full picture of what is going on in your applications.

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
