# Imports
import colorsys
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# Setup repository root and import path for the packaged backend.
repo_root = Path(__file__).resolve().parent.parent
if not (repo_root / "Dev" / "12_IO").is_dir():
    repo_root = Path.cwd()
    if repo_root.name == "12_IO":
        repo_root = repo_root.parents[1]
    elif (repo_root / "Dev" / "12_IO").is_dir():
        pass

orbit_gui_path = repo_root / "Orbit_gui"
if str(orbit_gui_path) not in sys.path:
    sys.path.insert(0, str(orbit_gui_path))

from nominal_orbit_model import repo_root as guide_repo_root, orbit_base_config
if guide_repo_root is not None:
    repo_root = guide_repo_root

src_path = repo_root / "src"
if src_path.is_dir() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from optics_gui.orbit_correction import (
    bpm_measurements_from_twiss,
    normalise_corrector_selection,
    plot_corrector_suggestions,
    plot_orbit_with_bpm,
)
from optics_gui.snapshot import (
    SnapshotOrbitCorrectionConfig,
    build_machine_snapshot,
    copy_snapshot_config,
)


def build_theme(hue):
    return {
        "accent": f"hsl({hue}, 80%, 45%)",
        "accent_soft": f"hsl({hue}, 70%, 92%)",
        "text": "#1f2937",
        "background": "#f8fafc",
    }


