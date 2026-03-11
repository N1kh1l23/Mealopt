from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from solver import FoodItem, Constraints, SolverStatus, solve_meal_plan
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="MealOpt API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


# ---- Load menu data on startup ----

def load_menu_data(filepath: str = "menu_data.json"):
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
                max_servings=1.5 if dish["price"] > 4 else 3,
                category="restaurant" if dish["price"] > 4 else "grocery",
            )
            foods.append(food)
            food_to_location[food_id] = restaurant
            food_id += 1

    return foods, food_to_location


ALL_FOODS, FOOD_TO_LOCATION = load_menu_data()


# ---- Request/Response Models ----

class PlanRequest(BaseModel):
    calorie_target: float = 2500
    protein_min: float = 150
    fat_min: float | None = None
    fat_max: float | None = None
    carb_min: float | None = None
    carb_max: float | None = None
    budget_max: float | None = 15.00
    mode: str = "all"


class FoodItemResponse(BaseModel):
    name: str
    servings: float
    calories: float
    protein: float
    fat: float
    carbs: float
    cost: float
    location: str
    address: str


class PlanResponse(BaseModel):
    status: str
    items: list[FoodItemResponse]
    total_calories: float
    total_protein: float
    total_fat: float
    total_carbs: float
    total_cost: float
    cost_per_gram_protein: float
    solver_time_ms: float


class NearbyRequest(BaseModel):
    latitude: float
    longitude: float
    radius: int = 3000  # meters
    type: str = "restaurant"  # restaurant, grocery_store, supermarket


# ---- Helper ----

def format_result(result, food_to_location) -> PlanResponse:
    items = []
    for item in result.items:
        loc = food_to_location[item.food.id]
        name = loc.split(":")[0]
        address = loc.split(": ")[1] if ": " in loc else ""
        items.append(FoodItemResponse(
            name=item.food.name,
            servings=item.servings,
            calories=item.total_calories,
            protein=item.total_protein,
            fat=item.total_fat,
            carbs=item.total_carbs,
            cost=item.total_cost,
            location=name,
            address=address,
        ))

    return PlanResponse(
        status=result.status.value,
        items=items,
        total_calories=result.total_calories,
        total_protein=result.total_protein,
        total_fat=result.total_fat,
        total_carbs=result.total_carbs,
        total_cost=result.total_cost,
        cost_per_gram_protein=result.cost_per_gram_protein,
        solver_time_ms=result.solver_time_ms,
    )


# ---- Endpoints ----

@app.get("/")
def root():
    return {
        "message": "MealOpt API is running",
        "foods_loaded": len(ALL_FOODS),
        "google_places": "connected" if GOOGLE_API_KEY else "no key found",
    }


@app.get("/foods")
def get_foods():
    result = []
    for food in ALL_FOODS:
        loc = FOOD_TO_LOCATION[food.id]
        result.append({
            "id": food.id,
            "name": food.name,
            "calories": food.calories,
            "protein": food.protein,
            "fat": food.fat,
            "carbs": food.carbs,
            "cost": food.cost,
            "category": food.category,
            "location": loc.split(":")[0],
            "address": loc.split(": ")[1] if ": " in loc else "",
        })
    return result


@app.post("/optimize", response_model=PlanResponse)
def optimize(req: PlanRequest):
    constraints = Constraints(
        calorie_target=req.calorie_target,
        protein_min=req.protein_min,
        fat_min=req.fat_min,
        fat_max=req.fat_max,
        carb_min=req.carb_min,
        carb_max=req.carb_max,
        budget_max=req.budget_max,
    )

    if req.mode == "grocery":
        foods = [f for f in ALL_FOODS if f.category == "grocery"]
    elif req.mode == "restaurant":
        foods = [f for f in ALL_FOODS if f.category == "restaurant"]
    else:
        foods = ALL_FOODS

    result = solve_meal_plan(foods, constraints)

    if result.status == SolverStatus.INFEASIBLE:
        return PlanResponse(
            status="infeasible", items=[],
            total_calories=0, total_protein=0, total_fat=0,
            total_carbs=0, total_cost=0, cost_per_gram_protein=0,
            solver_time_ms=result.solver_time_ms,
        )

    return format_result(result, FOOD_TO_LOCATION)


@app.post("/optimize/mix")
def optimize_mix(req: PlanRequest):
    restaurant_foods = [f for f in ALL_FOODS if f.category == "restaurant"]
    restaurant_constraints = Constraints(
        calorie_target=700,
        protein_min=40,
        fat_max=50,
        budget_max=req.budget_max or 15.00,
    )
    restaurant_result = solve_meal_plan(restaurant_foods, restaurant_constraints)

    if restaurant_result.status == SolverStatus.INFEASIBLE:
        return {"status": "infeasible", "message": "No restaurant meal found"}

    grocery_foods = [f for f in ALL_FOODS if f.category == "grocery"]
    remaining = Constraints(
        calorie_target=max(req.calorie_target - restaurant_result.total_calories, 500),
        protein_min=max(req.protein_min - restaurant_result.total_protein, 30),
        fat_min=max((req.fat_min or 0) - restaurant_result.total_fat, 0) or None,
        carb_max=max((req.carb_max or 500) - restaurant_result.total_carbs, 50) if req.carb_max else None,
        budget_max=max((req.budget_max or 20) - restaurant_result.total_cost, 3),
    )
    grocery_result = solve_meal_plan(grocery_foods, remaining)

    if grocery_result.status == SolverStatus.INFEASIBLE:
        return {"status": "infeasible", "message": "Can't fill remaining macros with grocery budget"}

    restaurant_plan = format_result(restaurant_result, FOOD_TO_LOCATION)
    grocery_plan = format_result(grocery_result, FOOD_TO_LOCATION)

    return {
        "status": "optimal",
        "restaurant_meal": restaurant_plan,
        "grocery_plan": grocery_plan,
        "combined": {
            "total_calories": round(restaurant_result.total_calories + grocery_result.total_calories, 1),
            "total_protein": round(restaurant_result.total_protein + grocery_result.total_protein, 1),
            "total_fat": round(restaurant_result.total_fat + grocery_result.total_fat, 1),
            "total_carbs": round(restaurant_result.total_carbs + grocery_result.total_carbs, 1),
            "total_cost": round(restaurant_result.total_cost + grocery_result.total_cost, 2),
        },
    }


