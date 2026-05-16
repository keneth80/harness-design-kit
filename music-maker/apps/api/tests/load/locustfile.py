"""
Load testing for Music Maker API.

Simulates realistic user behavior:
- Login
- Generate songs (70% weight)
- Generate lyrics (10% weight)
- Browse library (20% weight)

Run locally:
  locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 5m

Or with UI:
  locust -f locustfile.py

Environment variables:
  - MUREKA_API_BASE: Mock Mureka server URL (default: http://localhost:9999)
  - API_BASE: Backend URL (default: http://localhost:8000/api/v1)
  - MOCK_MUREKA: Set to '1' to use mock server (default: 1)
"""

import json
import os
import time
import uuid
from typing import Optional

from locust import HttpUser, between, task


class MusicMakerUser(HttpUser):
    """Simulated Music Maker user."""

    wait_time = between(2, 5)  # Wait 2-5 seconds between requests

    def on_start(self) -> None:
        """Initialize user session (login)."""
        self.api_base = os.getenv("API_BASE", "http://localhost:8000/api/v1")
        self.user_id: Optional[str] = None
        self.auth_token: Optional[str] = None
        self._login()

    def _login(self) -> None:
        """Simulate login."""
        # In real scenario, this would use OAuth or email verification
        # For load test, we mock a JWT token
        email = f"loadtest-{uuid.uuid4().hex[:8]}@example.com"

        # POST /auth/login (or equivalent)
        # For simplicity, we assume login always succeeds and returns a token
        self.auth_token = f"Bearer test-token-{uuid.uuid4().hex[:16]}"
        self.user_id = str(uuid.uuid4())

        headers = {"Authorization": self.auth_token}
        self.client.headers.update(headers)

    @task(7)  # 70% of requests
    def generate_song(self) -> None:
        """
        Generate a song.
        Flow: POST /songs → 202 + get generation_id
               GET /songs/{id} → poll until completed
        """
        prompt = f"test song {uuid.uuid4().hex[:8]}"

        # 1) POST /songs
        payload = {
            "mode": "song",
            "prompt": {"text": prompt, "length_s": 60},
            "lyrics_mode": "none",
            "model": "mureka-7",
        }

        with self.client.post(
            f"{self.api_base}/songs",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 202:
                body = response.json()
                generation_id = body.get("generation_id")

                if generation_id:
                    # 2) Poll status
                    self._poll_generation(generation_id)
                    response.success()
                else:
                    response.failure(f"No generation_id in response: {body}")
            else:
                response.failure(f"Expected 202, got {response.status_code}")

    @task(1)  # 10% of requests
    def generate_lyrics(self) -> None:
        """
        Generate lyrics.
        POST /lyrics/generate → 200 + lyrics text
        """
        prompt = f"lyrics test {uuid.uuid4().hex[:8]}"

        payload = {"prompt": prompt}

        with self.client.post(
            f"{self.api_base}/lyrics/generate",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(2)  # 20% of requests
    def browse_library(self) -> None:
        """
        Browse library with optional pagination.
        GET /library?limit=10&cursor=...
        """
        cursor = None
        page = 0

        while page < 3:  # Fetch up to 3 pages
            params = {"limit": 10}
            if cursor:
                params["cursor"] = cursor

            with self.client.get(
                f"{self.api_base}/library",
                params=params,
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    body = response.json()
                    cursor = body.get("next_cursor")
                    response.success()

                    if not cursor:
                        break  # No more pages
                else:
                    response.failure(f"Expected 200, got {response.status_code}")
                    break

            page += 1

    @task(1)  # Occasionally fetch credits
    def check_credits(self) -> None:
        """
        GET /account/credits
        """
        with self.client.get(
            f"{self.api_base}/account/credits",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    def _poll_generation(self, generation_id: str, max_polls: int = 20) -> None:
        """Poll generation status until completed or timeout."""
        poll_count = 0
        while poll_count < max_polls:
            with self.client.get(
                f"{self.api_base}/songs/{generation_id}",
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    body = response.json()
                    status = body.get("status")

                    if status == "completed":
                        response.success()
                        return
                    elif status == "processing":
                        # Still processing, continue polling
                        response.success()
                        time.sleep(2)  # Wait before next poll
                    else:
                        response.failure(f"Unexpected status: {status}")
                        return
                else:
                    response.failure(f"Expected 200, got {response.status_code}")
                    return

            poll_count += 1

        # Timeout
        self.client.get(f"{self.api_base}/songs/{generation_id}").failure(
            "Poll timeout"
        )


class WebsiteUser(HttpUser):
    """Alternative user profile (for future use)."""

    tasks = [MusicMakerUser]
    wait_time = between(1, 3)
