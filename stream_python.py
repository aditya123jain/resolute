import streamlit as st
import pandas as pd
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

CSV_FILE = r"D:\all_dta\resolute_corp\Gs_sheet_project\ALL_DATA.csv"

# ====== FULLSCREEN CONFIGURATION ======
# st.set_page_config(layout="wide")  # Maximize horizontal space

# Add manual fullscreen button (requires user click)
st.markdown("""
<style>
.fullscreen-button {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 9999;
    background-color: #2c3e50;
    color: white;
    border: none;
    padding: 10px 15px;
    border-radius: 5px;
    cursor: pointer;
}
</style>
<button class="fullscreen-button" onclick="toggleFullscreen()">⛶ Fullscreen</button>
<script>
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
            console.log(`Fullscreen failed: ${err.message}`);
        });
    } else {
        document.exitFullscreen();
    }
}
</script>
""", unsafe_allow_html=True)

# ====== AUTO-REFRESHING CSV DISPLAY ======
data_placeholder = st.empty()
status_text = st.empty()


class CSVHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(CSV_FILE):
            st.rerun()


def load_data():
    try:
        df = pd.read_csv(CSV_FILE)
        status_text.success(f"Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return df
    except Exception as e:
        status_text.error(f"Error: {str(e)}")
        return None


# Initial load
if os.path.exists(CSV_FILE):
    # Start file watcher
    event_handler = CSVHandler()
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(CSV_FILE), recursive=False)
    observer.start()

    try:
        while True:
            df = load_data()
            if df is not None:
                with data_placeholder.container():
                    st.dataframe(
                        df,
                        height=600,
                        use_container_width=True,
                        hide_index=True,
                        column_config={col: st.column_config.Column(width="large") for col in df.columns}
                    )
            time.sleep(0.5)

    except KeyboardInterrupt:
        observer.stop()
    observer.join()
else:
    st.error(f"File not found at: {CSV_FILE}")
# import streamlit as st
# import pandas as pd
# import os
#
# # File path for the CSV
# CSV_FILE = "ALL_DATA.csv"
#
# df = pd.read_csv(CSV_FILE)
#
# print(df.head())
#
# # Function to load CSV file
# def load_csv(file_path):
#     if os.path.exists(file_path):
#         return pd.read_csv(file_path)
#     else:
#         # Create an empty DataFrame if file doesn't exist
#         return pd.DataFrame(columns=["Name", "Age", "City"])
#
#
# # Function to save DataFrame to CSV
# def save_csv(df, file_path):
#     df.to_csv(file_path, index=False)
#     st.success("Changes saved to CSV file!")
#
#
# # Initialize session state for DataFrame
# if 'df' not in st.session_state:
#     st.session_state.df = load_csv(CSV_FILE)
#
# # Streamlit app title
# st.title("CSV File Editor")
#
# # Display editable DataFrame
# st.subheader("Edit Existing Data")
# edited_df = st.data_editor(
#     st.session_state.df,
#     num_rows="dynamic",  # Allows adding/deleting rows directly
#     key="data_editor"
# )
#
# # Update session state with edited DataFrame
# st.session_state.df = edited_df
#
# # Form to add new row
# st.subheader("Add New Row")
# with st.form(key="add_row_form"):
#     name = st.text_input("Name")
#     age = st.number_input("Age", min_value=0, step=1)
#     city = st.text_input("City")
#     submit_button = st.form_submit_button("Add Row")
#
#     if submit_button:
#         if name and city:
#             # Create new row as a DataFrame
#             new_row = pd.DataFrame([[name, age, city]], columns=["Name", "Age", "City"])
#             # Append new row to DataFrame
#             st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
#             st.success("Row added!")
#         else:
#             st.error("Please fill in all fields.")
#
# # Button to save changes to CSV
# if st.button("Save Changes to CSV"):
#     save_csv(st.session_state.df, CSV_FILE)
#
# # Display the current DataFrame
# st.subheader("Current Data")
# st.dataframe(st.session_state.df)