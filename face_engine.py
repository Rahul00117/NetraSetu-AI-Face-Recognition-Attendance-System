"""
Central face engine for detection, alignment, embedding and recognition.
Uses SCRFD for detection, norm_crop for alignment, ArcFace for embeddings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch
from torchvision import transforms

from face_alignment.alignment import norm_crop
from face_detection.scrfd.detector import SCRFD
from face_recognition.arcface.model import iresnet_inference

import database as db

logger = logging.getLogger(__name__)

_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

_detector: Optional[SCRFD] = None
_recognizer: Optional[torch.nn.Module] = None
_preprocess: Optional[transforms.Compose] = None

# Default detection size for SCRFD (avoids "input_size is not None or self.input_size" assert)
GROUP_PHOTO_DETECT_INPUT_SIZE = (640, 640)
GROUP_PHOTO_DETECT_THRESH = 0.25
GROUP_PHOTO_MAX_SIDE = 1280
FACE_CROP_PADDING_RATIO = 0.15


@dataclass
class RecognitionResult:
    bbox: Tuple[int, int, int, int]
    similarity: Optional[float]
    student_id: Optional[str]
    name: Optional[str]


@dataclass
class RecognitionReport:
    num_detected: int = 0
    num_recognized: int = 0
    num_unknown: int = 0
    confidence_scores: List[float] = field(default_factory=list)

    def to_message(self) -> str:
        return (
            f"Detected Faces: {self.num_detected} | "
            f"Recognized Students: {self.num_recognized} | "
            f"Unknown Faces: {self.num_unknown}"
        )


def _ensure_models_loaded():
    """Load SCRFD detector and ArcFace recognizer once. Set default input_size for SCRFD."""
    global _detector, _recognizer, _preprocess

    if _detector is None:
        _detector = SCRFD(
            model_file="face_detection/scrfd/weights/scrfd_2.5g_bnkps.onnx"
        )
        # Ensure SCRFD has input_size (avoids assert in detect() when ONNX has dynamic shape)
        _detector.prepare(
            ctx_id=0 if torch.cuda.is_available() else -1,
            input_size=GROUP_PHOTO_DETECT_INPUT_SIZE,
        )

    if _recognizer is None:

        _recognizer = iresnet_inference(
            model_name="r100",
            path="face_recognition/arcface/weights/arcface_r100.pth",
            device=_device,
        )

    if _preprocess is None:

        _preprocess = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Resize((112, 112)),
                transforms.Normalize(
                    mean=[0.5, 0.5, 0.5],
                    std=[0.5, 0.5, 0.5],
                ),
            ]
        )


def detect_faces(
    image_bgr: np.ndarray,
    det_thresh: float = 0.5,
    input_size: Optional[Tuple[int, int]] = None,
    max_num: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Detect faces with SCRFD. Always passes input_size to satisfy detector assert."""
    if image_bgr is None or not isinstance(image_bgr, np.ndarray) or image_bgr.size == 0:
        return (
            np.empty((0, 5), dtype=np.int32),
            np.empty((0, 5, 2), dtype=np.int32),
        )

    _ensure_models_loaded()
    input_size = input_size or GROUP_PHOTO_DETECT_INPUT_SIZE

    try:
        bboxes, landmarks = _detector.detect(
            image=image_bgr,
            thresh=det_thresh,
            input_size=input_size,
            max_num=max_num,
        )
    except Exception as e:
        logger.exception("SCRFD detect failed: %s", e)
        return (
            np.empty((0, 5), dtype=np.int32),
            np.empty((0, 5, 2), dtype=np.int32),
        )

    if bboxes is None or len(bboxes) == 0:
        return (
            np.empty((0, 5), dtype=np.int32),
            np.empty((0, 5, 2), dtype=np.int32),
        )
    return bboxes, landmarks


