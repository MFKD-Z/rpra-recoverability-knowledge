"""Morelli et al. (2025) static thin-wall milling deflection model.

Implements Eqs. (29)-(32) and Table 2 from:
L. Morelli et al., Journal of Manufacturing Processes 143 (2025) 369-386.
DOI: 10.1016/j.jmapro.2025.04.029

Lengths are in mm, elastic/cutting coefficients are in MPa (N/mm^2), and
the returned deflection is in mm unless the function name says otherwise.
"""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np


PAPER_TITLE = (
    "Static deflection of cantilever thin wall workpieces in peripheral "
    "milling: An analytical model"
)
DOI = "10.1016/j.jmapro.2025.04.029"
EQUATION_ID = "Eq. (32), with Eqs. (29)-(31)"

# Coefficients are ordered from fifth to zeroth grade. The paper denotes the
# first three rows A_j/B_j/C_j; Eq. (32) prints A_j/B_j/C_j.  We expose the
# shorter aliases A/B/C requested by the experiment specification.
TABLE2_COEFFICIENTS: Mapping[str, tuple[float, ...]] = {
    "A": (0.54285, -2.37321, 2.92818, -1.26926, 0.41783, -0.00270),
    "B": (-1.32670, 4.76385, -5.06127, 1.91583, -0.88927, 0.00455),
    "C": (0.78054, -2.33132, 2.16387, -1.06458, 0.99417, -0.00184),
    "Am": (0.32165, -2.68773, 3.04204, -0.19337, 0.10051, 0.00446),
    "Bm": (-0.98043, 4.43709, -3.05624, -1.23594, -0.71300, -0.00641),
    "Cm": (0.66653, -1.69511, 0.33740, -0.03578, 2.31081, 0.00202),
}

# Eq. (25), third through zeroth grade. Table 2 labels this row f(AR), while
# Eq. (25), Eq. (32), and the surrounding definition consistently use f(WR).
F_WR_COEFFICIENTS = (-0.26169, 0.52372, -0.17598, 0.11665)


def _require_finite_positive(name: str, value: float) -> None:
    if not math.isfinite(float(value)) or float(value) <= 0.0:
        raise ValueError(f"{name} must be finite and > 0; got {value!r}")


def width_ratio(height_mm: float, width_mm: float) -> float:
    _require_finite_positive("height_mm", height_mm)
    _require_finite_positive("width_mm", width_mm)
    return float(height_mm) / float(width_mm)


def aspect_ratio(height_mm: float, thickness_mm: float) -> float:
    _require_finite_positive("height_mm", height_mm)
    _require_finite_positive("thickness_mm", thickness_mm)
    return float(height_mm) / float(thickness_mm)


def normalized_coordinates(
    *, z_mm: float, axial_depth_mm: float, radial_depth_mm: float,
    height_mm: float, tool_diameter_mm: float,
) -> tuple[float, float, float]:
    """Return xi=z/h, gamma=ap/h, and psi=ar/Dt (Eqs. 6-8)."""
    _require_finite_positive("height_mm", height_mm)
    _require_finite_positive("tool_diameter_mm", tool_diameter_mm)
    xi = float(z_mm) / float(height_mm)
    gamma = float(axial_depth_mm) / float(height_mm)
    psi = float(radial_depth_mm) / float(tool_diameter_mm)
    if not 0.0 <= xi <= 1.0:
        raise ValueError(f"xi=z/h must be in [0,1]; got {xi}")
    if not 0.0 < gamma <= 1.0:
        raise ValueError(f"gamma=ap/h must be in (0,1]; got {gamma}")
    if not 0.0 < psi <= 1.0:
        raise ValueError(f"psi=ar/Dt must be in (0,1]; got {psi}")
    return xi, gamma, psi


def cutting_force_ratio(k_tc_mpa: float, k_rc_mpa: float) -> float:
    _require_finite_positive("k_tc_mpa", k_tc_mpa)
    if not math.isfinite(float(k_rc_mpa)) or float(k_rc_mpa) < 0.0:
        raise ValueError(f"k_rc_mpa must be finite and >= 0; got {k_rc_mpa!r}")
    return float(k_rc_mpa) / float(k_tc_mpa)


