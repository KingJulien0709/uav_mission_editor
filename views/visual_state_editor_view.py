import streamlit as st
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
from streamlit_flow.layouts import ManualLayout
from utils.mission_types_manager import load_mission_types, save_mission_type
from utils.ui_utils import navigate_to

# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

# High-contrast color scheme for better readability
STATE_COLORS = {
    'initial': {'bg': '#1565c0', 'border': '#0d47a1', 'text': '#ffffff'},
    'normal': {'bg': '#37474f', 'border': '#263238', 'text': '#ffffff'},
    'end': {'bg': '#2e7d32', 'border': '#1b5e20', 'text': '#ffffff'},
    'error': {'bg': '#c62828', 'border': '#b71c1c', 'text': '#ffffff'},
    'undefined': {'bg': '#616161', 'border': '#424242', 'text': '#ffffff'}
}

# Transition condition templates
CONDITION_TEMPLATES = [
    {"label": "Always True", "template": "True"},
    {"label": "Else (fallback)", "template": "else"},
    {"label": "Next Goal == value", "template": "{next_goal} == '{value}'"},
    {"label": "Action Name == value", "template": "action.name == '{value}'"},
    {"label": "Current Location == value", "template": "{current_location} == '{value}'"},
    {"label": "Locations to Visit Empty", "template": "{locations_to_be_visited} == []"},
    {"label": "Past Locations > N", "template": "len({past_locations}) > {value}"},
    {"label": "Custom Condition", "template": ""},
]


def get_available_tools_and_observations():
    """Get tools and observations from MissionEnvironment if available."""
    try:
        from uav_mission_env import MissionEnvironment
        return {
            'tools': MissionEnvironment.list_available_tools(),
            'observations': MissionEnvironment.list_available_observations()
        }
    except ImportError:
        return {
            'tools': ['next_goal', 'report_final_conclusion'],
            'observations': ['current_location', 'plan', 'locations_to_be_visited', 'past_locations', 'waypoint']
        }


def get_state_type(state_name: str, state_data: dict) -> str:
    """Determine the visual type of a state."""
    if state_name == 'end':
        return 'end'
    if state_name == 'error':
        return 'error'
    # Check if it's an end state by having only True -> end transitions
    if state_data:
        trans = state_data.get('state_transitions', {})
        conds = trans.get('conditions', [])
        if conds and all(c.get('next_state') in ('end', 'error') for c in conds):
            return 'end'
    return 'normal'


def reset_flow_state(m_type):
    """Reset flow state and increment version to force re-render."""
    flow_state_key = f"flow_state_{m_type}"
    flow_version_key = f"flow_version_{m_type}"
    st.session_state[flow_state_key] = None
    if flow_version_key in st.session_state:
        st.session_state[flow_version_key] += 1
    else:
        st.session_state[flow_version_key] = 1



# =============================================================================
# MAIN RENDER FUNCTION
# =============================================================================


