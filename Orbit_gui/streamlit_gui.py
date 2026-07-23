# Imports
import colorsys
from pathlib import Path
 
import streamlit as st
 
# Reuse the path setup and base config already built in nominal_orbit_model.py
# (repo_root, sys.path insertion of src/, lattice_folder, orbit_base_config)
# instead of duplicating it here.
from nominal_orbit_model import repo_root, orbit_base_config
 
from optics_gui.snapshot import build_machine_snapshot, copy_snapshot_config
from optics_gui.orbit_correction import bpm_measurements_from_twiss
 
st.set_page_config(page_title="Orbit models", layout="wide")
 
 
# ---------------------------------------------------------------------------
# Colour theme: a single hue slider drives every colour on the page
# ---------------------------------------------------------------------------
def hsl_to_hex(hue_deg, saturation, lightness):
    """Convert HSL (hue in degrees, saturation/lightness in 0-1) to a hex colour."""
    r, g, b = colorsys.hls_to_rgb((hue_deg % 360) / 360, lightness, saturation)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))
 
 
def build_theme(hue_deg):
    return {
        "primary": hsl_to_hex(hue_deg, 0.60, 0.42),
        "accent": hsl_to_hex(hue_deg + 40, 0.65, 0.55),
        "page_bg": hsl_to_hex(hue_deg, 0.35, 0.97),
        "sidebar_bg": hsl_to_hex(hue_deg, 0.30, 0.93),
        "card_bg": hsl_to_hex(hue_deg, 0.25, 0.99),
    }
 
 
def apply_theme_css(theme):
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {theme['page_bg']};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {theme['sidebar_bg']};
        }}
        h1, h2, h3 {{
            color: {theme['primary']};
        }}
        div[data-testid="stVerticalBlock"] > div:has(> div.stDataFrame),
        div[data-testid="stMetric"] {{
            background-color: {theme['card_bg']};
            border-radius: 0.5rem;
            padding: 0.5rem;
        }}
        div.stButton > button {{
            background-color: {theme['primary']};
            color: white;
            border: none;
        }}
        div.stButton > button:hover {{
            background-color: {theme['accent']};
            color: white;
        }}
        /* Slider handle/track colour. Selector names come from Streamlit's
           internal component markup and may shift between versions. */
        div[data-baseweb="slider"] div[role="slider"] {{
            background-color: {theme['primary']} !important;
        }}
        div[data-baseweb="slider"] > div > div {{
            background-color: {theme['accent']} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
 
 
st.sidebar.header("Appearance")
theme_hue = st.sidebar.slider(
    "Theme colour",
    min_value=0,
    max_value=360,
    value=210,
    help="Pick an accent hue (0-360 on the colour wheel) for the whole page.",
)
theme = build_theme(theme_hue)
apply_theme_css(theme)
 
st.title("Orbit GUI")
 
# ---------------------------------------------------------------------------
# Sidebar controls: cycle time and tune (set qx / set qy)
# ---------------------------------------------------------------------------
st.sidebar.header("Machine settings")
 
cycle_time_ms = st.sidebar.slider(
    "Cycle time [ms]",
    min_value=0.0,
    max_value=10.0,
    value=0.0,
    step=0.1,
    help="Time through the RCS acceleration cycle (0-10 ms).",
)
 
requested_qx = st.sidebar.number_input(
    "Set Qx (horizontal tune)",
    value=4.31,
    step=0.01,
    format="%.3f",
)
 
requested_qy = st.sidebar.number_input(
    "Set Qy (vertical tune)",
    value=3.83,
    step=0.01,
    format="%.3f",
)
 
jan26_error_table = repo_root / "Dev" / "Error_Tables" / "jan26_survey_corrected.tfs"
 
 
# ---------------------------------------------------------------------------
# Cached snapshot builders
#
# build_machine_snapshot(...) runs the full MAD-X model, which is expensive.
# st.cache_resource keys the cache on the function arguments, so MAD-X is
# only re-run when cycle time, tune, or error table selection actually change.
# ---------------------------------------------------------------------------
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
        error_table_paths=[str(jan26_error_table)],
        orbit_correction_configs=[],
    )
    return build_machine_snapshot(config)
 
 
@st.cache_resource(show_spinner="Sampling BPMs from the model orbit...")
def get_measured_bpm_table(cycle_time_ms, requested_qx, requested_qy):
    # The "measured" orbit here is a worked example: real BPM readings would
    # come from an archiver/EPICS export via optics_gui.io instead. To keep
    # cycle time / tune meaningful for this mode, BPM positions are sampled
    # from the model orbit at the chosen cycle time and tune, then a fixed
    # example displacement pattern is overlaid on top.
    snapshot = get_nominal_orbit_snapshot(cycle_time_ms, requested_qx, requested_qy)
    bpm_table = bpm_measurements_from_twiss(snapshot.table("twiss"), plane="H").head(8).copy()
    example_offsets_mm = [0.8, -0.6, 1.1, -0.9, 0.4, -0.3, 0.7, -0.5]
    bpm_table["closed_orbit_mm"] = example_offsets_mm[: len(bpm_table)]
    return bpm_table
 
 
# ---------------------------------------------------------------------------
# Plotting functions per mode
#
# Line colours are drawn from the same theme as the rest of the page, so the
# x/y traces shift together with the hue slider.
# ---------------------------------------------------------------------------
line_colors = [theme["primary"], theme["accent"]]
 
 
def nominal_orbit_plot():
    st.write("The ideal closed orbit with no errors, at the chosen cycle time and tune.")
    snapshot = get_nominal_orbit_snapshot(cycle_time_ms, requested_qx, requested_qy)
    st.dataframe(snapshot.table("orbit_summary"))
    st.line_chart(data=snapshot.table("orbit"), y=["x_mm", "y_mm"], x="s", color=line_colors)
 
 
def error_table_orbit_plot():
    st.write(
        "The closed orbit calculated after applying an error table (magnet "
        "misalignments/field errors) to the model at the chosen cycle time "
        "and tune. This shows the simulated orbit distortion caused by known "
        "machine imperfections."
    )
    snapshot = get_error_table_orbit_snapshot(cycle_time_ms, requested_qx, requested_qy)
    st.dataframe(snapshot.table("orbit_summary"))
    st.line_chart(data=snapshot.table("orbit"), y=["x_mm", "y_mm"], x="s", color=line_colors)
 
 
def measured_orbit_plot():
    st.write(
        "Example measured BPM orbit, sampled at real BPM locations for the "
        "chosen cycle time and tune."
    )
    bpm_table = get_measured_bpm_table(cycle_time_ms, requested_qx, requested_qy)
    st.line_chart(data=bpm_table, x="s", y="closed_orbit_mm", color=[theme["primary"]])
 
 
orbit_mode_selection = st.selectbox(
    label="Select orbit source mode", options=["Nominal", "Error Table", "Measured"]
)
 
if orbit_mode_selection == "Nominal":
    nominal_orbit_plot()
elif orbit_mode_selection == "Error Table":
    error_table_orbit_plot()
elif orbit_mode_selection == "Measured":
    measured_orbit_plot()