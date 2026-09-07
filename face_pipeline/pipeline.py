"""
Face pipeline: detection, 5-point landmark alignment, 128D encoding, and portrait cropping.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

DEFAULT_YUNET_MODEL = Path(__file__).resolve().parent.parent / "face_detection_yunet_2023mar.onnx"
DEFAULT_SFACE_MODEL = Path(__file__).resolve().parent.parent / "face_recognition_sface_2021dec.onnx"

# SFace cosine similarity threshold for genuine match (same identity)
SFACE_COSINE_THRESHOLD = 0.363


@dataclass
class FaceProfile:
    """A single detected face with bounding box, landmarks, and 128D biometric vector."""

    index: int
    confidence: float
    box: Tuple[int, int, int, int]  # (x, y, w, h)
    landmarks: List[Tuple[int, int]]  # 5 landmarks: right_eye, left_eye, nose_tip, right_mouth, left_mouth
    embedding: List[float] = field(default_factory=list)  # 128D biometric embedding
    cropped_headshot_path: Optional[str] = None
    aligned_face_path: Optional[str] = None

    @property
    def embedding_np(self) -> np.ndarray:
        return np.array(self.embedding, dtype=np.float32)

    def to_dict(self) -> dict:
        d = asdict(self)
        # embedding can be 128 floats, abbreviate in basic dict representation if needed
        return d


@dataclass
class FaceDetectionResult:
    """Summary of face processing on an image."""

    image_path: str
    image_width: int
    image_height: int
    faces_detected: int
    primary_face: Optional[FaceProfile] = None
    all_faces: List[FaceProfile] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def has_face(self) -> bool:
        return self.faces_detected > 0 and self.primary_face is not None

    def to_dict(self) -> dict:
        return {
            "image_path": self.image_path,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "faces_detected": self.faces_detected,
            "has_face": self.has_face,
            "error": self.error,
            "primary_face": self.primary_face.to_dict() if self.primary_face else None,
            "faces_count": len(self.all_faces),
        }


class FacePipeline:
    """
    Complete facial recognition and pre-processing pipeline.
    """

    def __init__(
        self,
        yunet_model_path: Optional[str] = None,
        sface_model_path: Optional[str] = None,
        confidence_threshold: float = 0.85,
    ):
        self.yunet_path = Path(yunet_model_path or DEFAULT_YUNET_MODEL)
        self.sface_path = Path(sface_model_path or DEFAULT_SFACE_MODEL)
        self.conf_threshold = confidence_threshold

        if not self.yunet_path.exists():
            raise FileNotFoundError(f"YuNet model file not found: {self.yunet_path}")
        if not self.sface_path.exists():
            raise FileNotFoundError(f"SFace model file not found: {self.sface_path}")

        # Initialize SFace recognizer
        self.recognizer = cv2.FaceRecognizerSF_create(str(self.sface_path), "")

    def _create_detector(self, width: int, height: int):
        detector = cv2.FaceDetectorYN_create(
            str(self.yunet_path),
            "",
            (width, height),
            score_threshold=self.conf_threshold,
            nms_threshold=0.3,
            top_k=5000,
        )
        detector.setInputSize((width, height))
        return detector

    def process_image(
        self,
        image_path: str,
        output_dir: Optional[str] = None,
        face_index: Optional[int] = None,
        headshot_margin: float = 0.60,   # #3: raised from 0.35 — more context improves search engine matching
        min_headshot_px: int = 300,       # #3: minimum output dimension to avoid tiny crops on small faces
    ) -> FaceDetectionResult:
        """
        Process an image:
        1. Detect all faces and their 5 landmarks using YuNet
        2. Extract 128D biometric embedding for each face using SFace
        3. Create 5-point affine aligned face crop
        4. Create clean portrait headshot crop with margin for reverse search
        """
        path = Path(image_path).expanduser().resolve()
        if not path.exists():
            return FaceDetectionResult(
                image_path=str(image_path),
                image_width=0,
                image_height=0,
                faces_detected=0,
                error=f"File not found: {path}",
            )

        img = cv2.imread(str(path))
        if img is None:
            return FaceDetectionResult(
                image_path=str(image_path),
                image_width=0,
                image_height=0,
                faces_detected=0,
                error=f"Could not decode image: {path}",
            )

        h, w, _ = img.shape
        detector = self._create_detector(w, h)
        _, raw_faces = detector.detect(img)

        if raw_faces is None or len(raw_faces) == 0:
            return FaceDetectionResult(
                image_path=str(path),
                image_width=w,
                image_height=h,
                faces_detected=0,
                error="No faces detected in the image. Please provide a clear, front-facing photo.",
            )

        # Output folder for crops
        out_folder = Path(output_dir or path.parent / "crops")
        out_folder.mkdir(parents=True, exist_ok=True)

        faces_list: List[FaceProfile] = []

        for i, raw_face in enumerate(raw_faces):
            box = raw_face[:4].astype(int)  # (x, y, w, h)
            conf = float(raw_face[-1])
            raw_landmarks = raw_face[4:14].reshape((5, 2)).astype(int)
            landmarks = [(int(pt[0]), int(pt[1])) for pt in raw_landmarks]

            # 1. Align face using SFace 5-point affine transformation
            aligned_face = self.recognizer.alignCrop(img, raw_face)
            aligned_path = str(out_folder / f"{path.stem}_aligned_face_{i}.jpg")
            cv2.imwrite(aligned_path, aligned_face)

            # 2. Extract 128D biometric feature vector
            feature = self.recognizer.feature(aligned_face)
            embedding_128d = feature.flatten().tolist()

            # 3. Create high-resolution portrait crop (optimal for search engines)
            # #3: margin is 60% of face bbox in each direction for more hair/shoulder context
            mx = int(box[2] * headshot_margin)
            my = int(box[3] * headshot_margin)
            x1 = max(0, box[0] - mx)
            y1 = max(0, box[1] - my)
            x2 = min(w, box[0] + box[2] + mx)
            y2 = min(h, box[1] + box[3] + my)

            headshot_crop = img[y1:y2, x1:x2]

            # #3: enforce minimum dimension — upscale tiny crops so search engines
            # can extract meaningful features (small faces in group photos etc.)
            crop_h, crop_w = headshot_crop.shape[:2]
            if crop_h < min_headshot_px or crop_w < min_headshot_px:
                scale = min_headshot_px / min(crop_h, crop_w)
                new_w = int(crop_w * scale)
                new_h = int(crop_h * scale)
                headshot_crop = cv2.resize(
                    headshot_crop, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4
                )

            headshot_path = str(out_folder / f"{path.stem}_headshot_{i}.jpg")
            cv2.imwrite(headshot_path, headshot_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

            face_profile = FaceProfile(
                index=i,
                confidence=conf,
                box=(int(box[0]), int(box[1]), int(box[2]), int(box[3])),
                landmarks=landmarks,
                embedding=embedding_128d,
                cropped_headshot_path=headshot_path,
                aligned_face_path=aligned_path,
            )
            faces_list.append(face_profile)

        # Select primary face:
        # If face_index specified, use that; otherwise pick the largest face by bounding box area
        if face_index is not None and 0 <= face_index < len(faces_list):
            primary = faces_list[face_index]
        else:
            primary = max(faces_list, key=lambda f: f.box[2] * f.box[3])

        return FaceDetectionResult(
            image_path=str(path),
            image_width=w,
            image_height=h,
            faces_detected=len(faces_list),
            primary_face=primary,
            all_faces=faces_list,
        )

    def compute_similarity(
        self,
        embedding1: np.ndarray | List[float],
        embedding2: np.ndarray | List[float],
    ) -> Tuple[float, bool]:
        """
        Compute Cosine Similarity between two 128D biometric face vectors.

        Returns:
            (similarity_score, is_match)
            Threshold: >= 0.363 (SFace standard)
        """
        e1 = np.array(embedding1, dtype=np.float32).reshape(1, -1)
        e2 = np.array(embedding2, dtype=np.float32).reshape(1, -1)

        score = float(self.recognizer.match(e1, e2, cv2.FaceRecognizerSF_FR_COSINE))
        is_match = score >= SFACE_COSINE_THRESHOLD
        return score, is_match

    def extract_embedding_from_bytes(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """
        Detect face and extract 128D embedding directly from raw image bytes.
        Returns None if no face detected.
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        h, w, _ = img.shape
        detector = self._create_detector(w, h)
        _, faces = detector.detect(img)
        if faces is None or len(faces) == 0:
            return None

        # Pick largest face
        primary_face = max(faces, key=lambda f: f[2] * f[3])
        aligned = self.recognizer.alignCrop(img, primary_face)
        feature = self.recognizer.feature(aligned)
        return feature.flatten()