def render_visual_state_editor():
    m_type = st.session_state.get('editing_mission_type')
    if not m_type:
        st.warning("No mission type selected for editing.")
        if st.button("🏠 Main Menu"):
            navigate_to('home')
        return

    mission_types = load_mission_types()
    if m_type not in mission_types:
        st.error(f"Mission type '{m_type}' not found.")
        if st.button("🏠 Main Menu"):
            navigate_to('home')
        return

    details = mission_types[m_type]
    
    # Ensure default_state and states are dictionaries
    if not isinstance(details.get("default_state"), dict):
        old_val = details.get("default_state")
        details["default_state"] = {"initial_state": old_val} if old_val else {}
    
    config = details["default_state"]
    
    if not isinstance(config.get("states"), dict):
        config["states"] = {}
    states = config["states"]

    # Ensure initial_state is valid
    if config.get("initial_state") and config["initial_state"] not in states and states:
        config["initial_state"] = list(states.keys())[0]
    elif not config.get("initial_state") and states:
        config["initial_state"] = list(states.keys())[0]
    
    initial_state = config.get("initial_state", "")

    # Header
    st.title(f"🎨 Visual Editor: {m_type.replace('_', ' ').title()}")
    
    col1, col2, col3 = st.columns([1, 1, 3])
    if col1.button("🏠 Main Menu"):
        navigate_to('home')
    if col2.button("🛠️ Text Editor"):
        navigate_to('mission_type_editor')

    # Build nodes and edges from configuration
    ui_metadata = details.get("ui_metadata", {})
    nodes, edges = build_graph_elements(states, initial_state, ui_metadata)

    # Version counter to force component re-render when changes are made
    flow_version_key = f"flow_version_{m_type}"
    if flow_version_key not in st.session_state:
        st.session_state[flow_version_key] = 0
    
    # Initialize Flow State ONLY once or on explicit reset
    flow_state_key = f"flow_state_{m_type}"
    if flow_state_key not in st.session_state or st.session_state.get(flow_state_key) is None:
        sel_id = st.session_state.pop(f"pending_selection_{m_type}", None)
        st.session_state[flow_state_key] = StreamlitFlowState(nodes=nodes, edges=edges, selected_id=sel_id)
    
    # Render Flow with ManualLayout - use version in key to force re-render
    flow_key = f"flow_{m_type}_v{st.session_state[flow_version_key]}"
    new_state = streamlit_flow(
        flow_key,
        st.session_state[flow_state_key],
        height=600,
        layout=ManualLayout(),
        get_node_on_click=True,
        get_edge_on_click=True,
        allow_new_edges=True,
        animate_new_edges=True,
        show_controls=True,
        show_minimap=True,
        hide_watermark=True
    )


    selected_id = new_state.selected_id

    # Detect and apply changes
    changes_made = False
    skipping_sync = st.session_state.get("skip_sync_once", False)

    if not skipping_sync:
        changes_made |= handle_new_edges(new_state, edges, states, details, m_type)
        changes_made |= handle_deleted_edges(new_state, edges, states, details, m_type)
        changes_made |= handle_deleted_nodes(new_state, nodes, states, details, m_type)
    else:
        st.session_state.skip_sync_once = False

    if changes_made:
        reset_flow_state(m_type)
        st.rerun()

    # Sidebar Editor
    render_sidebar_editor(selected_id, states, config, details, m_type, flow_state_key, edges, new_state, initial_state)

    # Update session state
    if not skipping_sync:
        st.session_state[flow_state_key] = new_state

    # Save positions if they changed
    new_positions = {node.id: [node.position['x'], node.position['y']] for node in new_state.nodes}
    if new_positions != ui_metadata.get("positions"):
        details.setdefault("ui_metadata", {})["positions"] = new_positions
        save_mission_type(m_type, details, prefer_yaml=True)


# =============================================================================
# GRAPH BUILDING
# =============================================================================

