# Step 1 - Imports
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Step 2 - Set page configuration
st.set_page_config(
    page_title="To Do App",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.extremelycoolapp.com/help',
        'Report a bug': "https://www.extremelycoolapp.com/bug",
        'About': "# This is a header. This is an *extremely* cool app!"
    }
)

# Step 3 - Initialize `fit_pressure` in session state with a default message
if 'fit_pressure' not in st.session_state:
    st.session_state['fit_pressure'] = "No inflection point detected"

# Step 4 - Sidebar setup
with st.sidebar:
    st.markdown("Welcome fella")
    text = st.text_input("Test")
    st.markdown(text)

# Step 5 - Updated data with 'Time', 'Pressure', and 'Strokes' columns
data = {
    'Time': [
        "10/27/2024 08:00:00", "10/27/2024 08:00:01", "10/27/2024 08:00:02", "10/27/2024 08:00:03",
        "10/27/2024 08:00:04", "10/27/2024 08:00:05", "10/27/2024 08:00:06", "10/27/2024 08:00:07",
        "10/27/2024 08:00:08", "10/27/2024 08:00:09", "10/27/2024 08:00:10", "10/27/2024 08:00:11",
        "10/27/2024 08:00:12", "10/27/2024 08:00:13", "10/27/2024 08:00:14", "10/27/2024 08:00:15",
        "10/27/2024 08:00:16", "10/27/2024 08:00:17", "10/27/2024 08:00:18", "10/27/2024 08:00:19",
        "10/27/2024 08:00:20", "10/27/2024 08:00:21", "10/27/2024 08:00:22", "10/27/2024 08:00:23",
        "10/27/2024 08:00:24", "10/27/2024 08:00:25", "10/27/2024 08:00:26", "10/27/2024 08:00:27",
        "10/27/2024 08:00:28", "10/27/2024 08:00:29", "10/27/2024 08:00:30", "10/27/2024 08:00:31",
        "10/27/2024 08:00:32", "10/27/2024 08:00:33", "10/27/2024 08:00:34", "10/27/2024 08:00:35",
        "10/27/2024 08:00:36", "10/27/2024 08:00:37", "10/27/2024 08:00:38", "10/27/2024 08:00:39",
        "10/27/2024 08:00:40", "10/27/2024 08:00:41", "10/27/2024 08:00:42", "10/27/2024 08:00:43",
        "10/27/2024 08:00:44", "10/27/2024 08:00:45", "10/27/2024 08:00:46", "10/27/2024 08:00:47",
        "10/27/2024 08:00:48", "10/27/2024 08:00:49"
    ],
    'Pressure': [
        0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95,
        100, 105, 107, 109, 111, 113, 115, 117, 119, 121, 123, 125, 127, 129, 131, 133,
        133, 133, 133, 133, 133, 133, 133, 133, 133, 133, 133, 133, 133, 133
    ],
    'Strokes': [
        20, 20, 20, 20, 20, 20, 20, 21, 21, 21, 21, 21, 21, 22, 22, 22, 22, 22, 22, 23,
        23, 23, 23, 23, 23, 24, 24, 24, 24, 24, 24, 25, 25, 25, 25, 25, 25, 26, 26, 26,
        26, 26, 26, 27, 27, 27, 27, 27, 27, 28
    ]
}


# Step 6 - Initialize the DataFrame in session state if not already set
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(data)

# Step 7 - Create two columns for the data table and chart
col1, col2 = st.columns([1, 2])

# Step 8 - Display scrollable, editable DataFrame in the left column
with col1:
    st.header("Edit Here")
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", height=400)

    # Well Information Section below the data table
    st.markdown("---")
    st.subheader("Well Information")

    # Input fields for well information
    tvd_poi = st.text_input("1. What is the TVD of the POI?", "")
    mud_weight = st.text_input("2. What is the Mud Weight?", "")

    # Display FIT Pressure value
    st.markdown("**FIT Pressure**")
    st.text_input("Selected Pressure Value", st.session_state['fit_pressure'], disabled=True)

    # Step 13 - Calculate and display FIT EMW if all necessary values are present
    try:
        # Convert inputs to floats if they are provided
        fit_pressure_value = float(st.session_state['fit_pressure']) if st.session_state['fit_pressure'] != "No inflection point detected" else None
        mud_weight_value = float(mud_weight) if mud_weight else None
        tvd_value = float(tvd_poi) if tvd_poi else None

        # Calculate FIT EMW if all values are valid
        if fit_pressure_value is not None and mud_weight_value is not None and tvd_value is not None:
            fit_emw = mud_weight_value + (fit_pressure_value / (0.052 * tvd_value))
            st.text_input("FIT EMW", f"{fit_emw:.2f}", disabled=True)
        else:
            st.text_input("FIT EMW", "Enter all values to calculate FIT EMW", disabled=True)

    except (ValueError, ZeroDivisionError):
        st.text_input("FIT EMW", "Calculation error - check input values", disabled=True)

