import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import script


def test_canonical_pi_name_removes_titles():
    assert script.canonical_pi_name("Mr Alex Sample") == "alex sample"
    assert script.canonical_pi_name("Prof Jamie Doe") == "jamie doe"
    assert script.canonical_pi_name("DOE, JANE") == "jane doe"


def test_main_generates_expected_outputs_and_deduplicates(tmp_path, monkeypatch):
    candidates_path = tmp_path / "candidates.xlsx"
    funded_path = tmp_path / "funded_pis.xlsx"
    output_dir = tmp_path / "reports"

    df_candidates = pd.DataFrame(
        [
            {
                "Name": "Alice",
                "Email": "alice@example.com",
                "Reseach Supervisor 1": "Mr Alex Sample",
                "Reseach Supervisor 2": "",
                "Reseach Supervisor 3": "",
                "Research Dept 1": "College of Computing & Data Science",
                "Research Dept 2": "",
                "Research Dept 3": "",
            },
            {
                "Name": "Bob",
                "Email": "bob@example.com",
                "Reseach Supervisor 1": "Some Other PI",
                "Reseach Supervisor 2": "Mr Alex Sample",
                "Reseach Supervisor 3": "",
                "Research Dept 1": "College of Computing & Data Science",
                "Research Dept 2": "College of Computing & Data Science",
                "Research Dept 3": "",
            },
            {
                "Name": "Cara",
                "Email": "cara@example.com",
                "Reseach Supervisor 1": "Mr Alex Sample",
                "Reseach Supervisor 2": "",
                "Reseach Supervisor 3": "",
                "Research Dept 1": "Nanyang Business School",
                "Research Dept 2": "",
                "Research Dept 3": "",
            },
            {
                "Name": "Dan",
                "Email": "dan@example.com",
                "Reseach Supervisor 1": "Mr Alex Sample",
                "Reseach Supervisor 2": "Mr Alex Sample",
                "Reseach Supervisor 3": "",
                "Research Dept 1": "College of Computing & Data Science",
                "Research Dept 2": "College of Computing & Data Science",
                "Research Dept 3": "",
            },
        ]
    )
    df_candidates.to_excel(candidates_path, index=False)

    df_funded = pd.DataFrame(
        [
            {
                "PI full name": "Alex Sample",
                "PI email": "alex.sample@example.edu",
            }
        ]
    )
    df_funded.to_excel(funded_path, index=False)

    monkeypatch.setattr(script, "CANDIDATES_FILE", str(candidates_path))
    monkeypatch.setattr(script, "FUNDED_PI_FILE", str(funded_path))
    monkeypatch.setattr(script, "OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(script, "COLLEGE_FILTER", "College of Computing & Data Science")

    script.main()

    all_matches = output_dir / "all_matched_students.xlsx"
    summary = output_dir / "summary.xlsx"
    per_pi = output_dir / "Alex_Sample_students.xlsx"

    assert all_matches.exists()
    assert summary.exists()
    assert per_pi.exists()

    df_matches = pd.read_excel(all_matches)

    # Cara is filtered out by COLLEGE_FILTER.
    # Dan selected same PI twice; only highest rank should remain.
    assert len(df_matches) == 3
    assert set(df_matches["Student Name"]) == {"Alice", "Bob", "Dan"}

    dan_rows = df_matches[df_matches["Student Name"] == "Dan"]
    assert len(dan_rows) == 1
    assert int(dan_rows.iloc[0]["Choice Rank"]) == 1
