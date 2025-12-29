import streamlit as st
from utils.data_utils import save_project_data
from utils.mission_types_manager import load_mission_types, get_mission_type_names
from utils.ui_utils import navigate_to, get_badge_html, get_split_badge_html, get_source_badge_html

def render_project_overview():
    proj_name = st.session_state.current_project
    data = st.session_state.project_data
    
    if not proj_name or data is None: 
        navigate_to('home')
        return

    st.title(f"📂 {proj_name}")
    
    # Header Actions
    col1, col2, col3, col4 = st.columns([1, 2.5, 1.5, 1])
    if col1.button("⬅️ Projects"): navigate_to('home')
    if col3.button("✨ Agentic Creation"): navigate_to('agentic_creation')
    if col4.button("💾 Save All"): 
        save_project_data(proj_name, data)
        st.toast("Project saved!")

    st.divider()

    # Filtering
    # Vertical stacking as requested
    available_tags = get_mission_type_names()
    selected_tags = st.multiselect("Filter by Type", available_tags, default=available_tags)
    
    available_splits = ["sft_train", "rl_train", "validation"]
    selected_splits = st.multiselect("Filter by Split", available_splits, default=available_splits)

    available_sources = ["manual", "synthetic"]
    selected_sources = st.multiselect("Filter by Source", available_sources, default=available_sources)

    # Mission List
    missions = data.get('missions', [])
    
    filtered_missions = [
        (i, m) for i, m in enumerate(missions) 
        if m.get('type', 'locate_and_report') in selected_tags
        and m.get('dataset_split', 'sft_train') in selected_splits
        and m.get('creation_source', 'manual') in selected_sources
    ]

    st.subheader(f"Missions ({len(filtered_missions)})")

    # Add New Mission
    with st.expander("➕ Add New Mission", expanded=False):
        with st.form("new_mission_form"):
            c_nm_1, c_nm_2, c_nm_3 = st.columns([2, 1, 1])
            nm_name = c_nm_1.text_input("Mission Name", "New Mission")
            nm_type = c_nm_2.selectbox("Mission Type", available_tags)
            nm_split = c_nm_3.selectbox("Dataset Split", available_splits)
            
            if st.form_submit_button("Create & Edit"):
                # Get default state for this type
                mt_config = load_mission_types().get(nm_type, {})
                new_m = {
                    "id": f"mission_{len(missions)+1}",
                    "name": nm_name,
                    "type": nm_type,
                    "dataset_split": nm_split,
                    "creation_source": "manual",
                    "state_config": mt_config.get("default_state", {}),
                    "waypoints": []
                }
                missions.append(new_m)
                save_project_data(proj_name, data)
                # Auto-navigate to editor
                st.session_state.current_mission_index = len(missions) - 1
                navigate_to('mission_editor')

    # List Display
    if not filtered_missions:
        st.info("No missions found matching filter.")
    else:
        for original_idx, m in filtered_missions:
            # Custom Card Layout using Container
            with st.container(border=True):
                # Layout: [Name (1.5)] [Tag (1.5)] [Split(1)] [Instruction (3)] [Edit (0.5)] [Delete (0.5)]
                c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.5, 1, 3, 0.5, 0.5])
                
                with c1:
                    st.markdown(f"**{m.get('name', 'Untitled')}** {get_source_badge_html(m.get('creation_source', 'manual'))}", unsafe_allow_html=True)
                
                with c2:
                    st.markdown(get_badge_html(m.get('type', 'unknown')), unsafe_allow_html=True)

                with c3:
                    st.markdown(get_split_badge_html(m.get('dataset_split', 'sft_train')), unsafe_allow_html=True)
                
                with c4:
                    inst = m.get('instruction', '')
                    if inst:
                        # Truncate and single line
                        display_inst = (inst[:50] + '...') if len(inst) > 50 else inst
                        st.caption(display_inst.replace('\n', ' '))
                
                with c5:
                    if st.button("✏️", key=f"edit_m_{original_idx}", help="Edit Mission"):
                        st.session_state.current_mission_index = original_idx
                        navigate_to('mission_editor')
                
                with c6:
                    if st.button("🗑️", key=f"del_m_{original_idx}", help="Delete Mission"):
                        missions.pop(original_idx)
                        save_project_data(proj_name, data)
                        st.rerun()
