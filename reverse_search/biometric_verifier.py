"""
Biometric Verification Filter for Reverse Search Results.
=========================================================

Filters and verifies candidate links returned by Google Lens / reverse search
against the user's authentic 128D facial biometric embedding.
"""

from __future__ import annotations

import concurrent.futures
from typing import List, Optional
import requests

from face_pipeline import FacePipeline
from reverse_search.base import SearchMatch, SearchResponse


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
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        })

    def verify_single_match(
        self,
        match: SearchMatch,
        query_embedding: List[float],
        timeout: int = 5,
    ) -> SearchMatch:
        """
        Download the candidate's thumbnail/image, extract its 128D face vector,
        and calculate the biometric cosine similarity.
        """
        # If no thumbnail or image available, cannot biometrically verify
        img_url = match.thumbnail or match.url
        if not img_url or not img_url.startswith(("http://", "https://")):
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
        Ranks results with verified matches first.
        """
        if not response.matches or not query_embedding:
            return response

        verified_matches: List[SearchMatch] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_match = {
                executor.submit(
                    self.verify_single_match, match, query_embedding
                ): match
                for match in response.matches
            }

            for future in concurrent.futures.as_completed(future_to_match):
                match = future.result()
                verified_matches.append(match)
                if progress_callback:
                    progress_callback(match)

        # Sort: Verified matches first, then by similarity score descending
        def sort_key(m: SearchMatch):
            is_v = 1 if m.biometrically_verified else 0
            score = m.biometric_similarity or -1.0
            return (is_v, score)

        verified_matches.sort(key=sort_key, reverse=True)
        response.matches = verified_matches
        return response

