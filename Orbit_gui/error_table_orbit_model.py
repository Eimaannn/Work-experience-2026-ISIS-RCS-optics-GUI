#Imports
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

# Error table orbit mode
try:
    from IPython.display import display
except ImportError:
    def display(obj):
        print(obj)

jan26_error_table = repo_root / "Dev" / "Error_Tables" / "jan26_survey_corrected.tfs"

jan26_errors = read_error_table(jan26_error_table)
jan26_error_summary = summarise_error_table(jan26_errors)

print(jan26_error_table)
print("rows:", jan26_error_summary["n_rows"])
print("unique names:", jan26_error_summary["n_unique_names"])
print("max |dx| [m]:", jan26_error_summary["max_abs_dx"])
print("max |dy| [m]:", jan26_error_summary["max_abs_dy"])

display(jan26_errors[["name", "dx", "dy", "dphi", "dtheta", "dpsi"]].head())

jan26_horizontal_misalignments = error_table_to_misalignment_offsets(jan26_errors, plane="x")
jan26_vertical_misalignments = error_table_to_misalignment_offsets(jan26_errors, plane="y")

display(
    jan26_horizontal_misalignments[
        ["name", "magnet", "S_centre", "offset_centre", "angle"]
    ].rename(columns={"offset_centre": "x_offset_mm", "angle": "x_angle_mrad"}).head()
)
display(
    jan26_vertical_misalignments[
        ["name", "magnet", "S_centre", "offset_centre", "angle"]
    ].rename(columns={"offset_centre": "y_offset_mm", "angle": "y_angle_mrad"}).head()
)

plot_error_table_misalignment_offsets(
    jan26_errors,
    plane="x",
    title="Jan26 horizontal magnet misalignments",
)
plot_error_table_misalignment_offsets(
    jan26_errors,
    plane="y",
    title="Jan26 vertical magnet misalignments",
)

edited_error_table_dir = repo_root / "madx_runs" / "student_error_table_edits"

# One-off DataFrame edit, useful for previewing exactly what will be zeroed.
sp0_qds_zeroed, sp0_qds_names = zero_error_table_magnets(
    jan26_errors,
    names=["SP0_QDS"],
    return_zeroed_names=True,
)
print("single magnet zeroed:", sp0_qds_names)

# Timestamped files for MAD-X: single magnet, multiple named magnets, and a full family.
single_magnet_edit = write_zeroed_error_table_copy(
    jan26_error_table,
    output_dir=edited_error_table_dir,
    names=["SP0_QDS"],
    suffix="sp0_qc_zeroed",
    return_table=True,
)
named_magnets_edit = write_zeroed_error_table_copy(
    jan26_error_table,
    output_dir=edited_error_table_dir,
    names=["SP0_QD", "SP1_QF", "SP3_DIP"],
    suffix="named_magnets_zeroed",
    return_table=True,
)
qc_family_edit = write_zeroed_error_table_copy(
    jan26_error_table,
    output_dir=edited_error_table_dir,
    families=["QC"],
    suffix="all_qc_zeroed",
    return_table=True,
)

print("single magnet file:", single_magnet_edit["path"])
print("named magnets file:", named_magnets_edit["path"])
print("QC family file:", qc_family_edit["path"])
print("QC rows zeroed:", qc_family_edit["zeroed_names"])

# Visual check: original table versus the all-QC-zeroed copy, in both planes.
plot_error_table_misalignment_offsets(
    jan26_errors,
    plane="x",
    title="Jan26 horizontal misalignments before QC removal",
)
plot_error_table_misalignment_offsets(
    qc_family_edit["table"],
    plane="x",
    title="Jan26 horizontal misalignments after QC removal",
)
plot_error_table_misalignment_offsets(
    jan26_errors,
    plane="y",
    title="Jan26 vertical misalignments before QC removal",
)
plot_error_table_misalignment_offsets(
    qc_family_edit["table"],
    plane="y",
    title="Jan26 vertical misalignments after QC removal",
)

display(
    qc_family_edit["table"]
    .loc[qc_family_edit["table"]["name"].str.endswith("_QDS"), ["name", "dx", "dy", "dphi", "dtheta", "dpsi"]]
    .head()
)

jan26_error_table = repo_root / "Dev" / "Error_Tables" / "jan26_survey_corrected.tfs"

error_orbit_config = copy_snapshot_config(
    orbit_base_config,
    snapshot_id="student_error_table_orbit",
    label="student error-table orbit",
    error_table_paths=[str(jan26_error_table)],
    orbit_correction_configs=[],
)

print(jan26_error_table)
print("exists:", jan26_error_table.is_file())

if RUN_FULL_MODEL:
    try:
        error_orbit_snapshot = build_machine_snapshot(error_orbit_config)
        orbit_snapshot = error_orbit_snapshot
        display(error_orbit_snapshot.table("orbit_summary"))
        display(error_orbit_snapshot.table("orbit").head())
    except Exception as exc:
        print(f"Full model run skipped due to error: {exc}")
        error_orbit_snapshot = None
        orbit_snapshot = None
else:
    print("Set RUN_FULL_MODEL = True to run MAD-X with the error table.")
    print("This mode displays the model orbit after applying error_table_paths.")

