"""
Mock Mureka API server for load testing.

Simulates Mureka behavior without consuming credits:
- POST /song/generate → returns task_id
- GET /task/{id} → progresses from pending → completed

Runs on port 9999 (MOCK_MUREKA_BASE_URL=http://localhost:9999 in load tests).
"""

import asyncio
import json
import logging
import uuid
from typing import Dict

from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory task store
TASKS: Dict[str, dict] = {}


async def handle_generate(request: web.Request) -> web.Response:
    """
    POST /song/generate

    Simulates Mureka's generate endpoint.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
        "status": "pending",
        "progress": 0,
        "poll_count": 0,
    }

    logger.info(f"Generated task {task_id}")
    return web.json_response(
        {
            "task_id": task_id,
            "status": "pending",
        }
    )


async def handle_task_status(request: web.Request) -> web.Response:
    """
    GET /task/{task_id}

    Simulates Mureka's task status endpoint.
    Progresses from pending → processing → completed.
    """
    task_id = request.match_info.get("task_id")

    if task_id not in TASKS:
        return web.json_response(
            {"error": "Task not found"},
            status=404,
        )

    task = TASKS[task_id]
    task["poll_count"] += 1

    # Simulate progress: complete after ~3 polls (15 seconds at 5-sec intervals)
    if task["poll_count"] >= 3:
        task["status"] = "completed"
        task["progress"] = 100
        response = {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "songs": [
                {
                    "id": f"song-{task_id[:8]}-A",
                    "variant": "A",
                    "mp3_url": f"https://cdn.mock/mock-{task_id}-A.mp3",
                    "wav_url": f"https://cdn.mock/mock-{task_id}-A.wav",
                    "cover_url": f"https://cdn.mock/mock-{task_id}-A.jpg",
                    "duration_ms": 90000,
                    "bpm": 90,
                    "key": "Cm",
                    "genres": ["lo-fi"],
                    "moods": ["ambient"],
                },
                {
                    "id": f"song-{task_id[:8]}-B",
                    "variant": "B",
                    "mp3_url": f"https://cdn.mock/mock-{task_id}-B.mp3",
                    "wav_url": f"https://cdn.mock/mock-{task_id}-B.wav",
                    "cover_url": f"https://cdn.mock/mock-{task_id}-B.jpg",
                    "duration_ms": 92000,
                    "bpm": 92,
                    "key": "Am",
                    "genres": ["lo-fi"],
                    "moods": ["ambient"],
                },
            ],
        }
    else:
        # Still processing
        task["progress"] = min(10 + task["poll_count"] * 30, 95)
        response = {
            "task_id": task_id,
            "status": "processing",
            "progress": task["progress"],
            "estimated_seconds_remaining": max(0, 45 - task["poll_count"] * 15),
        }

    logger.info(
        f"Task {task_id} status: {response['status']} "
        f"(poll #{task['poll_count']}, progress={response['progress']}%)"
    )
    return web.json_response(response)


async def handle_health(request: web.Request) -> web.Response:
    """GET /health — health check endpoint."""
    return web.json_response({"status": "ok"})


async def start_server(port: int = 9999) -> web.AppRunner:
    """Start mock Mureka server."""
    app = web.Application()

    # Routes
    app.router.add_post("/song/generate", handle_generate)
    app.router.add_get("/task/{task_id}", handle_task_status)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"Mock Mureka server started on http://0.0.0.0:{port}")
    return runner


async def main():
    """Run mock server indefinitely."""
    runner = await start_server(9999)
    try:
        # Keep running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
