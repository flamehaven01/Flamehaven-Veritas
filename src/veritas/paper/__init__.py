"""Paper/source intelligence module for VERITAS — AI Critique Experimental Report Analysis Framework.

Provides:
  - MethodologyDetector            : classifies experiment methodology from text
  - HypothesisExtractor            : extracts hypothesis, null-H, falsification criteria
  - BibliographyAnalyzer           : reference section quality metrics
  - ReproducibilityChecklistExtractor : ARRIVE/CONSORT criterion detection
"""

from .bibliography_analyzer import BibliographyAnalyzer
from .hypothesis_extractor import HypothesisExtractor
from .methodology_detector import MethodologyDetector
from .reproducibility_checklist import ReproducibilityChecklistExtractor

__all__ = [
    "MethodologyDetector",
    "HypothesisExtractor",
    "BibliographyAnalyzer",
    "ReproducibilityChecklistExtractor",
]
