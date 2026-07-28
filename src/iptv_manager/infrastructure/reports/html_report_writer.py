"""HTML report writer.

Renders a ValidationReport into a single self-contained HTML file
(inline CSS, no external requests) using Jinja2, so the report can be
opened directly in a browser or attached to a GitHub Actions run
artifact without any additional assets.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from iptv_manager.application.dto.validation_report import ValidationReport

_TEMPLATE_DIR = Path(__file__).parent / "templates"


class HTMLReportWriter:
    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )

    def write(self, report: ValidationReport, path: Path) -> None:
        template = self._env.get_template("report.html.j2")
        html = template.render(report=report)
        path.write_text(html, encoding="utf-8")
