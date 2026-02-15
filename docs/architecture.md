# MealOpt: AI-Powered Macro & Budget Meal Optimizer

## Full Architecture & Implementation Guide

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│              (React/Next.js Frontend — v2)                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS/JSON
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       API GATEWAY LAYER                         │
│                     FastAPI Application                         │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Auth Router  │  │ Meals Router │  │ Foods Router          │  │
│  │ POST /login  │  │ POST /plan   │  │ GET  /foods           │  │
│  │ POST /signup │  │ GET  /plans  │  │ POST /foods (admin)   │  │
│  └─────────────┘  └──────┬───────┘  └───────────────────────┘  │
└──────────────────────────┼──────────────────────────────────────┘
                           │
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────────────┐
│  SERVICE LAYER   │ │  OPTIMIZER   │ │   AI LAYER (v2)          │
│                  │ │   MODULE     │ │                          │
│ - UserService    │ │ PuLP/SciPy   │ │ - MealVariationService   │
│ - FoodService    │ │ LP Solver    │ │ - SubstitutionEngine     │
│ - MealPlanSvc    │ │              │ │ - RecipeGenerator        │
│ - GroceryListSvc │ │ Objective:   │ │                          │
│                  │ │ min(cost)    │ │ Calls Claude/GPT API     │
└────────┬─────────┘ └──────┬───────┘ └──────────────────────────┘
         │                  │
         ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA ACCESS LAYER                           │
│                  SQLAlchemy ORM + Repositories                  │
│                                                                 │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐ │
│  │ UserRepository │  │ FoodRepository  │  │ PlanRepository   │ │
│  └────────────────┘  └─────────────────┘  └──────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PostgreSQL Database                        │
│  users │ foods │ food_prices │ dietary_tags │ meal_plans │ ...  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

- **Repository Pattern**: Data access is abstracted behind repository classes. Services never write raw SQL or interact with the session directly. This makes swapping ORMs or adding caching trivial.
- **Optimizer as a pure module**: The LP solver takes dataclasses as input and returns dataclasses as output. It has ZERO knowledge of FastAPI, SQLAlchemy, or the database. This is critical — it makes it unit-testable in isolation.
- **AI Layer is a plugin**: The AI service depends on the optimizer's output schema, not the other way around. You can ship v1 without it and bolt it on later with zero refactoring.

---

## 2. Mathematical Formulation

### Decision Variables

Let `x_i` = number of servings of food item `i`, where `i ∈ {1, 2, ..., n}`

Each `x_i` is a **continuous variable** (you can have 1.5 servings of rice).

### Parameters (per food item `i`)

| Symbol     | Meaning                        |
|------------|--------------------------------|
| `c_i`      | Cost per serving ($)           |
| `cal_i`    | Calories per serving           |
| `p_i`      | Protein per serving (g)        |
| `f_i`      | Fat per serving (g)            |
| `carb_i`   | Carbs per serving (g)          |
| `x_min_i`  | Min servings (usually 0)       |
| `x_max_i`  | Max servings (e.g., 5)         |

### Objective Function

**Minimize total daily cost:**

```
minimize Z = Σ (c_i · x_i)  for all i
```

### Constraints

```
1. Calorie target:       Σ (cal_i · x_i)  >= CAL_TARGET
2. Calorie ceiling:      Σ (cal_i · x_i)  <= CAL_TARGET * 1.10   (10% buffer)
3. Protein minimum:      Σ (p_i · x_i)    >= PROTEIN_MIN
4. Fat range:            FAT_MIN  <= Σ (f_i · x_i)  <= FAT_MAX
5. Carb range:           CARB_MIN <= Σ (carb_i · x_i) <= CARB_MAX
6. Budget:               Σ (c_i · x_i)    <= DAILY_BUDGET
7. Serving bounds:       x_min_i <= x_i <= x_max_i   for all i
8. Non-negativity:       x_i >= 0                      for all i
```

### Dietary Filtering (Pre-Solver)

Dietary restrictions are NOT modeled as LP constraints. Instead, **filter the food list before passing it to the solver**. If a user is vegetarian, simply exclude all non-vegetarian foods from the input set. This is cleaner and computationally cheaper.

