import streamlit as st
import os
import yaml
from PIL import Image, ImageOps
from utils.data_utils import save_project_data, get_project_path
from utils.mission_types_manager import load_mission_types, get_mission_type_names
from utils.ui_utils import navigate_to, get_badge_html


def get_image_orientation(image_path: str) -> str:
    """Determine if an image is portrait or landscape, accounting for EXIF rotation."""
    try:
        with Image.open(image_path) as img:
            # Apply EXIF orientation to get the true display dimensions
            img_corrected = ImageOps.exif_transpose(img)
            if img_corrected is None:
                img_corrected = img
            width, height = img_corrected.size
            if height > width:
                return "portrait"
            else:
                return "landscape"
    except Exception:
        return "landscape"  # Default to landscape if can't read



@st.dialog("Image Viewer", width="large")
def show_image_dialog(image_path: str, image_name: str):
    """Display an image at full resolution in a dialog with EXIF correction."""
    try:
        with Image.open(image_path) as img:
            img_corrected = ImageOps.exif_transpose(img)
            if img_corrected is None:
                img_corrected = img.copy()
            else:
                img_corrected = img_corrected.copy()
            st.image(img_corrected, use_container_width=True)
    except Exception:
        st.image(image_path, use_container_width=True)
    st.caption(f"📷 {image_name}")
    if st.button("Close", use_container_width=True):
        st.rerun()