def build_graph_elements(states, initial_state, ui_metadata=None):
    """Convert YAML state config to graph nodes and edges with high-contrast styling."""
    nodes = []
    edges = []
    state_names = sorted(list(states.keys()))
    
    ui_metadata = ui_metadata or {}
    positions = ui_metadata.get("positions", {})
    
    cols = 2
    x_spacing, y_spacing = 300, 200
    
    for i, state_name in enumerate(state_names):
        state_data = states[state_name]
        if state_data is None:
            state_data = states[state_name] = {
                "prompt": "", "tools": [], "observations": [], 
                "state_transitions": {"conditions": []}
            }
        
        # Determine state type and colors
        is_initial = state_name == initial_state
        state_type = get_state_type(state_name, state_data)
        
        if is_initial:
            colors = STATE_COLORS['initial']
            label = f"🚀 {state_name}"
        elif state_type == 'end':
            colors = STATE_COLORS['end']
            label = f"🏁 {state_name}"
        elif state_type == 'error':
            colors = STATE_COLORS['error']
            label = f"⚠️ {state_name}"
        else:
            colors = STATE_COLORS['normal']
            label = f"📦 {state_name}"

        # Position
        if state_name in positions:
            pos = tuple(positions[state_name])
        else:
            row, col = divmod(i, cols)
            pos = (100 + col * x_spacing, 80 + row * y_spacing)

        # Tools and observations preview
        tools = state_data.get("tools", [])
        obs = state_data.get("observations", [])
        tools_str = ", ".join(tools[:2]) + ("..." if len(tools) > 2 else "") if tools else "none"
        
        nodes.append(StreamlitFlowNode(
            id=state_name,
            pos=pos,
            data={'label': label},
            node_type='default',
            source_position='bottom',
            target_position='top',
            draggable=True,
            connectable=True,
            deletable=True,
            style={
                'background': colors['bg'],
                'color': colors['text'],
                'border': f"3px solid {colors['border']}",
                'borderRadius': '10px',
                'padding': '12px',
                'width': '180px',
                'fontWeight': 'bold',
                'boxShadow': '0 4px 8px rgba(0,0,0,0.3)'
            }
        ))

        # Create edges for transitions - group by target to show as single edge
        trans = state_data.get("state_transitions", {})
        conditions = trans.get("conditions", [])
        
        # Group transitions by target
        target_conditions = {}  # target -> [(idx, condition), ...]
        for j, cond_data in enumerate(conditions):
            nxt = cond_data.get("next_state")
            if nxt:
                cond = cond_data.get("condition", "True")
                if nxt not in target_conditions:
                    target_conditions[nxt] = []
                target_conditions[nxt].append((j, cond))
        
        # Create one edge per target with combined label
        for nxt, cond_list in target_conditions.items():
            # Build combined label showing all conditions
            if len(cond_list) == 1:
                # Single condition - show as before
                display_label = cond_list[0][1]
                if len(display_label) > 30:
                    display_label = display_label[:27] + "..."
            else:
                # Multiple conditions - combine with newlines/separators
                labels = []
                for idx, cond in cond_list:
                    short_cond = cond if len(cond) < 25 else cond[:22] + "..."
                    labels.append(short_cond)
                display_label = " | ".join(labels)
                # If too long, show count
                if len(display_label) > 50:
                    display_label = f"{len(cond_list)} conditions"
            
            # Edge ID encodes all condition indices for editing
            indices_str = ",".join(str(idx) for idx, _ in cond_list)
            edge_id = f"{state_name}|{nxt}|{indices_str}"
            
            edges.append(StreamlitFlowEdge(
                id=edge_id,
                source=state_name,
                target=nxt,
                label=display_label,
                animated=False,
                edge_type='smoothstep',
                marker_end={'type': 'arrowclosed'},
                style={'stroke': '#64b5f6', 'strokeWidth': 2},
                label_style={'fill': '#ffffff', 'fontSize': '11px', 'fontWeight': 'bold'},
                label_show_bg=True,
                label_bg_style={'fill': '#1e1e1e', 'fillOpacity': 0.85, 'rx': 4, 'ry': 4},
                deletable=True
            ))

        
        # Error transition
        err = trans.get("error", {})
        if err.get("next_state"):
            edges.append(StreamlitFlowEdge(
                id=f"{state_name}|{err.get('next_state')}|error",
                source=state_name,
                target=err.get("next_state"),
                label="⚠️ error",
                style={'stroke': '#ef5350', 'strokeDasharray': '5,5', 'strokeWidth': 2},
                label_style={'fill': '#ffffff', 'fontSize': '11px', 'fontWeight': 'bold'},
                label_show_bg=True,
                label_bg_style={'fill': '#c62828', 'fillOpacity': 0.9, 'rx': 4, 'ry': 4},
                edge_type='smoothstep',
                marker_end={'type': 'arrowclosed'},
                deletable=True
            ))

    # Add referenced but undefined states (like 'end', 'error')
    referenced = set()
    for s_data in states.values():
        if s_data:
            t = s_data.get("state_transitions", {})
            for c in t.get("conditions", []):
                if c.get("next_state"):
                    referenced.add(c.get("next_state"))
            if t.get("error", {}).get("next_state"):
                referenced.add(t.get("error", {}).get("next_state"))
    
    for ref in referenced:
        if ref and ref not in states and not any(n.id == ref for n in nodes):
            if ref == 'end':
                colors = STATE_COLORS['end']
                label = '🏁 end'
            elif ref == 'error':
                colors = STATE_COLORS['error']
                label = '⚠️ error'
            else:
                colors = STATE_COLORS['undefined']
                label = f"❓ {ref}"
            
            if ref in positions:
                pos = tuple(positions[ref])
            else:
                row = len(nodes) // cols
                pos = (100 + (len(nodes) % cols) * x_spacing, 80 + row * y_spacing)

            nodes.append(StreamlitFlowNode(
                id=ref, pos=pos,
                data={'label': label}, node_type='default',
                source_position='bottom', target_position='top',
                connectable=True, deletable=False,
                style={
                    'background': colors['bg'],
                    'color': colors['text'],
                    'border': f"2px dashed {colors['border']}",
                    'borderRadius': '10px',
                    'padding': '10px',
                    'fontWeight': 'bold'
                }
            ))

    return nodes, edges


