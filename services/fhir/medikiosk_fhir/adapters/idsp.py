"""IDSP/IHIP syndromic export renderer (plan G6).

Renders MediKiosk's day×syndrome aggregation into the weekly S-form shape
used by IDSP's IHIP. Zero-copy: no data leaves the hospital unless the
district officer explicitly requests the CSV.
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any


_SYNDROME_MAP = {
    "fever": "Fever with or without rash",
    "cough": "Acute Respiratory Infection / Influenza-like illness",
    "rash": "Fever with rash",
    "diarrhea": "Acute Diarrheal Disease",
}


class IdspExportRenderer:
    def render_csv(self, payload: dict[str, Any]) -> bytes:
        district = payload.get("district", "Unknown")
        week = payload.get("week", date.today().isocalendar().week)
        year = payload.get("year", date.today().year)
        syndromes = payload.get("syndromes", {})

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["District", "Week", "Year", "Syndrome", "Count"])
        for key, count in syndromes.items():
            if count <= 0:
                continue
            label = _SYNDROME_MAP.get(key, key)
            writer.writerow([district, week, year, label, count])
        return buf.getvalue().encode("utf-8")
