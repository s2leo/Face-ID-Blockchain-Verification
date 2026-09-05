"""
Google Cloud Vision WEB_DETECTION reverse image search provider.

Docs: https://cloud.google.com/vision/docs/detecting-web
Free: 1,000 units/month
Requires: GOOGLE_APPLICATION_CREDENTIALS env var pointing to a service account JSON.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from reverse_search.base import BaseProvider, SearchMatch, SearchResponse

load_dotenv()


class GoogleVisionProvider(BaseProvider):
    """Google Cloud Vision API — WEB_DETECTION feature."""

    name = "google_cloud_vision"

    def _execute_search(self, image_path: str, **kwargs) -> SearchResponse:
        # Check credentials
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not creds_path or not Path(creds_path).exists():
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=(
                    "GOOGLE_APPLICATION_CREDENTIALS is not set or the file does not exist. "
                    "Create a service account key at "
                    "https://console.cloud.google.com/iam-admin/serviceaccounts "
                    "and set the path in .env"
                ),
            )

        # Lazy import — only needed if this provider is actually used
        try:
            from google.cloud import vision
        except ImportError:
            return SearchResponse(
                provider=self.name,
                query_image=image_path,
                error=(
                    "google-cloud-vision is not installed. "
                    "Run: pip install google-cloud-vision"
                ),
            )

        client = vision.ImageAnnotatorClient()

        # Build image source
        if image_path.startswith(("http://", "https://")):
            image = vision.Image(source=vision.ImageSource(image_uri=image_path))
        else:
            file_path = Path(image_path).expanduser().resolve()
            if not file_path.exists():
                return SearchResponse(
                    provider=self.name,
                    query_image=image_path,
                    error=f"Image file not found: {file_path}",
                )
            with open(file_path, "rb") as f:
                image = vision.Image(content=f.read())

        # Execute WEB_DETECTION
        response = client.web_detection(image=image)
        web = response.web_detection

        matches: list[SearchMatch] = []

        # Pages with matching images
        for page in web.pages_with_matching_images:
            matches.append(
                SearchMatch(
                    url=page.url,
                    title=page.page_title or "",
                    match_type="exact",
                )
            )

        # Full matching images
        for img in web.full_matching_images:
            matches.append(
                SearchMatch(
                    url=img.url,
                    match_type="exact",
                )
            )

        # Partial matching images
        for img in web.partial_matching_images:
            matches.append(
                SearchMatch(
                    url=img.url,
                    match_type="partial",
                )
            )

        # Visually similar images
        for img in web.visually_similar_images:
            matches.append(
                SearchMatch(
                    url=img.url,
                    match_type="similar",
                )
            )

        # Filter empties and deduplicate
        matches = [m for m in matches if m.url]
        seen = set()
        unique = []
        for m in matches:
            if m.url not in seen:
                seen.add(m.url)
                unique.append(m)

        return SearchResponse(
            provider=self.name,
            query_image=image_path,
            matches=unique,
        )

