"""
FaceCheck.id reverse face search provider.

Purpose-built for face search — ignores backgrounds, searches purely by
facial biometrics across social media, news, and public web profiles.
Works on ordinary people, not just celebrities.

API flow (2-step):
  1. POST /api/upload_pic  → returns id_search
  2. POST /api/search      → poll until output ready, returns items[]

TESTING_MODE=true  → free, searches ~100k faces (good for hackathon demo)
TESTING_MODE=false → full index (~billions of faces), costs 3 credits/search

Docs: https://facecheck.id/en/Face-Search/API
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from reverse_search.base import BaseProvider, SearchMatch, SearchResponse

load_dotenv()

FACECHECK_BASE = "https://facecheck.id"
POLL_INTERVAL = 2       # seconds between polls
MAX_POLLS = 60          # 2-minute timeout


class FaceCheckProvider(BaseProvider):
    name = "facecheck_id"

    def __init__(self, api_token: str | None = None, testing_mode: bool | None = None):
        self.api_token = api_token or os.getenv("FACECHECK_API_TOKEN", "")
        env_val = os.getenv("FACECHECK_TESTING_MODE", "true").lower()
        if testing_mode is not None:
            self.testing_mode = testing_mode
        else:
            self.testing_mode = env_val not in ("false", "0", "no")

    def _execute_search(self, image_path: str, **kwargs) -> SearchResponse:
        if not self.api_token:
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=(
                    "FACECHECK_API_TOKEN is not set. "
                    "Create a free account at https://facecheck.id "
                    "and add FACECHECK_API_TOKEN to your .env.\n"
                    "Set FACECHECK_TESTING_MODE=true for free testing (limited index)."
                ),
            )

        # Resolve image bytes
        if image_path.startswith(("http://", "https://")):
            try:
                r = requests.get(image_path, timeout=30)
                r.raise_for_status()
                image_bytes, filename = r.content, "query.jpg"
            except Exception as e:
                return SearchResponse(provider=self.name, query_image=image_path,
                                      error=f"Failed to download image: {e}")
        else:
            fp = Path(image_path).expanduser().resolve()
            if not fp.exists():
                return SearchResponse(provider=self.name, query_image=image_path,
                                      error=f"File not found: {fp}")
            image_bytes, filename = fp.read_bytes(), fp.name

        headers = {"accept": "application/json", "Authorization": self.api_token}

        # Step 1: upload
        try:
            up = requests.post(
                f"{FACECHECK_BASE}/api/upload_pic",
                headers=headers,
                files={"images": (filename, image_bytes), "id_search": (None, "")},
                timeout=60,
            )
            up.raise_for_status()
            up_data = up.json()
        except Exception as e:
            return SearchResponse(provider=self.name, query_image=image_path,
                                  error=f"Upload failed: {e}")

        if up_data.get("error"):
            return SearchResponse(provider=self.name, query_image=image_path,
                                  error=f"FaceCheck upload error: {up_data['error']} ({up_data.get('code')})")

        id_search = up_data.get("id_search")
        if not id_search:
            return SearchResponse(provider=self.name, query_image=image_path,
                                  error="FaceCheck did not return id_search after upload.")

        # Step 2: poll for results
        payload = {"id_search": id_search, "with_progress": True,
                   "status_only": False, "demo": self.testing_mode}

        for _ in range(MAX_POLLS):
            try:
                sr = requests.post(f"{FACECHECK_BASE}/api/search",
                                   headers=headers, json=payload, timeout=30)
                sr.raise_for_status()
                result = sr.json()
            except Exception as e:
                return SearchResponse(provider=self.name, query_image=image_path,
                                      error=f"Search poll failed: {e}")

            if result.get("error"):
                return SearchResponse(provider=self.name, query_image=image_path,
                                      error=f"FaceCheck error: {result['error']} ({result.get('code')})")

            if result.get("output"):
                items = result["output"].get("items", [])
                return self._parse_items(image_path, items)

            time.sleep(POLL_INTERVAL)

        return SearchResponse(provider=self.name, query_image=image_path,
                              error=f"FaceCheck timed out after {MAX_POLLS * POLL_INTERVAL}s.")

    def _parse_items(self, query_image: str, items: list) -> SearchResponse:
        matches: list[SearchMatch] = []
        for item in items:
            url = item.get("url", "")
            if not url:
                continue
            raw_score = item.get("score", 0)
            confidence = round(raw_score / 100.0, 4)
            b64 = item.get("base64", "")
            matches.append(SearchMatch(
                url=url,
                title=item.get("title", ""),
                thumbnail=f"data:image/jpeg;base64,{b64}" if b64 else "",
                match_type="visual",
                confidence=confidence,
                # FaceCheck already ran face matching — pre-mark high-confidence hits
                biometric_similarity=confidence,
                biometrically_verified=raw_score >= 70,
                verification_status="verified" if raw_score >= 70 else "lookalike",
            ))
        matches.sort(key=lambda m: m.confidence or 0, reverse=True)
        mode_note = " [TESTING MODE]" if self.testing_mode else ""
        return SearchResponse(
            provider=self.name + mode_note,
            query_image=query_image,
            matches=matches,
            search_url=f"{FACECHECK_BASE}/",
        )
