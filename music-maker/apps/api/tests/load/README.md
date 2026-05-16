# Load Testing: Music Maker API

This directory contains Locust-based load tests to validate backend performance under concurrent user load.

## Architecture

### Components
- **`locustfile.py`** — User behavior simulation (song generation, lyrics, library browsing)
- **`mock_mureka_server.py`** — Stub Mureka API server (port 9999)
  - Prevents real API charges during testing
  - Simulates task progress: pending → processing → completed (~3 polls / 15 seconds)

### User Scenarios

**MusicMakerUser** (weighted task distribution):
- 70% **Generate Song** (POST /songs → poll GET /songs/{id})
- 10% **Generate Lyrics** (POST /lyrics/generate)
- 20% **Browse Library** (GET /library with pagination)
- Occasional credit checks (GET /account/credits)

**Wait Time**: 2-5 seconds between requests (realistic user behavior)

## Running Load Tests

### Prerequisites
```bash
pip install locust aiohttp
```

Also add to `apps/api/pyproject.toml`:
```toml
[project.optional-dependencies]
load = [
  "locust>=2.16",
  "aiohttp>=3.9",
]
```

Install: `pip install -e ".[load]"` in `apps/api/`

### Local Test (with Mock Mureka)

**Terminal 1: Start mock Mureka server**
```bash
cd apps/api/tests/load
python mock_mureka_server.py
# Output: Mock Mureka server started on http://0.0.0.0:9999
```

**Terminal 2: Start backend**
```bash
cd apps/api
uvicorn app.main:app --reload
# API running on http://localhost:8000
```

**Terminal 3: Run Locust**
```bash
cd apps/api/tests/load
locust -f locustfile.py \
  --headless \
  --users 10 \
  --spawn-rate 2 \
  --run-time 5m \
  --host http://localhost:8000
```

### Parameters

| Param | Default | Description |
|-------|---------|-------------|
| `--users` | 10 | Concurrent virtual users |
| `--spawn-rate` | 2 | Users spawned per second |
| `--run-time` | 5m | Total test duration |
| `--host` | — | Backend base URL |

### Headless vs UI

**Headless (CI/automated):**
```bash
locust -f locustfile.py --headless \
  --users 10 --spawn-rate 2 --run-time 5m
```

**Web UI (interactive, port 8089):**
```bash
locust -f locustfile.py
# Open http://localhost:8089
# Click "Start swarming" to begin test
```

## Interpreting Results

### Locust Output (Headless)
```
 Name                 Method  Count  Avg(ms)  Min(ms)  Max(ms)  P50  P95  P99
 POST /songs            50    1245    950     3200    1100  1300  1500
 GET /songs/{id}       150    340     200     1200     300   400   500
 GET /library           100    280     150     950      250   350   420
 ...
```

**Key Metrics:**
- **Avg** — Average response time (should be <1s for APIs)
- **P95** — 95th percentile (most users experience this latency)
- **P99** — 99th percentile (tail latency for slow cases)
- **Count** — Total requests of that type

**Success Criteria (Staging):**
- P95 < 2 seconds
- P99 < 5 seconds
- Error rate < 1%

### Common Issues

#### High P95/P99
**Cause**: Backend or Mureka API slow
**Fix**: Check backend logs, database indexes, Celery worker count

#### High error rate
**Cause**: DB connection pool exhausted, rate limiting
**Fix**: Increase pool size, adjust load parameters

#### Timeout on poll
**Cause**: Generation queue backed up
**Fix**: Increase Celery workers (`docker-compose scale worker=N`)

## Making Real Mureka Calls

To test against live Mureka API (uses real credits):

```bash
export MUREKA_API_BASE="https://api.mureka.io"  # Real endpoint
export MOCK_MUREKA=""  # Disable mock
locust -f locustfile.py --users 2 --run-time 1m
```

**Warning**: Each generation costs 1-2 credits. Budget accordingly!

## Docker Integration

In CI, run via `make load`:
```bash
make load
```

This will:
1. Start mock Mureka server in background
2. Run `locust` headless for 5 minutes
3. Generate HTML report in `locust_report_TIMESTAMP.html`

## Advanced: Custom Scenarios

Edit `locustfile.py` to add scenarios:

```python
@task(5)
def my_new_scenario(self):
    """Custom test."""
    with self.client.get(..., catch_response=True) as response:
        if response.status_code == 200:
            response.success()
        else:
            response.failure(f"Got {response.status_code}")
```

## CI/CD Integration

Example GitHub Actions workflow (in `.github/workflows/load.yml`):

```yaml
name: Load Tests
on:
  schedule:
    - cron: '0 2 * * MON'  # Weekly on Monday 2 AM

jobs:
  load:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -e "apps/api[load]"
      - run: |
          cd apps/api/tests/load
          python mock_mureka_server.py &
          sleep 2
          locust -f locustfile.py --headless \
            --users 20 --spawn-rate 5 --run-time 10m \
            --host http://localhost:8000 \
            --csv=results
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: load-test-results
          path: apps/api/tests/load/results_stats.csv
```

## Monitoring with Prometheus

Add to `docker-compose.yml` to scrape Locust metrics:

```yaml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

Locust exposes metrics on `http://localhost:8089/stats/requests` (JSON).

## References

- [Locust Docs](https://docs.locust.io)
- [Load Testing Best Practices](https://en.wikipedia.org/wiki/Load_testing)
- [Music Maker API Docs](../../README.md)
