import streamlit as st
import time
import random
import os
import shutil
from datetime import datetime
import json
from utils.ui_utils import navigate_to
from utils.data_utils import save_project_data, get_project_path
from utils.mission_types_manager import load_mission_types
from data_gen.mission_gen_pipeline import MissionGenPipeline
from utils.config_manager import load_config

@st.dialog("Mission Inspector", width="large")
def inspect_dialog(item):
    st.subheader(f"{item['name']}")
    c1, c2 = st.columns(2)
    c1.info(f"Type: {item['type']}")
    c2.info(f"Split: {item.get('dataset_split', 'N/A')}")
    
    st.markdown("### Instruction")
    # Handle both 'instruction' and 'mission_instruction' keys
    instruction_text = item.get('mission_instruction', item.get('instruction', ''))
    st.text_area("Generated Instruction", instruction_text, height=150, disabled=True)
    
    # Display Waypoints and their images
    waypoints = item.get('waypoints', [])
    if waypoints:
        st.markdown("### Waypoints")
        for wp in waypoints:
            target_badge = "🎯 TARGET" if wp.get('is_target') else ""
            with st.expander(f"📍 {wp.get('id', 'Unknown')} {target_badge}", expanded=wp.get('is_target', False)):
                # Media display
                media_items = wp.get('media', {})
                if media_items:
                    if isinstance(media_items, dict):
                        media_paths = list(media_items.values())
                        media_labels = list(media_items.keys())
                    else:
                        media_paths = media_items
                        media_labels = [f"Image {i+1}" for i in range(len(media_items))]
                    
                    cols = st.columns(len(media_paths))
                    for idx, (m_path, label) in enumerate(zip(media_paths, media_labels)):
                        with cols[idx]:
                            # Resolve absolute path (images are in outputs/ relative to app dir)
                            if os.path.isabs(m_path):
                                abs_path = m_path
                            else:
                                abs_path = os.path.abspath(m_path)
                            
                            if os.path.exists(abs_path):
                                st.image(abs_path, caption=label, width='stretch')
                            else:
                                st.warning(f"Image not found: {m_path}")
                
                # Show landmarks if available
                landmarks = wp.get('landmarks', [])
                if landmarks:
                    st.caption("**Landmarks:**")
                    for lm in landmarks:
                        st.text(f"  • {lm.get('category', 'Unknown')}: {lm.get('name', 'N/A')}")
    
    with st.expander("State Configuration", expanded=False):
        st.json(item.get('state_config', {}))
        
    st.divider()
    col1, col2 = st.columns(2)
    if col1.button("✅ Accept Mission", width='stretch'):
        item['status'] = 'success'
        st.rerun()
    if col2.button("❌ Reject Mission", width='stretch'):
        item['status'] = 'failed'
        st.rerun()

