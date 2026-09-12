from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = ROOT / "core" / "templates" / "core" / "base.html"
SEMANTIC_CSS = ROOT / "core" / "static" / "core" / "css" / "semantic-state.css"


def test_semantic_state_styles_load_after_base_and_glaze_styles() -> None:
    source = BASE_TEMPLATE.read_text(encoding="utf-8")
    app_index = source.index("core/css/app.css")
    glaze_index = source.index("core/css/glaze-ui.css")
    semantic_index = source.index("core/css/semantic-state.css")

    assert app_index < glaze_index < semantic_index


def test_configuration_state_is_not_styled_as_verified_health() -> None:
    source = SEMANTIC_CSS.read_text(encoding="utf-8")

    neutral_rule_end = source.index("/* Positive operational states")
    neutral_rules = source[:neutral_rule_end]
    assert ".status-configured" in neutral_rules
    assert "color: var(--text-secondary);" in neutral_rules

    positive_start = source.index("/* Positive operational states")
    attention_start = source.index("/* Attention states")
    positive_rules = source[positive_start:attention_start]
    assert ".status-healthy" in positive_rules
    assert ".status-available" in positive_rules
    assert ".status-ready" in positive_rules
    assert ".status-active" in positive_rules
    assert ".status-configured" not in positive_rules
    assert "color: var(--good);" in positive_rules


def test_attention_unavailable_and_unknown_states_are_semantically_distinct() -> None:
    source = SEMANTIC_CSS.read_text(encoding="utf-8")

    assert ".status-unknown" in source
    assert ".status-inactive" in source
    assert ".status-degraded" in source
    assert ".status-restricted" in source
    assert ".status-unavailable" in source
    assert "color: var(--warning);" in source
    assert "color: var(--danger);" in source

    # Connectivity must not be promoted into service-availability styling.
    assert ".status-connected" not in source
    assert ".status-disconnected" not in source


def test_semantic_state_badges_preserve_forced_color_readability() -> None:
    source = SEMANTIC_CSS.read_text(encoding="utf-8")

    assert "@media (forced-colors: active)" in source
    assert "border-color: CanvasText;" in source
