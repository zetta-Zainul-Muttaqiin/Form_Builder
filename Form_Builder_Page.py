import streamlit as st
import os
import re
import glob
import uuid
import json
from datetime import datetime
from engine.form_builder import run_agent_form 
from setup import LOGGER, QUESTION_TYPES


st.set_page_config(
    page_title="AI Form Builder",
    layout="centered",
    initial_sidebar_state="expanded"
)

# *************** Session State to Hold Form Result ***************
if "form_result" not in st.session_state:
    st.session_state.form_result = None


def display_editable_form(form_result, form_path):
    if not form_result:
        st.warning("No form data.")
        return
    
    # Get list of labels and reverse lookup
    type_keys = list(QUESTION_TYPES.keys())
    type_labels = list(QUESTION_TYPES.values())

    form_description = form_result.get("description", "")
    form_steps = form_result.get("steps", [])

    st.markdown(f"### 📝 Form Description")
    st.text_area("Description:", value=form_description)

    for step_idx, step in enumerate(form_steps):
        step_name = step.get("step_name", f"Step {step_idx+1}")
        step_description = step.get("step_description", "")

        st.markdown(f"#### 🧾 {step_name}")
        st.caption(step_description)

        edited_questions = []

        for q_idx, question in enumerate(step.get("step_questions", [])):
            with st.container(border=True):

                st.markdown(f"**Question {q_idx+1}**")

                q_text = st.text_input(
                    "Question Text", value=question.get("question_text", ""),
                    key=f"qtext_{step_idx}_{q_idx}"
                )
                current_type_key = question.get("question_type", type_keys[0])
                current_label = QUESTION_TYPES.get(current_type_key, type_labels[0])
                default_index = type_labels.index(current_label)
                q_type = st.selectbox(
                    "Question Type", options=type_labels, index=default_index,
                    key=f"qtype_{step_idx}_{q_idx}"
                )

                q_desc = st.text_area(
                    "Question Description", value=question.get("question_description", ""),
                    key=f"qdesc_{step_idx}_{q_idx}"
                )

                q_example = st.text_area(
                    "Question Example", value=question.get("question_example", ""),
                    key=f"qexample_{step_idx}_{q_idx}"
                )

                # Format question_example if it's a list-type question
                parsed_example = q_example
                if q_type in [
                    "single_option", "multiple_option",
                    "dropdown_single_option", "multiple_choice_dropdown_menu",
                    "slider_rating"
                ]:
                    options = [opt.strip() for opt in re.split(r'[\n,]+', q_example) if opt.strip()]
                    parsed_example = " / ".join(options)

                edited_questions.append({
                    "question_text": q_text,
                    "question_type": q_type,
                    "question_description": q_desc,
                    "question_example": parsed_example
                })

        # Button to Save Changes for this step
        if st.button(f"💾 Save Step {step_idx+1}", key=f"save_step_{step_idx}", type='primary'):
            form_result["steps"][step_idx]["step_questions"] = edited_questions
            write_json_form(form_result, form_path)
            st.success(f"Step {step_idx+1} updated successfully.")

        st.markdown("---")

