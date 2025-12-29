# 🛸 UAV Mission Editor

A web-based editor for creating, managing, and visualizing UAV mission datasets with state machine configurations.

## Features

### 📂 Project Management
- Create and manage mission projects
- Each project contains multiple missions with waypoints
- Support for images and media attachments per waypoint

### 🎯 Mission Types
- Visual state machine editor for mission type configurations
- Define states, transitions, and conditions
- Configure tools and observations per state
- Supports multiple mission types (locate_and_track, locate_and_report, etc.)

### 🤖 Agentic Mission Generation
- AI-powered mission generation using Gemini
- Automatic waypoint and landmark creation
- Synthetic dataset generation with configurable distributions

### ☁️ Hugging Face Integration
- Sync projects to/from Hugging Face datasets
- Easy collaboration and data sharing

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd uav_mission_editor

# Install dependencies
pip install -r requirements.txt
```

### Running the App

```bash
streamlit run app.py --server.port 8501
```

Then open your browser to `http://localhost:8501`

## Project Structure

```
uav_mission_editor/
├── app.py                    # Main application entry point
├── requirements.txt          # Python dependencies
├── configs/
│   ├── app_config.json      # API keys and settings (gitignored)
│   └── mission_types/       # Mission type YAML configurations
├── views/
│   ├── home_view.py         # Main menu
│   ├── mission_editor_view.py
│   ├── visual_state_editor_view.py
│   ├── project_overview_view.py
│   └── ...
├── utils/
│   ├── data_utils.py
│   ├── mission_types_manager.py
│   └── ...
└── projects/                 # User projects (gitignored)
```

## Configuration

### API Keys (Settings Page)
- **Hugging Face Token**: For dataset sync
- **Gemini API Key**: For agentic mission generation

### Mission Types
Mission types define the state machine for UAV behavior:
- **States**: Define prompts, available tools, and observations
- **Transitions**: Conditions for moving between states
- **Initial State**: Starting point of the state machine

## Usage

1. **Create a Project**: Click "Create New Project" on the home page
2. **Add Missions**: Open a project and add missions with waypoints
3. **Configure Mission Types**: Use the visual editor to define state machines
4. **Generate Missions**: Use agentic creation for synthetic data
5. **Sync to HuggingFace**: Push your dataset for sharing
