from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


@dataclass
class AgentPlan:
    target_bank: str
    pdf_path: Path
    expected_csv_path: Path
    output_parser_path: Path


def read_expected_csv_schema(csv_path: Path) -> Tuple[List[str], pd.DataFrame]:
    df = pd.read_csv(csv_path)
    return list(df.columns), df


def guess_column_mapping(found_cols: List[str], expected_cols: List[str]) -> Dict[str, str]:
    """Map columns by fuzzy keyword matching.

    Returns mapping: found_col -> expected_col
    """
    key_map = {
        "date": ["date", "txn date", "transaction date"],
        "description": ["description", "narration", "details"],
        "debit": ["debit", "withdrawal", "dr", "debit amt"],
        "credit": ["credit", "deposit", "cr", "credit amt"],
        "balance": ["balance", "closing balance", "available balance"],
    }

    expected_lower = [c.lower() for c in expected_cols]
    mapping: Dict[str, str] = {}

    for f in found_cols:
        fl = f.lower().strip()
        matched_expected: str | None = None
        for expected in expected_cols:
            if expected.lower().strip() == fl:
                matched_expected = expected
                break

        if not matched_expected:
            # heuristic by keyword
            for expected_key, keywords in key_map.items():
                if any(k in fl for k in keywords):
                    # find expected column that contains the key
                    for e in expected_cols:
                        if expected_key in e.lower():
                            matched_expected = e
                            break
                if matched_expected:
                    break

        if matched_expected:
            mapping[f] = matched_expected

    return mapping


def generate_parser_code(bank: str, expected_cols: List[str]) -> str:
    """Generate a parser implementation using pdfplumber + pandas.

    The parser reads tables from the PDF, concatenates rows, renames columns
    using fuzzy mapping, coerces numeric columns, and returns only the expected
    columns in order.
    """
    expected_cols_literal = json.dumps(expected_cols)
    code = f'''from __future__ import annotations

from pathlib import Path
from typing import List

import pdfplumber
import pandas as pd
from dateutil import parser as date_parser


EXPECTED_COLUMNS: List[str] = {expected_cols_literal}


def _normalize_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s in ("", "-"):
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def _guess_mapping(cols):
    key_map = {{
        "date": ["date", "txn date", "transaction date"],
        "description": ["description", "narration", "details"],
        "debit": ["debit", "withdrawal", "dr", "debit amt"],
        "credit": ["credit", "deposit", "cr", "credit amt"],
        "balance": ["balance", "closing balance", "available balance"],
    }}
    mapping = {{}}
    for c in cols:
        cl = c.lower().strip()
        # exact
        for exp in EXPECTED_COLUMNS:
            if exp.lower().strip() == cl:
                mapping[c] = exp
                break
        if c in mapping:
            continue
        for key, kws in key_map.items():
            if any(k in cl for k in kws):
                for exp in EXPECTED_COLUMNS:
                    if key in exp.lower():
                        mapping[c] = exp
                        break
            if c in mapping:
                break
    return mapping


def parse(pdf_path: str) -> pd.DataFrame:
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                tbls = page.extract_tables()
            except Exception:
                tbls = []
            for t in tbls:
                if not t or len(t) < 2:
                    continue
                header = t[0]
                rows = t[1:]
                if not any(header):
                    # skip tables without headers
                    continue
                df = pd.DataFrame(rows, columns=[str(h).strip() if h is not None else "" for h in header])
                tables.append(df)

    if not tables:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)

    df = pd.concat(tables, ignore_index=True, sort=False)

    # drop empty columns
    df = df[[c for c in df.columns if c is not None and str(c).strip() != ""]]

    # rename to expected via heuristic
    mapping = _guess_mapping(list(df.columns))
    df = df.rename(columns=mapping)

    # keep only expected columns
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[EXPECTED_COLUMNS]

    # type normalization
    if any("date" in c.lower() for c in df.columns):
        date_col = [c for c in df.columns if "date" in c.lower()][0]
        def _norm_date(s):
            if s is None or str(s).strip() == "":
                return None
            try:
                d = date_parser.parse(str(s), dayfirst=True)
                return d.strftime("%d-%m-%Y")
            except Exception:
                return str(s)
        df[date_col] = df[date_col].map(_norm_date)

    # numeric columns
    for c in df.columns:
        cl = c.lower()
        if any(k in cl for k in ["debit", "credit", "balance", "amount", "amt"]):
            df[c] = df[c].map(_normalize_number)

    return df
'''
    return code


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def attempt_generate_and_validate(plan: AgentPlan) -> Tuple[bool, str]:
    from importlib import import_module
    import importlib.util
    import sys

    expected_cols, expected_df = read_expected_csv_schema(plan.expected_csv_path)
    code = generate_parser_code(plan.target_bank, expected_cols)
    write_file(plan.output_parser_path, code)

    # dynamic import of freshly written parser
    module_name = f"custom_parsers.{plan.target_bank}_parser"
    if module_name in sys.modules:
        del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, plan.output_parser_path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[assignment]

    parsed_df = module.parse(str(plan.pdf_path))  # type: ignore[attr-defined]

    # Ensure column order matches
    parsed_df = parsed_df[expected_cols]

    # Compare equality using pandas semantics
    equals = parsed_df.equals(expected_df)
    debug_info = {
        "expected_shape": tuple(expected_df.shape),
        "parsed_shape": tuple(parsed_df.shape),
        "first_mismatch": None,
    }
    if not equals:
        try:
            mismatch = (parsed_df != expected_df).stack()
            first = mismatch[mismatch].index[0]
            debug_info["first_mismatch"] = str(first)
        except Exception:
            pass
    return equals, json.dumps(debug_info)

