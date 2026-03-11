from dataclasses import dataclass
from enum import Enum
import pulp
import time


# ---- DATA MODELS ----

@dataclass
class FoodItem:
    id: int
    name: str
    calories: float
    protein: float
    fat: float
    carbs: float
    cost: float
    max_servings: float
    category: str


@dataclass
class Constraints:
    calorie_target: float
    protein_min: float
    fat_min: float | None = None
    fat_max: float | None = None
    carb_min: float | None = None
    carb_max: float | None = None
    budget_max: float | None = None


class SolverStatus(Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"


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
class Result:
    status: SolverStatus
    items: list[MealPlanItem]
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float
    total_cost: float
    cost_per_gram_protein: float
    solver_time_ms: float


# ---- SOLVER ----

def solve_meal_plan(foods: list[FoodItem], constraints: Constraints) -> Result:
    start = time.perf_counter()

    prob = pulp.LpProblem("MealOptimizer", pulp.LpMinimize)

    x = {
        f.id: pulp.LpVariable(f"x_{f.id}", lowBound=0, upBound=f.max_servings)
        for f in foods
    }

    prob += pulp.lpSum(f.cost * x[f.id] for f in foods)

    cal_ceiling = constraints.calorie_target * 1.10
    prob += pulp.lpSum(f.calories * x[f.id] for f in foods) >= constraints.calorie_target
    prob += pulp.lpSum(f.calories * x[f.id] for f in foods) <= cal_ceiling
    prob += pulp.lpSum(f.protein * x[f.id] for f in foods) >= constraints.protein_min

    if constraints.fat_min is not None:
        prob += pulp.lpSum(f.fat * x[f.id] for f in foods) >= constraints.fat_min
    if constraints.fat_max is not None:
        prob += pulp.lpSum(f.fat * x[f.id] for f in foods) <= constraints.fat_max
    if constraints.carb_min is not None:
        prob += pulp.lpSum(f.carbs * x[f.id] for f in foods) >= constraints.carb_min
    if constraints.carb_max is not None:
        prob += pulp.lpSum(f.carbs * x[f.id] for f in foods) <= constraints.carb_max
    if constraints.budget_max is not None:
        prob += pulp.lpSum(f.cost * x[f.id] for f in foods) <= constraints.budget_max

    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    elapsed = (time.perf_counter() - start) * 1000

    if prob.status != pulp.constants.LpStatusOptimal:
        return Result(
            status=SolverStatus.INFEASIBLE, items=[],
            total_calories=0, total_protein=0, total_fat=0,
            total_carbs=0, total_cost=0, cost_per_gram_protein=0,
            solver_time_ms=elapsed,
        )

    items = []
    for f in foods:
        s = x[f.id].varValue or 0.0
        if s > 0.001:
            items.append(MealPlanItem(
                food=f, servings=round(s, 2),
                total_calories=round(f.calories * s, 1),
                total_protein=round(f.protein * s, 1),
                total_fat=round(f.fat * s, 1),
                total_carbs=round(f.carbs * s, 1),
                total_cost=round(f.cost * s, 2),
            ))

    total_p = sum(i.total_protein for i in items)
    total_c = sum(i.total_cost for i in items)

    return Result(
        status=SolverStatus.OPTIMAL,
        items=sorted(items, key=lambda i: i.total_protein, reverse=True),
        total_calories=round(sum(i.total_calories for i in items), 1),
        total_protein=round(total_p, 1),
        total_fat=round(sum(i.total_fat for i in items), 1),
        total_carbs=round(sum(i.total_carbs for i in items), 1),
        total_cost=round(total_c, 2),
        cost_per_gram_protein=round(total_c / max(total_p, 0.01), 3),
        solver_time_ms=round(elapsed, 2),
    )


# ---- FOOD DATABASE ----

FOODS = [
    FoodItem(1,  "Chicken Breast (6oz)",         280, 53.0,  6.0,   0.0, 2.50, 4, "protein"),
    FoodItem(2,  "Chicken Thigh (6oz)",          280, 36.0, 16.0,   0.0, 1.80, 4, "protein"),
    FoodItem(3,  "Eggs (2 large)",               143, 12.6,  9.5,   0.7, 0.60, 5, "protein"),
    FoodItem(4,  "Canned Tuna (1 can)",          120, 27.0,  1.0,   0.0, 1.20, 3, "protein"),
    FoodItem(5,  "Ground Turkey 93% (6oz)",      250, 38.0, 10.0,   0.0, 2.20, 3, "protein"),
    FoodItem(6,  "Greek Yogurt (1 cup)",         130, 22.0,  0.7,   9.0, 1.00, 3, "dairy"),
    FoodItem(7,  "Whey Protein (1 scoop)",       120, 24.0,  1.5,   3.0, 0.80, 3, "protein"),
    FoodItem(8,  "Cottage Cheese (1 cup)",       220, 25.0,  9.0,   8.0, 1.50, 2, "dairy"),
    FoodItem(10, "White Rice (1 cup cooked)",    205,  4.3,  0.4,  44.5, 0.30, 6, "carb"),
    FoodItem(11, "Oats (1 cup dry)",             307, 10.7,  5.3,  54.8, 0.35, 3, "carb"),
    FoodItem(12, "Whole Wheat Bread (2 slices)", 160,  8.0,  2.0,  28.0, 0.40, 4, "carb"),
    FoodItem(13, "Pasta (2oz dry)",              200,  7.0,  1.0,  42.0, 0.25, 5, "carb"),
    FoodItem(14, "Sweet Potato (1 medium)",      103,  2.3,  0.1,  24.0, 0.75, 4, "carb"),
    FoodItem(15, "Banana (1 medium)",            105,  1.3,  0.4,  27.0, 0.25, 3, "fruit"),
    FoodItem(20, "Peanut Butter (2 tbsp)",       188,  8.0, 16.0,   6.0, 0.30, 4, "fat"),
    FoodItem(21, "Olive Oil (1 tbsp)",           119,  0.0, 14.0,   0.0, 0.20, 3, "fat"),
    FoodItem(22, "Almonds (1oz)",                164,  6.0, 14.0,   6.0, 0.60, 3, "fat"),
    FoodItem(23, "Whole Milk (1 cup)",           149,  8.0,  8.0,  12.0, 0.50, 4, "dairy"),
    FoodItem(24, "Avocado (1/2)",                120,  1.5, 11.0,   6.0, 1.00, 2, "fat"),
    FoodItem(30, "Broccoli (1 cup)",              55,  3.7,  0.6,  11.2, 0.75, 4, "vegetable"),
    FoodItem(31, "Frozen Mixed Veggies (1 cup)",  80,  4.0,  0.5,  15.0, 0.50, 4, "vegetable"),
    FoodItem(32, "Spinach (2 cups raw)",           14,  1.7,  0.2,   2.2, 0.60, 4, "vegetable"),
    FoodItem(40, "Black Beans (1 cup cooked)",   227, 15.2,  0.9,  40.8, 0.45, 4, "legume"),
    FoodItem(41, "Lentils (1 cup cooked)",       230, 17.9,  0.8,  39.9, 0.40, 4, "legume"),
    FoodItem(42, "Pinto Beans (1 cup cooked)",   245, 15.4,  1.1,  44.8, 0.40, 4, "legume"),
]


# ---- RUN IT ----

if __name__ == "__main__":
    print("=" * 65)
    print("MealOpt Solver — Running from VS Code")
    print("=" * 65)

    result = solve_meal_plan(
        foods=FOODS,
        constraints=Constraints(
            calorie_target=2500,
            protein_min=180,
            budget_max=12.00,
        ),
    )

    print(f"\nStatus: {result.status.value}")
    print(f"Solved in: {result.solver_time_ms}ms\n")

    if result.status == SolverStatus.OPTIMAL:
        print(f"{'Food':<35} {'Servings':>8} {'Cal':>7} {'Pro':>6} {'Cost':>6}")
        print("-" * 65)
        for item in result.items:
            print(f"{item.food.name:<35} {item.servings:>8.2f} {item.total_calories:>7.1f} "
                  f"{item.total_protein:>6.1f} ${item.total_cost:>5.2f}")
        print("-" * 65)
        print(f"{'TOTAL':<35} {'':>8} {result.total_calories:>7.1f} "
              f"{result.total_protein:>6.1f} ${result.total_cost:>5.2f}")
        print(f"\nCost per gram of protein: ${result.cost_per_gram_protein:.3f}")
    else:
        print("Infeasible! Try relaxing your constraints.")