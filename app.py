import streamlit as st
from utils.ui_utils import apply_custom_styles

# --- Views ---
from views.home_view import render_home
from views.settings_view import render_settings
from views.project_overview_view import render_project_overview
from views.mission_editor_view import render_mission_editor
from views.mission_type_editor_view import render_mission_type_editor
from views.agentic_creation_view import render_agentic_creation
from views.generation_progress_view import render_generation_progress
from views.visual_state_editor_view import render_visual_state_editor

# --- Configuration & Styling ---
st.set_page_config(page_title="UAV Mission Editor", page_icon="🛸", layout="wide")
apply_custom_styles()

# --- Session State Initialization ---
if 'page' not in st.session_state: st.session_state.page = 'home'
if 'current_project' not in st.session_state: st.session_state.current_project = None
if 'project_data' not in st.session_state: st.session_state.project_data = None
if 'current_mission_index' not in st.session_state: st.session_state.current_mission_index = None
if 'editing_mission_type' not in st.session_state: st.session_state.editing_mission_type = None

# --- Main Router ---
# We use a unique key based on the page to force Streamlit to recreate the container
# This prevents "ghost" elements from previous pages appearing if the new page is shorter
main_container = st.container(key=st.session_state.page)
with main_container:
    if st.session_state.page == 'home': render_home()
    elif st.session_state.page == 'settings': render_settings()
    elif st.session_state.page == 'project_overview': render_project_overview()
    elif st.session_state.page == 'mission_editor': render_mission_editor()
    elif st.session_state.page == 'mission_type_editor': render_mission_type_editor()
    elif st.session_state.page == 'agentic_creation': render_agentic_creation()
    elif st.session_state.page == 'generation_progress': render_generation_progress()
    elif st.session_state.page == 'visual_state_editor': render_visual_state_editor()

