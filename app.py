import streamlit as st
import pandas as pd
import numpy as np
import random

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

with st.sidebar:
    st.markdown("Welcome fella")
    text = st.text_input("Test")
    st.markdown(text)
    st.balloons()
    st.snow()

# Sample data for the table
data = {
    'Length': [1, 2, 3],
    'OD, in': [1, 2, 3],
    'ID, in': [4.5, 5.5, 6.5]
}



# Create a DataFrame
df = pd.DataFrame(data)
col1, col2, col3 = st.columns(3)
with col1:
    st.header("Edit Here")
    # Display the editable table without the calculated column initially
    editable_df = st.data_editor(df[['Length', 'OD, in', 'ID, in']], num_rows="dynamic")
    

# Recalculate the 'Capacity' column based on user-edited values
editable_df['Capacity bbl'] = editable_df['ID, in'] ** 2 / 1029.4 * editable_df['Length']

with col2:
    st.header("Calculated")
    # Show the updated DataFrame with the calculated column
    st.write("Edited Data with Calculated Column:")
    st.write(editable_df)

# Create a pivot table that sums the 'Length' and 'Capacity'
pivot_table = editable_df[['Length', 'Capacity bbl']].sum().to_frame().T
pivot_table.index = ['Total']  # Label the sum row as 'Total'
with col3:
    st.header("Summarized")
    # Display the pivot table
    st.write("Pivot Table with Sum of Length and Capacity bbl:")
    st.write(pivot_table)
