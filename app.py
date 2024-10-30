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

# Step 3 - Sidebar setup
with st.sidebar:
    st.markdown("Welcome fella")
    text = st.text_input("Test")
    st.markdown(text)

# Step 4 - Sample data with 'Time', 'Pressure', and 'Strokes' columns
data = {
    'Time': ["10/27/24 8:00 am", "10/27/24 8:01 am", "10/27/24 8:02 am"],  # Initial dates
    'Pressure': [1, 2, 3],
    'Strokes': [1, 2, 3]
}

# Step 5 - Initialize the DataFrame in session state if not already set
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(data)

# Step 6 - Create two columns for the data table and chart
col1, col2 = st.columns([1, 1])  # Adjust the ratio to control the width

# Step 7 - Display scrollable, editable DataFrame in the left column
with col1:
    st.header("Edit Here")
    with st.container():
        edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", height=400)  # Set height for scrolling

# Step 8 - Update session state with any new pasted data
st.session_state.df = edited_df

# Step 9 - Convert the 'Time' column to datetime with a specified format to retain seconds precision
try:
    st.session_state.df['Time'] = pd.to_datetime(st.session_state.df['Time'], format="%m/%d/%y %I:%M:%S %p", errors='coerce')
except ValueError:
    st.write("Ensure the pasted data has datetime values with seconds included.")

# Step 10 - Create `cleaned_df` after datetime conversion to remove invalid entries
cleaned_df = st.session_state.df.dropna(subset=['Time'])

# Calculate the first derivative of pressure
cleaned_df['First_Derivative'] = np.gradient(cleaned_df['Pressure'], (cleaned_df['Time'] - cleaned_df['Time'].iloc[0]).dt.total_seconds())

# Calculate the second derivative of pressure
cleaned_df['Second_Derivative'] = np.gradient(cleaned_df['First_Derivative'], (cleaned_df['Time'] - cleaned_df['Time'].iloc[0]).dt.total_seconds())

# Step 11 - Plot with Plotly: Original Pressure on primary y-axis and derivatives on secondary y-axis
with col2:
    st.header("Pressure with First and Second Derivatives")

    # Create a Plotly figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Plot Pressure on the primary y-axis
    fig.add_trace(go.Scatter(
        x=cleaned_df['Time'],
        y=cleaned_df['Pressure'],
        mode='lines+markers',
        name='Pressure',
        marker=dict(color='blue')
    ), secondary_y=False)

    # Plot First Derivative on the secondary y-axis
    fig.add_trace(go.Scatter(
        x=cleaned_df['Time'],
        y=cleaned_df['First_Derivative'],
        mode='lines',
        name='First Derivative',
        line=dict(color='green', dash='solid')
    ), secondary_y=True)

    # Plot Second Derivative on the secondary y-axis
    fig.add_trace(go.Scatter(
        x=cleaned_df['Time'],
        y=cleaned_df['Second_Derivative'],
        mode='lines',
        name='Second Derivative',
        line=dict(color='purple', dash='dot')
    ), secondary_y=True)

    # Update layout with titles for both y-axes
    fig.update_layout(
        title="Pressure and its Derivatives Over Time",
        xaxis_title="Time",
    )

    fig.update_yaxes(title_text="Pressure", secondary_y=False)
    fig.update_yaxes(title_text="Derivatives", secondary_y=True)

    # Display the plot in Streamlit
    st.plotly_chart(fig)
