"""Design system (#46): the forecast stepper and futures mode build their interface from
the shared components in static/ui.js, so a button, chip or drawer looks and behaves the
same everywhere and picks up the theme from tokens. These checks stop one-off markup
creeping back."""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "cultural_signal_graph" / "static"
FUTURES = STATIC / "futures"
COMPONENTS = ["Button", "Chip", "Panel", "Tabs", "Roller", "NodeCard", "Drawer", "Toasts", "Toggle", "EmptyState"]


def _views() -> dict[str, str]:
    views = {p.name: p.read_text(encoding="utf-8") for p in FUTURES.glob("*.js")}
    views["app.js"] = (STATIC / "app.js").read_text(encoding="utf-8")  # the stepper
    return views


def test_ui_module_exports_the_components():
    ui = (STATIC / "ui.js").read_text(encoding="utf-8")
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
        "innerHTML": "render with htm, not strings",
    }
    for name, src in _views().items():
        for needle, fix in raw.items():
            assert needle not in src, f"{name}: {needle!r} ({fix})"


def test_every_component_is_used_somewhere():
    used = "\n".join(_views().values())
    for name in COMPONENTS:
        assert f"<${{{name}}}" in used, name
    assert "toast(" in used


def test_both_pages_load_the_components():
    for page in ["index.html", "futures.html"]:
        assert "/static/ui.css" in (STATIC / page).read_text(encoding="utf-8"), page
    assert 'from "./ui.js"' in (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "ui.css").read_text(encoding="utf-8")
    for cls in ["ui-chip", "ui-panel", "ui-tabs", "ui-roller", "ui-drawer", "ui-toast", "ui-toggle", "ui-empty"]:
        assert f".{cls}" in css, cls
