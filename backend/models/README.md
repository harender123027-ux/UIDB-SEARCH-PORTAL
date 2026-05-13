# AI model weights (not in Git)

This directory holds **InsightFace** (`buffalo_l`) detection weights and the **AdaFace** IR-101 checkpoint used for face embeddings.

- **Git clone:** this folder is empty until you add weights (see below).
- **Handover ZIP:** may include `backend/models/` so police servers can install **offline** without downloading ~600 MB from the public internet.

## How to populate

1. **From handover package:** copy the entire `backend/models/` tree from the official UBIS handover archive.
2. **From a running install:** copy from another machine that already downloaded models.
3. **Automatic download (InsightFace):** on first API use that needs face detection, InsightFace can download `buffalo_l` under this `root` if the server has outbound internet. See `app/services/face_embedding.py` and `docs/HANDOVER_GURUGRAM/01_INSTALL.md`.
4. **AdaFace:** set `ADAFACE_MODEL_PATH` (default `models/adaface_ir101.ckpt` relative to `backend/`). Obtain the checkpoint per deployment docs if not bundled.

Do not commit large binaries to Git; keep them in handover media or internal artifact storage.
