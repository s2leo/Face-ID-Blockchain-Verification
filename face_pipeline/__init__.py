"""
face_pipeline — Biometric Facial Detection, Alignment, and 128D Encoding
========================================================================

Powered by deep neural network ONNX models:
  - Detection: YuNet (lightweight, ultra-fast, 5-landmark face detector)
  - Biometric Recognition: SFace (128-dimensional face embedding, cosine similarity)

Complies with Hackathon Requirement #1:
  "Detect and encode a face from an input photo (any library or API allowed)"
"""

from face_pipeline.pipeline import (
    FacePipeline,
    FaceDetectionResult,
    FaceProfile,
)

__all__ = [
    "FacePipeline",
    "FaceDetectionResult",
    "FaceProfile",
]

