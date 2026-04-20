"""Tests for ReproducibilityChecklistExtractor."""
import pytest
from veritas.paper.reproducibility_checklist import ReproducibilityChecklistExtractor
from veritas.types import ReproducibilityChecklist

EXT = ReproducibilityChecklistExtractor()


def test_data_detected():
    text = "Data are available on Zenodo at zenodo.org/record/12345."
    cl   = EXT.extract(text)
    item = next(i for i in cl.items if i.code == "DATA")
    assert item.satisfied is True
    assert item.note != ""


def test_code_detected():
    text = "Analysis code is available at github.com/lab/project."
    cl   = EXT.extract(text)
    item = next(i for i in cl.items if i.code == "CODE")
    assert item.satisfied is True


def test_prereg_detected():
    text = "The trial was registered on ClinicalTrials.gov (NCT00000001)."
    cl   = EXT.extract(text)
    item = next(i for i in cl.items if i.code == "PREREG")
    assert item.satisfied is True


def test_stats_detected():
    text = "Statistical analysis used ANOVA with p < 0.05 as threshold."
    cl   = EXT.extract(text)
    item = next(i for i in cl.items if i.code == "STATS")
    assert item.satisfied is True


def test_power_detected():
    text = "Sample size was determined using power analysis (power = 0.80, effect size d = 0.5)."
    cl   = EXT.extract(text)
    item = next(i for i in cl.items if i.code == "POWER")
    assert item.satisfied is True


def test_blind_detected():
    text = "The study used a double-blind design with allocation concealment."
    cl   = EXT.extract(text)
    item = next(i for i in cl.items if i.code == "BLIND")
    assert item.satisfied is True


def test_excl_detected():
    text = "Inclusion criteria: age 18–65. Exclusion criteria: prior surgery."
    cl   = EXT.extract(text)
    item = next(i for i in cl.items if i.code == "EXCL")
    assert item.satisfied is True


def test_conf_detected():
    text = "The authors declare no conflicts of interest."
    cl   = EXT.extract(text)
    item = next(i for i in cl.items if i.code == "CONF")
    assert item.satisfied is True


def test_nothing_detected():
    text = "This paper has no methodology description whatsoever."
    cl   = EXT.extract(text)
    assert all(i.satisfied is False for i in cl.items)


def test_score_full():
    text = (
        "Data available on zenodo. Code at github.com/x. "
        "Pre-registered on ClinicalTrials.gov. "
        "Sample size calculation was done (power = 0.80). "
        "Statistical analysis: ANOVA, p < 0.05. "
        "Double-blind design was used. "
        "Inclusion criteria were clearly stated. "
        "No conflicts of interest declared."
    )
    cl = EXT.extract(text)
    assert cl.score == 1.0


def test_score_zero():
    cl = EXT.extract("Empty text with no signals.")
    assert cl.score == 0.0


def test_returns_checklist_instance():
    result = EXT.extract("Some text.")
    assert isinstance(result, ReproducibilityChecklist)


def test_summary_format():
    cl = EXT.extract("Data available on figshare.")
    assert "satisfied" in cl.summary
    assert "not satisfied" in cl.summary


def test_default_checklist_has_8_items():
    cl = ReproducibilityChecklist.default()
    assert len(cl.items) == 8
    codes = [i.code for i in cl.items]
    assert "DATA" in codes and "CONF" in codes
