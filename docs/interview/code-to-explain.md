# Code to explain

The snippets most worth being able to walk through line by line. For each: what it does, why it's written this way, and the follow-up questions to expect. Practice explaining without reading.

## 1. The database session dependency (`api/db.py`)

```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- A generator dependency: FastAPI calls it per request, gives the yielded session to the endpoint, and resumes after the response so `finally` closes it, even on errors.
- The engine (connection pool) is created once at import; sessions are cheap and lazy, so a cache-hit redirect never actually uses a connection.

Expect: "What happens if the endpoint raises?" (finally still runs) · "How would tests use a different database?" (`app.dependency_overrides[get_db]`).

## 2. The timing decorator (`api/timing.py`)

```python
def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info("%s took %.1f ms", func.__name__, elapsed_ms)

    return wrapper
```

- `@timed` replaces the function with `wrapper`; `finally` logs the time even when a 404 is raised.
- `functools.wraps` copies the signature, which FastAPI reads for dependency injection; without it the endpoint breaks.
- `perf_counter` is monotonic, made for measuring durations.

Expect: "Order of `@app.get` and `@timed`?" (timed is applied first, then registered) · "How would you make it work for async functions?"

## 3. The redirect (`api/main.py`)

```python
@app.get("/{code}")
@timed
def follow_link(code: str, request: Request, db: Session = Depends(get_db)):
    long_url = get_cached_url(code)
    if long_url is not None:
        logger.info("cache hit for %s", code)
    else:
        logger.info("cache miss for %s", code)
        link = db.scalar(select(Link).where(Link.code == code))
        if link is None:
            raise HTTPException(status_code=404, detail="Link not found")
        long_url = link.long_url
        cache_url(code, long_url)

    publish_click(code, request.headers.get("user-agent"))
    return RedirectResponse(long_url, status_code=307)
```

- Cache-aside; both paths converge before publishing, so only existing links are counted.
- `publish_click` buffers the event and returns immediately; the redirect never waits on Kafka.
- 307 so browsers don't cache it and every click is seen.
- Must be the last route.

Expect: "What if Redis is down?" · "What if Kafka is down?" · "How would you invalidate the cache if links became editable?"

## 4. Creating a link with collision handling (`api/main.py`)

```python
for _ in range(MAX_CODE_ATTEMPTS):
    link = Link(code=generate_code(), long_url=str(payload.long_url))
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        continue
    db.refresh(link)
    return to_out(link)
raise HTTPException(status_code=500, detail="Could not generate a unique code")
```

- The unique index decides atomically; no check-then-insert race.
- `rollback()` clears the failed transaction before retrying.
- `refresh()` loads `id` and `created_at`, which Postgres generated.

Expect: "Why not check if the code exists first?" · "How likely is a collision?" (62^7 ≈ 3.5 trillion).

## 5. The rate limiter (`api/rate_limit.py`)

```python
window = int(time.time() // WINDOW_SECONDS)
key = f"rate:create:{ip}:{window}"
try:
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, WINDOW_SECONDS)
    count, _ = pipe.execute()
except redis.RedisError:
    logger.warning("Redis unavailable, skipping rate limit")
    return
if count > settings.create_rate_limit_per_minute:
    raise HTTPException(status_code=429, detail="...", headers={"Retry-After": str(retry_after)})
```

- One key per IP per minute; INCR is atomic, so it's correct across replicas; EXPIRE cleans up; the pipeline makes it one round trip.
- Fails open on Redis errors.
- Attached with `dependencies=[Depends(rate_limit_create)]`, so it runs before the endpoint.

Expect: "Weakness of fixed windows?" · "Behind a proxy, which IP?" · "Fail open or closed?"

## 6. The idempotent batch save (`worker/main.py`)

```python
def save(events: list[dict]) -> int:
    unique = list({e["event_id"]: e for e in events}.values())

    with SessionLocal() as db, db.begin():
        new_ids = set(
            db.scalars(
                pg_insert(ProcessedEvent)
                .values([{"event_id": e["event_id"]} for e in unique])
                .on_conflict_do_nothing(index_elements=["event_id"])
                .returning(ProcessedEvent.event_id)
            )
        )

        counts = Counter((e["code"], e["day"]) for e in unique if e["event_id"] in new_ids)
        if counts:
            stmt = pg_insert(DailyClick).values(
                [{"code": code, "day": day, "count": n} for (code, day), n in counts.items()]
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["code", "day"],
                set_={"count": DailyClick.count + stmt.excluded.count},
            )
            db.execute(stmt)

    return len(new_ids)
```

- Dedupe within the batch, then against history via `processed_events`.
- `RETURNING` tells us which IDs were new; only those are counted.
- `Counter` aggregates so each `(code, day)` appears once (Postgres rejects an upsert touching the same row twice in one statement).
- One transaction: either both inserts happen or neither. In the main loop, `consumer.commit()` runs only after this returns.

Expect: "Crash between DB commit and offset commit?" · "Why not Kafka exactly-once?" · "processed_events grows forever: what then?"

## 7. Readiness vs liveness (`api/main.py`)

```python
@app.get("/health")
def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}
```

- Liveness has no dependencies, so an outage doesn't trigger restarts.
- Readiness checks only what the app can't work without (Postgres, not Redis).
- `raise ... from exc` keeps the original error in the traceback.
- `/health` reports the commit SHA, so you can see what's deployed.

Expect: "What does Kubernetes do when each fails?" · "Why not check Redis too?"
