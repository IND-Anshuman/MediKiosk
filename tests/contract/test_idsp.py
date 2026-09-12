"""T3.14: IDSP syndromic export renderer (plan G6)."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any

import pytest


def _renderer():
    from medikiosk_fhir.adapters.idsp import IdspExportRenderer
    return IdspExportRenderer()


def test_renderer_returns_csv_bytes():
    r = _renderer()
    data = {
        "district": "Bangalore Urban",
        "week": date(2026, 9, 7).isocalendar().week,
        "year": 2026,
        "syndromes": {
            "fever": 12,
            "cough": 8,
            "rash": 1,
            "diarrhea": 3,
        },
    }
    out = r.render_csv(data)
    assert out.startswith(b"District,Week,Year")
    assert b"Bangalore Urban" in out
    assert b"Fever with or without rash,12" in out


def test_renderer_omits_zero_syndromes():
    r = _renderer()
    data = {
        "district": "Patna",
        "week": 36,
        "year": 2026,
        "syndromes": {"fever": 0, "cough": 5},
    }
    out = r.render_csv(data)
    assert b"fever" not in out  # zero count omitted
    assert b"Acute Respiratory" in out
    assert b",5" in out
