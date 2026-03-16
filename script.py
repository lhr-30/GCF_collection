import re
import sys
from pathlib import Path

import pandas as pd


# =========================
# 1. CONFIGURATION
# =========================

CANDIDATES_FILE = "candidates.xlsx"
FUNDED_PI_FILE = "funded_pis.xlsx"
OUTPUT_DIR = "reports"
CSV_ENCODING = "utf-8-sig"

# Set to None to run for all colleges/schools.
COLLEGE_FILTER = "College of Computing & Data Science"

FUNDED_PI_NAME_COL = "PI full name"
FUNDED_PI_EMAIL_COL = "PI email"

STUDENT_NAME_COL = "Name"
STUDENT_EMAIL_COL = "Email"

STUDENT_INFO_COLS = [
    "Appl. No",
    "Matric No",
    "Category",
    "Study Mode",
    "Birth Dt",
    "Sex",
    "Continent",
    "Nationality",
    "Degree",
    "Year",
    "Semester",
    "Home University",
    "Home Univ Country",
    "QS Rank",
    "Home Major 1",
    "Home Major 2",
    "Status",
    "CGPA",
    "CGPA Percent",
    "Research Experience",
    "APPL_IC_URL",
    "Video Resume",
]


# =========================
# 2. UTILITIES
# =========================


def require_columns(df, required_cols, df_name):
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in {df_name}: {missing}\\n"
            f"Available columns are:\\n{list(df.columns)}"
        )


def normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def detect_ranked_columns(columns, prefixes, max_rank=3):
    found = {}
    for col in columns:
        key = normalize_header(col)
        for prefix in prefixes:
            if key.startswith(prefix):
                suffix = key[len(prefix) :]
                if suffix.isdigit():
                    rank = int(suffix)
                    if 1 <= rank <= max_rank:
                        found[rank] = col
    return found


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def canonical_pi_name(text) -> str:
    if pd.isna(text):
        return ""
    s = normalize_whitespace(text).lower()

    # Convert "Last, First" -> "First Last"
    if s.count(",") == 1:
        left, right = [x.strip() for x in s.split(",")]
        if left and right:
            s = f"{right} {left}"

    # Remove common titles
    s = re.sub(
        r"\b(associate|assoc|assistant|asst|adjunct)\s+prof(?:essor)?\b",
        " ",
        s,
    )
    s = re.sub(r"\bprof(?:essor)?\b", " ", s)
    s = re.sub(r"\bdr\b", " ", s)
    s = re.sub(r"\b(mr|mrs|ms|miss|madam)\b", " ", s)

    # Remove punctuation but keep letters/numbers/spaces/hyphen
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def funded_name_variants(name):
    raw = "" if pd.isna(name) else str(name)
    variants = {raw}

    # Name without parenthesis
    no_paren = re.sub(r"\([^)]*\)", " ", raw)
    if normalize_whitespace(no_paren):
        variants.add(no_paren)

    # Text inside parenthesis as alias
    for alias in re.findall(r"\(([^)]*)\)", raw):
        alias = normalize_whitespace(alias)
        if alias:
            variants.add(alias)

    out = set()
    for v in variants:
        canon = canonical_pi_name(v)
        if canon:
            out.add(canon)
    return out


def priority_label(priority: int) -> str:
    if priority == 1:
        return "1st"
    if priority == 2:
        return "2nd"
    if priority == 3:
        return "3rd"
    return f"{priority}th"