def write_json_form(form_data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(form_data, f, indent=2)



# *************** Display Form in Tabs ***************
def display_selected_form(form_result, form_path):
    if not form_result:
        st.warning("No form selected.")
        return

    form_description = form_result.get("description", "")
    form_steps = form_result.get("steps", [])
    form_title = form_result.get("form_title", "Form Title")

    tab1, tab2 = st.tabs(["🗂 Form Details", "📝 Preview Form"])

    # *************** Tab 1: Form Details ***************
    with tab1:
        display_editable_form(form_result, form_path)

    # *************** Tab 2: Preview Form Interaction ***************
    with tab2:
        st.markdown(f"### 📝 {form_title}")
        st.info(form_description)
        
        for id_step, step in enumerate(form_steps):
            step_name = step.get("step_name", f"Step {id_step+1}")
            with st.expander(f"{id_step+1}/ {step_name}"):

                for id_question, question in enumerate(step.get("step_questions", [])):
                    render_question_input(question, id_step, id_question)


# *************** Render Question Input ***************
def render_question_input(question, step_idx, q_idx):
    question_text = question.get("question_text", "Untitled")
    question_type = question.get("question_type", "Unknown").lower().strip()
    question_example = question.get("question_example", "")
    input_key = f"step{step_idx}_q{q_idx}_{question_text[:5]}"

    if question_type == "short_text":
        st.text_input(question_text, placeholder=question_example or "", key=input_key)

    elif question_type == "text_area_long":
        st.text_area(question_text, placeholder=question_example or "", key=input_key)

    elif question_type == "date":
        st.date_input(question_text, key=input_key)

    elif question_type == "time":
        st.time_input(question_text, key=input_key)

    elif question_type == "duration":
        st.text_input(f"{question_text} (e.g. 1h 30m)", key=input_key)

    elif question_type == "email":
        st.text_input(question_text, placeholder="example@example.com", key=input_key)

    elif question_type == "multiple_choice_dropdown_menu":
        st.multiselect(question_text, options=question_example.split(" / ") if isinstance(question_example, str) else question_example, key=input_key)

    elif question_type == "dropdown_single_option":
        st.selectbox(question_text, options=question_example.split(" / ") if isinstance(question_example, str) else question_example, key=input_key)

    elif question_type == "multiple_option":
        st.multiselect(question_text, options=question_example.split(" / ") if isinstance(question_example, str) else question_example, key=input_key)

    elif question_type == "single_option":
        st.radio(question_text, options=question_example.split(" / ") if isinstance(question_example, str) else question_example, key=input_key)

    elif question_type == "slider_rating":
        render_slider_rating(question_text, question_example, input_key)

    elif question_type == "upload_document":
        st.file_uploader(question_text, type=["pdf", "docx", "txt"], key=input_key)

    else:
        st.warning(f"{question_text} - Unsupported input type: {question_type}")

def render_slider_rating(question_text,question_example, input_key):
    if question_example:
        try:
            # Try splitting by ' - ', ',' or space
            parts = re.split(r"[,\s\-]+", question_example.strip())
            min_val = int(parts[0])
            max_val = int(parts[1]) if len(parts) > 1 else min_val + 10
        except Exception as e:
            st.warning(f"⚠️ Invalid example format for slider: '{question_example}'. Using default 1-5")
            min_val, max_val = 1, 5
    else:
        min_val, max_val = 1, 5

    st.slider(
        label=question_text,
        min_value=min_val,
        max_value=max_val,
        key=input_key
    )


# *************** Render Question Card ***************
def render_question_card(question, index):
    question_text = question.get("question_text", "Untitled")
    question_type = question.get("question_type", "Unknown").lower().strip()
    question_description = question.get("question_description", "")
    question_example = question.get("question_example", "")

    # Render metadata as card
    with st.container():
        st.markdown(f"""
            <div style="border:1px solid #e6e6e6; border-left: 6px solid #A3A3FF;
                        padding: 12px 16px; margin-bottom: 10px; border-radius: 6px;
                        background-color: #f9f9f9;">
                <h4 style="margin-bottom: 0;">{index + 1}. {question_text}</h4>
                <p style="margin: 4px 0;"><strong>Type:</strong> {question_type}</p>
                <p style="margin: 4px 0;"><strong>Description:</strong> {question_description}</p>
                {f"<p style='margin: 4px 0;'><strong>Example:</strong> {question_example} </p>" if question_example else ""}
            </div>
        """, unsafe_allow_html=True)


# *************** Render All Steps ***************
def render_form_steps(steps: list):
    for index_step, step in enumerate(steps):
        st.markdown(f"### 🪜 Step {index_step + 1}: {step.get('step_name', 'Unnamed Step')}")
        st.markdown(f"**{step.get('step_description', '')}**")
        for index_question, question in enumerate(step.get("step_questions", [])):
            render_question_card(question, index_question)
        st.markdown("---")



# *************** Prompt Popup Dialog ***************
@st.dialog("Enter Form Prompt")
def prompt_dialog():
    prompt_input = st.text_area("Describe the form you want to create:", placeholder="e.g. A three-page student registration form...")
    col1, _ = st.columns(2)
    with col1:
        if st.button("🚀 Generate Form"):
            if not prompt_input.strip():
                st.warning("Please enter a prompt.")
                st.stop()
            with st.spinner("Generating form..."):
                try:
                    result = run_agent_form(prompt_input)
                    st.session_state.form_result = result
                    st.success("Form generated!")
                except Exception as error:
                    st.error("Failed to generate form.")
                    st.exception(error)
            
            if result:
                save_form_response(result)
                st.rerun(scope='fragment')

def save_form_response(form_response: dict):

    FORM_DIR = os.path.join('data', 'form_builder')
    # *************** Generate ID and Timestamp ***************
    form_id = f"form_{datetime.now().strftime('%d%m%Y')}_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now().strftime('%d_%m_%Y: %H:%M')

    # *************** Construct Save Format ***************
    save_data = {
        "form_id": form_id,
        "timestamp": {
            "created_at": created_at
        },
        "form_content": form_response
    }

    # *************** Save JSON ***************
    os.makedirs(FORM_DIR, exist_ok=True)
    file_path = os.path.join(FORM_DIR, f"{form_id}.json")
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2)

    return file_path