# =============================================================================
# SIDEBAR EDITOR
# =============================================================================

def render_sidebar_editor(selected_id, states, config, details, m_type, flow_state_key, edges, new_state, initial_state):
    """Render the improved sidebar editor for states and transitions."""
    
    env_data = get_available_tools_and_observations()
    available_tools = env_data['tools']
    available_observations = env_data['observations']
    
    with st.sidebar:
        st.header("🛸 Editor Panel")
        
        # State Editor
        if selected_id and selected_id in states:
            render_state_editor(
                selected_id, states, config, details, m_type, 
                flow_state_key, available_tools, available_observations, initial_state
            )
        
        # Edge selected
        elif selected_id and "|" in selected_id:
            render_edge_editor(selected_id, states, details, m_type, flow_state_key)
        
        else:
            st.info("👆 Click a state or transition to edit")

        st.divider()
        
        # Reset Layout Button
        if st.button("🔄 Reset Layout", use_container_width=True):
            if "ui_metadata" in details:
                del details["ui_metadata"]
                save_mission_type(m_type, details, prefer_yaml=True)
            reset_flow_state(m_type)
            st.rerun()

        # Create New State Section
        render_create_state_panel(states, config, details, m_type, flow_state_key, selected_id, available_tools, available_observations)


def render_state_editor(selected_id, states, config, details, m_type, flow_state_key, available_tools, available_observations, initial_state):
    """Render editor for a selected state node."""
    
    st.subheader(f"📦 {selected_id}")
    
    if states[selected_id] is None:
        states[selected_id] = {
            "prompt": "", "tools": [], "observations": [], 
            "state_transitions": {"conditions": []}
        }
    state_data = states[selected_id]
    
    # Initial State Toggle
    is_initial = selected_id == initial_state
    col_init, col_type = st.columns([1, 1])
    
    with col_init:
        if st.checkbox("🚀 Initial State", value=is_initial, key=f"initial_{selected_id}"):
            if not is_initial:
                config["initial_state"] = selected_id
                save_mission_type(m_type, details, prefer_yaml=True)
                reset_flow_state(m_type)
                st.toast(f"'{selected_id}' set as initial state")
                st.rerun()
    
    # State Type Info
    with col_type:
        state_type = get_state_type(selected_id, state_data)
        st.caption(f"Type: {state_type.title()}")
    
    st.divider()
    
    # Main Form
    with st.form(key=f"edit_{selected_id}"):
        # Prompt
        new_prompt = st.text_area(
            "📝 Prompt", 
            value=state_data.get("prompt", ""), 
            height=150,
            help="System prompt for this state"
        )
        
        # Tools Selection
        current_tools = state_data.get("tools", [])
        if not isinstance(current_tools, list):
            current_tools = []
        
        # Combine available tools with any custom tools already in the state
        all_tools = list(set(available_tools + current_tools))
        new_tools = st.multiselect(
            "🔧 Tools",
            options=all_tools,
            default=[t for t in current_tools if t in all_tools],
            help="Tools the agent can use"
        )
        
        # Custom tool input
        add_tool = st.text_input("➕ Add custom tool", placeholder="tool_name")
        
        # Observations Selection
        current_obs = state_data.get("observations", [])
        if not isinstance(current_obs, list):
            current_obs = []
        
        all_obs = list(set(available_observations + current_obs))
        new_obs = st.multiselect(
            "👁️ Observations",
            options=all_obs,
            default=[o for o in current_obs if o in all_obs],
            help="Data fields available to the agent"
        )
        
        add_obs = st.text_input("➕ Add custom observation", placeholder="observation_name")

        if st.form_submit_button("💾 Save State", use_container_width=True, type="primary"):
            state_data["prompt"] = new_prompt
            
            final_tools = list(new_tools)
            if add_tool and add_tool.strip() not in final_tools:
                final_tools.append(add_tool.strip())
            state_data["tools"] = final_tools

            final_obs = list(new_obs)
            if add_obs and add_obs.strip() not in final_obs:
                final_obs.append(add_obs.strip())
            state_data["observations"] = final_obs

            save_mission_type(m_type, details, prefer_yaml=True)
            st.toast("State saved!")
            st.rerun()

    # Transitions Section
    st.divider()
    st.subheader("🔗 Transitions")
    
    trans = state_data.get("state_transitions", {})
    conditions = trans.get("conditions", [])
    
    for idx, cond in enumerate(conditions):
        target = cond.get('next_state', '?')
        with st.expander(f"→ {target}", expanded=False):
            render_condition_editor(cond, idx, selected_id, details, m_type, flow_state_key, conditions)
    
    # Add New Transition
    with st.expander("➕ Add Transition"):
        render_add_transition(selected_id, states, details, m_type, flow_state_key)
    
    # Error Transition
    with st.expander("⚠️ Error Transition"):
        render_error_transition(selected_id, trans, states, details, m_type, flow_state_key)
    
    # Delete State
    st.divider()
    if st.button("🗑️ Delete State", type="secondary", use_container_width=True, key=f"del_state_{selected_id}"):
        delete_state(selected_id, states, details, m_type, flow_state_key)


