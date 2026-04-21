"""Base template interface for VERITAS report rendering."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import CritiqueReport


@dataclass
class TemplateSection:
    """One section of a rendered report."""

    title: str
    level: int  # heading depth (1=H1, 2=H2)
    body: str
    findings: list[str] = field(default_factory=list)


class BaseTemplate(ABC):
    """All output templates implement this interface."""

    TEMPLATE_ID: str = ""
    DISPLAY_NAME: str = ""
    SECTIONS: list[str] = []

    @abstractmethod
    def build(self, report: CritiqueReport) -> list[TemplateSection]:
        """Convert CritiqueReport into ordered TemplateSection list."""
        pass

    @classmethod
    def all_templates(cls) -> dict[str, BaseTemplate]:
        from .bmj import BMJTemplate
        from .ku import KUTemplate

        return {
            "bmj": BMJTemplate(),
            "ku": KUTemplate(),
        }
