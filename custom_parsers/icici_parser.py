from __future__ import annotations

from pathlib import Path
from typing import List

import pdfplumber
import pandas as pd
from dateutil import parser as date_parser


EXPECTED_COLUMNS: List[str] = ["Date", "Description", "Debit Amt", "Credit Amt", "Balance"]


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
    key_map = {
        "date": ["date", "txn date", "transaction date"],
        "description": ["description", "narration", "details"],
        "debit": ["debit", "withdrawal", "dr", "debit amt"],
        "credit": ["credit", "deposit", "cr", "credit amt"],
        "balance": ["balance", "closing balance", "available balance"],
    }
    mapping = {}
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
