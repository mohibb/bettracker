BetTracker
A self-hosted football betting tracker built with FastAPI and PostgreSQL. Connects to the-odds-api.com to pull live odds, automatically detects arbitrage opportunities across bookmakers, and manages the full betting lifecycle from selection to settlement.
---
Features
Live odds ingestion — fetches h2h odds across configurable bookmakers on a schedule
Arbitrage detection — automatically identifies and stores opportunities where the sum of inverse odds across bookmakers is less than 1
Cart-based bet placement — build singles, doubles and triples via a temporary in-memory cart (up to 3 legs)
Automated settlement — resolves bet legs and parent bets when match results come in
P&L summary — full breakdown of profit/loss by bet type, league and bookmaker
Notifications — in-app feed for arbitrage alerts, settled bets and low API quota warnings
API key rotation — round-robin across multiple odds API keys with usage tracking
---
Tech Stack
Layer	Technology
API	FastAPI
Database	PostgreSQL
ORM	SQLAlchemy
Migrations	Alembic
Scheduler	APScheduler
HTTP client	httpx
Testing	pytest + SQLite
CI	GitHub Actions
---
Project Structure
```
bettracker/
├── app/
│   ├── main.py              # FastAPI app, lifespan, router registration
│   ├── database.py          # SQLAlchemy engine and session
│   ├── models.py            # ORM models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── dependencies.py      # Shared logic: arbitrage detection, bet settlement, API key management
│   ├── scheduler.py         # APScheduler background jobs
│   └── routers/
│       ├── config.py        # Bookmakers and API key management
│       ├── odds.py          # Odds fetching and retrieval
│       ├── matches.py       # Match listing and odds history
│       ├── arbitrage.py     # Arbitrage opportunity endpoints
│       ├── cart.py          # In-memory cart
│       ├── bets.py          # Bet placement, listing and P\&L summary
│       ├── results.py       # Result fetching and bet settlement
│       └── notifications.py # Notification feed
├── tests/
│   └── test\_api.py          # Full test suite (uses SQLite in-memory DB)
├── .github/workflows/
│   └── test.yml             # CI: run tests + coverage on every push
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── alembic.ini              # (not yet generated — see Setup)
```
---
Setup
Prerequisites
Python 3.12+
PostgreSQL running locally or remotely
An API key from the-odds-api.com (free tier: 500 requests/month)
1. Clone and install
```bash
git clone https://github.com/your-username/bettracker.git
cd bettracker
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.txt
```
2. Configure environment
```bash
cp .env.example .env
```
Edit `.env`:
```env
DATABASE\_URL=postgresql://user:password@localhost:5432/bettracker
ODDS\_FETCH\_INTERVAL\_HOURS=4
RESULTS\_CHECK\_INTERVAL\_MINUTES=30
```
3. Create the database
```bash
createdb bettracker
```
The tables are created automatically on first startup via `Base.metadata.create\_all()`. See Migrations for production use.
4. Run the server
```bash
uvicorn app.main:app --reload
```
The API is available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`
---
Configuration
Adding bookmakers
Bookmakers must be registered before odds can be fetched. The `api\_key` field must match the key used by the-odds-api.com (find these in their documentation).
```bash
curl -X POST "http://localhost:8000/config/bookmakers?name=Unibet\&api\_key=unibet"
curl -X POST "http://localhost:8000/config/bookmakers?name=Bet365\&api\_key=bet365"
```
Adding an odds API key
```bash
curl -X POST http://localhost:8000/config/api-keys \\
  -H "Content-Type: application/json" \\
  -d '{"key": "your\_odds\_api\_key", "requests\_limit": 500}'
```
Multiple keys can be added. The app automatically uses the next available key when one is exhausted.
Fetching odds manually
```bash
curl -X POST http://localhost:8000/odds/fetch
```
This also runs automatically every `ODDS\_FETCH\_INTERVAL\_HOURS` hours.
---
Betting Workflow
```
1. Browse matches        GET /matches?status=upcoming
2. Check odds            GET /odds/{match\_id}
3. Add to cart           POST /cart/legs
4. Review cart           GET /cart
5. Place bet             POST /bets  {"stake": 10.0}
6. Check results         POST /results/check  (or wait for scheduler)
7. View P\&L              GET /bets/summary
```
Arbitrage workflow
```
1. View opportunities    GET /arbitrage
2. Place arb bet         POST /bets/arbitrage/{id}  {"opportunity\_id": 5, "stake": 100.0}
```
The arbitrage endpoint automatically splits the stake across all three outcomes so the return is identical regardless of result.
---
Scheduler
Two background jobs run automatically:
Job	Default interval	Manual trigger
Fetch odds + detect arbitrage	Every 4 hours	`POST /odds/fetch`
Check results + settle bets	Every 30 minutes	`POST /results/check`
Intervals are configured in `.env` via `ODDS\_FETCH\_INTERVAL\_HOURS` and `RESULTS\_CHECK\_INTERVAL\_MINUTES`.
---
Running Tests
```bash
pytest
```
The test suite uses an SQLite file-based database (`test.db`) — no PostgreSQL needed. All tables are dropped and recreated before each test for a clean slate.
```bash
# With coverage
pytest --cov=app --cov-report=term-missing
```
CI runs on every push and pull request via GitHub Actions.
---
Migrations
The app currently uses `Base.metadata.create\_all()` on startup, which is fine for development but does not handle schema changes safely. For production, use Alembic:
```bash
alembic init alembic
# Edit alembic.ini and alembic/env.py to point at your DATABASE\_URL and models
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```
---
API Reference
Full documentation is available in `API\_documentation.md` or interactively at `/docs` when the server is running.
---
Environment Variables
Variable	Default	Description
`DATABASE\_URL`	—	PostgreSQL connection string (required)
`ODDS\_FETCH\_INTERVAL\_HOURS`	`4`	How often to fetch odds
`RESULTS\_CHECK\_INTERVAL\_MINUTES`	`30`	How often to check match results
