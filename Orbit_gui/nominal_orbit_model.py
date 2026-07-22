#Imports
from IPython.display import display
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parent.parent
if not (repo_root / "Dev" / "12_IO").is_dir():
    repo_root = Path.cwd()
    if repo_root.name == "12_IO":
        repo_root = repo_root.parents[1]
    elif (repo_root / "Dev" / "12_IO").is_dir():
        pass

src_path = repo_root / "src"
if src_path.is_dir() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

RUN_FULL_MODEL = True
RUN_ORBIT_CORRECTION_EXAMPLE = True

print(f"repo_root = {repo_root}")
print(f"RUN_FULL_MODEL = {RUN_FULL_MODEL}")
print(f"RUN_ORBIT_CORRECTION_EXAMPLE = {RUN_ORBIT_CORRECTION_EXAMPLE}")

error_orbit_snapshot = None
orbit_snapshot = None
qc_zeroed_orbit_snapshot = None
measured_orbit_snapshot = None

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from optics_gui.cycle_time import RCSRamp
from optics_gui.machine_state import MachineState
from optics_gui.correctors import current_to_kick_rad, kick_rad_to_current
from optics_gui.errors import (
    read_error_table,
    summarise_error_table,
    write_zeroed_error_table_copy,
    zero_error_table_magnets,
)
from optics_gui.error_plots import error_table_to_misalignment_offsets, plot_error_table_misalignment_offsets
from optics_gui.tune import (
    build_tune_programme_table,
    build_working_point_table,
    generate_resonance_lines,
    evaluate_resonance_proximity,
    make_tune_diagram_inputs,
)
from optics_gui.snapshot import (
    SnapshotConfig,
    SnapshotSeriesConfig,
    SnapshotOrbitCorrectionConfig,
    build_machine_snapshot,
    build_full_cycle_snapshot_series,
    copy_snapshot_config,
)
from optics_gui.envelope import EnvelopeInputs, plot_envelope, plot_sigma, plot_envelope_comparison
from optics_gui.orbit_correction import (
    bpm_measurements_from_twiss,
    normalise_corrector_selection,
    plot_corrector_suggestions,
    plot_orbit_with_bpm,
)
from optics_gui.aperture import (
    read_source_aperture_csv,
    plot_aperture_envelope_with_margin,
    plot_margin,
)
from optics_gui.tune_plots import plot_tune_diagram_inputs
from optics_gui.io import (
    config_to_record,
    config_from_record,
    corrector_settings_from_table,
    normalise_bpm_table,
    normalise_corrector_table,
    snapshot_configs_from_table,
    write_snapshot_bundle,
    read_run_bundle,
    write_snapshot_config,
    read_snapshot_config,
    series_config_to_record,
    series_config_from_record,
    write_snapshot_series_config,
    read_snapshot_series_config,
)

lattice_folder = repo_root / "Dev" / "Lattice_Files" / "00_Simplified_Lattice"

orbit_base_config = SnapshotConfig(
    cycle_time_ms=0.0,
    label="orbit_base_config",
    case="nominal",
    snapshot_id="orbit_base_config",
    lattice_folder=str(lattice_folder),
    output_dir=str(repo_root / "Dev" / "12_IO" / "student_runs" / "orbit"),
)

print(orbit_base_config.resolved_label())
print("Imports worked")


# %%
#simplest orbit config, try this first  THIS IS NOMINAL ERROR CONGIG WAHHHHHH
nominal_orbit_config = copy_snapshot_config(
    orbit_base_config,
    snapshot_id="student_nominal_orbit",
    label="student nominal orbit",
    error_table_paths=[],
    orbit_correction_configs=[],
)

if RUN_FULL_MODEL:
    nominal_orbit_snapshot = build_machine_snapshot(nominal_orbit_config)
    orbit_snapshot = nominal_orbit_snapshot
    display(nominal_orbit_snapshot.table("orbit_summary"))
    display(nominal_orbit_snapshot.table("orbit").head())
else:
    print("Set RUN_FULL_MODEL = True to run MAD-X and create nominal_orbit_snapshot.")
    print("The Streamlit orbit GUI will mainly consume: snapshot.table('orbit') and snapshot.table('orbit_summary').")

# %%
#error table model 
# Bare nominal model orbit plot
if RUN_FULL_MODEL:
    ax = nominal_orbit_snapshot.table("orbit").plot(x="s", y=["x_mm", "y_mm"], figsize=(10, 4))
    ax.set_xlabel("s [m]")
    ax.set_ylabel("closed orbit [mm]")
    ax.set_title("Bare nominal model orbit")
else:
    print("Bare orbit plot skipped because RUN_FULL_MODEL is False.")