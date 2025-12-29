import streamlit as st
import yaml
import json
from utils.mission_types_manager import load_mission_types, save_mission_types
from utils.ui_utils import navigate_to

def render_mission_type_editor():
    m_type = st.session_state.editing_mission_type
    if not m_type:
        navigate_to('settings')
        return

    mission_types = load_mission_types()
    if m_type not in mission_types:
        st.error("Mission type not found")
        if st.button("Back"): navigate_to('settings')
        return

    details = mission_types[m_type]
    
    st.title(f"🛠️ Edit: {m_type.replace('_', ' ').title()}")
    col1, col2, col3 = st.columns([1, 1, 3])
    if col1.button("🏠 Main Menu"): navigate_to('home')
    if col2.button("🎨 Visual Editor"): navigate_to('visual_state_editor')

    with st.container(border=True):
        st.subheader("General Info")
        new_desc = st.text_input("Description", value=details.get("description", ""))

    st.subheader("State Configuration")
    
    # Toggle between View Modes
    edit_mode = st.radio("Format", ["YAML", "JSON"], horizontal=True)
    
    current_state = details.get("default_state", {})
    
    if edit_mode == "YAML":
        try:
            yaml_str = yaml.dump(current_state, indent=2, sort_keys=False)
        except Exception as e:
            yaml_str = "# Error converting to YAML\n" + str(e)
            
        new_yaml_str = st.text_area("YAML Configuration", value=yaml_str, height=600)
        
        if st.button("💾 Save Changes", type="primary"):
            try:
                new_state = yaml.safe_load(new_yaml_str)
                updated_types = mission_types.copy()
                updated_types[m_type] = {"description": new_desc, "default_state": new_state}
                save_mission_types(updated_types)
                st.success("Configuration saved successfully!")
            except yaml.YAMLError as e:
                st.error(f"Invalid YAML: {e}")
                
    else: # JSON
        json_str = json.dumps(current_state, indent=4)
        new_json_str = st.text_area("JSON Configuration", value=json_str, height=600)
        
        if st.button("💾 Save Changes", type="primary"):
            try:
                new_state = json.loads(new_json_str)
                updated_types = mission_types.copy()
                updated_types[m_type] = {"description": new_desc, "default_state": new_state}
                save_mission_types(updated_types)
                st.success("Configuration saved successfully!")
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
