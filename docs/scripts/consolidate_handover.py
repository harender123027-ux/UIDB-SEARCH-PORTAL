"""Consolidate the 18 HANDOVER_GURUGRAM markdown files into 6 logical documents.

The original 18 source files live in `docs/HANDOVER_GURUGRAM/`.  After running
this script they are removed and replaced by the 6 consolidated files; the
Word-doc builder (`build_ubis_handover_docx.py`) is then re-run so the .docx
volume reflects the new layout.

Each source file's existing H1 title is demoted to H2 and prefixed with the
original chapter number to keep the table of contents readable.  All other
content is preserved verbatim.
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "HANDOVER_GURUGRAM"

GROUPS: list[tuple[str, str, list[str]]] = [
    (
        "README.md",
        "UBIS — Gurugram Police IT handover",
        ["00_README_START_HERE.md"],
    ),
    (
        "01_INSTALL.md",
        "Install & first boot",
        [
            "01_HARDWARE_SOFTWARE_PREREQS.md",
            "07_SECRETS_GENERATION_METHODOLOGY.md",
            "02_INSTALL_ONPREM_STEP_BY_STEP.md",
            "03_FIRST_BOOT_CHECKLIST.md",
        ],
    ),
    (
        "02_OPERATIONS.md",
        "Operations, backup & security",
        [
            "04_OPERATIONS_RUNBOOK.md",
            "05_BACKUP_AND_RESTORE.md",
            "06_SECURITY_HARDENING.md",
        ],
    ),
    (
        "03_USER_GUIDES.md",
        "User guides & bulk import SOP",
        [
            "09_USER_GUIDE_ADMIN.md",
            "10_USER_GUIDE_SUPERVISOR.md",
            "11_USER_GUIDE_INVESTIGATOR.md",
            "12_USER_GUIDE_FIELD_OFFICER.md",
            "08_BULK_IMPORT_SOP_FOR_DATA_ENTRY.md",
        ],
    ),
    (
        "04_TRAINING_AND_SUPPORT.md",
        "Training, troubleshooting & support",
        [
            "13_HALF_DAY_TRAINING_PLAN.md",
            "14_TROUBLESHOOTING_AND_FAQ.md",
            "15_SUPPORT_AND_ESCALATION.md",
        ],
    ),
    (
        "05_ACCEPTANCE.md",
        "Acceptance, sign-off & verification report",
        ["16_ACCEPTANCE_AND_SIGNOFF.md", "17_VERIFICATION_REPORT.md"],
    ),
]


def _demote_h1(text: str, source_name: str) -> str:
    """Drop a source file's first H1 (we render our own per-section H2)."""
    lines = text.splitlines()
    out: list[str] = []
    skipped = False
    for line in lines:
        if not skipped and line.startswith("# "):
            skipped = True
            continue
        out.append(line)
    if not skipped:
        # No H1 in the source — keep content as-is.
        return text
    return "\n".join(out).lstrip("\n")


def consolidate() -> None:
    written: list[Path] = []
    for out_name, doc_title, sources in GROUPS:
        parts = [f"# {doc_title}\n"]
        for src_name in sources:
            src_path = SRC / src_name
            if not src_path.exists():
                raise FileNotFoundError(src_path)
            chapter_num = src_name.split("_", 1)[0]
            original_h1 = next(
                (line[2:].strip() for line in src_path.read_text().splitlines() if line.startswith("# ")),
                src_name,
            )
            body = _demote_h1(src_path.read_text(), src_name)
            parts.append(f"\n---\n\n## Chapter {chapter_num} — {original_h1}\n\n{body.rstrip()}\n")
        out_path = SRC / out_name
        out_path.write_text("".join(parts))
        written.append(out_path)
        print(f"  wrote {out_path.relative_to(SRC.parent.parent)} ({len(parts) - 1} chapters)")

    # Remove the 18 source files (now redundant) — but keep any consolidated outputs
    # we just wrote, plus anything else we don't recognise.
    keep = {p.name for p in written}
    for p in sorted(SRC.iterdir()):
        if p.is_file() and p.suffix == ".md" and p.name not in keep:
            p.unlink()
            print(f"  removed legacy {p.relative_to(SRC.parent.parent)}")


if __name__ == "__main__":
    consolidate()
