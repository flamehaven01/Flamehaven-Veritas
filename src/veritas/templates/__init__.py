"""Templates sub-package."""

from .base import BaseTemplate, TemplateSection
from .bmj import BMJTemplate
from .ku import KUTemplate

all_templates = BaseTemplate.all_templates
__all__ = ["BaseTemplate", "TemplateSection", "all_templates", "BMJTemplate", "KUTemplate"]
