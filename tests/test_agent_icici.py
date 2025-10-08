from __future__ import annotations

from pathlib import Path

import pandas as pd

from agent import run_agent


def test_agent_generates_icici_parser_and_matches_csv(tmp_path: Path) -> None:
    # Use repo data dir directly
    code = run_agent("icici")
    assert code == 0

    # Validate generated parser works and equals CSV
    from importlib import import_module

    parser = import_module("custom_parsers.icici_parser")
    pdf_path = Path("data/icici")
    # find any pdf
    pdf_files = list(pdf_path.glob("*.pdf"))
    if not pdf_files:
        pdf_files = list(pdf_path.glob("**/*.pdf"))
    assert pdf_files
    parsed = parser.parse(str(pdf_files[0]))
    expected = pd.read_csv(pdf_path / "result.csv")
    parsed = parsed[expected.columns.tolist()]
    assert parsed.equals(expected)

