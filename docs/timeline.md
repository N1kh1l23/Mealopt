# MealOpt — 14-Week Build Timeline
**Pace:** 5–10 hrs/week combined (~3–5 hrs each)
**Start:** Week of Feb 17 · **Target:** Mid-May (start of summer)

---

## Phase 1: Solver Core (Weeks 1–3)

The solver is the whole point. Nothing else matters until this works.

### Week 1 — Setup + First Solve
| Person A (Nikhil) | Person B (Partner) |
|---|---|
| Create GitHub repo + Colab notebook | Research USDA FoodData Central |
| Paste in starter solver code, get it running | Build initial food list: 25 items with verified macros + prices |
| Run the 4 test cases from the notebook | Document data sources (where each price/macro came from) |

**Done when:** Solver runs in Colab, produces a reasonable meal plan for 2500cal/180g protein/$12.

### Week 2 — Expand Data + Dietary Filtering
| Person A | Person B |
|---|---|
| Add dietary tag fields to FoodItem (is_vegetarian, is_dairy_free, is_gluten_free) | Add 25 more foods (target: 50 total across all categories) |
| Build pre-solver filtering function | Verify all macro data against USDA |
| Write vegetarian + dairy-free test cases | Build a display function that prints results as a clean table |

**Done when:** You can run `solve_meal_plan` with dietary filters and get correct results for 50 foods.

### Week 3 — Edge Cases + Grocery List
| Person A | Person B |
|---|---|
| Infeasibility handling: detect which constraint is too tight, return useful error messages | Grocery list aggregator: combine servings into real purchase quantities ("buy 1.5 lbs chicken breast") |
| Write 8-10 unit tests (infeasible budget, 0 protein, empty list, single food only, etc.) | Add serving size conversion logic (servings → grams → store quantities) |

**Done when:** Solver handles all edge cases gracefully, grocery list output works. Push cleaned-up code to GitHub.

**⏸️ Checkpoint:** Show someone the Colab notebook. If they can tweak constraints and get sensible plans, Phase 1 is solid.

---

## Phase 2: API + Database (Weeks 4–8)

Now you wrap the solver in a real backend. This is where you split into clearer roles.

### Week 4 — Project Scaffold + Database
| Person A (API/Backend focus) | Person B (Database/Data focus) |
|---|---|
| Set up project folder structure (from architecture doc Section 7) | Set up PostgreSQL locally (Docker recommended) |
| Initialize FastAPI app, install dependencies (poetry/uv) | Write SQLAlchemy ORM models for all tables |
| Create config.py with Pydantic Settings | Set up Alembic, run first migration |

**Done when:** `uvicorn app.main:app` starts, database tables exist, you can connect.

### Week 5 — Food CRUD + Seeding
| Person A | Person B |
|---|---|
| Build FoodRepository (CRUD operations) | Write seed_foods.py script to populate DB with your 50+ foods |
| Build GET /api/v1/foods endpoint with filtering (category, dietary tags, search) | Add food_prices and food_dietary_tags seed data |
| Pydantic response schemas for foods | Test that seed script is idempotent (safe to run twice) |

**Done when:** `GET /foods?category=protein&tags=vegetarian` returns correct filtered JSON.

### Week 6 — Meal Plan Generation Endpoint
| Person A | Person B |
|---|---|
| Build MealPlanService: fetch foods from DB → filter → call solver → return result | Write Pydantic schemas for plan generation request/response |
| Build POST /api/v1/plans/generate | Write integration tests: hit the endpoint, verify response shape |
| Wire up infeasibility error responses | Test with Postman/Thunder Client — try different constraint combos |

**Done when:** You can POST constraints to /plans/generate and get back an optimized meal plan from the database.

### Week 7 — Auth + Plan Persistence
| Person A | Person B |
|---|---|
| Implement JWT auth (python-jose + passlib) | Build PlanRepository: save/load plans to DB |
| POST /auth/signup, POST /auth/login, GET /auth/me | GET /api/v1/plans (list user's plans) |
| Add auth dependency to protected routes | GET /api/v1/plans/{id} with items |

**Done when:** Users can sign up, log in, generate plans, and see their history.

### Week 8 — Grocery List + Polish
| Person A | Person B |
|---|---|
| GET /api/v1/plans/{id}/grocery-list endpoint | Add request validation edge cases |
| Add rate limiting on /generate | Add structured logging (structlog) |
| Write API documentation (FastAPI auto-docs + examples) | Write 5+ integration tests for the full flow |

**Done when:** Full API works end-to-end. Auto-docs at /docs look clean.

**⏸️ Checkpoint:** Someone can use Postman to sign up, generate a plan, and get a grocery list. The API is complete.

---

## Phase 3: Deploy + Portfolio Polish (Weeks 9–11)

### Week 9 — Dockerize + Deploy
| Person A | Person B |
|---|---|
| Write Dockerfile + docker-compose.yml | Write .env.example, document all env vars |
| Test full app runs in Docker locally | Deploy to Railway or Render (pick one) |
| Set up health check endpoint | Verify deployed API works with Postman |

**Done when:** API is live on a public URL.

### Week 10 — README + Demo
| Person A | Person B |
|---|---|
| Write a strong README: problem statement, architecture diagram, tech stack, how to run | Create a demo video or GIF showing API usage |
| Add the math formulation explanation to README | Add sample curl commands / Postman collection |

**Done when:** Someone visiting your GitHub repo understands what this is and is impressed within 30 seconds.

### Week 11 — Buffer / Stretch Goals
Use this week to catch up if you fell behind, OR pick one stretch goal:
- Simple React frontend (even just a form + results display)
- Add 25 more foods to reach 75+
- Price comparison across stores
- Multi-day meal prep (solve 7 days at once)

---

## Phase 4: AI Layer — Optional (Weeks 12–14)

Only start this if Phases 1-3 are solid. This is bonus.

### Week 12–13 — AI Variation Service
| Person A | Person B |
|---|---|
| Build ai/ module structure | Write prompts for meal plan variations |
| Implement Claude/GPT API client wrapper | Implement "suggest substitutions" feature |
| Wire AI suggestions back through solver for validation | "Dorm-friendly version" prompt + endpoint |

### Week 14 — Polish + Ship
| Both |
|---|
| Final testing, bug fixes |
| Update README with AI features |
| Practice explaining the project for interviews |
| **You're done.** |

---

## Role Division Summary

This split works well if you haven't assigned roles yet:

| Role | Focus | Key Skills Developed |
|---|---|---|
| **Person A — API & Architecture** | FastAPI routes, service layer, auth, deployment | Backend engineering, system design, DevOps |
| **Person B — Data & Optimization** | Food database, seeding, ORM models, testing, grocery logic | Data modeling, SQL, testing, data accuracy |
| **Both** | Solver logic (Phase 1), README, AI layer | Optimization, technical writing |

Swap tasks freely — the split is a starting point, not a contract.

---

## Weekly Rhythm

A good cadence for undergrads:

- **Monday**: Quick sync (text/Discord, 10 min) — what are we each doing this week?
- **During week**: Work independently on your tasks, push to GitHub
- **Weekend**: Review each other's PRs, test together, update task list

---

## If You Fall Behind

This is designed with ~2 weeks of buffer built in. If midterms or assignments hit:

- **1 week behind:** Skip Week 11 stretch goals, you're fine
- **2 weeks behind:** Compress Phase 3 (deploy in 1 week instead of 2)
- **3+ weeks behind:** Ship without the AI layer — Phases 1-3 alone are a strong portfolio project