```python
# Pre-solver filtering
eligible_foods = [f for f in all_foods if user_constraints.satisfied_by(f)]
# Then pass only eligible_foods into the LP
```

### Why Linear Programming?

This problem is a variant of the **Diet Problem** (one of the first LP problems ever formulated, by Stigler in 1945). It's convex, has a guaranteed global optimum (if feasible), and solves in milliseconds for 100 items. No heuristics needed.

### Infeasibility Handling

The solver may return `Infeasible` if constraints conflict (e.g., 200g protein on $3/day). Your service layer must handle this gracefully:

1. Relax the budget constraint by 20%, re-solve
2. Relax the calorie ceiling, re-solve
3. If still infeasible, return a structured error explaining which constraints conflict

---

## 3. Step-by-Step Backend Build Plan

### Phase 1: Foundation (Days 1–3)
1. Initialize project with `poetry` or `uv` for dependency management
2. Set up FastAPI app scaffold with router separation
3. Configure SQLAlchemy async engine + Alembic for migrations
4. Define all ORM models (see Section 5)
5. Run initial migration, seed database with 50 foods
6. Write `FoodRepository` with basic CRUD

### Phase 2: Optimizer Core (Days 4–6)
1. Define input/output dataclasses (`OptimizationRequest`, `OptimizationResult`)
2. Implement LP solver using PuLP (see Section 4)
3. Write comprehensive unit tests for solver in isolation
4. Test edge cases: infeasible, single food, all constraints active
5. Benchmark solve time (should be <50ms for 100 items)

### Phase 3: API & Service Layer (Days 7–9)
1. Implement `MealPlanService` bridging API ↔ Optimizer ↔ DB
2. Build POST `/api/v1/plans/generate` endpoint
3. Build GET `/api/v1/plans/{id}` endpoint
4. Build GET `/api/v1/foods` with filtering
5. Add request validation with Pydantic models
6. Add structured error responses for infeasible results

### Phase 4: Auth & Persistence (Days 10–12)
1. Implement JWT auth (python-jose + passlib)
2. User registration + login endpoints
3. Save generated meal plans to DB, linked to user
4. GET `/api/v1/plans` — list user's saved plans
5. Add grocery list aggregation endpoint

### Phase 5: Polish & Deploy (Days 13–15)
1. Add logging (structlog)
2. Add rate limiting
3. Write integration tests
4. Dockerize the application
5. Deploy to Railway / Render / Fly.io
6. Write API documentation (auto-generated by FastAPI + manual examples)

---

## 4. Optimizer Code

