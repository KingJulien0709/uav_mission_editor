import streamlit as st
from utils.ui_utils import navigate_to
from utils.mission_types_manager import get_mission_type_names

def render_agentic_creation():
    st.title("✨ Agentic Mission Creation")
    
    col1, col2 = st.columns([1, 4])
    if col1.button("⬅️ Back"): navigate_to('project_overview')
    
    st.divider()

    # --- 1. Model Selection ---
    st.subheader("1. AI Models")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        
        # VLM - Instruction/Desc
        vlm_options = ["gemini-2.5-flash-lite", "gemini-3-flash"]
        st.session_state.ac_model_vlm = c1.selectbox(
            "Instruction VLM", 
            vlm_options, 
            index=0,
            help="Model for generating instructions and descriptions."
        )
        
        # Image Gen
        img_options = ["gemini-2.5-flash-image", "gemini-3-pro-image-preview"]
        st.session_state.ac_model_img = c2.selectbox(
            "Image Generation", 
            img_options, 
            index=0,
            help="Model for generating waypoint images."
        )
        
        # VLM - Verification
        verif_options = ["gemini-2.5-flash-lite", "gemini-3-flash"]
        st.session_state.ac_model_verif = c3.selectbox(
            "Verification VLM", 
            verif_options, 
            index=0,
            help="Model for verifying content."
        )

    # --- 2. Mission Parameters ---
    st.subheader("2. Parameters")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        num_missions = c1.number_input("Number of Missions", min_value=1, value=10, step=1)
        num_waypoints = c2.number_input("Waypoints per Mission", min_value=1, value=3, step=1)

    # --- 3. Ratios: Mission Tags ---
    st.subheader("3. Mission Tags Distribution")
    available_tags = get_mission_type_names()
    
    # Initialize session state for ratios if not present
    if 'ac_tag_ratios' not in st.session_state:
        st.session_state.ac_tag_ratios = {t: 1.0 for t in available_tags}
    
    with st.container(border=True):
        selected_tags = st.multiselect(
            "Select Tags to Generate", 
            available_tags, 
            default=available_tags
        )
        
        if selected_tags:
            st.caption("Adjust relative weights (ratios) for selected tags:")
            cols = st.columns(len(selected_tags))
            for i, tag in enumerate(selected_tags):
                with cols[i]:
                    st.markdown(f"**{tag}**")
                    st.session_state.ac_tag_ratios[tag] = st.number_input(
                        "Ratio", 
                        min_value=0.0, 
                        value=st.session_state.ac_tag_ratios.get(tag, 1.0), 
                        step=0.1, 
                        key=f"ratio_tag_{tag}"
                    )

    # --- 4. Ratios: Dataset Splits ---
    st.subheader("4. Dataset Split Distribution")
    available_splits = ["sft_train", "rl_train", "validation"]
    
    if 'ac_split_ratios' not in st.session_state:
        st.session_state.ac_split_ratios = {s: 1.0 for s in available_splits}

    with st.container(border=True):
        selected_splits = st.multiselect(
            "Select Splits", 
            available_splits, 
            default=available_splits
        )
        
        if selected_splits:
            st.caption("Adjust relative weights (ratios) for selected splits:")
            cols = st.columns(len(selected_splits))
            for i, split in enumerate(selected_splits):
                with cols[i]:
                    st.markdown(f"**{split}**")
                    st.session_state.ac_split_ratios[split] = st.number_input(
                        "Ratio", 
                        min_value=0.0, 
                        value=st.session_state.ac_split_ratios.get(split, 1.0), 
                        step=0.1, 
                        key=f"ratio_split_{split}"
                    )

    # --- Generate Action (Stub) ---
    st.divider()
    if st.button("🚀 Generate Missions", type="primary"):
        # Capture Config (Implicitly in session state or usage logic)
        st.session_state.gen_total_missions = num_missions
        st.session_state.gen_processed_count = 0
        st.session_state.gen_log = []
        st.session_state.is_generating = True
        st.session_state.gen_retry_queue = []
        st.session_state.gen_name_counter = 1
        
        # Init start time
        import time
        from datetime import datetime
        st.session_state.gen_start_time = datetime.now().timestamp()
        
        # Use navigate_to for internal session-state routing
        navigate_to('generation_progress')
