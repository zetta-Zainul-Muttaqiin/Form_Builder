import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import os
import re
import glob
import uuid
import json
from datetime import datetime
from setup import LOGGER, QUESTION_TYPES


from engine.form_builder import run_agent_form 
from engine.prompt_suggestion import run_prompt_suggestion


from helpers.streamlit_component import (
    render_date_input,
    render_duration,
    render_email_input,
    render_multiselect,
    render_radio,
    render_selectbox,
    render_short_text,
    render_slider_rating,
    render_text_area_long,
    render_time_input,
    render_upload_document
) 

st.set_page_config(
    page_title="AI Form Builder",
    layout="centered",
    initial_sidebar_state="expanded"
)

# *************** Session State to Hold Form Result ***************
if "form_result" not in st.session_state:
    st.session_state.form_result = None

if "form_loaded_name" not in st.session_state:
                st.session_state.form_loaded_name = None
                st.session_state.form_result = None



# *************** Prompt Popup Dialog ***************

def get_prompt_suggestions() -> dict:
    """Fetch prompt suggestions and cache them in session state."""
    if 'form_input_suggests' not in st.session_state:
        st.session_state.form_input_suggests = run_prompt_suggestion(3)
    return st.session_state.form_input_suggests

def render_prompt_suggestions():
    """Render prompt suggestion buttons and handle prompt injection."""
    suggestions = get_prompt_suggestions()
    st.markdown("##### 💡 Prompt Suggestions")
    _, col, _ = st.columns([0.05,0.9,0.05], vertical_alignment="center")
    for idx, prompt in enumerate(suggestions):
        key_prompt = f"prompt_suggest_{idx}"
        split_prompt = prompt.split()
        with col:
            if st.button(f"{' '.join(split_prompt[:20])}...", key=key_prompt, help=prompt):
                st.session_state.prompt_input_text = prompt
                st.rerun(scope="fragment")

def handle_generate_form(prompt_text: str) -> None:
    """Run agent to generate form and save it."""
    if not prompt_text.strip():
        st.warning("Please enter a prompt.")
        st.stop()

    with st.spinner("Generating form..."):
        try:
            result = run_agent_form(prompt_text)
            st.success("Form generated!")
        except Exception as error:
            st.error("❌ Failed to generate form.")
            st.exception(error)
            return

        if result:
            save_form_response(result)  # Save JSON file
            st.rerun()  # Trigger refresh to show in preview tab

@st.dialog("Enter Form Prompt", width="large")
def prompt_dialog():
    # Initialize prompt input text if needed
    if 'prompt_input_text' not in st.session_state:
        st.session_state.prompt_input_text = ""

    # Prompt input text area
    st.session_state.prompt_input_text = st.text_area(
        "Describe the form you want to create:",
        value=st.session_state.prompt_input_text,
        placeholder="e.g. A three-page student registration form..."
    )

    # Prompt suggestion section
    prompt_container = st.container(border=True)

    # Action buttons
    col1, _, col2 = st.columns([0.4,0.35,0.25])

    with col1:
        if st.button("🚀 Generate Form"):
            handle_generate_form(st.session_state.prompt_input_text)
    
    with prompt_container:
        with st.spinner("Creating prompt suggestions..."):
                render_prompt_suggestions()

    with col2:
        if st.button("🔁 Refresh Prompt"):
            with st.spinner("Refreshing prompt suggestions..."):
                st.session_state.form_input_suggests = run_prompt_suggestion()
                st.rerun(scope='fragment')
               

# *************** Shared Helper for List-Type Example Parsing ***************
def parse_list_type_example(example_text: str) -> list[str]:
    """
    Parse list-type example string into a list of options.
    
    Supports delimiters: newline (\n), comma (,), semicolon (;), slash (/), and backslash.
    """
    if not isinstance(example_text, str):
        return []
    
    normalized = example_text.replace("\\n", "\n")  # Convert escaped newline to real newline
    return [opt.strip() for opt in re.split(r'[\n,;/\\]+', normalized) if opt.strip()]


