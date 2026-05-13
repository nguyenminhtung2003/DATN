"""
Evaluate face verification threshold against a small demo dataset.

Dataset layout:

  dataset/
    positives/
    negatives/
    no_face/

The script uses FaceVerifier's existing image loading, preprocessing, and
fallback similarity scoring path so the result stays close to runtime behavior.
"""
import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from camera.face_verifier import FaceVerifier


EXPECTED_GROUPS = (
    ("positives", "positive"),
    ("negatives", "negative"),
    ("no_face", "no_face"),
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate DrowsiGuard face verification scores for a fixed demo dataset."
    )
    parser.add_argument("--rfid", required=True, help="Driver RFID UID to evaluate against")
    parser.add_argument("--dataset", required=True, help="Dataset directory with positives/negatives/no_face")
    parser.add_argument("--threshold", type=float, default=None, help="Threshold to evaluate")
    parser.add_argument("--json-out", required=True, help="Path to write the JSON report")
    parser.add_argument(
        "--face-data-dir",
        default=None,
        help="Optional override for config.FACE_DATA_DIR, useful for tests",
    )
    parser.add_argument(
        "--registry-path",
        default=None,
        help="Optional override for config.FACE_REGISTRY_PATH, useful for tests",
    )
    return parser.parse_args()


def apply_overrides(args):
    if args.face_data_dir:
        config.FACE_DATA_DIR = args.face_data_dir
    if args.registry_path:
        config.FACE_REGISTRY_PATH = args.registry_path
    if args.threshold is not None:
        config.FACE_VERIFY_THRESHOLD = float(args.threshold)


def iter_probe_files(dataset_dir: Path):
    for folder_name, expected in EXPECTED_GROUPS:
        folder = dataset_dir / folder_name
        if not folder.exists():
            continue
        for path in sorted(folder.iterdir()):
            if path.is_file():
                yield expected, path


def decision_from_score(score: float, threshold: float) -> str:
    if score >= threshold:
        return "MATCH"
    if score <= max(0.0, threshold - 0.18):
        return "MISMATCH"
    return "LOW_CONFIDENCE"


def row_passed(expected: str, decision: str) -> bool:
    if expected == "positive":
        return decision == "MATCH"
    return decision != "MATCH"


def prepare_references(verifier: FaceVerifier, rfid: str):
    valid_references = []
    for reference_path in verifier._reference_paths_for_uid(rfid):
        image = verifier._load_image(reference_path)
        prepared = verifier._prepare_image(image)
        if prepared is None:
            continue
        valid_references.append((reference_path, prepared))
    return valid_references


def score_probe(verifier: FaceVerifier, probe_path: Path, valid_references, threshold: float):
    probe_image = verifier._load_image(str(probe_path))
    probe_gray = verifier._prepare_image(probe_image)
    if probe_gray is None:
        return {
            "best_reference": None,
            "score": None,
            "decision": "NO_USABLE_IMAGE",
        }

    if not valid_references:
        return {
            "best_reference": None,
            "score": None,
            "decision": "NO_ENROLLMENT",
        }

    best_path = None
    best_score = -1.0
    for reference_path, reference_gray in valid_references:
        score = verifier._fallback_similarity(reference_gray, probe_gray)
        if score > best_score:
            best_score = score
            best_path = reference_path

    return {
        "best_reference": os.path.basename(best_path or ""),
        "score": round(float(best_score), 6),
        "decision": decision_from_score(best_score, threshold),
    }


def build_report(args):
    dataset_dir = Path(args.dataset)
    threshold = float(config.FACE_VERIFY_THRESHOLD)
    verifier = FaceVerifier()
    valid_references = prepare_references(verifier, args.rfid)

    rows = []
    for expected, probe_path in iter_probe_files(dataset_dir):
        scored = score_probe(verifier, probe_path, valid_references, threshold)
        row = {
            "file": probe_path.name,
            "path": str(probe_path.relative_to(dataset_dir)),
            "expected": expected,
            "best_reference": scored["best_reference"],
            "score": scored["score"],
            "threshold": threshold,
            "decision": scored["decision"],
        }
        row["passed"] = row_passed(expected, row["decision"])
        rows.append(row)

    passed = sum(1 for row in rows if row["passed"])
    failed = len(rows) - passed
    recommendation = "KEEP_THRESHOLD" if failed == 0 and rows else "REVIEW_THRESHOLD_OR_DATASET"

    return {
        "rfid": args.rfid,
        "dataset": str(dataset_dir),
        "threshold": threshold,
        "reference_count": len(valid_references),
        "rows": rows,
        "summary": {
            "total": len(rows),
            "passed": passed,
            "failed": failed,
            "recommendation": recommendation,
        },
    }


def print_report(report):
    print(
        "file,expected,best_reference,score,threshold,decision,passed"
    )
    for row in report["rows"]:
        score = "" if row["score"] is None else f"{row['score']:.3f}"
        print(
            f"{row['file']},{row['expected']},{row['best_reference'] or ''},"
            f"{score},{row['threshold']:.3f},{row['decision']},{row['passed']}"
        )
    summary = report["summary"]
    print(
        f"[FACE_EVAL] total={summary['total']} passed={summary['passed']} "
        f"failed={summary['failed']} recommendation={summary['recommendation']}"
    )


def main():
    args = parse_args()
    apply_overrides(args)
    report = build_report(args)

    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print_report(report)
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
