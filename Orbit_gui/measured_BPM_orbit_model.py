from nominal_orbit_model import  RUN_FULL_MODEL
import pandas as pd
from optics_gui.snapshot import build_machine_snapshot
from nominal_orbit_model import orbit_base_config
from pathlib import Path
import sys

repo_root = Path.cwd()
if not (repo_root / "Dev" / "07_Orbit_Correction").exists():
    repo_root = repo_root.parent

sys.path.insert(0, str(repo_root / "Orbit_gui"))
sys.path.insert(0, str(repo_root / "Dev" / "07_Orbit_Correction"))

from optics_gui.orbit_correction import bpm_measurements_from_twiss, plot_orbit_with_bpm, normalise_bpm_measurements

import importlib.util
from pathlib import Path

repo_root = globals().get("repo_root", Path.cwd())
if not (repo_root / "Dev" / "07_Orbit_Correction").exists():
    repo_root = repo_root.parent

module_path = repo_root / "Orbit_gui" / "nominal_orbit_model.py"

spec = importlib.util.spec_from_file_location("nominal_orbit_model", module_path)
nominal_orbit_model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nominal_orbit_model)

RUN_FULL_MODEL = nominal_orbit_model.RUN_FULL_MODEL
nominal_orbit_snapshot = nominal_orbit_model.nominal_orbit_snapshot

print(f"nominal_orbit_snapshot: {nominal_orbit_snapshot}")

if RUN_FULL_MODEL:
    measured_bpm_table = bpm_measurements_from_twiss(nominal_orbit_snapshot.table("twiss"), plane="H").head(8)
    measured_bpm_table = measured_bpm_table.copy()
    measured_bpm_table["closed_orbit_mm"] = [0.8, -0.6, 1.1, -0.9, 0.4, -0.3, 0.7, -0.5]
else:
    raw_measured_orbit = pd.DataFrame(
        [
            {"bpm": "sp0_r0hm1", "plane": "H", "closed_orbit_mm": 0.8, "closed_orbit_mm_err": 0.1, "s": 0.730500, "enabled": True},
            {"bpm": "sp0_r0hm2", "plane": "H", "closed_orbit_mm": -0.6, "closed_orbit_mm_err": 0.1, "s": 5.971000, "enabled": True},
            {"bpm": "sp1_r1hm1", "plane": "H", "closed_orbit_mm": 1.1, "closed_orbit_mm_err": 0.1, "s": 22.285282, "enabled": True},
            {"bpm": "sp1_r1hm2", "plane": "H", "closed_orbit_mm": -0.9, "closed_orbit_mm_err": 0.1, "s": 24.416282, "enabled": True},
        ]
    )
    measured_bpm_table = normalise_bpm_measurements(raw_measured_orbit)

measured_bpm_table = measured_bpm_table.copy()

from optics_gui.snapshot import copy_snapshot_config


if RUN_FULL_MODEL:
    jan26_error_table = repo_root / "Dev" / "Error_Tables" / "jan26_survey_corrected.tfs"
    
    error_orbit_config = copy_snapshot_config(
        orbit_base_config,
        snapshot_id="jan26_error_orbit",
        label="jan26 error orbit",
        error_table_paths=[str(jan26_error_table)],
        orbit_correction_configs=[],
    )
    
    error_orbit_snapshot = build_machine_snapshot(error_orbit_config)
    print(f"Created error_orbit_snapshot with error table: {jan26_error_table.name}")
else:
    print("error_orbit_snapshot creation skipped because RUN_FULL_MODEL is False.")

import matplotlib.pyplot as plt
from IPython.display import display


if RUN_FULL_MODEL:
    jan26_bpm_match = bpm_measurements_from_twiss(error_orbit_snapshot.table("twiss"), plane="H").head(8)
    ax = plot_orbit_with_bpm(
        error_orbit_snapshot.table("twiss"),
        jan26_bpm_match,
        plane="H",
        title="Jan26 error-table orbit sampled at real BPMs",
    )
else:
    jan26_bpm_match = measured_bpm_table.copy()
    print("Jan26 BPM sampling plot skipped because RUN_FULL_MODEL is False.")