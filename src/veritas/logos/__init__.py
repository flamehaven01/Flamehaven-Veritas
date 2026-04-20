"""LOGOS IRF-6D reasoning module for VERITAS — AI Critique Experimental Report Analysis Framework.

Provides:
  - IRFAnalyzer   : text-pattern 6D scorer (offline, no deps)
  - LogosBridge   : tries real LOGOS pipeline, falls back to IRFAnalyzer
  - OmegaFusion   : fuses SCI-EXP traceability omega with LOGOS omega
"""
from .irf_analyzer import IRFAnalyzer
from .logos_bridge import LogosBridge
from .omega_fusion import OmegaFusion

__all__ = ["IRFAnalyzer", "LogosBridge", "OmegaFusion"]
