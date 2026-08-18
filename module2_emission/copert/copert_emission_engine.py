"""Calculate per-vehicle COPERT-style emissions from quality-approved distance tracks.

Defect fix (Module 0, 2026-08-17): the factor-table directory now defaults to
module2_emission/factors, which is where the COPERT_2025_*.csv exports actually
live after the repo restructure. Previously the default pointed at a
non-existent "copert_factors" directory, so every emission record silently used
FALLBACK_SCENARIO_FACTOR and the COPERT tables were never actually read. A
missing factor directory is now a hard, loud failure instead of a silent
fallback; a missing/unmatched value inside an existing table is still a
per-pollutant, per-record logged fallback (recorded in the *_source column and
summarised on stdout), matching the project rule that the pipeline must never
crash but must never hide where a number came from either.

Factor-table parsing (Module 2, resolved 2026-08-18 -- see
docs/MODULE2_COPERT_METHODOLOGY.md for the full writeup): all four
COPERT_2025_*.csv exports are the same kind of file -- a 5-column, headerless
spreadsheet PIVOT export (row 0 is a junk label, not data). Column 0 is the
top-level vehicle category, forward-filled down its continuation rows; column
1 is either a fuel type, a "<Fuel> Total" subtotal label, or blank on a
segment-detail sub-row; column 4 is the g/km value. There is no single
"the" factor per category -- the table reports one line per (category, fuel,
segment) combination. FALLBACK_FACTORS were originally hand-picked from this
same file using a fixed, documented fuel-mix assumption (predominantly petrol
light-duty vehicles, predominantly diesel heavy-duty vehicles -- realistic for
the Indian urban fleet these videos were shot in): _parse_copert_pivot_table()
below applies that exact same rule programmatically and recovers every one of
the 16 FALLBACK_FACTORS values bit-for-bit from the raw CSVs. PM2.5's table
has the identical pivot structure to CO2/NOx/CO -- the ~338x bug documented in
docs/KNOWN_ISSUES.md came from a naive "any column literally named Total"
match grabbing the wrong row (a tonnes-for-a-reference-scenario aggregate),
not from the file being unusable. All four pollutants now parse from the real
tables, with a >=3x-deviation sanity check against FALLBACK_FACTORS as a
guard rail (the same kind of check that would have caught the PM2.5 bug
immediately).
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from configs.loader import load_config


FALLBACK_FACTORS = {
    "Passenger Cars": {"CO2": 149.1856, "NOx": 0.0414, "CO": 0.3529, "PM25": 0.0155},
    "L-Category": {"CO2": 73.1875, "NOx": 0.0311, "CO": 0.4329, "PM25": 0.0069},
    "Buses": {"CO2": 924.2413, "NOx": 1.2932, "CO": 0.3836, "PM25": 0.0639},
    "Heavy Duty Trucks": {"CO2": 1123.5121, "NOx": 0.3130, "CO": 0.0769, "PM25": 0.0702},
}

COPERT_LABELS = {
    "PASSENGER_CAR": "Passenger Cars",
    "MOTORCYCLE": "L-Category",
    "BUS": "Buses",
    "HEAVY_DUTY_TRUCK": "Heavy Duty Trucks",
}

VEHICLE_TYPE_TO_COPERT = {
    "car": "PASSENGER_CAR",
    "motorcycle": "MOTORCYCLE",
    "bus": "BUS",
    "truck": "HEAVY_DUTY_TRUCK",
}

# Defect fix 4b: the PM2.5 export was written without the "_EF" suffix that
# every other pollutant uses. Accept both spellings so the loader is not
# silently defeated by a filename mismatch.
FACTOR_FILENAMES = {
    "CO2": ["COPERT_2025_CO2_EF.csv"],
    "NOx": ["COPERT_2025_NOx_EF.csv"],
    "CO": ["COPERT_2025_CO_EF.csv"],
    "PM25": ["COPERT_2025_PM2.5_EF.csv", "COPERT_2025_PM2.5.csv"],
}

# The representative fuel/technology row to pick per category, applied by
# _parse_copert_pivot_table(). Sourced from configs/project_config.yaml
# (Module 0 convention: paths/thresholds/mappings live in one config file,
# not scattered module constants). See the module docstring and
# docs/MODULE2_COPERT_METHODOLOGY.md for why: this reproduces FALLBACK_FACTORS
# exactly because that is precisely how those constants were originally derived
# from this same file.
FUEL_SELECTOR_BY_CATEGORY = load_config()["copert_fuel_mix_assumption"]

# A parsed value further than this multiple from FALLBACK_FACTORS in either
# direction is rejected as a probable row-selection or unit error (the same
# check that would have caught the PM2.5 ~338x bug on the first record).
SANITY_CHECK_MAX_RATIO = load_config()["copert_factor_sanity_check_max_ratio"]


def _parse_copert_pivot_table(path: Path) -> dict[str, float]:
    """Parse one COPERT_2025_*.csv pivot export into {category: g/km factor}.

    Layout: 5 columns, no real header (row 0 is a junk "Total Total" label,
    not data). Column 0 is the top-level vehicle category, forward-filled
    across its continuation rows (blank where a row continues the category
    above it). Column 1 is a fuel type, a "<Fuel> Total" subtotal label, or
    blank on a further segment-detail sub-row. Column 4 is the g/km value,
    occasionally thousands-comma-formatted (e.g. "1,123.5121").
    """
    raw = pd.read_csv(path, header=None, encoding="latin1", dtype=str)
    raw = raw.iloc[1:]  # row 0 is the junk label row, not data.
    raw[0] = raw[0].replace("", np.nan).ffill()
    values: dict[str, float] = {}
    for category, fuel_selector in FUEL_SELECTOR_BY_CATEGORY.items():
        matches = raw.loc[(raw[0] == category) & (raw[1] == fuel_selector)]
        if matches.empty:
            continue
        value = pd.to_numeric(str(matches.iloc[0][4]).replace(",", ""), errors="coerce")
        if pd.notna(value):
            values[category] = float(value)
    return values


def load_copert_factors(factor_dir: Path) -> dict[str, dict[str, float]]:
    """Load and parse the COPERT factor tables. Fails loudly if the directory itself is missing."""
    if not factor_dir.exists():
        raise FileNotFoundError(
            f"COPERT factor directory not found: {factor_dir}. "
            "The engine will not silently fall back to scenario constants for an "
            "entire missing directory -- pass --factor-dir explicitly or restore "
            "module2_emission/factors/."
        )
    tables: dict[str, dict[str, float]] = {}
    for pollutant, candidate_names in FACTOR_FILENAMES.items():
        loaded = False
        for filename in candidate_names:
            path = factor_dir / filename
            if not path.exists():
                continue
            try:
                parsed = _parse_copert_pivot_table(path)
            except Exception as exc:  # Keep the provenance visible in output.
                print(f"WARNING: unable to parse {path}: {exc}")
                continue
            if parsed:
                tables[pollutant] = parsed
                loaded = True
                break
            print(f"WARNING: {path} parsed with no usable rows.")
        if not loaded:
            print(
                f"WARNING: no usable factor table found for {pollutant} in {factor_dir} "
                f"(looked for {candidate_names}); this pollutant will use "
                "FALLBACK_SCENARIO_FACTOR for every record."
            )
    return tables


def get_factor(category: str, pollutant: str, tables: dict[str, dict[str, float]]) -> tuple[float, str]:
    fallback = FALLBACK_FACTORS[category][pollutant]
    parsed = tables.get(pollutant, {}).get(category)
    if parsed is None:
        return fallback, "FALLBACK_SCENARIO_FACTOR"
    if fallback == 0:
        ratio_ok = parsed == 0
    else:
        ratio = parsed / fallback
        ratio_ok = (1.0 / SANITY_CHECK_MAX_RATIO) <= ratio <= SANITY_CHECK_MAX_RATIO
    if not ratio_ok:
        print(
            f"WARNING: parsed {pollutant} factor for {category} ({parsed}) differs from "
            f"FALLBACK_FACTORS ({fallback}) by more than {SANITY_CHECK_MAX_RATIO}x -- "
            "rejecting the parsed value as a likely row-selection or unit error and using "
            "the fallback constant instead."
        )
        return fallback, "FALLBACK_SCENARIO_FACTOR"
    return parsed, "COPERT_FACTOR_TABLE"


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate COPERT-style emissions per completed vehicle track.")
    parser.add_argument(
        "--input",
        default="outputs/module2_copert_scenario_distance/INDRA_COPERT_INPUT.csv",
        help="Distance-enriched COPERT-ready observation dataset.",
    )
    parser.add_argument(
        "--factor-dir",
        default="module2_emission/factors",
        help="Directory containing the COPERT_2025_*.csv implied-emission-factor exports.",
    )
    parser.add_argument("--output-dir", default="outputs/copert_emissions")
    parser.add_argument(
        "--output-csv",
        help="Emission result file. Defaults to vehicle_emissions.csv in --output-dir.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(input_path)
    required = {"video_id", "vehicle_id", "vehicle_type", "distance_km"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"Missing columns: {missing}. Generate distance_km before running emissions."
        )
    frame["distance_km"] = pd.to_numeric(frame["distance_km"], errors="coerce")
    frame = frame.loc[frame["distance_km"].notna() & (frame["distance_km"] >= 0)].copy()
    if "vehicle_total_distance_km" in frame.columns:
        frame["vehicle_total_distance_km"] = pd.to_numeric(
            frame["vehicle_total_distance_km"], errors="coerce"
        )
    if "in_roi" in frame.columns:
        frame = frame.loc[frame["in_roi"] == 1].copy()
    if "emission_eligible" in frame.columns:
        frame = frame.loc[frame["emission_eligible"] == 1].copy()
    if "copert_category" not in frame.columns:
        frame["copert_category"] = (
            frame["vehicle_type"].astype(str).str.lower().map(VEHICLE_TYPE_TO_COPERT)
        )

    # One distance per vehicle journey: use the final cumulative distance, not
    # every trajectory row, preventing frame-by-frame emission double counting.
    # ByteTrack IDs may have an occasional class flicker, so choose the dominant
    # class within a track instead of splitting the same ID into emissions twice.
    tracks = (
        frame.groupby(["video_id", "vehicle_id"], as_index=False)
        .agg(
            vehicle_type=(
                "vehicle_type",
                lambda values: values.astype(str).str.lower().mode().iat[0],
            ),
            distance_km=(
                "vehicle_total_distance_km" if "vehicle_total_distance_km" in frame.columns else "distance_km",
                "max",
            ),
            observations=("distance_km", "size"),
        )
    )
    tracks["copert_category"] = tracks["vehicle_type"].map(VEHICLE_TYPE_TO_COPERT)
    tracks["copert_factor_category"] = tracks["copert_category"].map(COPERT_LABELS)
    excluded = tracks.loc[tracks["copert_factor_category"].isna()].copy()
    excluded["exclusion_reason"] = "No approved COPERT factor mapping (e.g. three-wheeler)."
    included = tracks.loc[tracks["copert_factor_category"].notna()].copy()

    tables = load_copert_factors(Path(args.factor_dir))
    records = []
    for row in included.itertuples(index=False):
        record = {
            "video_id": row.video_id,
            "vehicle_id": row.vehicle_id,
            "vehicle_type": row.vehicle_type,
            "copert_category": row.copert_category,
            "copert_factor_category": row.copert_factor_category,
            "distance_km": row.distance_km,
        }
        for pollutant in ("CO2", "NOx", "CO", "PM25"):
            factor, source = get_factor(row.copert_factor_category, pollutant, tables)
            record[f"{pollutant}_EF_g_per_km"] = factor
            record[f"{pollutant}_g"] = row.distance_km * factor
            record[f"{pollutant}_source"] = source
        records.append(record)
    # pd.DataFrame([]) has zero columns (not even a header), which downstream
    # readers can't parse at all (EmptyDataError). An explicit column list
    # keeps a zero-row result a valid, header-only CSV instead.
    emission_columns = (
        ["video_id", "vehicle_id", "vehicle_type", "copert_category", "copert_factor_category", "distance_km"]
        + [f"{pollutant}_{suffix}" for pollutant in ("CO2", "NOx", "CO", "PM25") for suffix in ("EF_g_per_km", "g", "source")]
    )
    emissions = pd.DataFrame(records, columns=emission_columns)
    output_path = Path(args.output_csv) if args.output_csv else output_dir / "vehicle_emissions.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    emissions.to_csv(output_path, index=False)
    excluded.to_csv(output_dir / "excluded_vehicle_tracks.csv", index=False)

    print(f"Included vehicle tracks: {len(emissions):,}")
    print(f"Excluded vehicle tracks: {len(excluded):,}")
    print(f"Output: {output_path}")

    # Explicit, logged fallback summary -- never let a fallback hide inside a
    # column nobody reads. If a pollutant used the fallback for every record,
    # that is surfaced loudly here.
    if not emissions.empty:
        print("\nEmission-factor source summary (per pollutant):")
        any_full_fallback = False
        for pollutant in ("CO2", "NOx", "CO", "PM25"):
            counts = emissions[f"{pollutant}_source"].value_counts()
            table_count = int(counts.get("COPERT_FACTOR_TABLE", 0))
            fallback_count = int(counts.get("FALLBACK_SCENARIO_FACTOR", 0))
            print(
                f"  {pollutant:5s}: {table_count:6,} from COPERT_FACTOR_TABLE, "
                f"{fallback_count:6,} from FALLBACK_SCENARIO_FACTOR"
            )
            if table_count == 0 and fallback_count > 0:
                any_full_fallback = True
        if any_full_fallback:
            print(
                "\nWARNING: at least one pollutant used FALLBACK_SCENARIO_FACTOR for "
                "every record -- its factor table was not found or did not match any "
                "category. Check --factor-dir and the CSV filenames above.",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