def display_editable_form(form_result: dict, form_path: str):
    if not form_result:
        st.warning("No form data.")
        return
    
    # Get list of labels and reverse lookup
    type_keys = list(QUESTION_TYPES.keys())
    type_labels = list(QUESTION_TYPES.values())

    form_content = form_result.get('form_content', {})
    form_description = form_content.get("description", "")
    form_steps = form_content.get("steps", [])

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
                    # Support delimiters: newline, comma, semicolon, slash, backslash
                    options = parse_list_type_example(q_example)
                    parsed_example = " / ".join(options)

                edited_questions.append({
                    "question_text": q_text,
                    "question_type": type_keys[type_labels.index(q_type)],
                    "question_description": q_desc,
                    "question_example": parsed_example
                })

        # Button to Save Changes for this step
        if st.button(f"💾 Save Step {step_idx+1}", key=f"save_step_{step_idx}", type='primary'):
            form_content["steps"][step_idx]["step_questions"] = edited_questions
            form_result['form_content'] = form_content
            write_json_form(form_result, form_path)
            st.success(f"Step {step_idx+1} updated successfully.")

        st.markdown("---")


def write_json_form(form_data: dict, path: str):
    """
    Write form data as JSON to a file path, ensuring it is stored under 'data/form_builder'.

    Args:
        form_data (dict): The form data to be written.
        path (str): The relative or absolute file path.

    Returns:
        None
    """
    # *************** Define root directory ***************
    root_dir = os.path.join('data', 'form_builder')

    # *************** Normalize the input path ***************
    normalized_path = os.path.normpath(path)

    # *************** Check if path starts with 'data/form_builder' ***************
    # Only use the relative path to compare
    if not normalized_path.split(os.sep)[:2] == ['data', 'form_builder']:
        # If not, prepend root_dir to force write inside 'data/form_builder'
        final_path = os.path.join(root_dir, normalized_path)
    else:
        final_path = normalized_path

    # *************** Write the JSON file ***************
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump(form_data, f, indent=2)


# *************** Tab 3: Table View of Form Answers ***************
def render_form_table_preview(form_result: dict):

    form_content = form_result.get("form_content", {})
    form_title = form_content.get("form_title", "Form Title")
    form_steps = form_content.get("steps", [])

    table_data = []

    for step in form_steps:
        step_name = step.get("step_name", "")
        for question in step.get("step_questions", []):
            table_data.append({
                "form_name": form_title,
                "step_name": step_name,
                "question": question.get("question", ""),
                "answer": question.get("answer", "")  # Can update if answer is stored elsewhere
            })

    if table_data:
        df = pd.DataFrame(table_data)
        st.markdown(f"### 📊 Table of Form Answers")
        st.dataframe(df, use_container_width=True)

        # Optional: Export section
        with st.expander("📁 Export Table"):
            csv = df.to_csv(index=False)
            st.download_button("⬇️ Download as CSV", csv, file_name="form_answers.csv", mime="text/csv")
    else:
        st.info("No answers available yet to preview.")



# *************** Display Form in Tabs ***************
def display_selected_form(form_result: dict, form_path: str):

    if not form_result:
        st.warning("No form selected.")
        return

    # *************** Load Form Content ***************
    form_content = form_result.get('form_content', {})
    form_description = form_content.get("description", "")
    form_steps = form_content.get("steps", [])
    form_title = form_content.get("form_title", "Form Title")

    # *************** Define Output Path ***************
    output_dir = os.path.join("data", "output")
    os.makedirs(output_dir, exist_ok=True)
    csv_file = os.path.splitext(os.path.basename(form_path))[0] + ".csv"
    csv_path = os.path.join(output_dir, csv_file)

    # *************** Display Tabs ***************
    tab1, tab2, tab3, tab4 = st.tabs(["🗂 Form Details", "📝 Preview Form", "📊 Form Table Preview", "💬 Form Assistance"])


    # *************** Tab 1: Form Details ***************
    with tab1:
        display_editable_form(form_result, form_path)

    # *************** TAB 2: Preview + Submit ***************
    with tab2:
        render_form_preview_tab(form_title, form_description, form_steps)
        render_submit_button(form_title, csv_path)

    
    # *************** TAB 3: Display Saved Data ***************
    with tab3:
        st.markdown("### 📊 Submitted Answers")
        st.caption(f"Table Record of {form_title}")

        if os.path.exists(csv_path):
            df_submitted = pd.read_csv(csv_path)

            if df_submitted.empty:
                st.info("No submissions yet.")
            else:
                # Toggle to switch view
                toggle_pivot = st.toggle("↔ Filter to see answers grouped by submission", value=False)

                if toggle_pivot:
                    # Pivot the data: rows = submit_id, columns = question
                    df_pivot = df_submitted.pivot_table(
                        index='submit_id',
                        columns='question',
                        values='answer',
                        aggfunc='first'  # In case of duplicates, show first answer
                    ).reset_index()

                    st.dataframe(df_pivot, use_container_width=True)
                else:
                    # Default raw view
                    st.dataframe(df_submitted.sort_values(by="submit_id", ascending=False), use_container_width=True)

                # Optional: download button
                st.download_button(
                    label="📥 Download CSV",
                    data=df_submitted.to_csv(index=False),
                    file_name=os.path.basename(csv_path),
                    mime="text/csv"
                )
        else:
            st.info("No submission has been made yet.")
    
    # *************** TAB 4: CHAT BASED with FORM ASSISTANCE ***********
    with tab4:
        render_chat_form(form_result)
