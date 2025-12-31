import streamlit as st
import os
import time
from utils.data_utils import save_project_data, get_project_path, get_exports_dir, filter_missions, prepare_missions_for_export
from utils.mission_types_manager import load_mission_types, get_mission_type_names
from utils.ui_utils import navigate_to, get_badge_html, get_split_badge_html, get_source_badge_html
from utils.hf_utils import (
    export_missions_to_hf_dataset, 
    upload_dataset_to_hf, 
    load_hf_dataset_metadata,
    import_dataset_from_hf
)
from utils.config_manager import load_config


@st.dialog("Export Dataset", width="large")
def export_dialog(missions, project_name):
    """Dialog for exporting selected missions to HuggingFace format."""
    st.markdown(f"### 📤 Export {len(missions)} Missions")
    
    if len(missions) == 0:
        st.warning("No missions selected for export. Adjust your filters to include missions.")
        return
    
    # Show summary of what will be exported
    st.info(f"**{len(missions)}** missions will be exported based on current filter selection.")
    
    # Dataset naming
    st.markdown("#### Dataset Configuration")
    default_name = f"{project_name}_dataset"
    dataset_name = st.text_input("Dataset Name", value=default_name, help="Name for the exported dataset folder")
    
    # Export options
    col1, col2 = st.columns(2)
    with col1:
        export_local = st.checkbox("Save locally", value=True, help="Save dataset to local exports folder")
    with col2:
        upload_to_hf = st.checkbox("Upload to HuggingFace", value=False, help="Upload dataset to HuggingFace Hub")
    
    # HuggingFace options (if enabled)
    hf_repo_id = None
    hf_token = None
    hf_private = False
    
    if upload_to_hf:
        st.markdown("#### HuggingFace Settings")
        config = load_config()
        default_token = config.get("hf_token", "")
        
        hf_repo_id = st.text_input(
            "Repository ID", 
            placeholder="username/dataset-name",
            help="HuggingFace dataset repository ID"
        )
        hf_token = st.text_input(
            "HuggingFace Token", 
            value=default_token,
            type="password",
            help="Your HuggingFace access token with write permissions"
        )
        hf_private = st.checkbox("Private repository", value=False)
    
    st.divider()
    
    # Preview of missions
    with st.expander("Preview Missions to Export", expanded=False):
        for m in missions[:5]:  # Show first 5
            st.text(f"• {m.get('name', 'Untitled')} ({m.get('type', 'unknown')})")
        if len(missions) > 5:
            st.text(f"  ... and {len(missions) - 5} more")
    
    # Export button
    if st.button("🚀 Export Dataset", type="primary", use_container_width=True):
        with st.spinner("Exporting dataset..."):
            try:
                project_path = get_project_path(project_name)
                exports_dir = get_exports_dir()
                
                # Prepare missions for export
                prepared_missions = prepare_missions_for_export(missions, project_name)
                
                # Export to local HF format
                if export_local:
                    dataset_path = export_missions_to_hf_dataset(
                        missions=prepared_missions,
                        project_path=project_path,
                        output_dir=exports_dir,
                        dataset_name=dataset_name
                    )
                    st.success(f"✅ Dataset exported locally to: `{dataset_path}`")
                
                # Upload to HuggingFace
                if upload_to_hf:
                    if not hf_repo_id:
                        st.error("Please enter a HuggingFace repository ID")
                        return
                    if not hf_token:
                        st.error("Please enter your HuggingFace token")
                        return
                    
                    # If not exported locally, create temp export
                    if not export_local:
                        import tempfile
                        with tempfile.TemporaryDirectory() as tmpdir:
                            dataset_path = export_missions_to_hf_dataset(
                                missions=prepared_missions,
                                project_path=project_path,
                                output_dir=tmpdir,
                                dataset_name=dataset_name
                            )
                            url = upload_dataset_to_hf(
                                local_path=dataset_path,
                                repo_id=hf_repo_id,
                                token=hf_token,
                                private=hf_private
                            )
                    else:
                        url = upload_dataset_to_hf(
                            local_path=dataset_path,
                            repo_id=hf_repo_id,
                            token=hf_token,
                            private=hf_private
                        )
                    
                    st.success(f"✅ Dataset uploaded to: [{hf_repo_id}]({url})")
                
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"Export failed: {str(e)}")


