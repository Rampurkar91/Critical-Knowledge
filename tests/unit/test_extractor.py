"""Unit tests for deterministic, evidence-preserving extraction."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_engine.extractor import parse_source
from backend.app.config import SAMPLE_DATA_DIR

pytestmark = pytest.mark.unit


def _sample_files() -> list[Path]:
    manifest = json.loads((SAMPLE_DATA_DIR / "manifest.json").read_text())
    return [SAMPLE_DATA_DIR / item["file"] for item in manifest["sources"]]


def test_all_sample_sources_have_exact_evidence_offsets():
    files = _sample_files()
    assert len(files) == 10
    total = 0
    for path in files:
        content = path.read_text(encoding="utf-8")
        parsed = parse_source(content, fallback_title=path.stem)
        assert parsed.meta.source_ref.startswith("SRC-")
        assert parsed.records
        for record in parsed.records:
            assert content[record.evidence_start:record.evidence_end] == record.evidence_quote
            assert record.sensitivity >= 0
            assert record.node_key
        total += len(parsed.records)
    assert total > 70


def test_gold_extraction_labels_are_reproduced():
    gold = json.loads((SAMPLE_DATA_DIR / "gold_labels.json").read_text())
    actual: dict[str, set[str]] = {}
    dependency_pairs: set[str] = set()
    for path in _sample_files():
        parsed = parse_source(path.read_text(encoding="utf-8"))
        for record in parsed.records:
            actual.setdefault(record.claim_type, set()).add(record.external_ref)
            if record.claim_type == "dependency":
                dependency_pairs.add(f"{record.metadata['parent_ref']}|{record.value}")
    for claim_type, expected in gold["extraction"].items():
        assert set(expected) <= actual.get(claim_type, set()), f"missing {claim_type}: {set(expected) - actual.get(claim_type, set())}"
    assert set(gold["dependency_pairs"]) == dependency_pairs


def test_deliberately_unsupported_claim_has_no_evidence_link_marker():
    content = (SAMPLE_DATA_DIR / "05-risk-register.md").read_text(encoding="utf-8")
    parsed = parse_source(content)
    unsupported = [r for r in parsed.records if r.external_ref == "F-301"]
    assert len(unsupported) == 1
    assert unsupported[0].unsupported is True
    assert unsupported[0].claim_type == "state_change"


def test_restricted_source_is_classified_and_contains_canary():
    content = (SAMPLE_DATA_DIR / "09-restricted-security-review.md").read_text(encoding="utf-8")
    parsed = parse_source(content)
    assert parsed.meta.sensitivity == 3
    assert all(record.sensitivity == 3 for record in parsed.records)
    assert "RESTRICTED-CANARY-9F3A" in content


def test_superseding_records_and_conflict_keys_are_explicit():
    records = []
    for path in _sample_files():
        records.extend(parse_source(path.read_text()).records)
    supersedes = {r.supersedes_ref for r in records if r.supersedes_ref}
    assert {"DEC-001", "RISK-002"} <= supersedes
    keys = {r.normalized_key for r in records}
    assert {"task.KB-104.owner", "api.rate_limit"} <= keys