def render_condition_editor(cond, idx, state_id, details, m_type, flow_state_key, conditions):
    """Render editor for a single transition condition using a form to prevent auto-rerun."""
    
    current_cond = cond.get("condition", "True")
    
    # Use a form for editing (prevents rerun on widget changes)
    with st.form(key=f"cond_form_{state_id}_{idx}"):
        # Template selector
        template_labels = [t["label"] for t in CONDITION_TEMPLATES]
        selected_template = st.selectbox(
            "Template",
            options=["-- Keep Current --"] + template_labels,
            key=f"tmpl_{state_id}_{idx}"
        )
        
        # Value input for templates that need it
        template_value = st.text_input("Template Value (if needed)", key=f"val_{state_id}_{idx}", 
                                        help="Enter value for templates like 'Next Goal == value'")
        
        # Manual condition edit - starts with current value
        new_cond = st.text_area("Condition (edit directly or use template above)", 
                                value=current_cond, 
                                key=f"cond_{state_id}_{idx}", 
                                height=80)
        
        update_clicked = st.form_submit_button("✅ Update Condition", use_container_width=True)
    
    # Process form submission
    if update_clicked:
        # Check if template was selected
        final_cond = new_cond
        if selected_template != "-- Keep Current --":
            template = next(t["template"] for t in CONDITION_TEMPLATES if t["label"] == selected_template)
            if "{value}" in template and template_value:
                final_cond = template.replace("{value}", template_value)
            elif template:
                final_cond = template
        
        cond["condition"] = final_cond
        save_mission_type(m_type, details, prefer_yaml=True)
        reset_flow_state(m_type)
        st.toast("Transition updated!")
        st.rerun()
    
    # Delete button OUTSIDE the form so it works independently
    if st.button("🗑️ Delete Transition", key=f"del_{state_id}_{idx}", use_container_width=True, type="secondary"):
        conditions.pop(idx)
        save_mission_type(m_type, details, prefer_yaml=True)
        reset_flow_state(m_type)
        st.toast("Transition deleted!")
        st.rerun()



def render_add_transition(state_id, states, details, m_type, flow_state_key):
    """Render UI for adding a new transition."""
    
    possible_targets = list(states.keys()) + ["end", "error"]
    possible_targets = [t for t in possible_targets if t != state_id]
    
    target = st.selectbox("Target State", options=[""] + possible_targets, key=f"new_trans_target_{state_id}")
    
    # Template selector
    template_labels = [t["label"] for t in CONDITION_TEMPLATES]
    selected_template = st.selectbox("Condition Template", options=template_labels, key=f"new_trans_tmpl_{state_id}")
    
    template = next(t["template"] for t in CONDITION_TEMPLATES if t["label"] == selected_template)
    
    condition = template
    if "{value}" in template:
        value = st.text_input("Value", key=f"new_trans_val_{state_id}")
        if value:
            condition = template.replace("{value}", value)
    elif not template:
        condition = st.text_input("Custom Condition", value="True", key=f"new_trans_custom_{state_id}")
    
    if st.button("➕ Add Transition", key=f"add_trans_{state_id}", use_container_width=True):
        if target:
            state_data = states[state_id]
            trans = state_data.setdefault("state_transitions", {})
            conds = trans.setdefault("conditions", [])
            conds.append({"condition": condition, "next_state": target})
            save_mission_type(m_type, details, prefer_yaml=True)
            reset_flow_state(m_type)
            st.toast(f"Transition to '{target}' added!")
            st.rerun()
        else:
            st.warning("Select a target state")


