# ai-agent-challenge
Coding agent challenge which write custom parsers for Bank statement PDF.

## Run (5 steps)
1. Create venv and install deps:
   - Windows PowerShell:
     - `py -m venv .venv`
     - `.venv\\Scripts\\Activate.ps1`
     - `pip install -r requirements.txt`
2. Ensure sample data present under `data/icici/` including a PDF and `result.csv`.
3. Run the agent for ICICI:
   - `python agent.py --target icici`
4. Run tests:
   - `pytest -q`
5. Generate a new bank parser (example SBI) with your own folder `data/sbi/`:
   - `python agent.py --target sbi`

## Agent diagram (high-level)
Plan → Generate Parser Code → Import & Run on PDF → Compare with CSV → Self-fix (≤3 attempts).

## Notes
- The generated parser uses `pdfplumber` tables, normalizes dates to `dd-mm-YYYY`, and coerces numeric columns by heuristics.
- Contract: parser exposes `parse(pdf_path) -> pd.DataFrame` with columns identical and ordered like the expected CSV.