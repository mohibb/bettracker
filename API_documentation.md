# BetTracker API Documentation

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000`  
**Description:** Virtual football betting tracker — FastAPI + PostgreSQL

---

## Table of Contents

- [Overview](#overview)
- [Config](#config)
- [Leagues](#leagues)
- [Odds](#odds)
- [Matches](#matches)
- [Arbitrage](#arbitrage)
- [Cart](#cart)
- [Bets](#bets)
- [Results](#results)
- [Notifications](#notifications)
- [Schemas](#schemas)

---

## Overview

BetTracker is a REST API for tracking virtual football bets. It integrates with [the-odds-api.com](https://the-odds-api.com) to fetch live odds, automatically detects arbitrage opportunities across bookmakers, and manages a full betting workflow — from cart to settlement.

### Key Concepts

- **Cart** — A temporary in-memory store (up to 3 legs) that is converted into a bet on placement. Resets on server restart.
- **Bet Types** — Inferred automatically from cart size: `single` (1 leg), `double` (2 legs), `triple` (3 legs). Arbitrage bets are placed separately.
- **Arbitrage** — Detected automatically when fetching odds. Profitable when the sum of inverse odds across bookmakers is less than 1.
- **Settlement** — Triggered automatically when match results are fetched, or manually via `POST /results/check`.

---

## Config

Manage bookmakers and API keys.

### `GET /config/bookmakers`

List all bookmakers.

**Response:** `BookmakerResponse[]`

---

### `POST /config/bookmakers`

Add a new bookmaker.

**Query Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✓ | Display name, e.g. `"Unibet"` |
| `api_key` | string | | Key used by the-odds-api.com, e.g. `"unibet"` |

**Response:** `BookmakerResponse`

---

### `PATCH /config/bookmakers/{id}`

Enable or disable a bookmaker.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | integer | Bookmaker ID |

**Query Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `is_active` | boolean | ✓ | `true` to enable, `false` to disable |

**Response:** `BookmakerResponse`

---

### `GET /config/api-keys/status`

Check usage and remaining requests for all API keys.

**Response:** `ApiKeyResponse[]`

---

### `POST /config/api-keys`

Add a new odds API key to the rotation.

**Request Body:** `ApiKeyAdd`

```json
{
  "key": "your_api_key_here",
  "requests_limit": 500
}
```

**Response:** `ApiKeyResponse`

---

## Leagues

Manage the leagues the app tracks. Leagues must exist before odds can be fetched for them. Use `seed_leagues.py` to populate all supported leagues on first run.

### `GET /leagues`

List all leagues, ordered by country and name.

**Response:** `LeagueResponse[]`

---

### `GET /leagues/{id}`

Get a single league by ID.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | integer | League ID |

**Response:** `LeagueResponse`

**Errors:**

| Code | Description |
|------|-------------|
| `404` | League not found |

---

### `POST /leagues`

Add a new league.

**Request Body:** `LeagueBase`

```json
{
  "name": "Premier League",
  "key": "soccer_epl",
  "country": "England"
}
```

The `key` must match the sport key used by the-odds-api.com. Returns `400` if a league with that key already exists.

**Response:** `LeagueResponse`

**Errors:**

| Code | Description |
|------|-------------|
| `400` | League with that key already exists |

---

### `DELETE /leagues/{id}`

Delete a league by ID.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | integer | League ID |

**Response:**

```json
{
  "message": "League 'EPL' deleted"
}
```

**Errors:**

| Code | Description |
|------|-------------|
| `404` | League not found |

---

## Odds

Fetch and retrieve betting odds.

### `GET /odds`

Get the most recent odds for every upcoming match (one record per match).

**Response:** `OddsResponse[]`

---

### `GET /odds/{match_id}`

Get all bookmaker odds for a specific match.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `match_id` | string | Match ID (hex string from the-odds-api.com) |

**Response:** `OddsResponse[]`

---

### `POST /odds/fetch`

Fetch fresh odds from the-odds-api.com. Stores odds historically and detects arbitrage opportunities. Runs automatically on a schedule but can be triggered manually.

**Response:**

```json
{
  "new_odds_stored": 42,
  "arbitrage_opportunities_found": 2
}
```

> **Note:** This endpoint consumes API key quota. Each league fetch uses one request. A low-quota notification is created automatically when fewer than 50 requests remain.

---

## Matches

Browse upcoming, live, and finished matches.

### `GET /matches`

List all matches, ordered by kick-off time.

**Query Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `league_id` | integer | Filter by league |
| `status` | string | Filter by status: `upcoming`, `live`, `finished`, `cancelled` |

**Response:** `MatchResponse[]`

---

### `GET /matches/{id}`

Get a single match by ID, including current odds from all bookmakers.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | string | Match ID |

**Response:** `MatchResponse`

**Errors:**

| Code | Description |
|------|-------------|
| `404` | Match not found |

---

### `GET /matches/{id}/odds/history`

Get the full odds history for a match — how odds moved over time across all bookmakers.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | string | Match ID |

**Response:** `OddsResponse[]` (ordered by `fetched_at` ascending)

---

## Arbitrage

View detected arbitrage opportunities.

### `GET /arbitrage`

All current arbitrage opportunities on upcoming matches, sorted by margin (best first).

**Response:** `ArbitrageResponse[]`

---

### `GET /arbitrage/history`

All past detected arbitrage opportunities, most recent first.

**Response:** `ArbitrageResponse[]`

---

### `GET /arbitrage/{id}`

Get a single arbitrage opportunity by ID.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | integer | Opportunity ID |

**Response:** `ArbitrageResponse`

**Errors:**

| Code | Description |
|------|-------------|
| `404` | Opportunity not found |

---

## Cart

An in-memory shopping cart for building bets. Maximum 3 legs. Resets on server restart.

### `GET /cart`

View current cart contents and inferred bet type.

**Response:** `CartResponse`

```json
{
  "id": 1,
  "legs": [...],
  "bet_type": "double",
  "created_at": "2025-01-01T12:00:00"
}
```

`bet_type` is one of: `empty`, `single`, `double`, `triple`.

---

### `POST /cart/legs`

Add a match selection to the cart.

**Request Body:** `CartLegAdd`

```json
{
  "match_id": "abc123",
  "bookmaker_id": 1,
  "selection": "home"
}
```

`selection` must be one of: `home`, `draw`, `away`.

**Response:**

```json
{
  "message": "Added to cart",
  "cart_size": 2
}
```

**Errors:**

| Code | Description |
|------|-------------|
| `400` | Cart is full (max 3 legs) |
| `400` | Match already in cart |

---

### `DELETE /cart/legs/{leg_id}`

Remove a single leg from the cart by its position ID.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `leg_id` | integer | Leg ID (1-based, assigned when added) |

**Response:**

```json
{
  "message": "Removed from cart",
  "cart_size": 1
}
```

---

### `DELETE /cart`

Clear the entire cart.

**Response:**

```json
{
  "message": "Cart emptied"
}
```

---

## Bets

Place and manage bets.

### `POST /bets`

Place a bet from the current cart contents. Bet type is inferred automatically from cart size. Clears the cart on success.

**Request Body:** `PlaceBetRequest`

```json
{
  "stake": 10.00
}
```

**Response:** `BetResponse`

**Errors:**

| Code | Description |
|------|-------------|
| `400` | Cart is empty |
| `404` | Match not found |
| `400` | Match is not upcoming |
| `404` | No odds found for a match |

---

### `POST /bets/arbitrage/{opportunity_id}`

Place an arbitrage bet in one action. Automatically splits the total stake across home, draw, and away so the return is identical regardless of result. Creates three separate bet records.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `opportunity_id` | integer | Arbitrage opportunity ID |

**Request Body:** `PlaceArbitrageBetRequest`

```json
{
  "opportunity_id": 5,
  "stake": 100.00
}
```

**Response:** `BetResponse[]` (array of 3 bets, one per outcome)

**Errors:**

| Code | Description |
|------|-------------|
| `404` | Opportunity not found |

---

### `GET /bets`

List all bets, most recent first.

**Query Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `type` | string | Filter by type: `single`, `double`, `triple`, `arbitrage` |
| `status` | string | Filter by status: `pending`, `won`, `lost`, `void` |

**Response:** `BetResponse[]`

---

### `GET /bets/summary`

Full P&L summary across all settled bets. Includes breakdowns by bet type, league, and bookmaker.

**Response:** `BettingSummary`

```json
{
  "bets": 20,
  "won": 8,
  "lost": 12,
  "staked": 200.00,
  "returned": 185.50,
  "profit": -14.50,
  "roi_percent": -7.25,
  "win_rate_percent": 40.0,
  "open_bets": 3,
  "by_type": { ... },
  "by_league": { ... },
  "by_bookmaker": { ... }
}
```

---

### `GET /bets/{id}`

Get a single bet by ID, including all its legs.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | integer | Bet ID |

**Response:** `BetResponse`

**Errors:**

| Code | Description |
|------|-------------|
| `404` | Bet not found |

---

## Results

Fetch match results and settle bets.

### `POST /results/check`

Fetch results for all pending bets on finished matches. Settles each leg and its parent bet automatically. Runs on a schedule but can be triggered manually.

**Response:**

```json
{
  "legs_settled": 6
}
```

> **Note:** A `bet_settled` notification is created for each bet that resolves.

---

### `GET /results/{match_id}`

Get the result for a specific match.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `match_id` | string | Match ID |

**Response:**

```json
{
  "match_id": "abc123",
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "home_goals": 2,
  "away_goals": 1,
  "result": "home",
  "status": "finished"
}
```

**Errors:**

| Code | Description |
|------|-------------|
| `404` | Match not found |

---

## Notifications

In-app notification feed for arbitrage alerts, settled bets, and API key warnings.

### `GET /notifications`

Get all unread notifications, most recent first.

**Response:** `NotificationResponse[]`

Notification types:

| Type | Trigger |
|------|---------|
| `arbitrage` | A new arbitrage opportunity was detected |
| `bet_settled` | A bet was settled (won or lost) |
| `api_key_low` | An API key has fewer than 50 requests remaining |

---

### `PATCH /notifications/{id}/read`

Mark a single notification as read.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `id` | integer | Notification ID |

**Response:**

```json
{
  "message": "Marked as read"
}
```

**Errors:**

| Code | Description |
|------|-------------|
| `404` | Notification not found |

---

### `DELETE /notifications`

Delete all notifications that have already been read.

**Response:**

```json
{
  "message": "Read notifications cleared"
}
```

---

## Schemas

### `LeagueResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | League ID |
| `name` | string | Display name, e.g. `"EPL"` |
| `key` | string | the-odds-api.com sport key, e.g. `"soccer_epl"` |
| `country` | string | Country or region, e.g. `"England"` |