def list_saved_forms():
    form_dir = "data/form_builder"
    os.makedirs(form_dir, exist_ok=True)
    form_list = []

    for path in glob.glob(os.path.join(form_dir, "form_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                timestamp = data.get("timestamp", {}).get("created_at", "00_00_0000: 00:00")
                form_list.append((path, timestamp))
        except Exception as e:
            LOGGER.error(f"Error reading {path}: {e}")
    
    # Sort by timestamp descending
    form_list.sort(key=lambda x: datetime.strptime(x[1], "%d_%m_%Y: %H:%M"), reverse=True)

    return [item[0] for item in form_list]


def load_form_content(file_path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def main_page():
    # *************** Main UI: Result Section ***************
    st.title("📝 AI-Powered Form Builder")
    st.markdown("Click the button below to generate a Form using Agentic AI.")
    
    with st.sidebar:
        st.markdown("### 📄 Generated Forms")

        form_files = list_saved_forms()
        with st.container(border=True, height=350):
            if not form_files:
                st.info("No saved forms found.")
            else:
                for file_path in form_files:
                    data = load_form_content(file_path)
                    file_name = os.path.basename(file_path)
                    form_id = data.get('form_id', 'id')
                    form_title = data.get("form_content").get('form_title', '')
                    created_at = data.get("timestamp", {}).get("created_at", "unknown")

                    # Display card-like layout
                    container = st.container(key=form_id)
                    container.markdown(f"""
                        <div style="border: 1px solid #ddd; border-radius: 10px; padding: 10px; margin-bottom: 10px;">
                            <strong>{form_title if form_title else file_name}</strong><br>
                            <span style='color: gray;'>🕒 {created_at}</span><br><br>
                        </div>
                    """, unsafe_allow_html=True)

                    view_key = f"view_{form_id}"
                    view_button = container.button("🔍 View", key=view_key)
                    if view_button:
                        st.session_state.form_result = data["form_content"]
                        st.session_state.form_loaded_name = file_name  # optional: track which was loaded
                    
                    st.markdown("\n")
                
    
    # *************** Show Prompt Button ***************
    if st.button("Create New Form Prompt"):
        prompt_dialog()

    st.divider()

    # *************** Display the Form Result ***************
    if st.session_state.form_result:
        display_selected_form(st.session_state.form_result, st.session_state.form_loaded_name)



if __name__ == "__main__":
    main_page()