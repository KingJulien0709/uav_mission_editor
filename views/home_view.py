import streamlit as st
from utils.data_utils import list_projects, create_project, load_project_data
from utils.mission_types_manager import load_mission_types, save_mission_type, delete_mission_type
from utils.ui_utils import navigate_to

def render_home():
    st.title("🛸 UAV Mission Editor")
    c1, c2 = st.columns([3, 1])
    with c2: 
        if st.button("⚙️ Settings"): navigate_to('settings')
    st.divider()
    
    # Two-column layout: Projects and Mission Types
    col_left, col_right = st.columns([1, 1])
    
    # Left column: Projects
    with col_left:
        st.subheader("📂 Projects")
        
        with st.expander("➕ Create New Project", expanded=False):
            pn = st.text_input("Project Name", key="new_project_name")
            if st.button("Create", key="create_project_btn"):
                if pn:
                    if create_project(pn):
                        st.success(f"Created {pn}")
                        st.session_state.current_project = pn
                        st.session_state.project_data = load_project_data(pn)
                        navigate_to('project_overview')
                    else: st.error("Project already exists")

        projs = list_projects()
        if projs:
            for p in projs:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{p}**")
                    if c2.button("Open", key=f"open_{p}"):
                        st.session_state.current_project = p
                        st.session_state.project_data = load_project_data(p)
                        navigate_to('project_overview')
        else:
            st.info("No projects yet. Create one to get started.")
    
    # Right column: Mission Types
    with col_right:
        st.subheader("🎯 Mission Types")
        st.caption("Configure state machines for different mission types")
        
        # Create new mission type
        with st.expander("➕ Create New Mission Type", expanded=False):
            new_name = st.text_input("Mission Type Name", key="new_mt_name", placeholder="e.g. search_and_rescue")
            new_desc = st.text_input("Description", key="new_mt_desc", placeholder="Search for targets and rescue")
            
            if st.button("Create Mission Type", key="create_mt_btn"):
                if new_name:
                    # Normalize name (lowercase with underscores)
                    normalized_name = new_name.lower().replace(" ", "_").replace("-", "_")
                    
                    # Check if exists
                    mission_types = load_mission_types()
                    if normalized_name in mission_types:
                        st.error(f"Mission type '{normalized_name}' already exists")
                    else:
                        # Create with default structure
                        new_config = {
                            "description": new_desc or normalized_name.replace("_", " ").title(),
                            "default_state": {
                                "initial_state": "execution",
                                "states": {
                                    "execution": {
                                        "prompt": "You are a UAV controller executing a task.\n\n## Reasoning\nPut your thought process inside <think></think> tags.",
                                        "tools": ["next_goal"],
                                        "observations": ["current_location", "plan"],
                                        "state_transitions": {
                                            "conditions": [
                                                {"condition": "True", "next_state": "end"}
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                        save_mission_type(normalized_name, new_config, prefer_yaml=True)
                        st.success(f"Created '{normalized_name}'")
                        st.session_state.editing_mission_type = normalized_name
                        st.rerun()
                else:
                    st.warning("Enter a name for the mission type")
        
        mission_types = load_mission_types()
        
        for m_type, details in mission_types.items():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"**{m_type.replace('_', ' ').title()}**")
                c1.caption(details.get("description", ""))
                
                if c2.button("✏️ Edit", key=f"edit_mt_{m_type}"):
                    st.session_state.editing_mission_type = m_type
                    navigate_to('visual_state_editor')
                
                # Delete with confirmation
                delete_key = f"delete_mt_{m_type}"
                confirm_key = f"confirm_delete_{m_type}"
                
                if confirm_key in st.session_state and st.session_state[confirm_key]:
                    # Show confirmation buttons
                    if c3.button("⚠️ Confirm", key=f"confirm_btn_{m_type}", type="primary"):
                        delete_mission_type(m_type)
                        st.session_state[confirm_key] = False
                        st.toast(f"Deleted '{m_type}'")
                        st.rerun()
                else:
                    if c3.button("🗑️", key=delete_key, help="Delete this mission type"):
                        st.session_state[confirm_key] = True
                        st.rerun()
        
        # Cancel any pending delete confirmations
        for m_type in mission_types.keys():
            confirm_key = f"confirm_delete_{m_type}"
            if confirm_key in st.session_state and st.session_state[confirm_key]:
                if st.button(f"❌ Cancel delete of '{m_type}'", key=f"cancel_{m_type}"):
                    st.session_state[confirm_key] = False
                    st.rerun()