# Step 9 - Update session state with any new pasted data
st.session_state.df = edited_df

# Step 10 - Convert 'Time' column to datetime with a specified format
try:
    st.session_state.df['Time'] = pd.to_datetime(st.session_state.df['Time'], format="%m/%d/%y %I:%M:%S %p", errors='coerce')
except ValueError:
    st.write("Ensure the pasted data has datetime values with seconds included.")

# Step 11 - Clean DataFrame and drop invalid 'Time' entries
cleaned_df = st.session_state.df.dropna(subset=['Time'])

# Step 12 - Calculate derivatives if there are enough data points
inflection_time = None
inflection_pressure = None
if len(cleaned_df) > 1:
    cleaned_df['First_Derivative'] = np.gradient(cleaned_df['Pressure'], (cleaned_df['Time'] - cleaned_df['Time'].iloc[0]).dt.total_seconds())
    cleaned_df['Second_Derivative'] = np.gradient(cleaned_df['First_Derivative'], (cleaned_df['Time'] - cleaned_df['Time'].iloc[0]).dt.total_seconds())

    # Find the first point where the second derivative is less than zero
    inflection_points = cleaned_df[cleaned_df['Second_Derivative'] < 0]
    if not inflection_points.empty:
        inflection_time = inflection_points.iloc[0]['Time']
        inflection_pressure = inflection_points.iloc[0]['Pressure']
        st.session_state['fit_pressure'] = inflection_pressure

# Check if 'First_Derivative' and 'Second_Derivative' columns exist before setting slider ranges
if 'First_Derivative' in cleaned_df.columns and 'Second_Derivative' in cleaned_df.columns:
    derivatives_min = min(cleaned_df[['First_Derivative', 'Second_Derivative']].min().min() - 20, -25)
    derivatives_max = max(cleaned_df[['First_Derivative', 'Second_Derivative']].max().max() + 20, 25)
else:
    # Default range if derivatives are not available
    derivatives_min, derivatives_max = -25, 25

# Set min and max ranges for the pressure slider to ensure valid range
pressure_min = cleaned_df['Pressure'].min() - 20 if not cleaned_df['Pressure'].isna().all() else 0
pressure_max = cleaned_df['Pressure'].max() + 20 if not cleaned_df['Pressure'].isna().all() else 100

# Plotting with Plotly in the right column
with col2:
    st.header("Pressure with First and Second Derivatives")

    # Y-axis range sliders
    y_min, y_max = st.slider("Adjust Y-axis range for Pressure", min_value=float(pressure_min), max_value=float(pressure_max), value=(float(pressure_min), float(pressure_max)))
    dy_min, dy_max = st.slider("Adjust Y-axis range for Derivatives", min_value=float(derivatives_min), max_value=float(derivatives_max), value=(float(derivatives_min), float(derivatives_max)))

    # Create a Plotly figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.update_layout(height=600, width=900)

    # Plot Pressure on the primary y-axis
    fig.add_trace(go.Scatter(
        x=cleaned_df['Time'],
        y=cleaned_df['Pressure'],
        mode='lines+markers',
        name='Pressure',
        marker=dict(color='blue'),
        hoverinfo="x+y"
    ), secondary_y=False)

    # Plot derivatives on the secondary y-axis if available
    if 'First_Derivative' in cleaned_df.columns and 'Second_Derivative' in cleaned_df.columns:
        fig.add_trace(go.Scatter(
            x=cleaned_df['Time'],
            y=cleaned_df['First_Derivative'],
            mode='lines',
            name='First Derivative',
            line=dict(color='green', dash='solid'),
            hoverinfo="x+y"
        ), secondary_y=True)

        fig.add_trace(go.Scatter(
            x=cleaned_df['Time'],
            y=cleaned_df['Second_Derivative'],
            mode='lines',
            name='Second Derivative',
            line=dict(color='purple', dash='dot'),
            hoverinfo="x+y"
        ), secondary_y=True)

    # Plot the inflection point as a red marker on the Pressure plot
    if inflection_time is not None and inflection_pressure is not None:
        fig.add_trace(go.Scatter(
            x=[inflection_time],
            y=[inflection_pressure],
            mode='markers',
            name='Inflection Point',
            marker=dict(color='red', size=10),
            hoverinfo="x+y"
        ))

    # Update layout with titles and y-axis range
    fig.update_layout(title="Pressure and its Derivatives Over Time", xaxis_title="Time")
    fig.update_yaxes(title_text="Pressure", range=[y_min, y_max], secondary_y=False)
    fig.update_yaxes(title_text="Derivatives", range=[dy_min, dy_max], secondary_y=True)

    # Display plot
    st.plotly_chart(fig)