def _align_face_with_padding(image_bgr, bbox, landmarks):

    x1, y1, x2, y2 = map(int, bbox[:4])

    h_img, w_img = image_bgr.shape[:2]

    pad_w = int((x2 - x1) * FACE_CROP_PADDING_RATIO)
    pad_h = int((y2 - y1) * FACE_CROP_PADDING_RATIO)

    x1 = max(0, x1 - pad_w)
    y1 = max(0, y1 - pad_h)
    x2 = min(w_img, x2 + pad_w)
    y2 = min(h_img, y2 + pad_h)

    crop = image_bgr[y1:y2, x1:x2]

    if crop.size == 0:
        return norm_crop(image_bgr, landmarks)

    lmk_crop = np.array(landmarks) - np.array([x1, y1])

    return norm_crop(crop, lmk_crop)


@torch.no_grad()
def _get_feature_from_aligned(face_bgr: np.ndarray) -> np.ndarray:
    """Extract L2-normalized ArcFace embedding from aligned face crop."""
    if face_bgr is None or face_bgr.size == 0:
        return np.zeros(512, dtype=np.float32)  # fallback; caller may check

    _ensure_models_loaded()
    rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
    tensor = _preprocess(rgb).unsqueeze(0).to(_device)
    emb = _recognizer(tensor).cpu().numpy()
    emb = np.asarray(emb, dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(emb)
    if norm > 1e-8:
        emb = emb / norm
    return emb


def extract_main_face_embedding_from_path(image_path):

    img = cv2.imread(image_path)

    if img is None:
        return None

    bboxes, landmarks = detect_faces(
        img,
        input_size=GROUP_PHOTO_DETECT_INPUT_SIZE,
    )

    if len(bboxes) == 0:
        return None

    areas = (bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])

    idx = int(np.argmax(areas))

    aligned = norm_crop(img, landmarks[idx])

    return _get_feature_from_aligned(aligned)


def register_student_face(student_id, image_path):

    emb = extract_main_face_embedding_from_path(image_path)

    if emb is None:
        return False

    db.save_face_embedding(student_id, emb)

    return True


def _load_known_embeddings():

    student_ids, embeddings = db.get_all_face_embeddings()

    if embeddings.size == 0 or len(student_ids) == 0:
        return [], np.empty((0, 0), dtype=np.float32)

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)

    embeddings = embeddings / np.maximum(norms, 1e-8)

    return student_ids, embeddings


def _cosine_similarity(
    query_emb: np.ndarray, known_embs: np.ndarray
) -> Tuple[np.ndarray, int]:
    """Cosine similarity between query and known embeddings. Safe for empty known_embs."""
    if (
        known_embs is None
        or known_embs.size == 0
        or query_emb is None
        or query_emb.size == 0
    ):
        return np.array([0.0], dtype=np.float32), 0

    query_emb = np.asarray(query_emb, dtype=np.float32).reshape(-1)
    query_norm = np.linalg.norm(query_emb)
    query_emb = query_emb / np.maximum(query_norm, 1e-8)

    if known_embs.ndim == 1:
        known_embs = known_embs.reshape(1, -1)
    sims = np.dot(known_embs, query_emb.T).ravel()
    best_idx = int(np.argmax(sims))
    return sims, best_idx


def recognize_faces_in_image(
    image_bgr: np.ndarray, threshold: float = 0.4
) -> List[RecognitionResult]:
    """Detect faces, align, embed, compare with DB. Returns list of RecognitionResult."""
    if image_bgr is None or image_bgr.size == 0:
        return []

    bboxes, landmarks = detect_faces(
        image_bgr,
        det_thresh=GROUP_PHOTO_DETECT_THRESH,
        input_size=GROUP_PHOTO_DETECT_INPUT_SIZE,
    )

    results: List[RecognitionResult] = []
    if len(bboxes) == 0:
        return results

    student_ids, known_embs = _load_known_embeddings()
    n_known = len(student_ids)
    if n_known == 0 or known_embs.size == 0:
        # No registered students: mark all as unknown
        for box in bboxes:
            x1, y1, x2, y2, _ = box
            results.append(
                RecognitionResult(
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    similarity=0.0,
                    student_id=None,
                    name=None,
                )
            )
        return results

    for box, lmk in zip(bboxes, landmarks):
        try:
            aligned = norm_crop(image_bgr, lmk)
            query_emb = _get_feature_from_aligned(aligned)
        except Exception as e:
            logger.warning("Align/embed failed for one face: %s", e)
            x1, y1, x2, y2, _ = box
            results.append(
                RecognitionResult(
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    similarity=0.0,
                    student_id=None,
                    name=None,
                )
            )
            continue

        sims, best_idx = _cosine_similarity(query_emb, known_embs)
        sim = float(sims[best_idx]) if sims.size > 0 else 0.0

        if sim >= threshold and best_idx < n_known:
            sid = student_ids[best_idx]
            student_row = db.get_student(sid)
            name = student_row["name"] if student_row else sid
        else:
            sid = None
            name = None

        x1, y1, x2, y2, _ = box
        results.append(
            RecognitionResult(
                bbox=(int(x1), int(y1), int(x2), int(y2)),
                similarity=sim,
                student_id=sid,
                name=name,
            )
        )

    return results