---

### `BookmakerResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Bookmaker ID |
| `name` | string | Display name, e.g. `"Unibet"` |
| `api_key` | string \| null | the-odds-api.com key, e.g. `"unibet"` |
| `is_active` | boolean | Whether this bookmaker is included in odds fetches |

---

### `OddsResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Odds record ID |
| `match_id` | string | Associated match ID |
| `home` | float | Home win odds |
| `draw` | float | Draw odds |
| `away` | float | Away win odds |
| `bookmaker` | `BookmakerResponse` | The bookmaker that offered these odds |
| `fetched_at` | datetime | When these odds were recorded |

---

### `MatchResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Hex match ID from the-odds-api.com |
| `home_team` | string | Home team name |
| `away_team` | string | Away team name |
| `kick_off` | datetime | Scheduled kick-off time |
| `league` | `LeagueResponse` | League details |
| `status` | string | `upcoming`, `live`, `finished`, `cancelled` |
| `result` | string \| null | `home`, `draw`, `away` — null if not yet finished |
| `home_goals` | integer \| null | Final home goals |
| `away_goals` | integer \| null | Final away goals |
| `odds` | `OddsResponse[]` | Current odds from all bookmakers |

---

### `ArbitrageResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Opportunity ID |
| `match` | `MatchResponse` | The match this opportunity is for |
| `home_odds` | float | Best available home odds |
| `draw_odds` | float | Best available draw odds |
| `away_odds` | float | Best available away odds |
| `home_bookmaker` | `BookmakerResponse` \| null | Bookmaker offering the best home odds |
| `draw_bookmaker` | `BookmakerResponse` \| null | Bookmaker offering the best draw odds |
| `away_bookmaker` | `BookmakerResponse` \| null | Bookmaker offering the best away odds |
| `margin_percent` | float | Guaranteed profit margin as a percentage |
| `detected_at` | datetime | When this opportunity was detected |