def render_chat_form(form_result: dict):
    st.markdown("### 🤖 Chat with Form Assistant")

    form_id = form_result.get("form_id") if "form_result" in st.session_state else None

    if not form_id:
        st.warning("Please select a form first.")
        st.stop()

    # Load form JSON
    form_path = f"data/form_builder/{form_id}.json"
    if not os.path.exists(form_path):
        st.error(f"Form not found: {form_path}")
        st.stop()

    with open(form_path) as f:
        current_form = json.load(f)

    # Load chat history
    memory_path = f"data/chat_history/memory_{form_id}.json"
    if os.path.exists(memory_path):
        with open(memory_path) as f:
            messages = json.load(f)
    else:
        messages = []

    # Display existing messages
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Get user input
    user_input = st.chat_input("Ask something about this form...")
    if user_input:
        # Display user input
        st.chat_message("user").markdown(user_input)


# *************** TAB 2: Preview + Submit ***************
def render_form_preview_tab(form_title: str, form_description: str, form_steps: list[dict]):
    st.markdown(f"### 📝 {form_title}")
    st.info(form_description)

    st.session_state.question_list = []

    # Render all steps and questions
    for id_step, step in enumerate(form_steps):
        step_name = step.get("step_name", f"Step {id_step + 1}")

        with st.expander(f"{id_step + 1}/ {step_name}"):
            for id_question, question in enumerate(step.get("step_questions", [])):
                
                try:
                    render_question_input(question, id_step, id_question)

                except Exception as error_input:
                    st.error(f"Error While Create input form for {step_name} -> {question}", icon="🚨")

                st.session_state.question_list.append(
                    (id_step, id_question, step_name, question.get("question_text", ""))
                )

def render_submit_button(form_title: str, csv_path: str):

    # On Submit
    if st.button("✅ Submit Form", type="primary", use_container_width=True):
        if 'question_list' not in st.session_state:
            st.warning("⚠️ No Input in the Form yet.")
            return
        
        new_answers = collect_answers(form_title, st.session_state.get('question_list', []))

        if not new_answers:
            st.warning("⚠️ No answers provided.")
            return

        success = save_answers_to_csv(new_answers, csv_path)
        if success:
            st.success(f"✅ Form submitted and saved to `{csv_path}`")


# *************** Utility: Format Answer Based on Type ***************
def format_answer(answer):
    if isinstance(answer, str):
        return answer.strip()
    elif isinstance(answer, list):
        return ', '.join(str(a) for a in answer)
    elif isinstance(answer, datetime):
        return answer.strftime("%d/%m/%Y, %H:%M:%S")
    return str(answer)


# *************** Utility: Collect All Answers ***************
def collect_answers(form_title, question_list):
    new_answers = []
    str_id = str(uuid.uuid4()).split('-')[0]
    input_id = f"{datetime.now().strftime('%d%m%y-%H%M')}-{str_id}"

    for id_step, id_question, step_name, question_text in question_list:
        key = f"step{id_step}_quest{id_question}"
        answer = st.session_state.get(key, "")

        answer = format_answer(answer)

        if answer:
            new_answers.append({
                "submit_id": input_id,
                "form_name": form_title,
                "step_name": step_name,
                "question": question_text,
                "answer": answer
            })

    return new_answers