def render_error_transition(state_id, trans, states, details, m_type, flow_state_key):
    """Render error transition editor."""
    
    err = trans.get("error", {})
    possible_targets = [""] + list(states.keys()) + ["end", "error"]
    current_target = err.get("next_state", "")
    
    try:
        default_index = possible_targets.index(current_target)
    except ValueError:
        default_index = 0

    err_tgt = st.selectbox("Error Target", options=possible_targets, index=default_index, key=f"err_tgt_{state_id}")
    
    if st.button("Update Error", key=f"err_upd_{state_id}", use_container_width=True):
        if err_tgt:
            trans["error"] = {"next_state": err_tgt}
        elif "error" in trans:
            del trans["error"]
        save_mission_type(m_type, details, prefer_yaml=True)
        reset_flow_state(m_type)
        st.toast("Error transition updated!")
        st.rerun()


def render_edge_editor(selected_id, states, details, m_type, flow_state_key):
    """Render editor for a selected edge - handles multiple conditions per edge."""
    
    parts = selected_id.split("|")
    if len(parts) >= 3:
        src, tgt = parts[0], parts[1]
        indices_str = parts[2]
        
        st.subheader(f"🔗 {src} → {tgt}")
        
        if "error" in indices_str:
            st.info("⚠️ Error transition - edit via State Editor")
            return
        
        if src in states:
            trans = states[src].get("state_transitions", {})
            conds = trans.get("conditions", [])
            
            # Parse indices (could be "0" or "0,1,2" for multiple)
            try:
                indices = [int(i) for i in indices_str.split(",")]
            except ValueError:
                st.error("Invalid edge selection")
                return
            
            # Show editor for each condition
            for enum_idx, idx in enumerate(indices):
                if idx < len(conds):
                    c = conds[idx]
                    if len(indices) > 1:
                        st.markdown(f"**Condition {enum_idx + 1} of {len(indices)}**")
                    render_condition_editor(c, idx, src, details, m_type, flow_state_key, conds)
                    if enum_idx < len(indices) - 1:
                        st.divider()



def render_create_state_panel(states, config, details, m_type, flow_state_key, selected_id, available_tools, available_observations):
    """Render the create new state panel."""
    
    st.subheader("➕ Create State")
    
    with st.container(border=True):
        if "creation_counter" not in st.session_state:
            st.session_state.creation_counter = 0
        
        ns = st.text_input(
            "State Name", 
            placeholder="e.g. search_target", 
            key=f"ns_input_{st.session_state.creation_counter}"
        )
        
        template = st.selectbox("Template", [
            "Empty State",
            "Execution State",
            "Conclusion State",
            "Copy Selected"
        ], key=f"template_input_{st.session_state.creation_counter}")

        if st.button("🚀 Create", use_container_width=True, type="primary"):
            if not ns:
                st.error("Enter a state name")
            elif ns in states:
                st.error(f"'{ns}' already exists")
            elif not ns.replace("_", "").isalnum():
                st.error("Invalid name - use letters, numbers, underscores")
            else:
                new_state_data = {
                    "prompt": "", 
                    "tools": [], 
                    "observations": [], 
                    "state_transitions": {"conditions": []}
                }
                
                if not states:
                    config["initial_state"] = ns
                    st.info(f"'{ns}' set as initial state")

                if template == "Execution State":
                    new_state_data["prompt"] = "You are a UAV controller executing a task plan.\n\n## Reasoning\nPut your thought process inside <think></think> tags."
                    new_state_data["tools"] = ["next_goal"]
                    new_state_data["observations"] = ["current_location", "plan", "locations_to_be_visited"]
                elif template == "Conclusion State":
                    new_state_data["prompt"] = "Provide the final answer based on all gathered data."
                    new_state_data["tools"] = ["report_final_conclusion"]
                    new_state_data["observations"] = ["plan"]
                    new_state_data["state_transitions"]["conditions"] = [{"condition": "True", "next_state": "end"}]
                elif template == "Copy Selected" and selected_id and selected_id in states:
                    import copy
                    new_state_data = copy.deepcopy(states[selected_id])
                    new_state_data["state_transitions"] = {"conditions": []}

                states[ns] = new_state_data
                config["states"] = states
                details["default_state"] = config
                
                # Position
                if "ui_metadata" not in details:
                    details["ui_metadata"] = {"positions": {}}
                
                positions = details["ui_metadata"]["positions"]
                if selected_id and selected_id in positions:
                    pos = positions[selected_id]
                    positions[ns] = [pos[0] + 250, pos[1]]
                elif positions:
                    max_y = max(p[1] for p in positions.values())
                    positions[ns] = [100, max_y + 200]
                else:
                    positions[ns] = [100, 100]

                save_mission_type(m_type, details, prefer_yaml=True)
                
                st.session_state.creation_counter += 1
                reset_flow_state(m_type)
                st.session_state[f"pending_selection_{m_type}"] = ns
                st.session_state.skip_sync_once = True
                
                st.toast(f"State '{ns}' created!")
                st.rerun()


