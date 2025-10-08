from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol
import pandas as pd


class BankStatementParser(Protocol):
    """Contract for all bank statement parsers.

    Implementations must expose a `parse(pdf_path)` function that returns a
    pandas DataFrame with columns exactly matching the expected CSV schema.
    """

    def parse(self, pdf_path: str) -> pd.DataFrame:  # pragma: no cover - interface
        ...


class BankStatementParserABC(ABC):
    @abstractmethod
    def parse(self, pdf_path: str) -> pd.DataFrame:  # pragma: no cover - interface
        raise NotImplementedError