def stationary_milling_factor(
    radial_immersion: float | np.ndarray,
    cutting_force_ratio_value: float,
    branch: str = "down",
) -> float | np.ndarray:
    """Stationary milling factor S(psi), Eq. (29) down / Eq. (30) up."""
    psi = np.asarray(radial_immersion, dtype=float)
    if np.any(~np.isfinite(psi)) or np.any((psi <= 0.0) | (psi > 1.0)):
        raise ValueError("radial_immersion psi must be finite and in (0,1]")
    kr = float(cutting_force_ratio_value)
    if not math.isfinite(kr) or kr < 0.0:
        raise ValueError("cutting_force_ratio_value must be finite and >= 0")
    base = (
        np.arccos(1.0 - 2.0 * psi)
        - 2.0 * (1.0 - 2.0 * psi) * np.sqrt(psi * (1.0 - psi))
    )
    radial = 4.0 * kr * (psi - psi**2)
    if branch == "down":
        result = base + radial
    elif branch == "up":
        result = base - radial
    else:
        raise ValueError("branch must be 'down' or 'up'")
    if np.ndim(result) == 0:
        return float(result)
    return result


def uniformly_distributed_load_n_per_mm(
    *, tooth_count: int, feed_per_tooth_mm: float, k_tc_mpa: float,
    stationary_factor: float | np.ndarray,
) -> float | np.ndarray:
    """Uniform line load q in N/mm, Eq. (31)."""
    if int(tooth_count) != tooth_count or int(tooth_count) <= 0:
        raise ValueError("tooth_count must be a positive integer")
    _require_finite_positive("feed_per_tooth_mm", feed_per_tooth_mm)
    _require_finite_positive("k_tc_mpa", k_tc_mpa)
    q = (
        int(tooth_count) * float(feed_per_tooth_mm) * float(k_tc_mpa)
        * np.asarray(stationary_factor, dtype=float) / (4.0 * math.pi)
    )
    if np.ndim(q) == 0:
        return float(q)
    return q


def polynomial_values(gamma: float) -> dict[str, float]:
    if not math.isfinite(float(gamma)) or not 0.0 < float(gamma) <= 1.0:
        raise ValueError("gamma must be finite and in (0,1]")
    return {name: float(np.polyval(coeffs, gamma)) for name, coeffs in TABLE2_COEFFICIENTS.items()}


def f_width_ratio(wr: float) -> float:
    if not math.isfinite(float(wr)) or float(wr) <= 0.0:
        raise ValueError("WR must be finite and > 0")
    return float(np.polyval(F_WR_COEFFICIENTS, wr))


def _shape_factor(*, xi: float, gamma: float, wr: float, poisson_ratio: float) -> float:
    vals = polynomial_values(gamma)
    if wr <= 0.25:
        return (1.0 - poisson_ratio**2) * (
            vals["A"] * xi**4 + vals["B"] * xi**3 + vals["C"] * xi**2
        )
    if wr < 0.7:
        return (1.0 - poisson_ratio**2) * f_width_ratio(wr) * (
            vals["Am"] * xi**4 + vals["Bm"] * xi**3 + vals["Cm"] * xi**2
        )
    return (wr / 24.0) * (
        xi**4 - 4.0 * xi**3 + 6.0 * xi**2
        - 4.0 * (1.0 - gamma) ** 3 * xi + (1.0 - gamma) ** 4
    )