def apply_theme_css(theme):
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {theme['background']}; color: {theme['text']}; }}
        div[data-testid="stSidebar"] {{ background: {theme['accent_soft']}; }}
        .stButton > button, .stSelectbox > div > div, .stSlider > div > div {{ border-color: {theme['accent']}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="ISIS Orbit explorer", layout="wide")
st.title("ISIS Orbit explorer")

error_table_path = repo_root / "Dev" / "Error_Tables" / "jan26_survey_corrected.tfs"

nominal_snapshot_config = copy_snapshot_config(
    orbit_base_config,
    snapshot_id="student_nominal_orbit",
    label="Nominal orbit snapshot",
    error_table_paths=[],
    orbit_correction_configs=[],
    run_envelope=False,
    run_aperture=False,
)

error_snapshot_config = copy_snapshot_config(
    orbit_base_config,
    snapshot_id="student_error_table_orbit",
    label="Error-table orbit snapshot",
    error_table_paths=[str(error_table_path)] if error_table_path.exists() else [],
    orbit_correction_configs=[],
    run_envelope=False,
    run_aperture=False,
)


@st.cache_resource(show_spinner="Running MAD-X model for nominal orbit...")
def get_nominal_orbit_snapshot(cycle_time_ms, requested_qx, requested_qy):
    config = copy_snapshot_config(
        orbit_base_config,
        snapshot_id="gui_nominal_orbit",
        label="GUI nominal orbit",
        cycle_time_ms=cycle_time_ms,
        requested_qx=requested_qx,
        requested_qy=requested_qy,
        error_table_paths=[],
        orbit_correction_configs=[],
        run_envelope=False,
        run_aperture=False,
    )
    return build_machine_snapshot(config)


@st.cache_resource(show_spinner="Running MAD-X model with error table...")
def get_error_table_orbit_snapshot(cycle_time_ms, requested_qx, requested_qy):
    config = copy_snapshot_config(
        orbit_base_config,
        snapshot_id="gui_error_table_orbit",
        label="GUI error-table orbit",
        cycle_time_ms=cycle_time_ms,
        requested_qx=requested_qx,
        requested_qy=requested_qy,
        error_table_paths=[str(error_table_path)] if error_table_path.exists() else [],
        orbit_correction_configs=[],
        run_envelope=False,
        run_aperture=False,
    )
    return build_machine_snapshot(config)


@st.cache_resource(show_spinner="Sampling BPMs from the model orbit...")
def get_measured_bpm_table(cycle_time_ms, requested_qx, requested_qy, plane="H"):
    snapshot = get_nominal_orbit_snapshot(cycle_time_ms, requested_qx, requested_qy)
    bpm_table = bpm_measurements_from_twiss(snapshot.table("twiss"), plane=plane).head(8).copy()
    example_offsets_mm = [0.8, -0.6, 1.1, -0.9, 0.4, -0.3, 0.7, -0.5]
    bpm_table["closed_orbit_mm"] = example_offsets_mm[: len(bpm_table)]
    return bpm_table


def get_editable_data_editor():
    return getattr(st, "data_editor", None) or getattr(st, "experimental_data_editor", None)


def editable_bpm_table(bpm_table, key):
    data_editor = get_editable_data_editor()
    if data_editor is None:
        st.warning("Streamlit version does not support editable BPM tables. Showing a static table instead.")
        st.dataframe(bpm_table, width="stretch")
        return bpm_table

    edited = data_editor(
        bpm_table,
        key=key,
        num_rows="fixed",
        use_container_width=True,
    )
    return edited


def select_correctors_for_demo(plane, names):
    correctors = normalise_corrector_selection(plane=plane)
    selected = {name.lower() for name in names}
    correctors["enabled"] = correctors["corrector"].str.lower().isin(selected)
    return correctors


def get_orbit_snapshot(key):
    cache = st.session_state.setdefault("orbit_gui_snapshots", {})
    if key not in cache:
        if key == "nominal":
            cache[key] = build_machine_snapshot(nominal_snapshot_config)
        elif key == "error":
            cache[key] = build_machine_snapshot(error_snapshot_config)
        elif key == "correction":
            error_snapshot = get_orbit_snapshot("error")
            bpm_h = bpm_measurements_from_twiss(error_snapshot.table("twiss"), plane="H")
            bpm_v = bpm_measurements_from_twiss(error_snapshot.table("twiss"), plane="V")
            h_correctors = select_correctors_for_demo(
                "H",
                ["r0hd1_kick", "r3hd1_kick", "r5hd1_kick", "r9hd1_kick"],
            )
            v_correctors = select_correctors_for_demo(
                "V",
                ["r0vd1_kick", "r3vd1_kick", "r5vd1_kick", "r9vd1_kick"],
            )
            correction_snapshot_config = copy_snapshot_config(
                base_snapshot_config,
                snapshot_id="student_error_table_orbit_correction",
                label="Error-table orbit correction snapshot",
                error_table_paths=[str(error_table_path)] if error_table_path.exists() else [],
                orbit_correction_configs=[
                    SnapshotOrbitCorrectionConfig(
                        plane="H",
                        label="horizontal_error_table_orbit",
                        bpm_measurements=bpm_h,
                        correctors=h_correctors,
                    ),
                    SnapshotOrbitCorrectionConfig(
                        plane="V",
                        label="vertical_error_table_orbit",
                        bpm_measurements=bpm_v,
                        correctors=v_correctors,
                    ),
                ],
            )
            cache[key] = build_machine_snapshot(correction_snapshot_config)
        else:
            raise KeyError(f"Unknown orbit snapshot key: {key}")
    return cache[key]


def orbit_line_chart(df, y_columns, title):
    if df is None or df.empty:
        st.write("No orbit data available.")
        return
    chart_df = df.set_index("s")[y_columns].copy()
    chart_df.index.name = "s"
    st.line_chart(chart_df)


def display_snapshot_tables(snapshot, title):
    st.header(title)
    with st.expander("Orbit summary and tables", expanded=True):
        st.subheader("Orbit summary")
        st.dataframe(snapshot.table("orbit_summary"), width="stretch")
        st.subheader("Orbit table")
        st.dataframe(snapshot.table("orbit"), width="stretch")
        if "twiss" in snapshot.available_tables():
            st.subheader("TWISS table (first 20 rows)")
            st.dataframe(snapshot.table("twiss").head(20), width="stretch")


def display_correction_results(snapshot):
    if not snapshot.orbit_correction_results:
        st.warning("No orbit correction results are available for this snapshot.")
        return

    st.header("Correction suggestions")
    st.subheader("Correction summary")
    st.dataframe(snapshot.table("orbit_correction_summary"), width="stretch")

    st.subheader("Corrector suggestion table")
    st.dataframe(snapshot.table("orbit_correction_correctors"), width="stretch")

    st.subheader("BPM before/after comparison")
    st.dataframe(snapshot.table("orbit_correction_bpm_comparison"), width="stretch")

    st.subheader("Before / after monitor summaries")
    col1, col2 = st.columns(2)
    with col1:
        st.write("Before correction")
        st.dataframe(snapshot.table("orbit_correction_before"), width="stretch")
    with col2:
        st.write("After correction")
        st.dataframe(snapshot.table("orbit_correction_after"), width="stretch")

    for result in snapshot.orbit_correction_results:
        st.subheader(f"Orbit correction: {result.label} ({result.plane})")
        fig, ax = plt.subplots(figsize=(11, 4))
        plot_orbit_with_bpm(
            result.result.measured_twiss_df,
            result.result.bpm_measurements,
            plane=result.plane,
            ax=ax,
            label="Measured orbit",
            title=f"{result.plane} plane measured orbit and correction suggestion",
        )
        plot_orbit_with_bpm(
            result.result.corrected_twiss_df,
            result.result.bpm_measurements,
            plane=result.plane,
            ax=ax,
            label="Corrected orbit",
            orbit_kwargs={"linestyle": "--"},
        )
        st.pyplot(fig) 
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4))
        plot_corrector_suggestions(
            result.result.correctors,
            ax=ax,
            value="delta_current_A",
            title=f"{result.plane} corrector current suggestions",
        )
        st.pyplot(fig)
        plt.close(fig)

        if not snapshot.table("orbit_correction_warnings").empty:
            st.subheader("Correction warnings")
            st.dataframe(snapshot.table("orbit_correction_warnings"), use_container_width=True)


