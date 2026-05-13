"""
Local face detection and embedding. Uses InsightFace for detection/alignment and AdaFace for embeddings.
"""
import hashlib
import os

import numpy as np

try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    class nn:
        class Module:
            pass
    torch = None
from pathlib import Path
from typing import Any

from app.config import (
    ADAFACE_MODEL_PATH,
    EMBEDDING_DIM,
    FACE_DETECTION_THRESHOLD,
    FACE_EMBEDDINGS_PER_IMAGE_MAX,
)

# Try insightface for detection/alignment
try:
    import cv2
    from insightface.app import FaceAnalysis
    _INSIGHTFACE_AVAILABLE = True
except Exception:
    _INSIGHTFACE_AVAILABLE = False
    cv2 = None
    FaceAnalysis = None

_app: object | None = None
_adaface_model: object | None = None # Using object because nn.Module might not exist


# --- AdaFace Model Architecture (Simplified IR-101) ---
def conv3x3(in_planes, out_planes, stride=1):
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride, padding=1, bias=False)

class BasicBlock(nn.Module):
    expansion = 1
    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super().__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.PReLU(planes)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        return out

class IBlock(nn.Module):
    expansion = 1
    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super().__init__()
        self.bn1 = nn.BatchNorm2d(inplanes)
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.prelu = nn.PReLU(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x
        out = self.bn1(x)
        out = self.conv1(out)
        out = self.bn2(out)
        out = self.prelu(out)
        out = self.conv2(out)
        out = self.bn3(out)
        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        return out

class AdaFace(nn.Module):
    def __init__(self, block, layers, embedding_size=512):
        super().__init__()
        self.inplanes = 64
        self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.prelu = nn.PReLU(64)
        self.layer1 = self._make_layer(block, 64, layers[0], stride=2)
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)
        self.bn2 = nn.BatchNorm2d(512)
        self.dropout = nn.Dropout(p=0)
        self.fc = nn.Linear(512 * 7 * 7, embedding_size)
        self.features = nn.BatchNorm1d(embedding_size, affine=False)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )
        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.prelu(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.bn2(x)
        x = torch.flatten(x, 1)
        x = self.dropout(x)
        x = self.fc(x)
        return x

def _get_adaface():
    global _adaface_model
    if not _TORCH_AVAILABLE:
        return None
    if _adaface_model is None:
        model = AdaFace(IBlock, [3, 4, 23, 3]) # IR-101
        if os.path.exists(ADAFACE_MODEL_PATH):
            try:
                state_dict = torch.load(ADAFACE_MODEL_PATH, map_location='cpu')
                if 'state_dict' in state_dict:
                    state_dict = state_dict['state_dict']
                model.load_state_dict({k.replace('model.', ''): v for k, v in state_dict.items()}, strict=False)
            except Exception:
                pass
        model.eval()
        _adaface_model = model
    return _adaface_model


def _get_app():
    global _app
    if _app is None and _INSIGHTFACE_AVAILABLE:
        try:
            # Detection and landmarks only
            _app = FaceAnalysis(name="buffalo_l", root=str(Path(__file__).resolve().parents[2]), allowed_modules=["detection"])
            _app.prepare(ctx_id=-1, det_thresh=FACE_DETECTION_THRESHOLD, det_size=(640, 640))
        except Exception:
            pass
    return _app


def _align_face(img, landmarks):
    """
    Standard similarity transform to align face to 112x112 using 5 landmarks.
    Reference points from standard ArcFace/AdaFace alignment.
    """
    src = np.array([
        [30.2946, 51.6963], [70.5318, 51.5014], [51.3531, 71.7366],
        [34.2525, 92.3655], [68.4552, 92.2041]], dtype=np.float32)
    dst = landmarks.astype(np.float32)
    tform = cv2.estimateAffinePartial2D(dst, src)[0]
    aligned = cv2.warpAffine(img, tform, (112, 112))
    return aligned


def _preprocess(aligned_img):
    """Preprocess 112x112 UI image for AdaFace (BGR -> RGB, normalize)"""
    img = cv2.cvtColor(aligned_img, cv2.COLOR_BGR2RGB)
    img = ((img / 255.0) - 0.5) / 0.5
    img = np.transpose(img, (2, 0, 1))
    if not _TORCH_AVAILABLE:
        return img # Return numpy array if torch is missing
    return torch.from_numpy(img).unsqueeze(0).float()


def _placeholder_embedding(image_bytes: bytes) -> tuple[np.ndarray, float]:
    """Deterministic 512-d vector from image hash for fallback."""
    h = hashlib.sha256(image_bytes).digest()
    np.random.seed(int.from_bytes(h[:4], "big"))
    emb = np.random.randn(EMBEDDING_DIM).astype(np.float32) * 0.1
    return emb / (np.linalg.norm(emb) + 1e-6), 10.0 # moderate quality


def extract_face_embeddings(
    image_path: Path,
    image_type: str = "face_frontal",
    enforce_detection: bool = True
) -> list[dict[str, Any]]:
    """
    Extract face embeddings using AdaFace.
    Returns list of dicts with: embedding, confidence, quality.
    """
    image_bytes = image_path.read_bytes()
    app = _get_app()
    model = _get_adaface()

    if app is None or cv2 is None or model is None:
        if os.getenv("ENVIRONMENT") == "production":
            print("WARNING: AI Models not found at /app/models! Ensure Azure Storage Container is mounted correctly.")
        emb, qual = _placeholder_embedding(image_bytes)
        return [{"embedding": emb, "confidence": 0.5, "quality": qual}]

    img = cv2.imread(str(image_path))
    if img is None:
        if not enforce_detection:
            emb, qual = _placeholder_embedding(image_bytes)
            return [{"embedding": emb, "confidence": 0.0, "quality": qual}]
        return []

    faces = app.get(img)
    faces = sorted(faces, key=lambda f: -float(getattr(f, "det_score", 0) or 0))
    results = []

    for face in faces[:FACE_EMBEDDINGS_PER_IMAGE_MAX]:
        if float(getattr(face, "det_score", 0) or 0) < FACE_DETECTION_THRESHOLD:
            continue
        if face.kps is not None:
            aligned = _align_face(img, face.kps)
            input_tensor = _preprocess(aligned)
            if _TORCH_AVAILABLE and model:
                with torch.no_grad():
                    out = model(input_tensor)
                    magnitude = torch.norm(out, dim=1).item()
                    embedding = (out / (magnitude + 1e-6)).cpu().numpy()[0]
            else:
                embedding, magnitude = _placeholder_embedding(image_bytes)

            results.append({
                "embedding": embedding,
                "confidence": float(face.det_score),
                "quality": magnitude
            })

    if not results and not enforce_detection:
        # Fallback: take center crop or full image
        h, w = img.shape[:2]
        size = min(h, w)
        cy, cx = h // 2, w // 2
        r = max(1, size // 2)
        crop = img[max(0, cy-r):min(h, cy+r), max(0, cx-r):min(w, cx+r)]
        if crop.size > 0:
            resized = cv2.resize(crop, (112, 112))
            input_tensor = _preprocess(resized)
            if _TORCH_AVAILABLE and model:
                with torch.no_grad():
                    out = model(input_tensor)
                    magnitude = torch.norm(out, dim=1).item()
                    embedding = (out / (magnitude + 1e-6)).cpu().numpy()[0]
            else:
                embedding, magnitude = _placeholder_embedding(image_bytes)
            results.append({
                "embedding": embedding,
                "confidence": 0.0, # Not detected
                "quality": magnitude
            })

    return results


def extract_embeddings_from_bytes(
    image_bytes: bytes,
    image_type: str = "face_frontal",
    enforce_detection: bool = True
) -> list[dict[str, Any]]:
    """Extract embeddings from in-memory image bytes."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(image_bytes)
        path = Path(f.name)
    try:
        return extract_face_embeddings(path, image_type, enforce_detection)
    finally:
        if path.exists():
            path.unlink()
