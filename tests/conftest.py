"""Pytest fixtures shared across tests."""
from __future__ import annotations

import sys
import pytest

# Ensure src is importable
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parents[1] / "src"))

SAMPLE_REPORT = """
Experiment: Effect of temperature on enzyme activity.
Hypothesis: Higher temperature increases reaction rate up to 37C.
Materials: 10 mL enzyme solution (0.5 mg/mL), buffer pH 7.0, spectrophotometer.
Method: Samples heated to 25, 30, 37, 42, 50C. Absorbance measured at t=0, 5, 10 min.
Results: Activity peaked at 37C (OD=1.24). At 50C activity dropped to OD=0.31.
Data file: raw_absorbance_table_v1.csv. Figure 1 shows rate vs temperature.
Conclusion: Enzyme is thermolabile above 42C, consistent with known melting profiles.
Reference: Smith et al. 2020, Journal of Biochemistry 45(2):112-118.
"""

MINIMAL_REPORT = "Some experiment was done. Results were obtained."


@pytest.fixture
def sample_text():
    return SAMPLE_REPORT.strip()


@pytest.fixture
def minimal_text():
    return MINIMAL_REPORT.strip()


@pytest.fixture
def engine():
    from veritas.engine import SciExpCritiqueEngine
    return SciExpCritiqueEngine()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from veritas.api.app import app
    return TestClient(app)
