"""Static accessibility contract for the server-rendered verification UI."""

from html.parser import HTMLParser

from proof.api import _INDEX_HTML


class _UIContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.input_ids: set[str] = set()
        self.label_targets: set[str] = set()
        self.attributes_by_id: dict[str, dict[str, str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        element_id = attributes.get("id")
        if element_id:
            self.attributes_by_id[element_id] = attributes
        if tag in {"input", "select", "textarea"} and element_id:
            self.input_ids.add(element_id)
        if tag == "label" and attributes.get("for"):
            self.label_targets.add(attributes["for"])


def _parse_ui() -> _UIContractParser:
    parser = _UIContractParser()
    parser.feed(_INDEX_HTML)
    return parser


def test_verification_fields_have_programmatic_labels() -> None:
    """Every user-editable verification field has a matching label target."""
    parser = _parse_ui()
    expected_fields = {"tx_hash", "sender", "recipient", "asset_code", "amount_xlm", "reference", "network"}
    assert expected_fields.issubset(parser.input_ids)
    assert expected_fields.issubset(parser.label_targets)


def test_dynamic_states_are_announced() -> None:
    """Errors, example descriptions, and results are perceivable when updated."""
    parser = _parse_ui()
    assert parser.attributes_by_id["error"]["role"] == "alert"
    assert parser.attributes_by_id["error"]["aria-live"] == "assertive"
    assert parser.attributes_by_id["example_desc"]["role"] == "status"
    assert parser.attributes_by_id["result"]["aria-live"] == "polite"


def test_icon_and_control_buttons_have_accessible_names() -> None:
    """Controls whose visible content can change still have accessible names."""
    parser = _parse_ui()
    assert parser.attributes_by_id["lang_btn"]["aria-label"] == "Switch language"
    assert parser.attributes_by_id["theme_btn"]["aria-label"] == "Switch color theme"