@st.dialog("Import Dataset", width="large")
def import_dialog(project_name, data):
    """Dialog for importing missions from a HuggingFace dataset."""
    st.markdown("### 📥 Import from HuggingFace")
    
    # HuggingFace repo input
    config = load_config()
    default_token = config.get("hf_token", "")
    
    hf_repo_id = st.text_input(
        "HuggingFace Repository ID",
        placeholder="username/dataset-name",
        help="Enter the HuggingFace dataset repository ID to import from"
    )
    
    hf_token = st.text_input(
        "HuggingFace Token (optional)",
        value=default_token,
        type="password",
        help="Required for private repositories"
    )
    
    # Initialize session state for validation results
    if 'import_validation_result' not in st.session_state:
        st.session_state.import_validation_result = None
    if 'import_repo_checked' not in st.session_state:
        st.session_state.import_repo_checked = None
    
    # Validate button
    if st.button("🔍 Check Dataset", use_container_width=True):
        if not hf_repo_id:
            st.error("Please enter a repository ID")
            return
        
        with st.spinner("Validating dataset format..."):
            is_valid, message, count = load_hf_dataset_metadata(
                repo_id=hf_repo_id,
                token=hf_token if hf_token else None
            )
            st.session_state.import_validation_result = (is_valid, message, count)
            st.session_state.import_repo_checked = hf_repo_id
    
    # Show validation result
    if st.session_state.import_validation_result and st.session_state.import_repo_checked == hf_repo_id:
        is_valid, message, count = st.session_state.import_validation_result
        
        if is_valid:
            st.success(f"✅ {message}")
            st.info(f"Ready to import **{count}** missions from `{hf_repo_id}`")
            
            # Import options
            st.markdown("#### Import Options")
            
            col1, col2 = st.columns(2)
            if col1.button("✅ Accept Import", type="primary", use_container_width=True):
                with st.spinner("Importing missions..."):
                    try:
                        project_path = get_project_path(project_name)
                        success, msg, imported_missions = import_dataset_from_hf(
                            repo_id=hf_repo_id,
                            project_path=project_path,
                            token=hf_token if hf_token else None
                        )
                        
                        if success:
                            # Add imported missions to project
                            existing_count = len(data.get('missions', []))
                            for i, m in enumerate(imported_missions):
                                m['id'] = f"mission_{existing_count + i + 1}"
                                m['creation_source'] = 'imported'
                                data['missions'].append(m)
                            
                            save_project_data(project_name, data)
                            st.success(f"✅ {msg}")
                            
                            # Clear validation state
                            st.session_state.import_validation_result = None
                            st.session_state.import_repo_checked = None
                            
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Import failed: {msg}")
                            
                    except Exception as e:
                        st.error(f"Import failed: {str(e)}")
            
            if col2.button("❌ Cancel", use_container_width=True):
                st.session_state.import_validation_result = None
                st.session_state.import_repo_checked = None
                st.rerun()
        else:
            st.error(f"❌ Invalid dataset format: {message}")
            st.markdown("""
            **Required format for uav_mission_env compatibility:**
            - Each mission must have: `instruction`, `waypoints`, `state_config`
            - Each waypoint must have: `id`, `gt_entities`, `is_target`, `media`
            """)


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

    available_sources = ["manual", "synthetic", "imported"]
    selected_sources = st.multiselect("Filter by Source", available_sources, default=available_sources)

    # Mission List
    missions = data.get('missions', [])
    
    filtered_missions = [
        (i, m) for i, m in enumerate(missions) 
        if m.get('type', 'locate_and_report') in selected_tags
        and m.get('dataset_split', 'sft_train') in selected_splits
        and m.get('creation_source', 'manual') in selected_sources
    ]

    # Export/Import Section
    st.divider()
    exp_col1, exp_col2, exp_col3, exp_col4 = st.columns([2, 1.5, 1.5, 1])
    
    with exp_col1:
        st.markdown(f"**📊 Current Selection:** {len(filtered_missions)} missions")
    
    with exp_col2:
        if st.button("📤 Export Selection", use_container_width=True, 
                     help="Export currently filtered missions to HuggingFace format"):
            # Get the actual mission objects for export
            missions_to_export = [m for _, m in filtered_missions]
            export_dialog(missions_to_export, proj_name)
    
    with exp_col3:
        if st.button("📥 Import Dataset", use_container_width=True,
                     help="Import missions from a HuggingFace dataset"):
            import_dialog(proj_name, data)
    
    st.divider()

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