```python
"""
mealopt/optimizer/solver.py

Pure optimization module. No framework dependencies.
Input: dataclasses. Output: dataclasses. Testable in isolation.
"""

from dataclasses import dataclass
from enum import Enum
import pulp


@dataclass
class FoodItem:
    id: int
    name: str
    calories: float      # per serving
    protein: float       # grams per serving
    fat: float           # grams per serving
    carbs: float         # grams per serving
    cost: float          # $ per serving
    max_servings: float  # upper bound (e.g., 5.0)
    category: str        # "protein", "carb", "fat", "vegetable", etc.


@dataclass
class OptimizationConstraints:
    calorie_target: float
    calorie_ceiling: float | None = None  # defaults to target * 1.10
    protein_min: float = 0.0
    fat_min: float | None = None
    fat_max: float | None = None
    carb_min: float | None = None
    carb_max: float | None = None
    budget_max: float | None = None


class SolverStatus(Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    ERROR = "error"


@dataclass
class MealPlanItem:
    food: FoodItem
    servings: float
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float
    total_cost: float


@dataclass
class OptimizationResult:
    status: SolverStatus
    items: list[MealPlanItem]
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float
    total_cost: float
    cost_per_gram_protein: float
    solver_time_ms: float


def solve_meal_plan(
    foods: list[FoodItem],
    constraints: OptimizationConstraints,
) -> OptimizationResult:
    """
    Solve the diet optimization problem via linear programming.

    Objective:  minimize Σ(cost_i * x_i)
    Subject to: macro and budget constraints
    """
    import time
    start = time.perf_counter()

    if not foods:
        return OptimizationResult(
            status=SolverStatus.INFEASIBLE,
            items=[], total_calories=0, total_protein=0,
            total_fat=0, total_carbs=0, total_cost=0,
            cost_per_gram_protein=0, solver_time_ms=0,
        )

    # --- Define problem ---
    prob = pulp.LpProblem("MealOptimizer", pulp.LpMinimize)

    # --- Decision variables: servings of each food ---
    x = {
        f.id: pulp.LpVariable(
            name=f"x_{f.id}",
            lowBound=0,
            upBound=f.max_servings,
            cat="Continuous",
        )
        for f in foods
    }

    # --- Objective: minimize cost ---
    prob += pulp.lpSum(f.cost * x[f.id] for f in foods), "TotalCost"

    # --- Constraints ---
    cal_ceiling = constraints.calorie_ceiling or constraints.calorie_target * 1.10

    prob += (
        pulp.lpSum(f.calories * x[f.id] for f in foods) >= constraints.calorie_target,
        "MinCalories",
    )
    prob += (
        pulp.lpSum(f.calories * x[f.id] for f in foods) <= cal_ceiling,
        "MaxCalories",
    )
    prob += (
        pulp.lpSum(f.protein * x[f.id] for f in foods) >= constraints.protein_min,
        "MinProtein",
    )

    if constraints.fat_min is not None:
        prob += (
            pulp.lpSum(f.fat * x[f.id] for f in foods) >= constraints.fat_min,
            "MinFat",
        )
    if constraints.fat_max is not None:
        prob += (
            pulp.lpSum(f.fat * x[f.id] for f in foods) <= constraints.fat_max,
            "MaxFat",
        )
    if constraints.carb_min is not None:
        prob += (
            pulp.lpSum(f.carbs * x[f.id] for f in foods) >= constraints.carb_min,
            "MinCarbs",
        )
    if constraints.carb_max is not None:
        prob += (
            pulp.lpSum(f.carbs * x[f.id] for f in foods) <= constraints.carb_max,
            "MaxCarbs",
        )
    if constraints.budget_max is not None:
        prob += (
            pulp.lpSum(f.cost * x[f.id] for f in foods) <= constraints.budget_max,
            "MaxBudget",
        )

    # --- Solve ---
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    elapsed_ms = (time.perf_counter() - start) * 1000

    if prob.status != pulp.constants.LpStatusOptimal:
        return OptimizationResult(
            status=SolverStatus.INFEASIBLE,
            items=[], total_calories=0, total_protein=0,
            total_fat=0, total_carbs=0, total_cost=0,
            cost_per_gram_protein=0, solver_time_ms=elapsed_ms,
        )

    # --- Extract results ---
    items: list[MealPlanItem] = []
    for f in foods:
        servings = x[f.id].varValue or 0.0
        if servings > 0.001:  # threshold to filter noise
            items.append(MealPlanItem(
                food=f,
                servings=round(servings, 2),
                total_calories=round(f.calories * servings, 1),
                total_protein=round(f.protein * servings, 1),
                total_fat=round(f.fat * servings, 1),
                total_carbs=round(f.carbs * servings, 1),
                total_cost=round(f.cost * servings, 2),
            ))

    totals = lambda attr: round(sum(getattr(i, attr) for i in items), 2)

    total_protein = totals("total_protein")
    total_cost = totals("total_cost")

    return OptimizationResult(
        status=SolverStatus.OPTIMAL,
        items=sorted(items, key=lambda i: i.total_cost, reverse=True),
        total_calories=totals("total_calories"),
        total_protein=total_protein,
        total_fat=totals("total_fat"),
        total_carbs=totals("total_carbs"),
        total_cost=total_cost,
        cost_per_gram_protein=round(total_cost / max(total_protein, 0.01), 3),
        solver_time_ms=round(elapsed_ms, 2),
    )
```

### Usage Example

