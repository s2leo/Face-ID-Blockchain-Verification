"""
FaceCheck.id reverse face search provider.

Why FaceCheck.id for non-famous people?
  - Purpose-built for face search, not general image matching.
  - Crawls social media profiles, dating sites, mugshot databases, and news sites
    specifically looking for faces — not background/object similarities.
  - Works on ordinary people who have any public profile photo online.
  - Returns a 0–100 confidence score per match.
  - TESTING_MODE=True: searches only ~100k faces, fast, free (no credits deducted).
    Flip to False for full production search (~billions of indexed faces).

API flow (2-step):
  1. POST /api/upload_pic  → returns id_search
  2. POST /api/search      → poll until output is ready, returns items[]

Docs: https://facecheck.id/en/Face-Search/API
Pricing: 3 credits/search, ~$0.10/credit (paid via crypto)
Free testing: TESTING_MODE=True (limited index, no billing)
"""

from __future__ import annotations

import os
import time
import base64
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

from reverse_search.base import BaseProvider, SearchMatch, SearchResponse

load_dotenv()

FACECHECK_BASE = "https://facecheck.id"
POLL_INTERVAL_SECONDS = 2
MAX_POLL_ATTEMPTS = 60  # 2-minute timeout


class FaceCheckProvider(BaseProvider):
    """
    FaceCheck.id face-specific reverse image search.

    Best provider for finding non-famous individuals — it ignores backgrounds
    and scene context and searches purely by facial biometrics across social,
    news, and public web profiles.
    """

    name = "facecheck_id"

    def __init__(
        self,
        api_token: str | None = None,
        testing_mode: bool | None = None,
    ):
        self.api_token = api_token or os.getenv("FACECHECK_API_TOKEN", "")
        # Default to testing mode unless explicitly overridden or env var says otherwise
        env_testing = os.getenv("FACECHECK_TESTING_MODE", "true").lower()
        if testing_mode is not None:
            self.testing_mode = testing_mode
        else:
            self.testing_mode = env_testing not in ("false", "0", "no")

    def _execute_search(self, image_path: str, **kwargs) -> SearchResponse:
        if not self.api_token:
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=(
                    "FACECHECK_API_TOKEN is not set. "
                    "Create a free account at https://facecheck.id "
                    "and add your token to .env as FACECHECK_API_TOKEN.\n"
                    "Note: TESTING_MODE=True uses a small index and is free — "
                    "set FACECHECK_TESTING_MODE=false in .env for production results."
                ),
            )

        # Resolve local file
        if image_path.startswith(("http://", "https://")):
            # Download the image first — FaceCheck only accepts file uploads
            try:
                resp = requests.get(image_path, timeout=30)
                resp.raise_for_status()
                image_bytes = resp.content
                filename = "query.jpg"
            except Exception as e:
                return SearchResponse(
                    provider=self.name,
                    query_image=image_path,
                    error=f"Failed to download image from URL: {e}",
                )
        else:
            file_path = Path(image_path).expanduser().resolve()
            if not file_path.exists():
                return SearchResponse(
                    provider=self.name,
                    query_image=image_path,
                    error=f"Image file not found: {file_path}",
                )
            image_bytes = file_path.read_bytes()
            filename = file_path.name

        headers = {
            "accept": "application/json",
            "Authorization": self.api_token,
        }

        # Step 1: Upload the face image
        try:
            upload_resp = requests.post(
                f"{FACECHECK_BASE}/api/upload_pic",
                headers=headers,
                files={"images": (filename, image_bytes), "id_search": (None, "")},
                timeout=60,
            )
            upload_resp.raise_for_status()
            upload_data = upload_resp.json()
        except Exception as e:
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=f"Upload failed: {e}",
            )

        if upload_data.get("error"):
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=f"FaceCheck upload error: {upload_data['error']} (code: {upload_data.get('code')})",
            )

        id_search = upload_data.get("id_search")
        if not id_search:
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error="FaceCheck did not return id_search after upload.",
            )

        # Step 2: Poll for results
        search_payload = {
            "id_search": id_search,
            "with_progress": True,
            "status_only": False,
            "demo": self.testing_mode,
        }

        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                search_resp = requests.post(
                    f"{FACECHECK_BASE}/api/search",
                    headers=headers,
                    json=search_payload,
                    timeout=30,
                )
                search_resp.raise_for_status()
                result = search_resp.json()
            except Exception as e:
                return SearchResponse(
                    provider=self.name,
                    query_image=image_path,
                    error=f"Search poll failed (attempt {attempt + 1}): {e}",
                )

            if result.get("error"):
                return SearchResponse(
                    provider=self.name,
                    query_image=image_path,
                    error=f"FaceCheck search error: {result['error']} (code: {result.get('code')})",
                )

            if result.get("output"):
                items = result["output"].get("items", [])
                return self._parse_items(image_path, items, testing_mode=self.testing_mode)

            # Still processing — progress is in result["progress"] (0–100)
            progress = result.get("progress", 0)
            msg = result.get("message", "searching...")
            # Brief wait before next poll
            time.sleep(POLL_INTERVAL_SECONDS)

        return SearchResponse(
            provider=self.name,
            query_image=image_path,
            error=f"FaceCheck search timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s.",
        )

    def _parse_items(
        self,
        query_image: str,
        items: list,
        testing_mode: bool = True,
    ) -> SearchResponse:
        matches: list[SearchMatch] = []

        for item in items:
            url = item.get("url", "")
            if not url:
                continue

            # FaceCheck score is 0–100; normalize to 0.0–1.0 for consistency
            raw_score = item.get("score", 0)
            confidence = round(raw_score / 100.0, 4)

            # Thumbnail is base64-encoded JPEG
            b64_thumb = item.get("base64", "")
            # We store it as a data-URI so BiometricVerifier can skip thumbnail
            # download (FaceCheck already ran face search — no need to re-verify)
            thumbnail = f"data:image/jpeg;base64,{b64_thumb}" if b64_thumb else ""

            matches.append(
                SearchMatch(
                    url=url,
                    title=item.get("title", ""),
                    thumbnail=thumbnail,
                    match_type="visual",
                    confidence=confidence,
                    # FaceCheck already performed face matching — pre-mark as
                    # biometrically verified if score ≥ 70 (high confidence)
                    biometric_similarity=confidence,
                    biometrically_verified=raw_score >= 70,
                    verification_status="verified" if raw_score >= 70 else "lookalike",
                )
            )

        # Sort by confidence descending
        matches.sort(key=lambda m: m.confidence or 0, reverse=True)

        note = " [TESTING MODE — limited index]" if testing_mode else ""
        return SearchResponse(
            provider=self.name + note,
            query_image=query_image,
            matches=matches,
            search_url=f"{FACECHECK_BASE}/",
        )
