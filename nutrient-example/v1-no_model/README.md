# NutriTrack — Baseline Application (v1)

> This is the starting point of a case study on adopting AI into a real product. The application itself is intentionally simple — what matters is the journey from here.

---

## Meet NutriComp

NutriComp is a small health-tech startup building **NutriTrack**, a web app that helps users log their daily meals and understand their nutrient intake. The product is straightforward: pick foods, enter amounts, and see how close you are to your daily targets.

Up until now, the application had requested the users to manually input their meals. With the recent emergence of AI, the company had decided to incorporate it into their application logic, allowing the users to take a picture of their meal, and have the ingridients automatically logged.

---

## Running this version

```bash
cd nutrient-example/v1-no_model
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn
uvicorn app:app --reload
```

Open [http://localhost:8000](http://localhost:8000) and you have the full app.