```python
foods = [
    FoodItem(1, "Chicken Breast (6oz)", 280, 53, 6, 0, 2.50, 4, "protein"),
    FoodItem(2, "White Rice (1 cup)", 205, 4.3, 0.4, 44.5, 0.30, 6, "carb"),
    FoodItem(3, "Black Beans (1 cup)", 227, 15.2, 0.9, 40.8, 0.45, 4, "protein"),
    FoodItem(4, "Banana", 105, 1.3, 0.4, 27, 0.25, 3, "fruit"),
    FoodItem(5, "Whole Milk (1 cup)", 149, 8, 8, 12, 0.50, 4, "dairy"),
    FoodItem(6, "Eggs (2 large)", 143, 12.6, 9.5, 0.7, 0.60, 4, "protein"),
    FoodItem(7, "Oats (1 cup)", 307, 10.7, 5.3, 54.8, 0.35, 3, "carb"),
    FoodItem(8, "Peanut Butter (2 tbsp)", 188, 8, 16, 6, 0.30, 4, "fat"),
    FoodItem(9, "Broccoli (1 cup)", 55, 3.7, 0.6, 11.2, 0.75, 4, "vegetable"),
    FoodItem(10, "Greek Yogurt (1 cup)", 130, 22, 0.7, 9, 1.00, 3, "dairy"),
]

constraints = OptimizationConstraints(
    calorie_target=2500,
    protein_min=180,
    fat_max=80,
    budget_max=12.00,
)

result = solve_meal_plan(foods, constraints)
```

---

## 5. Database Schema

### ER Relationships

```
users ──< meal_plans ──< meal_plan_items >── foods
                                              foods ──< food_prices
                                              foods >──< dietary_tags (via food_dietary_tags)
```

### Table Definitions

```sql
-- Core user table
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name  VARCHAR(100),
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Food catalog (admin-managed, seeded)
CREATE TABLE foods (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    category      VARCHAR(50) NOT NULL,        -- protein, carb, fat, vegetable, fruit, dairy
    serving_size  VARCHAR(100) NOT NULL,        -- "1 cup", "6 oz", "2 large"
    serving_grams FLOAT NOT NULL,              -- normalized weight in grams
    calories      FLOAT NOT NULL,
    protein       FLOAT NOT NULL,
    fat           FLOAT NOT NULL,
    carbs         FLOAT NOT NULL,
    fiber         FLOAT DEFAULT 0,
    max_servings  FLOAT DEFAULT 5.0,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- Price tracking (supports price history + regional pricing later)
CREATE TABLE food_prices (
    id            SERIAL PRIMARY KEY,
    food_id       INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    price         NUMERIC(6,2) NOT NULL,       -- cost per serving
    source        VARCHAR(100) DEFAULT 'manual', -- 'manual', 'walmart_api', 'kroger_api'
    region        VARCHAR(50) DEFAULT 'default',
    effective_date DATE DEFAULT CURRENT_DATE,
    created_at    TIMESTAMPTZ DEFAULT now(),

    -- For MVP: one active price per food per region
    UNIQUE(food_id, region, effective_date)
);

-- Dietary classification tags
CREATE TABLE dietary_tags (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL           -- vegetarian, vegan, dairy-free, gluten-free, halal, etc.
);

-- Many-to-many: which tags apply to which foods
CREATE TABLE food_dietary_tags (
    food_id INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES dietary_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (food_id, tag_id)
);

-- Generated meal plans
CREATE TABLE meal_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Input constraints (stored for reproducibility)
    calorie_target  FLOAT NOT NULL,
    protein_min     FLOAT NOT NULL,
    fat_min         FLOAT,
    fat_max         FLOAT,
    carb_min        FLOAT,
    carb_max        FLOAT,
    budget_max      NUMERIC(6,2),

    -- Solver output summary
    total_calories  FLOAT NOT NULL,
    total_protein   FLOAT NOT NULL,
    total_fat       FLOAT NOT NULL,
    total_carbs     FLOAT NOT NULL,
    total_cost      NUMERIC(6,2) NOT NULL,
    cost_per_g_protein NUMERIC(6,3),
    solver_status   VARCHAR(20) NOT NULL,       -- optimal, infeasible
    solver_time_ms  FLOAT,

    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_meal_plans_user ON meal_plans(user_id, created_at DESC);

-- Individual items in a meal plan
CREATE TABLE meal_plan_items (
    id           SERIAL PRIMARY KEY,
    plan_id      UUID NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    food_id      INTEGER NOT NULL REFERENCES foods(id),
    servings     FLOAT NOT NULL,
    calories     FLOAT NOT NULL,
    protein      FLOAT NOT NULL,
    fat          FLOAT NOT NULL,
    carbs        FLOAT NOT NULL,
    cost         NUMERIC(6,2) NOT NULL
);

CREATE INDEX idx_plan_items_plan ON meal_plan_items(plan_id);
```

