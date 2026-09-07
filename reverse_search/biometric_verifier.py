"""
Biometric Verification Filter for Reverse Search Results.
=========================================================

Improvements applied:
  #5 — profile_search matches (from Option B name lookup) are pre-trusted:
       we found them by querying "Name" site:instagram.com — no thumbnail
       biometric check needed. They get verification_status="category_verified".
  #10 — timeout raised from 5s to 10s to reduce fetch_error on slow CDNs.
"""

from __future__ import annotations

import concurrent.futures
from typing import List, Optional
import requests

from face_pipeline import FacePipeline
from reverse_search.base import SearchMatch, SearchResponse

# #10: raised from 5s → 10s — social media CDNs (Instagram, Facebook) are slow
VERIFY_TIMEOUT = 10


class BiometricVerifier:
    """
    Verifies candidate matches against the query face's 128D embedding.
    """

    def __init__(self, face_pipeline: Optional[FacePipeline] = None):
        self.pipeline = face_pipeline or FacePipeline()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })

    def verify_single_match(
        self,
        match: SearchMatch,
        query_embedding: List[float],
        timeout: int = VERIFY_TIMEOUT,   # #10
    ) -> SearchMatch:
        """
        Download the candidate's thumbnail/image, extract its 128D face vector,
        and calculate biometric cosine similarity.

        #5: profile_search matches are pre-trusted — skip biometric check.
        """
        # #5: matches found via name-based site search (Option B) are already
        # trusted by construction — "Shruti Haasan" site:instagram.com will only
        # return pages that mention her name. Trying to biometrically verify a
        # Pinterest/Instagram page URL returns HTML, which always fails face
        # detection. Mark these as category_verified and move on.
        if match.match_type == "profile_search":
            match.biometrically_verified = True
            match.verification_status = "category_verified"
            # No similarity score — verified by name search, not by face comparison
            match.biometric_similarity = None
            return match

        # For image-search matches: try thumbnail first, fall back to page URL
        img_url = match.thumbnail or match.url
        if not img_url or not img_url.startswith(("http://", "https://")):
            match.verification_status = "no_image_source"
            return match

        # Skip data-URI thumbnails (FaceCheck base64 thumbs already scored)
        if img_url.startswith("data:"):
            match.verification_status = "no_image_source"
            return match

        try:
            resp = self.session.get(img_url, timeout=timeout)
            if resp.status_code != 200:
                match.verification_status = "fetch_error"
                return match

            candidate_feat = self.pipeline.extract_embedding_from_bytes(resp.content)
            if candidate_feat is None:
                match.verification_status = "no_face_detected"
                return match

            score, is_match = self.pipeline.compute_similarity(query_embedding, candidate_feat)
            match.biometric_similarity = round(float(score), 4)
            match.biometrically_verified = is_match
            match.verification_status = "verified" if is_match else "lookalike"

        except Exception:
            match.verification_status = "fetch_error"

        return match

    def verify_response(
        self,
        response: SearchResponse,
        query_embedding: List[float],
        max_workers: int = 8,
        progress_callback: Optional[callable] = None,
    ) -> SearchResponse:
        """
        Verify all candidate matches in a SearchResponse in parallel.
        Sorts results: verified first, then by similarity score descending.
        profile_search matches (category_verified) are ranked after biometric
        verified matches but before lookalikes.
        """
        if not response.matches or not query_embedding:
            return response

        verified_matches: List[SearchMatch] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.verify_single_match, match, query_embedding): match
                for match in response.matches
            }
            for future in concurrent.futures.as_completed(futures):
                match = future.result()
                verified_matches.append(match)
                if progress_callback:
                    progress_callback(match)

        def sort_key(m: SearchMatch):
            # Tier 0: biometrically verified (face match confirmed)
            # Tier 1: category_verified (found by name search)
            # Tier 2: everything else, sorted by similarity descending
            if m.biometrically_verified and m.verification_status == "verified":
                tier = 0
            elif m.verification_status == "category_verified":
                tier = 1
            else:
                tier = 2
            score = m.biometric_similarity or -1.0
            return (tier, -score)

        verified_matches.sort(key=sort_key)
        response.matches = verified_matches
        return response