def render_generation_progress():
    st.title("🚀 Generating Missions...")
    
    # State Initialization check
    if 'gen_total_missions' not in st.session_state:
        st.warning("No generation process active.")
        if st.button("Back"): navigate_to('agentic_creation')
        return

    # --- Header Stats ---
    total = st.session_state.gen_total_missions
    processed = st.session_state.gen_processed_count
    
    # Calculate Time
    start_time = st.session_state.gen_start_time
    elapsed = datetime.now().timestamp() - start_time
    elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))
    
    # Estimate Remaining
    eta_str = "--:--:--"
    if processed > 0:
        avg_time = elapsed / processed
        remaining_count = total - processed
        eta_seconds = remaining_count * avg_time
        eta_str = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Progress", f"{processed}/{total}")
    c2.metric("Elapsed", elapsed_str)
    c3.metric("Est. Remaining", eta_str)
    if st.button("🛑 Stop / Back"):
        st.session_state.is_generating = False
        navigate_to('agentic_creation')

    # Progress Bar
    prog_val = processed / total if total > 0 else 0
    st.progress(prog_val)

    # --- Live Log ---
    st.subheader("Mission Log")
    log_container = st.container(border=True)
    
    # Display Logs (Reverse order)
    with log_container:
        # Show current working item if active
        if processed < total and st.session_state.is_generating:
            with st.container():
                cols = st.columns([0.5, 4])
                cols[0].markdown("### 🔄") 
                cols[1].markdown(f"**Generating Mission #{processed + 1}...**")
                
        # Show history
        # Iterate with index to allow modification
        for i in range(len(st.session_state.gen_log) - 1, -1, -1):
            item = st.session_state.gen_log[i]
            c_icon, c_info, c_act = st.columns([0.5, 2.5, 2])
            
            icon = "✅" 
            if item['status'] == 'failed': icon = "❌"
            elif item['status'] == 'verified_fail': icon = "⚠️"
            
            c_icon.markdown(f"### {icon}")
            c_info.markdown(f"**{item['name']}**")
            c_info.caption(f"Status: {item['status']} | Type: {item['type']}")
            
            # Actions
            with c_act:
                # Common Inspect Button
                ic1, ic2, ic3 = st.columns([1, 1, 1])
                if ic1.button("🔍", key=f"insp_{item['id']}"):
                    inspect_dialog(item)

                if item['status'] == 'success':
                    # Allow Reject override
                    if ic3.button("❌", key=f"rej_suc_{item['id']}"):
                        item['status'] = 'failed'
                        st.rerun()
                        
                elif item['status'] == 'verified_fail':
                    if ic2.button("✅", key=f"acc_{item['id']}"):
                        item['status'] = 'success'
                        st.rerun()
                    if ic3.button("❌", key=f"rej_{item['id']}"):
                        item['status'] = 'failed'
                        st.rerun()
                        
                elif item['status'] == 'failed':
                    if ic2.button("🔄", key=f"retry_{item['id']}", help="Retry Generation"):
                        # Remove from log and decrement processed count to trigger re-generation
                        st.session_state.gen_retry_queue.append(item['name'])
                        st.session_state.gen_log.pop(i)
                        st.session_state.gen_processed_count -= 1
                        st.session_state.is_generating = True
                        st.rerun()
            st.divider()

    # --- Simulation Logic (Demo) ---
    if st.session_state.is_generating and processed < total:
        time.sleep(1.5) # Simulate work
        
        # Determine Name (Retry or New)
        if st.session_state.get('gen_retry_queue'):
            m_name = st.session_state.gen_retry_queue.pop(0)
        else:
            ctr = st.session_state.get('gen_name_counter', 1)
            m_name = f"Generated Mission {ctr}"
            st.session_state.gen_name_counter = ctr + 1
        
        # Real Pipeline Execution
        try:
            config = load_config()
            api_key = config.get("gemini_api_key")
            
            if not api_key:
                st.error("Gemini API Key not found in settings!")
                st.session_state.is_generating = False
                st.stop()

            # Initialize pipeline with selected models
            pipeline = MissionGenPipeline(
                api_key=api_key,
                instruction_vlm=st.session_state.get("ac_model_vlm", "gemini-2.5-flash-lite"),
                image_generation_model=st.session_state.get("ac_model_img", "gemini-2.5-flash-image"),
                verification_vlm=st.session_state.get("ac_model_verif", "gemini-2.5-flash-lite"),
                waypoints_per_mission=st.session_state.get("gen_waypoints_per_mission", 3) # Need to ensure this is passed or default
            )

            # Determine Mission Type based on ratios
            available_tags = [t for t, r in st.session_state.get('ac_tag_ratios', {}).items() if r > 0]
            if not available_tags: available_tags = ["locate_and_report"] # Fallback
            
            # Weighted choice for type
            weights = [st.session_state.ac_tag_ratios[t] for t in available_tags]
            selected_type = random.choices(available_tags, weights=weights, k=1)[0]
            
            # Determine Split based on ratios
            available_splits = [s for s, r in st.session_state.get('ac_split_ratios', {}).items() if r > 0]
            if not available_splits: available_splits = ["sft_train"]
            
            split_weights = [st.session_state.ac_split_ratios[s] for s in available_splits]
            selected_split = random.choices(available_splits, weights=split_weights, k=1)[0]

            # Run Pipeline
            # Note: pipeline.run_pipeline returns the mission dictionary directly
            new_entry = pipeline.run_pipeline(
                mission_type_str=selected_type,
                dataset_split=selected_split
            )
            
            # Post-process entry to match our view requirements
            new_entry['name'] = m_name
            # Ensure status is set based on validation
            val_res = new_entry.get('validation_result', {})
            if val_res.get('mission_is_valid'):
                new_entry['status'] = 'success'
            elif val_res.get('needs_human_review'):
                 new_entry['status'] = 'verified_fail' # Or maybe review needed
            else:
                new_entry['status'] = 'failed'
                
            # If pipeline returned 'failed' id explicitly
            if new_entry.get('id') == 'failed':
                 new_entry['status'] = 'failed'
            else:
                 new_entry['id'] = f"gen_{int(time.time())}_{random.randint(1000,9999)}"

        except Exception as e:
            st.error(f"Pipeline Error: {e}")
            new_entry = {
                "id": f"err_{int(time.time())}",
                "name": m_name,
                "type": "error",
                "status": "failed",
                "instruction": f"Error during generation: {str(e)}",
                "state_config": {},
                "waypoints": []
            }
        
        # Update state
        st.session_state.gen_log.append(new_entry)
        st.session_state.gen_processed_count += 1
        st.rerun()
        
    elif processed >= total and st.session_state.is_generating:
        st.success("Generation Complete!")
        st.session_state.is_generating = False
        st.rerun()

    # --- Import Action ---
    if not st.session_state.is_generating and processed >= total:
        successful = [m for m in st.session_state.gen_log if m['status'] == 'success']
        if successful:
            st.info(f"Ready to import {len(successful)} missions.")
            if st.button("📥 Import to Project", type="primary"):
                proj_name = st.session_state.current_project
                data = st.session_state.project_data
                if proj_name and data:
                    # Append new missions
                    current_len = len(data.get('missions', []))
                    mission_types = load_mission_types()
                    
                    # Create project images directory
                    project_path = get_project_path(proj_name)
                    project_images_dir = os.path.join(project_path, "images")
                    os.makedirs(project_images_dir, exist_ok=True)
                    
                    for idx, m in enumerate(successful):
                        mission_id = f"mission_{current_len + idx + 1}"
                        
                        # Process waypoints: copy images to project folder and update paths
                        processed_waypoints = []
                        for wp in m.get('waypoints', []):
                            processed_wp = wp.copy()
                            media_items = wp.get('media', {})
                            
                            if isinstance(media_items, dict):
                                new_media = {}
                                for label, src_path in media_items.items():
                                    # Resolve absolute source path
                                    if os.path.isabs(src_path):
                                        abs_src = src_path
                                    else:
                                        abs_src = os.path.abspath(src_path)
                                    
                                    if os.path.exists(abs_src):
                                        # Create destination filename: mission_id_waypoint_id_label
                                        wp_id = wp.get('id', 'wp')
                                        dest_filename = f"{mission_id}_{wp_id}_{label}"
                                        dest_path = os.path.join(project_images_dir, dest_filename)
                                        
                                        # Copy the image
                                        shutil.copy2(abs_src, dest_path)
                                        
                                        # Store relative path for project
                                        new_media[label] = os.path.join("images", dest_filename)
                                    else:
                                        # Keep original path if file doesn't exist (for debugging)
                                        new_media[label] = src_path
                                processed_wp['media'] = new_media
                            else:
                                # Handle list format if needed
                                new_media = []
                                for src_path in media_items:
                                    if os.path.isabs(src_path):
                                        abs_src = src_path
                                    else:
                                        abs_src = os.path.abspath(src_path)
                                    
                                    if os.path.exists(abs_src):
                                        wp_id = wp.get('id', 'wp')
                                        dest_filename = f"{mission_id}_{wp_id}_{os.path.basename(src_path)}"
                                        dest_path = os.path.join(project_images_dir, dest_filename)
                                        shutil.copy2(abs_src, dest_path)
                                        new_media.append(os.path.join("images", dest_filename))
                                    else:
                                        new_media.append(src_path)
                                processed_wp['media'] = new_media
                            
                            processed_waypoints.append(processed_wp)
                        
                        # Construct proper mission object
                        mt_config = mission_types.get(m['type'], {})
                        final_m = {
                            "id": mission_id,
                            "name": m['name'],
                            "type": m['type'],
                            "dataset_split": m.get('dataset_split', 'sft_train'),
                            "creation_source": "synthetic",
                            "state_config": m.get('state_config', {}), # Use generated config if available
                            "waypoints": processed_waypoints,
                            "mission_instruction": m.get('mission_instruction', m.get('instruction', '')), # Handle both keys
                            "instruction": m.get('mission_instruction', m.get('instruction', '')) # Keep redundant for now or standardize
                        }
                        data['missions'].append(final_m)
                    
                    save_project_data(proj_name, data)
                    st.success(f"Imported {len(successful)} missions!")
                    time.sleep(1)
                    navigate_to('project_overview')
        else:
            st.warning("No successful missions to import.")
            if st.button("Back"): navigate_to('agentic_creation')
