# GCF PI Matcher

This project matches student applications to funded PIs and generates one output file per PI.

## What It Does

1. Reads student applications from `tests/demo_candidates.xlsx` (or `.csv` with same basename as fallback).
2. Reads funded PI list from `tests/demo_funded_pis.xlsx` (or `.csv` with same basename as fallback).
3. Matches PI names robustly (handles title prefixes like `Prof`, `Dr`, `Mr`, and common formatting variations).
4. Keeps only the highest-priority choice if the same student selects the same PI multiple times.
5. Generates:
   - `reports/all_matched_students.xlsx`
   - `reports/summary.xlsx`
   - `reports/<PI>_students.xlsx` (one file per PI)

## Input Files

Default file names (configured in `script.py`, anonymized demo inputs):

- `tests/demo_candidates.xlsx`
- `tests/demo_funded_pis.xlsx`

Required columns:

- Candidate file:
  - `Name`
  - `Email`
  - PI choice columns like `Reseach Supervisor 1/2/3` (or `Research Supervisor 1/2/3`)
- Funded PI file:
  - `PI full name`
  - `PI email` (optional but recommended)

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python script.py
```

## Run with Docker

Build image:

```bash
docker build -t hongrui0/gcf:latest .
```

Run (mount current directory so input/output files stay on host):

```bash
docker run --rm -v "$PWD:/work" -w /work hongrui0/gcf:latest
```

## Configuration

Edit these constants in `script.py`:

- `COLLEGE_FILTER`
  - Default: `College of Computing & Data Science`
  - Set to `None` to run across all colleges/schools
- `CANDIDATES_FILE`
- `FUNDED_PI_FILE`
- `OUTPUT_DIR`

If you run production data, point these two paths to your local protected files.

## Privacy Note

The Docker build context is restricted via `.dockerignore` so personal data files are not included in the image build context by default.

## CI

GitHub Actions workflow is in `.github/workflows/ci.yml`. It installs dependencies and runs tests on push and pull requests.
