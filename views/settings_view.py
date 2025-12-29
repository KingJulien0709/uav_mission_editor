import streamlit as st
from utils.config_manager import load_config, save_config
from utils.hf_utils import sync_from_hf, sync_to_hf
from utils.ui_utils import navigate_to

def render_settings():
    st.title("⚙️ Settings")
    
    tabs = st.tabs(["API Keys", "Sync"])
    
    with tabs[0]:
        config = load_config()
        with st.form("settings_form"):
            hf_token = st.text_input("Hugging Face Token", value=config.get("hf_token", ""), type="password")
            gemini_key = st.text_input("Gemini API Key", value=config.get("gemini_api_key", ""), type="password")
            if st.form_submit_button("💾 Save Keys"):
                save_config(hf_token, gemini_key)
                st.success("Keys saved.")

    with tabs[1]:
        config = load_config()
        repo_id = st.text_input("Repository ID", placeholder="username/dataset-name")
        c1, c2 = st.columns(2)
        if c1.button("⬇️ Pull Project"):
            if repo_id and config.get('hf_token'):
                with st.spinner("Pulling..."):
                    sync_from_hf(repo_id, "projects", token=config.get("hf_token"))
                    st.success("Synced!")
        if c2.button("⬆️ Push Project"):
            if repo_id and config.get('hf_token'):
                with st.spinner("Pushing..."):
                    sync_to_hf(repo_id, "projects", token=config.get("hf_token"))
                    st.success("Pushed!")

    st.divider()
    if st.button("⬅️ Back"): navigate_to('home')