### Design Notes

- **`food_prices` is a separate table** intentionally. In v2, you can track price history over time, pull from grocery APIs (Walmart, Kroger), and support regional pricing. For MVP, each food has one row here.
- **`dietary_tags` is normalized** via a join table. A food can be both "vegetarian" and "gluten-free". Filtering happens with a simple `NOT EXISTS` subquery for excluded tags.
- **Meal plans store both inputs and outputs**. This is critical for reproducibility — if a user asks "why did I get this plan?", you can re-run the solver with the stored constraints.
- **UUIDs for user-facing IDs**, serial integers for internal foreign keys. This prevents ID enumeration attacks while keeping joins efficient.

---

## 6. API Endpoint Design

### Auth

| Method | Endpoint               | Description                | Auth? |
|--------|------------------------|----------------------------|-------|
| POST   | `/api/v1/auth/signup`  | Register new user          | No    |
| POST   | `/api/v1/auth/login`   | Get JWT access token       | No    |
| GET    | `/api/v1/auth/me`      | Get current user profile   | Yes   |

### Foods

| Method | Endpoint                    | Description                     | Auth? |
|--------|-----------------------------|---------------------------------|-------|
| GET    | `/api/v1/foods`             | List foods (filterable)         | No    |
| GET    | `/api/v1/foods/{id}`        | Get single food with macros     | No    |
| GET    | `/api/v1/foods/tags`        | List all dietary tags           | No    |

**Query params for GET /foods:**
```
?category=protein&tags=vegetarian,gluten-free&search=chicken&limit=50&offset=0
```

### Meal Plans

| Method | Endpoint                          | Description                    | Auth? |
|--------|-----------------------------------|--------------------------------|-------|
| POST   | `/api/v1/plans/generate`          | Generate optimized meal plan   | Yes   |
| GET    | `/api/v1/plans`                   | List user's saved plans        | Yes   |
| GET    | `/api/v1/plans/{id}`              | Get specific plan with items   | Yes   |
| GET    | `/api/v1/plans/{id}/grocery-list` | Get aggregated grocery list    | Yes   |
| DELETE | `/api/v1/plans/{id}`              | Delete a saved plan            | Yes   |

### Generate Request Body

```json
{
  "calorie_target": 2500,
  "protein_min": 180,
  "fat_min": 50,
  "fat_max": 80,
  "carb_min": null,
  "carb_max": 300,
  "budget_max": 12.00,
  "dietary_tags": ["vegetarian"],
  "excluded_food_ids": [14, 27],
  "save": true
}
```

### Generate Response Body

```json
{
  "status": "optimal",
  "summary": {
    "total_calories": 2512.3,
    "total_protein": 183.2,
    "total_fat": 67.4,
    "total_carbs": 278.1,
    "total_cost": 9.47,
    "cost_per_gram_protein": 0.052,
    "solver_time_ms": 12.4
  },
  "items": [
    {
      "food_id": 1,
      "food_name": "Chicken Breast (6oz)",
      "servings": 2.34,
      "calories": 655.2,
      "protein": 124.0,
      "fat": 14.0,
      "carbs": 0.0,
      "cost": 5.85
    }
  ],
  "plan_id": "a1b2c3d4-...",
  "constraints_used": { ... }
}
```

### Error Response (Infeasible)

```json
{
  "status": "infeasible",
  "error": "No feasible meal plan exists for the given constraints.",
  "suggestions": [
    "Try increasing your daily budget from $8.00 to $12.00",
    "Try reducing protein target from 200g to 160g",
    "Try removing some dietary restrictions"
  ]
}
```

---

## 7. Project Folder Structure