with st.sidebar:
    st.header("Appearance")
    theme_hue = st.slider(
        "Theme colour",
        min_value=0,
        max_value=360,
        value=210,
        help="Pick an accent hue (0-360 on the colour wheel) for the whole page.",
    )
    theme = build_theme(theme_hue)
    apply_theme_css(theme)

    st.header("Machine settings")
    cycle_time_ms = st.slider(
        "Cycle time [ms]",
        min_value=0.0,
        max_value=10.0,
        value=0.0,
        step=0.1,
        help="Time through the RCS acceleration cycle (0-10 ms).",
    )
    requested_qx = st.number_input(
        "Set Qx (horizontal tune)",
        value=4.31,
        step=0.01,
        format="%.3f",
    )
    requested_qy = st.number_input(
        "Set Qy (vertical tune)",
        value=3.83,
        step=0.01,
        format="%.3f",
    )

    st.header("Orbit source")
    orbit_mode = st.selectbox(
        "Select orbit source mode",
        ["Nominal", "Error Table", "Measured"],
    )
    enable_correction = st.checkbox("Show correction suggestions", value=True)
    bpm_plane = st.selectbox("Measured BPM plane", ["H", "V"], index=0)
    show_only_enabled_bpm = st.checkbox("Plot only enabled BPMs", value=True)
    show_bpm_editor = st.checkbox("Show editable BPM table", value=True)

st.write(
    "This GUI displays the nominal orbit, the error-table orbit, and a simple measured BPM orbit example. "
    "The error-table mode can also show read-only correction suggestions using the packaged optics backend."
)

try:
    nominal_snapshot = get_nominal_orbit_snapshot(cycle_time_ms, requested_qx, requested_qy)
    error_snapshot = get_error_table_orbit_snapshot(cycle_time_ms, requested_qx, requested_qy)
except Exception as exc:
    st.error(f"Failed to build base orbit snapshots: {exc}")
    raise

if orbit_mode == "Nominal":
    st.subheader("Nominal model orbit")
    orbit_line_chart(nominal_snapshot.table("orbit"), ["x_mm", "y_mm"], "Nominal orbit")
    display_snapshot_tables(nominal_snapshot, "Nominal orbit model")
elif orbit_mode == "Error Table":
    st.subheader("Error-table model orbit")
    orbit_line_chart(error_snapshot.table("orbit"), ["x_mm", "y_mm"], "Error-table orbit")
    display_snapshot_tables(error_snapshot, "Error-table orbit model")
    if enable_correction:
        try:
            correction_snapshot = get_orbit_snapshot("correction")
            display_correction_results(correction_snapshot)
        except Exception as exc:
            st.error(f"Failed to build orbit correction snapshot: {exc}")
elif orbit_mode == "Measured":
    st.subheader("Measured BPM orbit example")
    measured_bpm = get_measured_bpm_table(cycle_time_ms, requested_qx, requested_qy, plane=bpm_plane)
    if show_bpm_editor:
        measured_bpm = editable_bpm_table(measured_bpm, key="measured_bpm_table")
    else:
        st.dataframe(measured_bpm, width="stretch")

    if show_only_enabled_bpm:
        measured_bpm = measured_bpm[measured_bpm["enabled"]].copy()

    if measured_bpm.empty:
        st.warning("No enabled BPM measurements are available.")
    else:
        st.dataframe(measured_bpm, width="stretch")
        chart_df = measured_bpm.set_index("s")["closed_orbit_mm"].copy()
        chart_df.index.name = "s"
        st.line_chart(chart_df)


#RUN THIS VIA cd C:\Users\Visitor\Desktop\Work-experience-2026-ISIS-RCS-optics-GUI && python -m streamlit run Orbit_gui/streamlit_gui.py, in your gitbash!