def render_mission_editor():
    proj_name = st.session_state.current_project
    data = st.session_state.project_data
    m_idx = st.session_state.current_mission_index
    
    if m_idx is None or m_idx >= len(data.get('missions', [])):
        navigate_to('project_overview')
        return

    mission = data['missions'][m_idx]

    # Top Bar
    c1, c2, c3 = st.columns([0.5, 3, 1])
    if c1.button("⬅️ Back"): navigate_to('project_overview')
    c2.markdown(f"### Editing: {mission.get('name')} {get_badge_html(mission.get('type', ''))}", unsafe_allow_html=True)
    if c3.button("💾 Save"): 
        save_project_data(proj_name, data)
        st.toast("Saved!")

    # Mission Config
    with st.expander("Mission Configuration & State", expanded=True):
        # Layout: Name (2) | Type (1) | Split (1)
        c_meta_1, c_meta_2, c_meta_3 = st.columns([2, 1, 1])
        mission['name'] = c_meta_1.text_input("Name", mission.get('name', ''))
        
        # Mission Type Switcher
        available_types = get_mission_type_names()
        current_type = mission.get('type', available_types[0] if available_types else "")
        
        def on_type_change():
            new_t = st.session_state.temp_mission_type
            mission['type'] = new_t
            # Reset state config to default for the new type
            defaults = load_mission_types().get(new_t, {}).get('default_state', {})
            mission['state_config'] = defaults
            
        c_meta_2.selectbox(
            "Mission Type", 
            available_types, 
            index=available_types.index(current_type) if current_type in available_types else 0,
            key="temp_mission_type",
            on_change=on_type_change
        )
        
        # Dataset Split Selector
        splits = ["sft_train", "rl_train", "validation"]
        current_split = mission.get('dataset_split', 'sft_train')
        if current_split not in splits: current_split = 'sft_train'
        
        mission['dataset_split'] = c_meta_3.selectbox(
            "Dataset Split",
            splits,
            index=splits.index(current_split)
        )
        
        # Instruction / Plan
        st.markdown("**Mission Instruction / Plan**")
        mission['instruction'] = st.text_area(
            "Instructions for this specific mission",
            value=mission.get('mission_instruction', mission.get('instruction', '')),
            height=100,
            label_visibility="collapsed"
        )
        # Sync simple `instruction` key for backward compat if needed
        mission['mission_instruction'] = mission['instruction']

        
        # Read-only State Configuration
        with st.expander("State Configuration (Read-Only)"):
            st.caption(f"derived from type: {mission.get('type')}")
            current_state = mission.get('state_config', {})
            try:
                val = yaml.dump(current_state, indent=2)
                st.code(val, language='yaml')
            except: 
                 st.text(str(current_state))

    st.subheader("Waypoints")
    
    # Validation Result Display
    if 'validation_result' in mission:
        with st.expander("Validation Result", expanded=False):
            res = mission['validation_result']
            st.markdown(f"**Valid:** {res.get('mission_is_valid', False)}")
            st.markdown(f"**Confidence:** {res.get('confidence_score', 0.0)}")
            st.markdown(f"**Reasoning:** {res.get('reasoning', '')}")

    waypoints = mission.get('waypoints', [])
    
    # Waypoint Iteration
    for i, wp in enumerate(waypoints):
        with st.container():
            st.markdown(f'<div class="waypoint-card">', unsafe_allow_html=True)
            
            # Header
            wc1, wc2, wc3 = st.columns([2, 1, 0.5])
            wp['id'] = wc1.text_input("ID", value=wp.get('id', ''), key=f"wp_{i}_id")
            
            # Target Logic
            def on_target_chg(idx):
                for iw, w in enumerate(mission['waypoints']): 
                    if iw != idx: w['is_target'] = False
            
            is_target = wc2.checkbox("Is Target", value=wp.get('is_target', False), key=f"wp_{i}_t", on_change=on_target_chg, args=(i,))
            wp['is_target'] = is_target

            if wc3.button("🗑️", key=f"wp_{i}_del"):
                waypoints.pop(i)
                st.rerun()

            # Entities
            with st.expander("Ground Truth Entities"):
                entities = wp.get('gt_entities', {})
                new_ent = {}
                for k, v in entities.items():
                    ec1, ec2, ec3 = st.columns([1,1,0.2])
                    nk = ec1.text_input("Key", k, key=f"e_{i}_{k}_k")
                    nv = ec2.text_input("Val", str(v), key=f"e_{i}_{k}_v")
                    if not ec3.button("x", key=f"e_{i}_{k}_d"): new_ent[nk] = nv
                if st.button("Add Entity", key=f"e_{i}_add"): new_ent["key"] = "val"
                wp['gt_entities'] = new_ent

            # Media
            st.write("**Media**")
            uploader_key = f"upl_{i}_{len(wp.get('media', []))}"
            uploaded = st.file_uploader("Upload", accept_multiple_files=True, key=uploader_key)
            if uploaded:
                images_dir = os.path.join(get_project_path(proj_name), "images")
                os.makedirs(images_dir, exist_ok=True)
                for f in uploaded:
                    with open(os.path.join(images_dir, f.name), "wb") as bf: bf.write(f.getbuffer())
                    rel_p = os.path.join("images", f.name)
                    if 'media' not in wp: wp['media'] = []
                    if rel_p not in wp['media']: wp['media'].append(rel_p)
                st.rerun()



            # Display Media (Handle both Dict and List formats)
            media_items = wp.get('media', [])
            if isinstance(media_items, dict):
                # Convert dict {'filename': 'path'} to simple list of paths for display
                # We lose the key (filename) in this simple view but it works for now
                media_path_list = list(media_items.values())
            else:
                media_path_list = media_items

            if media_path_list:
                st.markdown('<div class="media-scroll">', unsafe_allow_html=True)
                media_cols = st.columns(len(media_path_list))
                for mi, m_path in enumerate(media_path_list):
                    fpath = os.path.join(get_project_path(proj_name), m_path)
                    with media_cols[mi]:
                        if os.path.exists(fpath):
                            if m_path.endswith(('.png','.jpg','.jpeg')):
                                # Load image and apply EXIF orientation correction
                                try:
                                    with Image.open(fpath) as img:
                                        img_corrected = ImageOps.exif_transpose(img)
                                        if img_corrected is None:
                                            img_corrected = img.copy()
                                        else:
                                            img_corrected = img_corrected.copy()
                                        width, height = img_corrected.size
                                        
                                        # Determine orientation based on corrected dimensions
                                        if height > width:
                                            orientation = "portrait"
                                            display_width = 100
                                        else:
                                            orientation = "landscape"
                                            display_width = 180
                                        
                                        # Display corrected image
                                        st.image(img_corrected, width=display_width)
                                        st.caption(f"📷 {orientation.title()}")
                                except Exception:
                                    st.image(fpath, width=150)
                                
                                # View full resolution button
                                if st.button("🔍 View", key=f"view_m_{i}_{mi}"):
                                    show_image_dialog(fpath, os.path.basename(m_path))
                            else: st.video(fpath)
                            
                            # Deletion logic (more complex with dicts, keeping simple for now)
                            if st.button("❌", key=f"del_m_{i}_{mi}"):
                                if isinstance(wp.get('media'), dict):
                                    # Find key by value
                                    key_to_del = next((k for k, v in wp['media'].items() if v == m_path), None)
                                    if key_to_del: del wp['media'][key_to_del]
                                else:
                                    wp['media'].pop(mi)
                                st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            # Landmarks Display (Read-Only for now)
            if 'landmarks' in wp and wp['landmarks']:
                with st.expander(f"Landmarks ({len(wp['landmarks'])})"):
                    for li, landmark in enumerate(wp['landmarks']):
                        cat = landmark.get('category', 'other')
                        
                        st.markdown(f"**{landmark.get('name', 'Unnamed Landmark')}**")
                        
                        # Display all attributes in a structured way
                        attr_cols = st.columns([1, 3])
                        
                        # Category
                        attr_cols[0].markdown("**Category:**")
                        attr_cols[1].markdown(f"`{cat}`")
                        
                        # Visual Attributes
                        if landmark.get('visual_attributes'):
                            attr_cols = st.columns([1, 3])
                            attr_cols[0].markdown("**Visual:**")
                            attr_cols[1].markdown(landmark.get('visual_attributes'))
                        
                        # Text Content
                        if landmark.get('text_content'):
                            attr_cols = st.columns([1, 3])
                            attr_cols[0].markdown("**Text:**")
                            attr_cols[1].markdown(f"`{landmark.get('text_content')}`")
                        
                        # Position
                        if landmark.get('position'):
                            pos = landmark.get('position')
                            attr_cols = st.columns([1, 3])
                            attr_cols[0].markdown("**Position:**")
                            attr_cols[1].markdown(f"x: `{pos[0]}`, y: `{pos[1]}`")
                        
                        # Divider between landmarks
                        if li < len(wp['landmarks']) - 1:
                            st.divider()
            st.markdown('</div>', unsafe_allow_html=True)

    if st.button("➕ Add Waypoint"):
        waypoints.append({"id": f"wp_{len(waypoints)+1}", "gt_entities": {}, "is_target": False, "media": []})
        st.rerun()
