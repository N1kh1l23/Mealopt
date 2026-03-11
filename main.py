"""
MealOpt Main — Merges the LP solver with restaurant/store location data.

Flow:
1. Load menu_data.json (restaurants + grocery stores with macros & prices)
2. User sets their macro targets and budget
3. Solver finds the optimal combination of items across ALL locations
4. Results show what to buy and WHERE to buy it
"""

import json
from solver import FoodItem, Constraints, SolverStatus, solve_meal_plan


def load_menu_data(filepath: str) -> tuple[list[FoodItem], dict[int, str]]:
    """
    Loads menu_data.json and converts it into FoodItem objects for the solver.
    Returns the food list and a mapping of food_id -> restaurant name.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    foods = []
    food_to_location = {}
    food_id = 1

    for restaurant, dishes in raw.items():
        for dish in dishes:
            food = FoodItem(
                id=food_id,
                name=dish["item"],
                calories=dish["cal"],
                protein=dish["pro"],
                fat=dish["fat"],
                carbs=dish["carb"],
                cost=dish["price"],
                max_servings=1.5 if dish["price"] > 4 else 3,  # restaurants capped at 1.5
                category="restaurant" if dish["price"] > 4 else "grocery",
            )
            foods.append(food)
            food_to_location[food_id] = restaurant
            food_id += 1

    return foods, food_to_location


def print_results(result, food_to_location):
    """Pretty-print the optimized meal plan grouped by location."""

    if result.status == SolverStatus.INFEASIBLE:
        print("\n  No feasible plan found. Try:")
        print("  - Increasing your budget")
        print("  - Lowering your protein target")
        print("  - Removing macro restrictions")
        return

    # Group items by location
    location_groups = {}
    for item in result.items:
        loc = food_to_location[item.food.id]
        if loc not in location_groups:
            location_groups[loc] = []
        location_groups[loc].append(item)

    print(f"\nStatus: {result.status.value}")
    print(f"Solved in: {result.solver_time_ms}ms")
    print(f"\n{'=' * 70}")

    for location, items in location_groups.items():
        loc_cost = sum(i.total_cost for i in items)
        loc_name = location.split(":")[0]  # Just the restaurant name
        loc_address = location.split(": ")[1] if ": " in location else ""

        print(f"\n  {loc_name}")
        print(f"  {loc_address}")
        print(f"  {'─' * 60}")

        for item in items:
            print(f"    {item.servings:.1f}x {item.food.name:<35} "
                  f"{item.total_protein:>5.1f}g pro  ${item.total_cost:.2f}")

        print(f"  {'─' * 60}")
        print(f"  {'Subtotal:':<42} ${loc_cost:.2f}")

    print(f"\n{'=' * 70}")
    print(f"  DAILY TOTALS")
    print(f"    Calories: {result.total_calories:.0f}")
    print(f"    Protein:  {result.total_protein:.0f}g")
    print(f"    Fat:      {result.total_fat:.0f}g")
    print(f"    Carbs:    {result.total_carbs:.0f}g")
    print(f"    Cost:     ${result.total_cost:.2f}")
    print(f"    Cost per gram of protein: ${result.cost_per_gram_protein:.3f}")
    print(f"{'=' * 70}")


# ---- RUN IT ----

if __name__ == "__main__":
    print("=" * 70)
    print("  MealOpt — Macro & Budget Meal Optimizer")
    print("  Optimizing across restaurants AND grocery stores near you")
    print("=" * 70)

    # Load all food sources
    foods, food_to_location = load_menu_data("menu_data.json")
    print(f"\n  Loaded {len(foods)} items from {len(set(food_to_location.values()))} locations")

    # ---- CHANGE THESE TO YOUR GOALS ----
    constraints = Constraints(
        calorie_target=2500,
        protein_min=180,
        fat_min=50,       # forces some fat sources (meat, PB, etc.)
        carb_max=350,     # prevents all-bean plans
        budget_max=15.00,
    )

    print(f"  Target: {constraints.calorie_target:.0f} cal, "
          f"{constraints.protein_min:.0f}g protein, "
          f"${constraints.budget_max:.2f} budget")

    # Solve
    result = solve_meal_plan(foods, constraints)
    print_results(result, food_to_location)

    # ---- GROCERY ONLY MODE ----
    print("\n\n")
    print("=" * 70)
    print("  GROCERY ONLY — Same targets, only store items")
    print("=" * 70)

    grocery_foods = [f for f in foods if f.category == "grocery"]
    print(f"\n  Loaded {len(grocery_foods)} grocery items")

    result2 = solve_meal_plan(grocery_foods, constraints)
    print_results(result2, food_to_location)

    # ---- RESTAURANT ONLY MODE ----
    print("\n\n")
    print("=" * 70)
    print("  EATING OUT — Best single meal for your macros under budget")
    print("=" * 70)

    restaurant_foods = [f for f in foods if f.category == "restaurant"]
    print(f"\n  Loaded {len(restaurant_foods)} restaurant items")

    # For a single meal out, aim for ~800 cal and ~50g protein
    restaurant_constraints = Constraints(
        calorie_target=700,
        protein_min=40,
        fat_max=50,
        budget_max=15.00,
    )

    result3 = solve_meal_plan(restaurant_foods, restaurant_constraints)
    print_results(result3, food_to_location)

    # ---- MIX MODE — One restaurant meal + grocery for the rest ----
    print("\n\n")
    print("=" * 70)
    print("  MIX MODE — One restaurant meal + groceries for the rest of the day")
    print("=" * 70)

    # If we found a restaurant meal, subtract its macros from daily targets
    if result3.status == SolverStatus.OPTIMAL:
        remaining = Constraints(
            calorie_target=max(constraints.calorie_target - result3.total_calories, 500),
            protein_min=max(constraints.protein_min - result3.total_protein, 30),
            fat_min=max((constraints.fat_min or 0) - result3.total_fat, 0),
            carb_max=max((constraints.carb_max or 500) - result3.total_carbs, 50),
            budget_max=max((constraints.budget_max or 20) - result3.total_cost, 3),
        )

        print(f"\n  After eating out: need {remaining.calorie_target:.0f} cal, "
              f"{remaining.protein_min:.0f}g protein, ${remaining.budget_max:.2f} left")

        result4 = solve_meal_plan(grocery_foods, remaining)
        print_results(result4, food_to_location)

        # Combined totals
        if result4.status == SolverStatus.OPTIMAL:
            print(f"\n  {'=' * 66}")
            print(f"  FULL DAY COMBINED")
            print(f"    Calories: {result3.total_calories + result4.total_calories:.0f}")
            print(f"    Protein:  {result3.total_protein + result4.total_protein:.0f}g")
            print(f"    Cost:     ${result3.total_cost + result4.total_cost:.2f}")
            print(f"  {'=' * 66}")