#Imports
import streamlit as st
from error_table_orbit_model import error_orbit_snapshot
from nominal_orbit_model import nominal_orbit_snapshot
from measured_BPM_orbit_model import measured_bpm_table

#Website formatting
st.title("Orbit GUI")

#Error table model orbit plot
def error_table_orbit_plot():
    st.write("The closed orbit calculated after applying an error table taking into account factors such as  magnet misalignments or field errors to the model. This shows the simulated orbit distortion caused by known machine imperfections.")
    st.line_chart(data = error_orbit_snapshot.table("orbit"), y = ["x_mm", "y_mm"], x = "s")

#Nominal model orbit plot
def nominal_orbit_plot():
    st.write("The ideal closed orbit with no errors")
    st.line_chart(data = nominal_orbit_snapshot.table("orbit"), y = ["x_mm", "y_mm"], x = "s")

#Measured model orbit plot 
def measured_orbit_plot():
    st.line_chart(data = measured_bpm_table, x = "s", y = "closed_orbit_mm")

orbit_mode_selection = st.selectbox(label = "Select orbit source mode", options = [ "Nominal", "Error Table", "Measured"])

if orbit_mode_selection == "Nominal":
    nominal_orbit_plot()
elif orbit_mode_selection == "Error Table":
    error_table_orbit_plot()
elif orbit_mode_selection == "Measured":
    measured_orbit_plot()
    