def delete_state(state_id, states, details, m_type, flow_state_key):
    """Delete a state and clean up references."""
    
    if state_id in states:
        del states[state_id]
        
        # Remove transitions pointing to this state
        for s_name, s_data in states.items():
            if s_data:
                t = s_data.get("state_transitions", {})
                conds = t.get("conditions", [])
                s_data["state_transitions"]["conditions"] = [
                    c for c in conds if c.get("next_state") != state_id
                ]
                if t.get("error", {}).get("next_state") == state_id:
                    del t["error"]
        
        # Remove from positions
        if "ui_metadata" in details and "positions" in details["ui_metadata"]:
            if state_id in details["ui_metadata"]["positions"]:
                del details["ui_metadata"]["positions"][state_id]
        
        save_mission_type(m_type, details, prefer_yaml=True)
        reset_flow_state(m_type)
        st.toast(f"State '{state_id}' deleted")
        st.rerun()


# =============================================================================
# CHANGE HANDLERS
# =============================================================================

def handle_new_edges(new_state, original_edges, states, details, m_type):
    """Detect and save new edges created visually."""
    original_ids = {e.id for e in original_edges}
    changed = False
    
    for edge in new_state.edges:
        if edge.id not in original_ids:
            src, tgt = edge.source, edge.target
            if src in states:
                trans = states[src].setdefault("state_transitions", {})
                conds = trans.setdefault("conditions", [])
                
                if not any(c.get("next_state") == tgt for c in conds):
                    conds.append({"condition": "True", "next_state": tgt})
                    save_mission_type(m_type, details, prefer_yaml=True)
                    st.toast(f"✨ Transition: {src} → {tgt}")
                    changed = True
    return changed


def handle_deleted_edges(new_state, original_edges, states, details, m_type):
    """Detect and remove edges deleted visually."""
    current_edge_ids = {e.id for e in new_state.edges}
    changed = False
    
    for orig_edge in original_edges:
        if orig_edge.id not in current_edge_ids:
            parts = orig_edge.id.split("|")
            if len(parts) >= 2:
                src, tgt = parts[0], parts[1]
                is_error = "error" in orig_edge.id
                
                if src in states:
                    trans = states[src].get("state_transitions", {})
                    
                    if is_error:
                        if "error" in trans:
                            del trans["error"]
                            save_mission_type(m_type, details, prefer_yaml=True)
                            st.toast("🗑️ Error transition removed")
                            changed = True
                    else:
                        conds = trans.get("conditions", [])
                        for idx, c in enumerate(conds):
                            if c.get("next_state") == tgt:
                                conds.pop(idx)
                                save_mission_type(m_type, details, prefer_yaml=True)
                                st.toast(f"🗑️ Transition removed: {src} → {tgt}")
                                changed = True
                                break
    return changed


def handle_deleted_nodes(new_state, original_nodes, states, details, m_type):
    """Detect and remove nodes deleted visually."""
    current_node_ids = {n.id for n in new_state.nodes}
    changed = False
    
    for orig_node in original_nodes:
        if orig_node.id not in current_node_ids:
            if orig_node.id in states:
                del states[orig_node.id]
                for s_name, s_data in states.items():
                    if s_data:
                        t = s_data.get("state_transitions", {})
                        conds = t.get("conditions", [])
                        s_data["state_transitions"]["conditions"] = [
                            c for c in conds if c.get("next_state") != orig_node.id
                        ]
                        if t.get("error", {}).get("next_state") == orig_node.id:
                            del t["error"]
                
                if "ui_metadata" in details and "positions" in details["ui_metadata"]:
                    if orig_node.id in details["ui_metadata"]["positions"]:
                        del details["ui_metadata"]["positions"][orig_node.id]
                
                save_mission_type(m_type, details, prefer_yaml=True)
                st.toast(f"🗑️ State '{orig_node.id}' removed")
                changed = True
    return changed