# Jan26 error-table model orbit plot
if RUN_FULL_MODEL and error_orbit_snapshot is not None:
    ax = error_orbit_snapshot.table("orbit").plot(x="s", y=["x_mm", "y_mm"], figsize=(10, 4))
    ax.set_xlabel("s [m]")
    ax.set_ylabel("closed orbit [mm]")
    ax.set_title("Model orbit after Jan26 survey error table")
else:
    print("Error-table orbit plot skipped because RUN_FULL_MODEL is False or the full model could not be built.")
 
if RUN_FULL_MODEL and error_orbit_snapshot is not None:
    try:
        qc_zeroed_orbit_config = copy_snapshot_config(
            orbit_base_config,
            snapshot_id="student_error_table_orbit_without_qc",
            label="student error-table orbit without QC rows",
            error_table_paths=[qc_family_edit["path"]],
            orbit_correction_configs=[],
        )
        qc_zeroed_orbit_snapshot = build_machine_snapshot(qc_zeroed_orbit_config)

        original_orbit = error_orbit_snapshot.table("orbit")[["name", "s", "x_mm", "y_mm"]]
        qc_zeroed_orbit = qc_zeroed_orbit_snapshot.table("orbit")[["name", "x_mm", "y_mm"]]
        qc_orbit_difference = original_orbit.merge(
            qc_zeroed_orbit,
            on="name",
            suffixes=("_with_qc", "_without_qc"),
        )
        qc_orbit_difference["delta_x_mm"] = qc_orbit_difference["x_mm_without_qc"] - qc_orbit_difference["x_mm_with_qc"]
        qc_orbit_difference["delta_y_mm"] = qc_orbit_difference["y_mm_without_qc"] - qc_orbit_difference["y_mm_with_qc"]

        qc_orbit_difference_summary = pd.DataFrame(
            [
                {
                    "max_abs_delta_x_mm": qc_orbit_difference["delta_x_mm"].abs().max(),
                    "max_abs_delta_y_mm": qc_orbit_difference["delta_y_mm"].abs().max(),
                    "rms_delta_x_mm": (qc_orbit_difference["delta_x_mm"] ** 2).mean() ** 0.5,
                    "rms_delta_y_mm": (qc_orbit_difference["delta_y_mm"] ** 2).mean() ** 0.5,
                }
            ]
        )
        display(qc_orbit_difference_summary)
        assert qc_orbit_difference_summary[["max_abs_delta_x_mm", "max_abs_delta_y_mm"]].to_numpy().max() > 0.0

        orbit_before_after = qc_orbit_difference[[
            "s",
            "x_mm_with_qc",
            "x_mm_without_qc",
            "y_mm_with_qc",
            "y_mm_without_qc",
        ]].rename(
            columns={
                "x_mm_with_qc": "x with QC",
                "x_mm_without_qc": "x without QC",
                "y_mm_with_qc": "y with QC",
                "y_mm_without_qc": "y without QC",
            }
        )
        ax_before_after = orbit_before_after.plot(
            x="s",
            y=["x with QC", "x without QC", "y with QC", "y without QC"],
            figsize=(10, 4),
        )
        ax_before_after.set_xlabel("s [m]")
        ax_before_after.set_ylabel("closed orbit [mm]")
        ax_before_after.set_title("Closed orbit before and after QC error-table removal")

        ax = qc_orbit_difference.plot(x="s", y=["delta_x_mm", "delta_y_mm"], figsize=(10, 4))
        ax.set_xlabel("s [m]")
        ax.set_ylabel("orbit change after zeroing QC rows [mm]")
        ax.set_title("MAD-X check: Jan26 table minus all-QC-zeroed table")
    except Exception as exc:
        print(f"QC-zeroed orbit comparison skipped due to error: {exc}")
else:
    print("QC-zeroed orbit comparison skipped because RUN_FULL_MODEL is False or the full model could not be built.")

# Provide a concrete snapshot object for the orbit-correction example section.
if error_orbit_snapshot is not None:
    measured_orbit_snapshot = error_orbit_snapshot
else:
    measured_orbit_snapshot = None

if RUN_FULL_MODEL and RUN_ORBIT_CORRECTION_EXAMPLE and measured_orbit_snapshot is not None:
    print("Prepared measured_orbit_snapshot for orbit-correction workflow")
    available_tables = measured_orbit_snapshot.available_tables()
    print("Orbit correction tables available:", available_tables)

    if "orbit_correction_summary" in available_tables:
        display(measured_orbit_snapshot.table("orbit_correction_summary"))
    if "orbit_correction_bpm" in available_tables:
        display(measured_orbit_snapshot.table("orbit_correction_bpm"))
    if "orbit_correction_bpm_comparison" in available_tables:
        display(measured_orbit_snapshot.table("orbit_correction_bpm_comparison"))
    if "orbit_correction_correctors" in available_tables:
        display(measured_orbit_snapshot.table("orbit_correction_correctors"))
    if "orbit_correction_before" in available_tables:
        display(measured_orbit_snapshot.table("orbit_correction_before"))
    if "orbit_correction_after" in available_tables:
        display(measured_orbit_snapshot.table("orbit_correction_after"))
else:
    print("Orbit correction example skipped because RUN_FULL_MODEL or RUN_ORBIT_CORRECTION_EXAMPLE is False, or no snapshot was built.")