def deflection_mm(
    *, height_mm: float, width_mm: float, thickness_after_mm: float,
    tool_diameter_mm: float, tooth_count: int, feed_per_tooth_mm: float,
    axial_depth_mm: float, radial_depth_mm: float, k_tc_mpa: float,
    k_rc_mpa: float, youngs_modulus_mpa: float, poisson_ratio: float,
    xi: float = 1.0, milling_branch: str = "down",
    enforce_thin_plate: bool = True,
) -> float:
    """Evaluate Eq. (32); thickness is explicitly the post-cut thickness t_e."""
    for name, value in (
        ("height_mm", height_mm), ("width_mm", width_mm),
        ("thickness_after_mm", thickness_after_mm),
        ("tool_diameter_mm", tool_diameter_mm),
        ("feed_per_tooth_mm", feed_per_tooth_mm),
        ("axial_depth_mm", axial_depth_mm), ("radial_depth_mm", radial_depth_mm),
        ("k_tc_mpa", k_tc_mpa), ("youngs_modulus_mpa", youngs_modulus_mpa),
    ):
        _require_finite_positive(name, value)
    if not math.isfinite(float(poisson_ratio)) or not 0.0 <= float(poisson_ratio) < 0.5:
        raise ValueError("poisson_ratio must be finite and in [0,0.5)")
    if radial_depth_mm > tool_diameter_mm:
        raise ValueError("radial_depth_mm cannot exceed tool_diameter_mm")
    wr = width_ratio(height_mm, width_mm)
    ar = aspect_ratio(height_mm, thickness_after_mm)
    if enforce_thin_plate and ar < 10.0 - 1e-12:
        raise ValueError(f"Morelli thin-plate domain requires AR=h/t >= 10; got {ar}")
    xi_v, gamma, psi = normalized_coordinates(
        z_mm=float(xi) * float(height_mm), axial_depth_mm=axial_depth_mm,
        radial_depth_mm=radial_depth_mm, height_mm=height_mm,
        tool_diameter_mm=tool_diameter_mm,
    )
    kr = cutting_force_ratio(k_tc_mpa, k_rc_mpa)
    s_factor = stationary_milling_factor(psi, kr, milling_branch)
    shape = _shape_factor(xi=xi_v, gamma=gamma, wr=wr, poisson_ratio=poisson_ratio)
    delta = (
        (3.0 * int(tooth_count) * float(feed_per_tooth_mm) / math.pi)
        * float(s_factor) * (float(k_tc_mpa) / float(youngs_modulus_mpa))
        * (float(height_mm) / float(thickness_after_mm)) ** 3 * shape
    )
    if not math.isfinite(delta) or delta < -1e-12:
        raise ArithmeticError(f"non-physical deflection result: {delta}")
    return max(0.0, float(delta))


def pass_deflection_um(radial_removal_mm: float, thickness_after_mm: float, cfg: Mapping) -> float:
    return 1000.0 * deflection_mm(
        height_mm=cfg["workpiece_height_mm"], width_mm=cfg["workpiece_width_mm"],
        thickness_after_mm=thickness_after_mm, tool_diameter_mm=cfg["tool_diameter_mm"],
        tooth_count=cfg["tooth_count"], feed_per_tooth_mm=cfg["feed_per_tooth_mm"],
        axial_depth_mm=cfg["axial_depth_mm"], radial_depth_mm=radial_removal_mm,
        k_tc_mpa=cfg["k_tc_mpa"], k_rc_mpa=cfg["k_rc_mpa"],
        youngs_modulus_mpa=cfg["youngs_modulus_mpa"], poisson_ratio=cfg["poisson_ratio"],
        xi=cfg.get("evaluation_xi", 1.0), milling_branch=cfg.get("milling_branch", "down"),
    )


def pass_deflection_um_vectorized(
    radial_removal_mm: np.ndarray, thickness_after_mm: float | np.ndarray, cfg: Mapping,
) -> np.ndarray:
    """Vectorized Eq. (32) for fixed geometry, used only to build backward sets."""
    removals = np.asarray(radial_removal_mm, dtype=float)
    thickness = np.asarray(thickness_after_mm, dtype=float)
    wr = width_ratio(cfg["workpiece_height_mm"], cfg["workpiece_width_mm"])
    gamma = cfg["axial_depth_mm"] / cfg["workpiece_height_mm"]
    xi = cfg.get("evaluation_xi", 1.0)
    if np.any(removals <= 0.0) or np.any(removals > cfg["tool_diameter_mm"]):
        raise ValueError("vectorized radial removal outside Morelli domain")
    if np.any(thickness <= 0.0) or np.any(cfg["workpiece_height_mm"] / thickness < 10.0 - 1e-12):
        raise ValueError("vectorized post-cut thickness outside AR>=10 domain")
    psi = removals / cfg["tool_diameter_mm"]
    kr = cutting_force_ratio(cfg["k_tc_mpa"], cfg["k_rc_mpa"])
    sf = stationary_milling_factor(psi, kr, cfg.get("milling_branch", "down"))
    shape = _shape_factor(xi=xi, gamma=gamma, wr=wr, poisson_ratio=cfg["poisson_ratio"])
    delta_mm = (
        (3.0 * cfg["tooth_count"] * cfg["feed_per_tooth_mm"] / math.pi)
        * sf * (cfg["k_tc_mpa"] / cfg["youngs_modulus_mpa"])
        * (cfg["workpiece_height_mm"] / thickness) ** 3 * shape
    )
    return 1000.0 * np.asarray(delta_mm, dtype=float)