```
mealopt/
├── alembic/                        # Database migrations
│   ├── versions/
│   └── env.py
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app factory
│   ├── config.py                   # Pydantic Settings (env vars)
│   ├── dependencies.py             # Dependency injection (get_db, get_current_user)
│   │
│   ├── api/                        # API layer (thin — validation + routing only)
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # Aggregates all v1 routers
│   │   │   ├── auth.py
│   │   │   ├── foods.py
│   │   │   └── plans.py
│   │   └── schemas/                # Pydantic request/response models
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── foods.py
│   │       └── plans.py
│   │
│   ├── models/                     # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── food.py
│   │   ├── meal_plan.py
│   │   └── base.py                 # Declarative base + mixins
│   │
│   ├── repositories/               # Data access layer (queries only)
│   │   ├── __init__.py
│   │   ├── base.py                 # Generic CRUD base repository
│   │   ├── user_repo.py
│   │   ├── food_repo.py
│   │   └── plan_repo.py
│   │
│   ├── services/                   # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── food_service.py
│   │   ├── meal_plan_service.py    # Orchestrates: filter foods → solve → persist
│   │   └── grocery_service.py
│   │
│   └── optimizer/                  # Pure optimization module (NO framework deps)
│       ├── __init__.py
│       ├── models.py               # Dataclasses: FoodItem, Constraints, Result
│       └── solver.py               # LP solver (PuLP)
│
├── ai/                             # v2: AI enhancement layer (separate package)
│   ├── __init__.py
│   ├── client.py                   # LLM API client wrapper
│   ├── variation_service.py        # Generate alternative plans
│   ├── substitution_service.py     # Ingredient swaps
│   └── recipe_service.py           # Cooking instructions
│
├── scripts/
│   ├── seed_foods.py               # Seed database with 50-100 foods
│   └── benchmark_solver.py         # Performance testing
│
├── tests/
│   ├── unit/
│   │   ├── test_solver.py          # Test optimizer in isolation
│   │   └── test_services.py
│   ├── integration/
│   │   ├── test_api_plans.py
│   │   └── test_api_auth.py
│   └── conftest.py                 # Fixtures, test DB setup
│
├── Dockerfile
├── docker-compose.yml              # App + PostgreSQL
├── pyproject.toml
├── alembic.ini
├── .env.example
└── README.md
```

### Why This Structure Matters

The separation is **not cosmetic**. Each layer has a strict dependency direction:

```
API → Services → Repositories → Models
                → Optimizer (no DB knowledge)
```

- **API layer** only does: parse request, call service, return response. No business logic.
- **Service layer** orchestrates: "fetch eligible foods, filter by dietary tags, call solver, persist results." This is where your business rules live.
- **Repository layer** only does: database queries. Returns ORM models or domain objects.
- **Optimizer** is a pure function module. It takes dataclasses in, returns dataclasses out. It doesn't import SQLAlchemy, FastAPI, or anything framework-specific.

This means you can:
- Unit test the solver with zero database setup
- Swap PostgreSQL for SQLite in tests
- Replace PuLP with OR-Tools without touching the API
- Add a CLI interface that reuses Services without the API layer

---

## 8. Deployment Plan (MVP)

### Docker Setup

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://mealopt:mealopt@db:5432/mealopt
      - JWT_SECRET=change-me-in-production
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: mealopt
      POSTGRES_USER: mealopt
      POSTGRES_PASSWORD: mealopt
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mealopt"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml
COPY . .
RUN alembic upgrade head

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Deployment Options (Ranked)

1. **Railway** — Easiest. Native PostgreSQL add-on. Push to deploy. Free tier works for MVP.
2. **Render** — Similar to Railway. Free PostgreSQL (90-day limit).
3. **Fly.io** — More control. Good for demonstrating DevOps knowledge.
4. **AWS (ECS + RDS)** — Overkill for MVP, but impressive if you want to show AWS experience. Use Terraform to define infrastructure-as-code.

### Production Checklist
- [ ] Environment variables for all secrets (never hardcode)
- [ ] CORS configuration for frontend origin
- [ ] Rate limiting on `/generate` (e.g., 10 req/min per user)
- [ ] Health check endpoint: `GET /health`
- [ ] Structured JSON logging
- [ ] Alembic migrations run on deploy

---

## 9. What Makes This Technically Impressive

### For Internship Interviews

This project demonstrates competencies that most student projects don't:

| Signal                          | What It Shows                                              |
|---------------------------------|------------------------------------------------------------|
| Linear programming solver       | You understand mathematical optimization, not just CRUD    |
| Layered architecture            | You know how to structure production code, not just scripts |
| Repository pattern              | You understand data access abstraction                     |
| Pydantic validation             | You handle input validation systematically                 |
| Infeasibility handling          | You think about edge cases and failure modes               |
| JWT auth                        | You understand authentication fundamentals                 |
| Alembic migrations              | You manage schema evolution properly                       |
| Docker + compose                | You can containerize and deploy                            |
| Solver benchmarking             | You measure performance and care about it                  |
| Separated AI layer              | You can design service boundaries and plugin architectures |
| Unit tests on the solver        | You test critical business logic in isolation               |