def recognize_faces_in_group_photo(
    image_bgr: np.ndarray, threshold: float = 0.4
) -> Tuple[List[RecognitionResult], RecognitionReport]:
    """
    Full pipeline for group photo: preprocess, detect all faces, align, embed,
    compare with DB. Returns (results, report) with summary counts.
    """
    report = RecognitionReport()

    if image_bgr is None or not isinstance(image_bgr, np.ndarray) or image_bgr.size == 0:
        logger.warning("recognize_faces_in_group_photo: invalid image")
        return [], report

    try:
        # Optional resize for very large images to avoid OOM and speed up
        h, w = image_bgr.shape[:2]
        if max(h, w) > GROUP_PHOTO_MAX_SIDE:
            scale = GROUP_PHOTO_MAX_SIDE / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            image_bgr = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    except Exception as e:
        logger.warning("Resize failed: %s", e)

    # Detect all faces with SCRFD
    bboxes, landmarks = detect_faces(
        image_bgr,
        det_thresh=GROUP_PHOTO_DETECT_THRESH,
        input_size=GROUP_PHOTO_DETECT_INPUT_SIZE,
        max_num=0,
    )

    report.num_detected = len(bboxes)
    if report.num_detected == 0:
        return [], report

    student_ids, known_embs = _load_known_embeddings()
    n_known = len(student_ids)
    results: List[RecognitionResult] = []
    confidence_scores: List[float] = []

    for box, lmk in zip(bboxes, landmarks):
        try:
            aligned = norm_crop(image_bgr, lmk)
            query_emb = _get_feature_from_aligned(aligned)
        except Exception as e:
            logger.warning("Align/embed failed for one face: %s", e)
            x1, y1, x2, y2, _ = box
            results.append(
                RecognitionResult(
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    similarity=0.0,
                    student_id=None,
                    name=None,
                )
            )
            report.num_unknown += 1
            continue

        sims, best_idx = _cosine_similarity(query_emb, known_embs)
        sim = float(sims[best_idx]) if sims.size > 0 else 0.0
        confidence_scores.append(sim)

        if sim >= threshold and n_known > 0 and best_idx < n_known:
            sid = student_ids[best_idx]
            student_row = db.get_student(sid)
            name = student_row["name"] if student_row else sid
            results.append(
                RecognitionResult(
                    bbox=(int(box[0]), int(box[1]), int(box[2]), int(box[3])),
                    similarity=sim,
                    student_id=sid,
                    name=name,
                )
            )
            report.num_recognized += 1
        else:
            results.append(
                RecognitionResult(
                    bbox=(int(box[0]), int(box[1]), int(box[2]), int(box[3])),
                    similarity=sim,
                    student_id=None,
                    name=None,
                )
            )
            report.num_unknown += 1

    report.confidence_scores = confidence_scores
    return results, report


def draw_recognition_results(
    image_bgr: np.ndarray, results: List[RecognitionResult]
) -> np.ndarray:
    """Draw bounding boxes and labels on image. Safe for empty results or None similarity."""
    if image_bgr is None or image_bgr.size == 0:
        return image_bgr
    annotated = image_bgr.copy()
    if not results:
        return annotated

    for res in results:
        x1, y1, x2, y2 = res.bbox
        label = "Unknown"
        sim = res.similarity
        if res.name and sim is not None:
            label = f"{res.name} ({sim:.2f})"
        elif sim is not None:
            label = f"? ({sim:.2f})"

        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            annotated,
            label,
            (x1, max(y1 - 10, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
    return annotated