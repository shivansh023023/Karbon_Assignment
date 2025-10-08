from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from agent_utils import AgentPlan, attempt_generate_and_validate


def run_agent(target: str, data_dir: Optional[str] = None, max_attempts: int = 3) -> int:
    base = Path(data_dir) if data_dir else Path("data") / target
    # Heuristic: look for any pdf and a csv named result.csv
    pdf_candidates = sorted(base.glob("*.pdf")) + sorted(base.glob("**/*.pdf"))
    if not pdf_candidates:
        raise FileNotFoundError(f"No PDF found under {base}")
    pdf_path = pdf_candidates[0]

    csv_path = base / "result.csv"
    if not csv_path.exists():
        # fallback: any csv in the dir
        csv_candidates = sorted(base.glob("*.csv")) + sorted(base.glob("**/*.csv"))
        if not csv_candidates:
            raise FileNotFoundError(f"No CSV found under {base}")
        csv_path = csv_candidates[0]

    output_parser = Path("custom_parsers") / f"{target}_parser.py"

    plan = AgentPlan(
        target_bank=target,
        pdf_path=pdf_path,
        expected_csv_path=csv_path,
        output_parser_path=output_parser,
    )

    for attempt in range(1, max_attempts + 1):
        success, debug = attempt_generate_and_validate(plan)
        if success:
            print(f"Attempt {attempt}: PASS")
            return 0
        print(f"Attempt {attempt}: FAIL -> {debug}")

    print("Max attempts reached without success.")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent-as-Coder: Bank PDF Parser Generator")
    parser.add_argument("--target", required=True, help="Target bank key, e.g., icici or sbi")
    parser.add_argument("--data-dir", default=None, help="Optional override for data directory")
    parser.add_argument("--max-attempts", type=int, default=3, help="Self-fix attempts")
    args = parser.parse_args()

    raise SystemExit(run_agent(args.target, args.data_dir, args.max_attempts))


if __name__ == "__main__":
    main()