### Talking Points for Interviews

- "I formulated the meal planning problem as a linear program — it's a variant of Stigler's Diet Problem from 1945. The solver finds the globally optimal solution in under 50ms for 100 food items."
- "The optimizer module has zero framework dependencies. It takes dataclasses in and returns dataclasses out. I can unit test it without spinning up a database or HTTP server."
- "I designed the AI layer as a plugin that consumes the solver's output schema. The deterministic solver is the source of truth; the AI layer only augments it."

---

## 10. Evolution Path: MVP → Startup Architecture

### v1 → v2 Progression

```
v1 (MVP - You Are Here)
├── Monolith FastAPI
├── 50-100 predefined foods
├── Single-day plans
├── PuLP solver
├── Basic JWT auth
└── PostgreSQL

v2 (AI Enhancement)
├── + AI variation service (Claude API)
├── + Ingredient substitution engine
├── + Recipe/cooking instruction generation
├── + Multi-day meal prep plans
├── + React frontend
└── + Food price API integration (Walmart/Kroger)

v3 (Scale)
├── + Redis cache for solver results
├── + Celery/ARQ task queue for async plan generation
├── + Multi-day optimization (7-day meal prep)
├── + User preference learning (track which plans users save/reject)
├── + Webhook for price updates
└── + Rate limiting + API keys for third-party access

v4 (Platform)
├── + Microservice extraction (solver as gRPC service)
├── + Kubernetes deployment
├── + Real-time price tracking pipeline
├── + Mobile app (React Native)
├── + Social features (share meal plans)
├── + Affiliate grocery links (monetization)
└── + B2B API for fitness apps
```

### AI Layer Architecture (v2 Detail)

```python
# ai/variation_service.py

"""
The AI layer takes a solved meal plan and generates variations.
It does NOT replace the solver — it wraps it.

Flow:
1. User generates plan via solver (deterministic, optimal)
2. User requests "give me alternatives"
3. AI layer takes the plan + constraints, prompts Claude to suggest
   ingredient swaps that stay within macro bounds
4. Each suggestion is RE-VALIDATED through the solver to guarantee
   constraint satisfaction
"""

from dataclasses import dataclass

@dataclass
class VariationRequest:
    original_plan: OptimizationResult
    constraints: OptimizationConstraints
    variation_type: str  # "budget_lower", "higher_protein", "dorm_friendly"

class MealVariationService:
    def __init__(self, llm_client, solver_fn):
        self.llm = llm_client
        self.solve = solver_fn  # Injected — same solver function from optimizer/

    async def generate_variation(self, request: VariationRequest) -> OptimizationResult:
        # 1. Ask LLM to suggest food swaps
        prompt = self._build_prompt(request)
        suggestions = await self.llm.complete(prompt)

        # 2. Parse suggested food list
        modified_foods = self._parse_suggestions(suggestions)

        # 3. RE-SOLVE through the deterministic optimizer
        #    The AI suggests, but the solver validates.
        return self.solve(modified_foods, request.constraints)
```

**Key principle**: The AI **suggests**, the solver **validates**. Users never see a plan that hasn't passed through the LP solver. This gives you the creativity of LLMs with the guarantees of mathematical optimization.

### Scaling Considerations

- **Caching**: Hash the input constraints + food set → cache the result. Two users with identical inputs get instant responses.
- **Async generation**: For multi-day plans (7-day meal prep), the solver runs 7 LPs. Offload to a task queue (ARQ or Celery) and return a job ID. Poll or use WebSockets for completion.
- **Price freshness**: Food prices change. Build a pipeline that pulls from grocery APIs nightly and updates `food_prices`. The solver always uses the latest active price.
- **Solver upgrade path**: PuLP → Google OR-Tools → Gurobi. The interface doesn't change because the optimizer module is isolated. OR-Tools handles mixed-integer programming if you later want "exactly 3 meals" (integer constraint).
