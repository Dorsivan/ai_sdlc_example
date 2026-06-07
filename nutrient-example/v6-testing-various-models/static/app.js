const foodSelect = document.getElementById("foodSelect");
const gramsInput = document.getElementById("gramsInput");
const mealNameInput = document.getElementById("mealName");
const eatenOnInput = document.getElementById("eatenOn");
const addItemBtn = document.getElementById("addItemBtn");
const logMealBtn = document.getElementById("logMealBtn");
const refreshSummaryBtn = document.getElementById("refreshSummaryBtn");
const mealItemsList = document.getElementById("mealItemsList");
const summaryContainer = document.getElementById("summaryContainer");
const statusMessage = document.getElementById("statusMessage");

let foods = {};
let currentMealItems = [];

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function setStatus(message, type = "") {
  statusMessage.textContent = message;
  statusMessage.className = `status ${type}`;
}

function formatNutrientName(name) {
  return name
    .replaceAll("_", " ")
    .replace("kcal", "kcal")
    .replace(" g", "g")
    .replace(" mg", "mg");
}

async function loadFoods() {
  const response = await fetch("/foods");

  if (!response.ok) {
    throw new Error("Could not load foods.");
  }

  foods = await response.json();

  foodSelect.innerHTML = "";

  for (const [foodId, food] of Object.entries(foods)) {
    const option = document.createElement("option");
    option.value = foodId;
    option.textContent = food.name;
    foodSelect.appendChild(option);
  }
}

function renderMealItems() {
  mealItemsList.innerHTML = "";

  if (currentMealItems.length === 0) {
    const empty = document.createElement("li");
    empty.textContent = "No items added yet.";
    mealItemsList.appendChild(empty);
    return;
  }

  currentMealItems.forEach((item, index) => {
    const food = foods[item.food_id];

    const li = document.createElement("li");

    const text = document.createElement("span");
    text.textContent = `${food.name} — ${item.grams}g`;

    const removeBtn = document.createElement("button");
    removeBtn.textContent = "Remove";
    removeBtn.className = "remove-btn";
    removeBtn.onclick = () => {
      currentMealItems.splice(index, 1);
      renderMealItems();
    };

    li.appendChild(text);
    li.appendChild(removeBtn);
    mealItemsList.appendChild(li);
  });
}

function addMealItem() {
  const foodId = foodSelect.value;
  const grams = Number(gramsInput.value);

  if (!foodId) {
    setStatus("Please choose a food.", "error");
    return;
  }

  if (!grams || grams <= 0) {
    setStatus("Please enter a valid amount in grams.", "error");
    return;
  }

  currentMealItems.push({
    food_id: foodId,
    grams
  });

  gramsInput.value = "";
  setStatus("");
  renderMealItems();
}

async function logMeal() {
  const mealName = mealNameInput.value.trim();
  const eatenOn = eatenOnInput.value;

  if (!mealName) {
    setStatus("Please enter a meal name.", "error");
    return;
  }

  if (currentMealItems.length === 0) {
    setStatus("Please add at least one food item.", "error");
    return;
  }

  const payload = {
    meal_name: mealName,
    eaten_on: eatenOn,
    items: currentMealItems
  };

  const response = await fetch("/meals", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const error = await response.json();
    setStatus(error.detail || "Could not log meal.", "error");
    return;
  }

  const result = await response.json();

  currentMealItems = [];
  mealNameInput.value = "";
  renderMealItems();

  setStatus("Meal logged successfully.", "success");
  renderSummary(result.daily_summary);
}

async function loadSummary() {
  const day = eatenOnInput.value;

  const response = await fetch(`/summary/${day}`);

  if (!response.ok) {
    setStatus("Could not load summary.", "error");
    return;
  }

  const summary = await response.json();
  renderSummary(summary);
}

function renderSummary(summary) {
  summaryContainer.innerHTML = "";

  const comparison = summary.comparison || {};
  const entries = Object.entries(comparison);

  if (entries.length === 0) {
    summaryContainer.innerHTML = `
      <p class="empty-state">
        No nutrient data yet for ${summary.date}.
      </p>
    `;
    return;
  }

  entries.forEach(([nutrient, data]) => {
    const percentage = data.percentage ?? 0;
    const safeWidth = Math.min(percentage, 100);

    const card = document.createElement("div");
    card.className = "nutrient-card";

    card.innerHTML = `
      <div class="nutrient-top">
        <div class="nutrient-name">${formatNutrientName(nutrient)}</div>
        <div class="nutrient-values">
          ${data.consumed} / ${data.required}
          — ${percentage}%
        </div>
      </div>

      <div class="progress-bar">
        <div class="progress-fill" style="width: ${safeWidth}%"></div>
      </div>
    `;

    summaryContainer.appendChild(card);
  });
}

async function init() {
  eatenOnInput.value = todayIsoDate();

  try {
    await loadFoods();
    renderMealItems();
    await loadSummary();
  } catch (error) {
    setStatus(error.message, "error");
  }
}

addItemBtn.addEventListener("click", addMealItem);
logMealBtn.addEventListener("click", logMeal);
refreshSummaryBtn.addEventListener("click", loadSummary);

eatenOnInput.addEventListener("change", loadSummary);

init();