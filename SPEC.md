# RSS News Aggregation — SPEC

## Goal
Add a news aggregation system that fetches, stores, and displays market news from 130+ RSS feeds across 10 categories. Available to the AI content generation pipeline and human users.

---

## Data Model

### NewsSource
Persisted feed registry. One row per RSS feed.

| Field | Type | Notes |
|---|---|---|
| id | Integer | PK |
| category | String(50) | e.g. "Forex", "Crypto", "General" |
| name | String(100) | Display name, e.g. "ForexLive" |
| url | String(500) | RSS feed URL |
| enabled | Boolean | Whether to fetch this feed (default True) |
| last_fetched_at | DateTime | Last successful fetch |
| last_error | String | Last error message |
| fetch_count | Integer | Total successful fetches |
| created_at | DateTime | |
| updated_at | DateTime | |

### NewsItem
Individual news articles fetched from feeds.

| Field | Type | Notes |
|---|---|---|
| id | Integer | PK |
| source_id | Integer | FK → NewsSource.id |
| title | String(500) | Article headline |
| description | Text | First ~300 chars, HTML stripped |
| url | String(1000) | Link to full article |
| published_at | DateTime | Article publish date (from feed) |
| fetched_at | DateTime | When we fetched it |
| is_read | Boolean | User-marked read |
| is_starred | Boolean | User-marked starred |
| tags | String | Comma-separated tags derived from source category |

Unique constraint on (source_id, url) to prevent duplicates.

---

## Backend

### rss_news_service.py changes

- Keep `RSS_FEEDS` dict but replace the hardcoded 2-entry dict with dynamic loading from DB (NewsSource table).
- Keep `get_fxstreet_news()` as a helper — it becomes `fetch_source(source: NewsSource)` → `List[Dict]`.
- New function `fetch_all_sources(limit_per_source: int = 20)` — iterates all enabled sources, fetches in async batches, deduplicates, stores to DB.
- New function `get_news_items(filters)` — reads from DB with filtering/pagination.
- New function `mark_read(item_id)` / `mark_starred(item_id)` — update flags.
- Rate limiting: max 10 concurrent feed fetches to avoid hammering servers.

### news.py router (new)

| Method | Endpoint | Description |
|---|---|---|
| GET | /news/ | List news items (paginated, filterable) |
| GET | /news/sources | List all configured RSS sources |
| POST | /news/fetch | Trigger fetch of all (or specific category) feeds |
| PATCH | /news/{id}/read | Mark item as read |
| PATCH | /news/{id}/star | Toggle starred |
| DELETE | /news/ | Purge items older than N days (admin) |

Query params on GET /news/: `category`, `source`, `is_read`, `is_starred`, `limit` (default 50), `offset`.

### data_aggregator.py changes
- Import and call `fetch_all_sources()` during the morning pipeline so AI-generated content is informed by latest headlines.

### cron_scheduler.py changes
- Add a `news` job type that runs `fetch_all_sources()` every 30 minutes.

---

## Frontend

### News page (`/news`)
- Full-width layout, two-column: sidebar (categories) + main feed.
- Category list from NewsSource categories — clicking filters the feed.
- Each news card: source name, time ago, title (linked to external URL), description snippet, read/star actions.
- "Refresh" button triggers a fetch.
- "Mark all read" button.
- Pagination (load more on scroll or "Show more" button).

### Data flow
1. User opens `/news`.
2. Frontend calls `GET /news/?limit=50` — gets cached items from DB.
3. Items display immediately (fast, from DB).
4. Optionally trigger `POST /news/fetch` to fetch fresh items — shows loading state, then prepends new items.

---

## RSS Feed Loading

On first startup (or via management command), the 130 feeds from `rss.txt` are seeded into the NewsSource table. The CSV format:

```
Category,Name,RSS URL
```

Feeds are inserted with `enabled=True`. The app never hardcodes feed URLs again — everything reads from DB.

---

## Performance Considerations

- **Async batch fetching**: `asyncio.Semaphore(10)` caps concurrent requests to 10 feeds at a time.
- **Individual feed timeout**: 15s per feed — slow feeds don't block the batch.
- **Deduplication**: unique constraint on (source_id, url) prevents storing the same article twice on re-fetch.
- **Incremental fetch**: `last_fetched_at` tracked per source; we fetch only since last successful fetch (if feed supports `If-Modified-Since`).
- **Background fetching**: Cron job every 30 min keeps the DB fresh; frontend never waits on slow RSS feeds.

---

## Files to Create/Modify

| File | Change |
|---|---|
| `app/models/models.py` | Add NewsSource, NewsItem models |
| `app/schemas/schemas.py` | Add Pydantic schemas for news |
| `app/services/rss_news_service.py` | Full rewrite: DB-driven, async batch, store to DB |
| `app/routers/news.py` | **NEW** — all news API endpoints |
| `app/services/data_aggregator.py` | Call `fetch_all_sources()` in pipeline |
| `cron_scheduler.py` | Add `job_types["news"]` for 30-min refresh |
| `seed.py` | Add command to seed 130 feeds from rss.txt |
| `frontend/app/news/page.tsx` | **NEW** — News page |
| `frontend/lib/api.ts` | Add `getNews()`, `fetchNews()`, `markRead()`, `markStarred()` |
| `frontend/components/NewsCard.tsx` | **NEW** — news item card |