# *************** Utility: Save Answers to CSV Safely ***************
def save_answers_to_csv(new_answers, csv_path):
    try:
        if os.path.exists(csv_path):
            df_existing = pd.read_csv(csv_path)
        else:
            df_existing = pd.DataFrame(columns=["submit_id", "form_name", "step_name", "question", "answer"])

        df_new = pd.DataFrame(new_answers)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)

        df_combined.drop_duplicates(
            subset=["submit_id", "form_name", "step_name", "question"],
            keep="last",
            inplace=True
        )

        df_combined.to_csv(csv_path, index=False)
        return True
    except Exception as e:
        st.error(f"❌ Error saving answers: {e}")
        return False


# *************** Render Question Input ***************
def render_question_input(question: dict, step_idx: int, q_idx: int):
    
    question_text = question.get("question_text", "Untitled")
    question_type = question.get("question_type", "Unknown").lower().strip()
    question_description = question.get("question_description", "")
    question_example = question.get("question_example", question_description)
    options = parse_list_type_example(question_example) if isinstance(question_example, str) else question_example
    input_key = f"step{step_idx}_quest{q_idx}"

    RENDERERS = {
        "short_text": render_short_text,
        "text_area_long": render_text_area_long,
        "date": render_date_input,
        "time": render_time_input,
        "duration": render_duration,
        "email": render_email_input,
        "multiple_choice_dropdown_menu": render_multiselect,
        "dropdown_single_option": render_selectbox,
        "multiple_option": render_multiselect,
        "single_option": render_radio,
        "slider_rating": render_slider_rating,
        "upload_document": render_upload_document
    }

    render_func = RENDERERS.get(question_type)
    if render_func:
        render_func(question_text, input_key, question_description, options)
    else:
        st.warning(f"{question_text} - Unsupported input type: {question_type}")


def save_form_response(form_response: dict) -> str:

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
    st.session_state.form_result = save_data
    # *************** Save JSON ***************
    os.makedirs(FORM_DIR, exist_ok=True)
    file_path = os.path.join(FORM_DIR, f"{form_id}.json")
    
    st.session_state.form_loaded_name = file_path
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2)

    return file_path



def list_saved_forms() -> list:
    FORM_DIR = "data/form_builder"
    os.makedirs(FORM_DIR, exist_ok=True)
    form_list = []

    for path in glob.glob(os.path.join(FORM_DIR, "form_*.json")):
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


def load_form_content(file_path: str) -> dict:
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
        
        if not form_files:
            st.info("No saved forms found.")
        
        else:
            st.caption("Please Select on of the Form Generated first.")
            
            # *************** Load form data ***************
            form_items = []
            form_map = {}

            for file_path in form_files:
                data = load_form_content(file_path)
                file_name = os.path.basename(file_path)

                form_title = data.get("form_content", {}).get('form_title', '')
                created_at = data.get("timestamp", {}).get("created_at", "unknown")

                # Format label to show title and created time
                display_title = form_title or file_name
                label = f"{display_title} — 🕒 {created_at.replace('_', '/')}"

                form_items.append(label)
                form_items.append("---")
                form_map[label] = {
                    "data": data,
                    "file_name": file_name
                }

            # *************** FORM OPTION MENU ***************
            selected_label = option_menu(
                menu_title="",
                options=form_items,
                icons=["file-earmark-text"] * len(form_items),
                menu_icon=None,
                default_index=0,
                styles={
                    "nav-link-selected": {"background-color": "#F84952"},
                    "nav-link": {
                        "white-space": "normal",
                        "height": "auto",
                        "min-height": "50px",
                        "font-size": "13px"
                    },
                }
            )

            # *************** Update selected form ***************
            selected_form = form_map[selected_label]
            st.session_state.form_result = selected_form["data"]
            st.session_state.form_loaded_name = selected_form["file_name"]

                
    
    # *************** Show Prompt Button ***************
    if st.button("Create New Form Prompt"):
        prompt_dialog()

    st.divider()

    # *************** Display the Form Result ***************
    form_result = st.session_state.get('form_result', {})
    form_file = st.session_state.get('form_loaded_name', {})
    if form_result:
        display_selected_form(form_result, form_file)


if __name__ == "__main__":
    main_page()