# ---- Google Places Nearby Search ----

@app.post("/nearby")
def nearby_places(req: NearbyRequest):
    """Find nearby restaurants and grocery stores using Google Places API."""

    if not GOOGLE_API_KEY:
        return {"error": "Google Places API key not configured"}

    url = "https://places.googleapis.com/v1/places:searchNearby"

    # Map friendly names to Google place types
    type_map = {
        "restaurant": ["restaurant", "fast_food_restaurant", "meal_takeaway"],
        "grocery": ["grocery_store", "supermarket"],
        "all": ["restaurant", "fast_food_restaurant", "grocery_store", "supermarket"],
    }

    place_types = type_map.get(req.type, type_map["all"])

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.rating,places.priceLevel,places.types,places.googleMapsUri",
    }

    body = {
        "includedTypes": place_types,
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": req.latitude,
                    "longitude": req.longitude,
                },
                "radius": req.radius,
            }
        },
    }

    try:
        resp = requests.post(url, json=body, headers=headers)
        data = resp.json()

        if "places" not in data:
            return {"places": [], "message": data.get("error", {}).get("message", "No results")}

        places = []
        for p in data["places"]:
            places.append({
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "address": p.get("formattedAddress", ""),
                "lat": p.get("location", {}).get("latitude"),
                "lng": p.get("location", {}).get("longitude"),
                "rating": p.get("rating"),
                "price_level": p.get("priceLevel"),
                "types": p.get("types", []),
                "maps_url": p.get("googleMapsUri", ""),
            })

        return {"places": places, "count": len(places)}

    except Exception as e:
        return {"error": str(e)}

# ---- Nearby-Aware Optimization ----
class NearbyOptimizeRequest(BaseModel):
    calorie_target: float = 2500
    protein_min: float = 150
    fat_min: float | None = None
    fat_max: float | None = None
    carb_min: float | None = None
    carb_max: float | None = None
    budget_max: float | None = 15.00
    mode: str = "all"
    nearby_names: list[str] = []  # e.g. ["Chick-fil-A", "Trader Joe's", "Whole Foods"]


@app.post("/optimize/nearby")
def optimize_nearby(req: NearbyOptimizeRequest):
    """
    Optimize using only foods from locations that are actually near the user.
    Matches nearby place names against menu_data.json entries.
    """

    if not req.nearby_names:
        return {"status": "error", "message": "No nearby places provided"}

    # Match nearby names to our menu data
    # Fuzzy match: if "Chick-fil-A" is nearby and menu has "Chick-fil-A: 569 Huntington Ave..."
    matched_foods = []
    matched_locations = set()

    for food in ALL_FOODS:
        location_full = FOOD_TO_LOCATION[food.id]
        location_name = location_full.split(":")[0].strip().lower()

        for nearby_name in req.nearby_names:
            nearby_lower = nearby_name.strip().lower()
            # Match if either name contains the other
            if nearby_lower in location_name or location_name in nearby_lower:
                matched_foods.append(food)
                matched_locations.add(location_full.split(":")[0].strip())
                break

    if not matched_foods:
        return {
            "status": "no_match",
            "message": "None of the nearby places match our menu database yet.",
            "nearby_names": req.nearby_names,
            "suggestion": "We have data for: " + ", ".join(
                sorted(set(loc.split(":")[0].strip() for loc in FOOD_TO_LOCATION.values()))
            ),
        }

    constraints = Constraints(
        calorie_target=req.calorie_target,
        protein_min=req.protein_min,
        fat_min=req.fat_min,
        fat_max=req.fat_max,
        carb_min=req.carb_min,
        carb_max=req.carb_max,
        budget_max=req.budget_max,
    )

    if req.mode == "grocery":
        matched_foods = [f for f in matched_foods if f.category == "grocery"]
    elif req.mode == "restaurant":
        matched_foods = [f for f in matched_foods if f.category == "restaurant"]

    result = solve_meal_plan(matched_foods, constraints)

    if result.status == SolverStatus.INFEASIBLE:
        return {
            "status": "infeasible",
            "message": "No feasible plan from nearby places. Try increasing budget or relaxing targets.",
            "matched_locations": list(matched_locations),
            "matched_food_count": len(matched_foods),
        }

    plan = format_result(result, FOOD_TO_LOCATION)

    return {
        "status": "optimal",
        "matched_locations": list(matched_locations),
        "matched_food_count": len(matched_foods),
        "plan": plan,
    }