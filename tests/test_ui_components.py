"""Design system (#46): futures mode builds its interface from the shared components in
static/futures/ui.js, so a button, chip or drawer looks and behaves the same everywhere
and picks up the theme from tokens. These checks stop one-off markup creeping back."""

import re
from pathlib import Path

FUTURES = Path(__file__).resolve().parents[1] / "src" / "cultural_signal_graph" / "static" / "futures"
COMPONENTS = ["Button", "Chip", "Panel", "Tabs", "Roller", "NodeCard", "Drawer", "Toasts", "Toggle", "EmptyState"]


def _views() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in FUTURES.glob("*.js") if p.name != "ui.js"}


def test_ui_module_exports_the_components():
    ui = (FUTURES / "ui.js").read_text(encoding="utf-8")
    for name in COMPONENTS:
        assert re.search(rf"export function {name}\(", ui), name
    assert "export function toast(" in ui


def test_views_use_components_not_raw_markup():
    raw = {
        "<button": "use Button, Chip (toggle), Tabs",
        "<aside": "use Drawer",
        'class="card': "use Panel",
        "class=${`card": "use Panel",
        "a.btn": "use Button href=",
    }
    for name, src in _views().items():
        for needle, fix in raw.items():
            assert needle not in src, f"{name}: {needle!r} ({fix})"


def test_every_component_is_used_somewhere():
    used = "\n".join(_views().values())
    for name in COMPONENTS:
        assert f"<${{{name}}}" in used, name
    assert "toast(" in used


def test_component_styles_are_loaded():
    page = (FUTURES.parent / "futures.html").read_text(encoding="utf-8")
    assert '/static/futures/ui.css' in page
    css = (FUTURES / "ui.css").read_text(encoding="utf-8")
    for cls in ["ui-chip", "ui-panel", "ui-tabs", "ui-roller", "ui-drawer", "ui-toast", "ui-toggle", "ui-empty"]:
        assert f".{cls}" in css, cls
