"""Minimal smoke test against the real Mureka API.

Run from `apps/api/`:

    uv run python scripts/smoke_mureka.py            # lyrics only (cheapest)
    uv run python scripts/smoke_mureka.py --song     # lyrics + song generation (consumes credits)

Reads .env from the project root (../../.env) if present.
Prints PASS/FAIL and key metrics only. Never echoes the API key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path


def _load_root_env() -> None:
    """Load .env from project root before importing Settings."""
    root_env = Path(__file__).resolve().parents[3] / ".env"
    if not root_env.exists():
        return
    for line in root_env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_root_env()

# Add apps/api to sys.path so `import app.*` works when run as a script.
_API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API_ROOT))

from app.config import get_settings  # noqa: E402
from app.core.exceptions import (  # noqa: E402
    MurekaPermanentError,
    MurekaTransientError,
)
from app.services.mureka_client import MurekaClient  # noqa: E402


def _redact(s: str) -> str:
    if len(s) <= 8:
        return "***"
    return f"{s[:4]}…{s[-2:]}"


async def smoke_lyrics(client: MurekaClient) -> bool:
    print("─" * 60)
    print("[1/2] generate_lyrics — prompt: '도시의 새벽, 그리움' (ko)")
    t0 = time.perf_counter()
    try:
        result = await client.generate_lyrics(
            prompt="도시의 새벽, 그리움. 잔잔하고 감성적인 가사.",
            language="ko",
        )
    except MurekaPermanentError as e:
        print(f"  FAIL (permanent): code={e.code} status={e.status_code} msg={e}")
        return False
    except MurekaTransientError as e:
        print(f"  FAIL (transient/retries exhausted): code={e.code} msg={e}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL (unexpected): {type(e).__name__}: {e}")
        return False

    elapsed = time.perf_counter() - t0
    lyrics = result.lyrics or ""
    n_lines = lyrics.count("\n") + 1 if lyrics else 0
    print(f"  PASS  ({elapsed:.2f}s)  lyrics: {n_lines} lines, {len(lyrics)} chars")
    print(f"  preview: {lyrics[:160].replace(chr(10), ' ⏎ ')}{'…' if len(lyrics) > 160 else ''}")
    print(f"  raw keys: {sorted(result.raw.keys())[:8]}")
    return True


async def smoke_song(client: MurekaClient, *, length_s: int = 30, max_poll: int = 60) -> bool:
    print("─" * 60)
    print(f"[2/2] generate_song — Lo-fi piano, {length_s}s (instrumental)")
    t0 = time.perf_counter()
    try:
        task = await client.generate_instrumental(
            prompt="Lo-fi piano, mellow rainy mood, soft drums",
            model="auto",
            length_s=length_s,
        )
    except MurekaPermanentError as e:
        print(f"  FAIL submit (permanent): code={e.code} status={e.status_code} msg={e}")
        return False
    except MurekaTransientError as e:
        print(f"  FAIL submit (transient): code={e.code} msg={e}")
        return False

    print(f"  submitted task_id={_redact(task.task_id)} state={task.state}")
    if not task.task_id:
        print("  FAIL: empty task_id returned")
        return False

    last_state = "pending"
    for i in range(1, max_poll + 1):
        await asyncio.sleep(5)
        try:
            status = await client.query_task(task.task_id)
        except MurekaTransientError as e:
            print(f"  [{i:02d}] transient: {e}")
            continue
        except MurekaPermanentError as e:
            print(f"  FAIL poll (permanent): {e}")
            return False

        if status.state != last_state:
            print(f"  [{i:02d}] state: {last_state} → {status.state}  stage={status.stage}  progress={status.progress}")
            last_state = status.state

        if status.state == "completed":
            elapsed = time.perf_counter() - t0
            print(f"  PASS  ({elapsed:.1f}s, {i} polls)")
            for j, item in enumerate(status.items):
                print(f"    variant {chr(65 + j)}: url={item.url[:80]}{'…' if len(item.url) > 80 else ''}")
                print(f"      duration_ms={item.duration_ms} bpm={item.bpm} key={item.key}")
            print(f"    raw keys: {sorted(status.raw.keys())[:10]}")
            return True

        if status.state == "failed":
            print(f"  FAIL: state=failed code={status.error_code} msg={status.error_message}")
            print(f"    raw keys: {sorted(status.raw.keys())[:10]}")
            return False

    print(f"  FAIL: timeout after {max_poll} polls ({max_poll * 5}s)")
    return False


async def main(args: argparse.Namespace) -> int:
    settings = get_settings()

    if settings.mureka_api_key.get_secret_value() in ("", "mk_replace_me"):
        print("ERROR: MUREKA_API_KEY not set in .env")
        return 2

    print("=" * 60)
    print("Mureka Smoke Test")
    print("=" * 60)
    print(f"  base       : {settings.mureka_api_base}")
    print(f"  key        : {_redact(settings.mureka_api_key.get_secret_value())}")
    print(f"  timeout_s  : {settings.mureka_timeout_s}")
    print(f"  song step  : {'enabled' if args.song else 'skipped (use --song)'}")

    async with MurekaClient(settings=settings) as client:
        ok_lyrics = await smoke_lyrics(client)
        ok_song = True
        if args.song:
            ok_song = await smoke_song(client, length_s=args.length, max_poll=args.max_poll)

    print("=" * 60)
    if ok_lyrics and ok_song:
        print("RESULT: PASS")
        return 0
    print(f"RESULT: FAIL (lyrics={'ok' if ok_lyrics else 'fail'}, song={'ok' if ok_song else 'fail/skipped'})")
    return 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--song", action="store_true", help="also run song generation (consumes credits)")
    p.add_argument("--length", type=int, default=30, help="song length in seconds")
    p.add_argument("--max-poll", type=int, default=60, help="max poll attempts (×5s)")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
