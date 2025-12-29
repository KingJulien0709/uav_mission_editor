import streamlit as st
from PIL import Image, ImageOps

def navigate_to(page):
    """Simple navigation helper using session state."""
    st.session_state.page = page
    st.rerun()

def get_badge_html(tag_type):
    """Returns HTML for a mission tag badge."""
    return f'<span class="badge-{tag_type}">{tag_type.replace("_", " ").title()}</span>'

@st.dialog("Media Preview", width="large")
def preview_media(file_path):
    """Dialog for previewing images or video."""
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        img = Image.open(file_path)
        img = ImageOps.exif_transpose(img)
        st.image(img)
    elif file_path.lower().endswith(('.mp4', '.avi', '.mov')):
        st.video(file_path)

def apply_custom_styles():
    """Injects custom CSS into the Streamlit app."""
    st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }
        .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
        # .project-card, .mission-card, .waypoint-card { ... } /* Legacy classes, using st.container now */
        
        .media-scroll {
            display: flex;
            overflow-x: auto;
            gap: 15px;
            padding: 10px 0;
        }
        .media-scroll img, .media-scroll video {
            height: 150px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .badge-locate_and_report { background-color: #e3f2fd; color: #0d47a1; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }
        .badge-locate_and_land_safely { background-color: #e8f5e9; color: #1b5e20; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }
        .badge-locate_and_track { background-color: #fff3e0; color: #e65100; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }
        
        .badge-sft_train { background-color: #f3e5f5; color: #4a148c; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; border: 1px solid #ce93d8; }
        .badge-rl_train { background-color: #e0f2f1; color: #004d40; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; border: 1px solid #80cbc4; }
        .badge-validation { background-color: #f5f5f5; color: #616161; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; border: 1px solid #e0e0e0; }
        
        .badge-manual { background-color: #e3f2fd; color: #0d47a1; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; border: 1px solid #90caf9; }
        .badge-synthetic { background-color: #f3e5f5; color: #7b1fa2; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; border: 1px solid #ce93d8; }
        
        /* Hide sidebar navigation */
        [data-testid="stSidebarNav"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

def get_split_badge_html(split_name):
    """Returns HTML for a dataset split badge."""
    if not split_name: return ""
    return f'<span class="badge-{split_name}">{split_name.replace("_", " ").upper()}</span>'

def get_source_badge_html(source_name):
    """Returns HTML for a creation source badge."""
    if not source_name: return ""
    if source_name == "synthetic":
        return f'<span class="badge-synthetic">✨ SYNTHETIC</span>'
    return f'<span class="badge-{source_name}">{source_name.upper()}</span>'