---

### `CartResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Always `1` (single cart per session) |
| `legs` | `CartLegResponse[]` | Current selections |
| `bet_type` | string | `empty`, `single`, `double`, or `triple` |
| `created_at` | datetime | When the first leg was added |

---

### `BetResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Bet ID |
| `type` | string | `single`, `double`, `triple`, `arbitrage` |
| `stake` | float | Amount staked |
| `potential_return` | float | Maximum possible return |
| `actual_return` | float \| null | Actual return after settlement |
| `status` | string | `pending`, `won`, `lost`, `void` |
| `placed_at` | datetime | When the bet was placed |
| `settled_at` | datetime \| null | When the bet was settled |
| `legs` | `BetLegResponse[]` | Individual match selections |

---

### `BetLegResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Leg ID |
| `match` | `MatchResponse` | The match this leg is on |
| `bookmaker` | `BookmakerResponse` \| null | Bookmaker used for this leg |
| `selection` | string | `home`, `draw`, or `away` |
| `odds` | float | Odds at time of placement |
| `result` | string | `pending`, `won`, `lost`, `void` |

---

### `BettingSummary`

| Field | Type | Description |
|-------|------|-------------|
| `bets` | integer | Total settled bets |
| `won` | integer | Number won |
| `lost` | integer | Number lost |
| `staked` | float | Total amount staked |
| `returned` | float | Total amount returned |
| `profit` | float | `returned - staked` |
| `roi_percent` | float | Return on investment as a percentage |
| `win_rate_percent` | float | Percentage of bets won |
| `open_bets` | integer | Currently pending bets |
| `by_type` | object | Summary broken down by bet type |
| `by_league` | object | Summary broken down by league |
| `by_bookmaker` | object | Summary broken down by bookmaker |

---

### `NotificationResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Notification ID |
| `message` | string | Human-readable notification text |
| `type` | string | `arbitrage`, `bet_settled`, or `api_key_low` |
| `is_read` | boolean | Whether it has been read |
| `created_at` | datetime | When it was created |

---

### `ApiKeyResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Key ID |
| `requests_used` | integer | Requests consumed so far |
| `requests_limit` | integer | Total request allowance |
| `requests_remaining` | integer | `requests_limit - requests_used` |
| `is_active` | boolean | Whether this key is available for use |
| `last_used_at` | datetime \| null | When it was last used |
