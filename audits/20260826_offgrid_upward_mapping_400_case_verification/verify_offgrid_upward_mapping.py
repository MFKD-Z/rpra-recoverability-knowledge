"""Exact, isolated verification of the 400-case upward retrieval protocol.

This script deliberately does not alter the RPRA implementation or recompute the
continuous constrained references.  It reuses the frozen EXP-0 detail table,
rebuilds only the discrete sets, and maps serialized observations with Decimal
arithmetic to the smallest represented integer grid state not below each value.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Mapping

import numpy as np


AUDIT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = AUDIT_DIR.parents[1]
WORKSPACE_ROOT = REPOSITORY_ROOT.parent.parent
SOURCE_DIR = REPOSITORY_ROOT / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from rpra.recoverable_set import build_backward_set, lookup_membership  # noqa: E402
from rpra.reproduction import _heldout_states, load_all_configurations  # noqa: E402


GRID_TEXTS = ("0.004", "0.002", "0.001", "0.0005", "0.00025")
DETAIL_SOURCE = WORKSPACE_ROOT / "tables" / "heldout_400_agreement.csv"
HISTORICAL_SUMMARY_SOURCE = WORKSPACE_ROOT / "tables" / "EXP2_grid_sensitivity.csv"
PUBLIC_REFERENCE_SOURCE = REPOSITORY_ROOT / "data" / "reference" / "grid_robustness.csv"
DETAIL_OUTPUT = AUDIT_DIR / "offgrid_upward_mapping_400_verification.csv"
SUMMARY_OUTPUT = AUDIT_DIR / "offgrid_upward_mapping_summary.csv"
METADATA_OUTPUT = AUDIT_DIR / "verification_metadata.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_upward_grid_index(
    observed_text: str,
    grid_text: str,
    domain_min_text: str,
    domain_max_text: str,
) -> int | None:
    """Return the exact upward integer-grid index, or None outside the domain."""
    observed = Decimal(observed_text)
    domain_min = Decimal(domain_min_text)
    domain_max = Decimal(domain_max_text)
    if observed < domain_min or observed > domain_max:
        return None
    grid = Decimal(grid_text)
    reciprocal = Decimal(1) / grid
    if reciprocal != reciprocal.to_integral_value():
        raise ValueError(f"grid does not have an integer reciprocal: {grid_text}")
    return int((observed / grid).to_integral_value(rounding=ROUND_CEILING))


def direct_membership(state_i: int, backward: Mapping) -> bool:
    final_values = np.asarray(
        backward["stages_int"][backward["pass_count"]], dtype=np.int64
    )
    index = int(np.searchsorted(final_values, state_i))
    return bool(index < len(final_values) and final_values[index] == state_i)


def focused_mapping_checks() -> dict[str, bool]:
    grid = "0.001"
    lo = "4.180"
    hi = "4.800"
    checks = {
        "exact_grid_point": exact_upward_grid_index("4.586", grid, lo, hi) == 4586,
        "minimally_above_grid_point": (
            exact_upward_grid_index("4.586000000000000001", grid, lo, hi) == 4587
        ),
        "below_next_grid_point": (
            exact_upward_grid_index("4.586999999999999999", grid, lo, hi) == 4587
        ),
        "upper_domain_boundary": exact_upward_grid_index("4.800", grid, lo, hi) == 4800,
        "outside_domain_not_clamped": (
            exact_upward_grid_index("4.800000000000000001", grid, lo, hi) is None
        ),
    }
    if not all(checks.values()):
        raise AssertionError(f"focused exact-mapping check failed: {checks}")

    # Establish why the historical tolerance-adjusted ceiling is not the exact
    # mathematical rule in general, without modifying that historical function.
    next_float = float(np.nextafter(4.586, np.inf))
    synthetic = {
        "scale": 1000,
        "pass_count": 1,
        "stages_int": {1: np.asarray([4586, 4587], dtype=np.int64)},
    }
    _, legacy_mapped = lookup_membership(next_float, synthetic, snap="ceil")
    exact_mapped_i = exact_upward_grid_index(str(next_float), grid, lo, hi)
    checks["legacy_tolerance_divergence_reproduced"] = (
        int(round(legacy_mapped * 1000)) == 4586 and exact_mapped_i == 4587
    )
    if not checks["legacy_tolerance_divergence_reproduced"]:
        raise AssertionError("historical tolerance divergence was not reproduced")
    return checks


def error_type(discrete: bool, continuous: bool) -> str:
    if discrete and continuous:
        return "AGREEMENT_RECOVERABLE"
    if not discrete and not continuous:
        return "AGREEMENT_IRRECOVERABLE"
    if not discrete and continuous:
        return "CONSERVATIVE_FALSE_REJECTION"
    return "OPTIMISTIC_FALSE_ACCEPTANCE"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not DETAIL_SOURCE.is_file():
        raise FileNotFoundError(f"frozen held-out detail source not found: {DETAIL_SOURCE}")
    if not HISTORICAL_SUMMARY_SOURCE.is_file():
        raise FileNotFoundError(
            f"historical grid summary source not found: {HISTORICAL_SUMMARY_SOURCE}"
        )

    source_hash_before = sha256(DETAIL_SOURCE)
    source_rows = read_rows(DETAIL_SOURCE)
    if len(source_rows) != 400:
        raise AssertionError(f"expected 400 frozen states, found {len(source_rows)}")

    cfg = load_all_configurations(REPOSITORY_ROOT)["3pass_100um"]
    domain_min_text = str(cfg["heldout_state_min_mm"])
    domain_max_text = str(cfg["heldout_state_max_mm"])
    generated_once = _heldout_states(cfg)
    generated_twice = _heldout_states(cfg)
    source_floats = [float(row["state_mm"]) for row in source_rows]
    deterministic = generated_once == generated_twice == source_floats
    if not deterministic:
        raise AssertionError("frozen states differ from deterministic repository generator")

    focused_checks = focused_mapping_checks()
    historical_rows = {
        row["grid_mm"]: row for row in read_rows(HISTORICAL_SUMMARY_SOURCE)
    }
    public_rows = {
        row["grid_mm"]: row for row in read_rows(PUBLIC_REFERENCE_SOURCE)
    }

    detail_rows: list[dict] = []
    summary_rows: list[dict] = []
    all_off_grid = True
    all_legacy_equivalent = True

    for grid_text in GRID_TEXTS:
        variant = dict(cfg)
        variant["state_grid_mm"] = float(grid_text)
        backward = build_backward_set(3, variant)
        scale = int(backward["scale"])
        counts = {
            "N_total": len(source_rows),
            "N_valid": 0,
            "N_agreement": 0,
            "N_conservative_false_rejection": 0,
            "N_optimistic_false_acceptance": 0,
            "N_outside_represented_domain": 0,
            "N_invalid_reference": 0,
            "legacy_mapping_equivalent_cases": 0,
        }
        max_mapping_delta_um = Decimal(0)

        for source in source_rows:
            observed_text = source["state_mm"]
            observed = Decimal(observed_text)
            continuous_text = source["full_reopt_decision"].strip().upper()
            margin_text = source["recoverability_margin_um"].strip()
            exact_i = exact_upward_grid_index(
                observed_text, grid_text, domain_min_text, domain_max_text
            )

            if exact_i is None:
                counts["N_outside_represented_domain"] += 1
                detail_rows.append(
                    {
                        "case_id": source["state_id"],
                        "s_observed_mm": observed_text,
                        "grid_mm": grid_text,
                        "s_upward_mapped_mm": "",
                        "mapping_delta_um": "",
                        "discrete_status": "",
                        "continuous_status": "",
                        "continuous_margin_um": margin_text,
                        "agreement": "false",
                        "error_type": "OUTSIDE_REPRESENTED_DOMAIN",
                    }
                )
                continue
            if continuous_text not in {"PASS", "FAIL"} or not margin_text:
                counts["N_invalid_reference"] += 1
                detail_rows.append(
                    {
                        "case_id": source["state_id"],
                        "s_observed_mm": observed_text,
                        "grid_mm": grid_text,
                        "s_upward_mapped_mm": str(Decimal(exact_i) / Decimal(scale)),
                        "mapping_delta_um": "",
                        "discrete_status": "",
                        "continuous_status": "",
                        "continuous_margin_um": margin_text,
                        "agreement": "false",
                        "error_type": "INVALID_REFERENCE",
                    }
                )
                continue

            continuous = continuous_text == "PASS"
            discrete = direct_membership(exact_i, backward)
            mapped = Decimal(exact_i) / Decimal(scale)
            mapping_delta_um = (mapped - observed) * Decimal(1000)
            if mapping_delta_um < 0 or mapping_delta_um >= Decimal(grid_text) * 1000:
                raise AssertionError(
                    f"invalid upward delta for {source['state_id']} at {grid_text}"
                )
            max_mapping_delta_um = max(max_mapping_delta_um, mapping_delta_um)
            agreement = discrete == continuous
            category = error_type(discrete, continuous)
            counts["N_valid"] += 1
            counts["N_agreement"] += int(agreement)
            counts["N_conservative_false_rejection"] += int(
                category == "CONSERVATIVE_FALSE_REJECTION"
            )
            counts["N_optimistic_false_acceptance"] += int(
                category == "OPTIMISTIC_FALSE_ACCEPTANCE"
            )

            legacy_member, legacy_mapped = lookup_membership(
                float(observed_text), backward, snap="ceil"
            )
            legacy_i = int(round(legacy_mapped * scale))
            legacy_equivalent = legacy_i == exact_i and legacy_member == discrete
            counts["legacy_mapping_equivalent_cases"] += int(legacy_equivalent)
            all_legacy_equivalent = all_legacy_equivalent and legacy_equivalent

            on_grid = observed / Decimal(grid_text) == (
                observed / Decimal(grid_text)
            ).to_integral_value()
            all_off_grid = all_off_grid and not on_grid

            detail_rows.append(
                {
                    "case_id": source["state_id"],
                    "s_observed_mm": observed_text,
                    "grid_mm": grid_text,
                    "s_upward_mapped_mm": format(mapped, "f"),
                    "mapping_delta_um": format(mapping_delta_um, "f"),
                    "discrete_status": "RECOVERABLE" if discrete else "IRRECOVERABLE",
                    "continuous_status": (
                        "RECOVERABLE" if continuous else "IRRECOVERABLE"
                    ),
                    "continuous_margin_um": margin_text,
                    "agreement": str(agreement).lower(),
                    "error_type": category,
                }
            )

        if counts["N_valid"]:
            agreement_rate = counts["N_agreement"] / counts["N_valid"]
        else:
            agreement_rate = ""
        historical = historical_rows[grid_text]
        public = public_rows[grid_text]
        if counts["N_agreement"] != int(historical["heldout_agreement_count"]):
            raise AssertionError(f"historical agreement mismatch at grid {grid_text}")
        if counts["N_optimistic_false_acceptance"] != int(
            historical["unsafe_optimistic_classification_count"]
        ):
            raise AssertionError(f"historical unsafe-count mismatch at grid {grid_text}")
        if counts["N_agreement"] != int(public["heldout_agreement_of_400"]):
            raise AssertionError(f"public reference agreement mismatch at grid {grid_text}")

        summary_rows.append(
            {
                "grid_mm": grid_text,
                **counts,
                "agreement_rate": agreement_rate,
                "max_mapping_delta_um": format(max_mapping_delta_um, "f"),
                "all_400_cases_deterministic": str(deterministic).lower(),
                "continuous_reference_unchanged": "true",
            }
        )

    source_hash_after = sha256(DETAIL_SOURCE)
    continuous_reference_unchanged = source_hash_before == source_hash_after
    if not continuous_reference_unchanged:
        raise AssertionError("frozen continuous reference changed during verification")
    if len(detail_rows) != 400 * len(GRID_TEXTS):
        raise AssertionError("detail output is not the required 400 x 5 rows")
    if not all_legacy_equivalent:
        raise AssertionError("legacy and exact mappings differ for a frozen held-out case")

    write_rows(
        DETAIL_OUTPUT,
        [
            "case_id",
            "s_observed_mm",
            "grid_mm",
            "s_upward_mapped_mm",
            "mapping_delta_um",
            "discrete_status",
            "continuous_status",
            "continuous_margin_um",
            "agreement",
            "error_type",
        ],
        detail_rows,
    )
    write_rows(
        SUMMARY_OUTPUT,
        [
            "grid_mm",
            "N_total",
            "N_valid",
            "N_agreement",
            "agreement_rate",
            "N_conservative_false_rejection",
            "N_optimistic_false_acceptance",
            "max_mapping_delta_um",
            "N_outside_represented_domain",
            "N_invalid_reference",
            "legacy_mapping_equivalent_cases",
            "all_400_cases_deterministic",
            "continuous_reference_unchanged",
        ],
        summary_rows,
    )
    metadata = {
        "task": "OFFGRID_UPWARD_MAPPING_400_CASE_VERIFICATION",
        "audit_classification": "DIFFERENT_MAPPING_USED",
        "reason": (
            "Historical lookup uses ceil(raw - 1e-12), which differs from exact "
            "upward mapping for minimally-above-grid inputs."
        ),
        "repository_root": str(REPOSITORY_ROOT),
        "frozen_detail_source": str(DETAIL_SOURCE),
        "frozen_detail_sha256_before": source_hash_before,
        "frozen_detail_sha256_after": source_hash_after,
        "continuous_reference_unchanged": continuous_reference_unchanged,
        "deterministic_generator_matches_frozen_rows": deterministic,
        "all_400_off_grid_at_all_tested_resolutions": all_off_grid,
        "legacy_mapping_matches_exact_for_all_2000_evaluations": all_legacy_equivalent,
        "focused_mapping_checks": focused_checks,
        "detail_row_count": len(detail_rows),
        "summary": summary_rows,
    }
    METADATA_OUTPUT.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