def safe_filename(name: str) -> str:
    name = str(name).strip()
    name = re.sub(r"[^\w\s\-\.]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name[:120] if name else "unknown_pi"


def dept_matches_filter(value, college_filter):
    if not college_filter:
        return True
    if pd.isna(value):
        return False
    left = normalize_whitespace(value).lower()
    right = normalize_whitespace(college_filter).lower()
    return right in left


def resolve_input_path(configured_name: str) -> Path:
    """
    Prefer the configured path. If it doesn't exist, try same basename with xlsx/csv.
    """
    p = Path(configured_name)
    if p.exists():
        return p

    candidates = []
    stem = p.with_suffix("")
    for ext in [".xlsx", ".csv"]:
        alt = Path(f"{stem}{ext}")
        if alt.exists():
            candidates.append(alt)
    if candidates:
        return candidates[0]
    return p


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return pd.read_excel(path, engine="openpyxl")
    if suffix == ".csv":
        return pd.read_csv(path, encoding=CSV_ENCODING)
    raise ValueError(f"Unsupported input format: {path}")


# =========================
# 3. MAIN
# =========================


def main():
    candidates_path = resolve_input_path(CANDIDATES_FILE)
    funded_path = resolve_input_path(FUNDED_PI_FILE)
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not candidates_path.exists():
        raise FileNotFoundError(f"Candidates file not found: {candidates_path}")
    if not funded_path.exists():
        raise FileNotFoundError(f"Funded PI file not found: {funded_path}")

    df_candidates = read_table(candidates_path)
    df_funded = read_table(funded_path)

    require_columns(df_funded, [FUNDED_PI_NAME_COL], "funded PI file")
    require_columns(df_candidates, [STUDENT_NAME_COL, STUDENT_EMAIL_COL], "candidate file")

    choice_cols = detect_ranked_columns(
        df_candidates.columns,
        prefixes=["researchsupervisor", "reseachsupervisor"],
        max_rank=3,
    )
    if not choice_cols:
        raise ValueError(
            "Cannot find choice columns like 'Research/Reseach Supervisor 1/2/3'."
        )

    dept_cols = detect_ranked_columns(
        df_candidates.columns,
        prefixes=["researchdept", "reseachdept"],
        max_rank=3,
    )

    title_cols = detect_ranked_columns(
        df_candidates.columns,
        prefixes=["researchtitle", "reseachtitle"],
        max_rank=3,
    )

    pi_lookup = {}
    ambiguous_keys = set()

    for _, row in df_funded.iterrows():
        pi_name = row.get(FUNDED_PI_NAME_COL, "")
        pi_email = row.get(FUNDED_PI_EMAIL_COL, "") if FUNDED_PI_EMAIL_COL in df_funded.columns else ""
        pi_info = {
            "pi_name": pi_name,
            "pi_email": pi_email,
        }

        for key in funded_name_variants(pi_name):
            if key in pi_lookup:
                if pi_lookup[key]["pi_name"] != pi_name:
                    ambiguous_keys.add(key)
            else:
                pi_lookup[key] = pi_info

    for key in ambiguous_keys:
        pi_lookup.pop(key, None)

    matches = []

    for _, row in df_candidates.iterrows():
        # De-duplicate repeated PI choices by the same student:
        # keep only the highest priority (smallest rank).
        best_by_pi = {}

        for rank in sorted(choice_cols):
            choice_col = choice_cols[rank]
            choice_raw = row.get(choice_col, "")
            choice_key = canonical_pi_name(choice_raw)
            if not choice_key:
                continue
            if choice_key not in pi_lookup:
                continue

            dept_col = dept_cols.get(rank)
            dept_value = row.get(dept_col, "") if dept_col else ""
            if COLLEGE_FILTER and dept_col and not dept_matches_filter(dept_value, COLLEGE_FILTER):
                continue

            title_col = title_cols.get(rank)
            title_value = row.get(title_col, "") if title_col else ""

            pi_info = pi_lookup[choice_key]
            record = {
                "PI Name": pi_info["pi_name"],
                "PI Email": pi_info["pi_email"],
                "Choice Rank": rank,
                "Choice Priority": priority_label(rank),
                "Matched PI (Student Input)": choice_raw,
                "Chosen Research Dept": dept_value,
                "Chosen Research Title": title_value,
                "Student Name": row.get(STUDENT_NAME_COL, ""),
                "Student Email": row.get(STUDENT_EMAIL_COL, ""),
            }

            for c in STUDENT_INFO_COLS:
                if c in df_candidates.columns and c not in record:
                    record[c] = row.get(c, "")

            pi_name = pi_info["pi_name"]
            if pi_name not in best_by_pi or rank < best_by_pi[pi_name]["Choice Rank"]:
                best_by_pi[pi_name] = record

        matches.extend(best_by_pi.values())

    if not matches:
        print("No matched students found.")
        return

    df_matches = pd.DataFrame(matches)
    df_matches = df_matches.sort_values(
        ["PI Name", "Choice Rank", "Student Name"]
    ).reset_index(drop=True)

    all_matches_path = output_dir / "all_matched_students.xlsx"
    df_matches.to_excel(all_matches_path, index=False, engine="openpyxl")

    summary_rows = []

    for pi_name, df_pi in df_matches.groupby("PI Name", dropna=False):
        filename = f"{safe_filename(pi_name)}_students.xlsx"
        out_path = output_dir / filename
        df_pi.to_excel(out_path, index=False, engine="openpyxl")

        rank_counts = df_pi["Choice Rank"].value_counts().to_dict()
        summary_rows.append(
            {
                "PI Name": pi_name,
                "PI Email": df_pi["PI Email"].iloc[0] if "PI Email" in df_pi.columns else "",
                "Num Students": len(df_pi),
                "Num 1st Choice": rank_counts.get(1, 0),
                "Num 2nd Choice": rank_counts.get(2, 0),
                "Num 3rd Choice": rank_counts.get(3, 0),
                "Output File": str(out_path),
            }
        )

    df_summary = pd.DataFrame(summary_rows).sort_values("PI Name").reset_index(drop=True)
    summary_path = output_dir / "summary.xlsx"
    df_summary.to_excel(summary_path, index=False, engine="openpyxl")

    print(f"Done. Generated {len(summary_rows)} per-PI files.")
    print(f"All matches: {all_matches_path.resolve()}")
    print(f"Summary: {summary_path.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
