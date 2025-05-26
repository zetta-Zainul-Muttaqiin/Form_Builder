import streamlit as st
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

st.set_page_config(
    page_title="AI Form Builder",
    layout="centered",
    initial_sidebar_state="expanded"
)

# *************** Session State to Hold Form Result ***************
if "form_result" not in st.session_state:
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
    _, col, _ = st.columns([0.1,0.8,0.1], vertical_alignment="center")
    for idx, prompt in enumerate(suggestions):
        key_prompt = f"prompt_suggest_{idx}"
        with col:
            if st.button(f"{prompt[:45]}...", key=key_prompt, help=prompt):
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
            st.session_state.form_result = result
            st.success("Form generated!")
        except Exception as error:
            st.error("❌ Failed to generate form.")
            st.exception(error)
            return

        if result:
            save_form_response(result)  # Save JSON file
            st.rerun()  # Trigger refresh to show in preview tab

@st.dialog("Enter Form Prompt")
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
    col1, _, col2 = st.columns([1,0.5,1])

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
    
    Supports delimiters: newline (\n), comma (,), semicolon (;), slash (/), and backslash (\).
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
    FORM_DIR = os.path.join('data', 'form_builder', path)
    with open(FORM_DIR, "w", encoding="utf-8") as f:
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
    output_dir = "data/output"
    os.makedirs(output_dir, exist_ok=True)
    csv_file = os.path.splitext(os.path.basename(form_path))[0] + ".csv"
    csv_path = os.path.join(output_dir, csv_file)

    # *************** Display Tabs ***************
    tab1, tab2, tab3 = st.tabs(["🗂 Form Details", "📝 Preview Form", "📊 Form Table Preview"])


    # *************** Tab 1: Form Details ***************
    with tab1:
        display_editable_form(form_result, form_path)

    # *************** TAB 2: Preview + Submit ***************
    with tab2:
        st.markdown(f"### 📝 {form_title}")
        st.info(form_description)

        st.session_state.question_list = []
        for id_step, step in enumerate(form_steps):
            step_name = step.get("step_name", f"Step {id_step + 1}")
            with st.expander(f"{id_step + 1}/ {step_name}"):
                for id_question, question in enumerate(step.get("step_questions", [])):
                    render_question_input(question, id_step, id_question)
                    print(f"{id_question} Question: {question}")
                    st.session_state.question_list.append((id_step, id_question, step_name, question.get("question", "")))

        if st.button("✅ Submit Form", type="primary", use_container_width=True):
            # Collect Answers from Session State
            new_answers = []
            for id_step, id_question, step_name, question_text in st.session_state.question_list:
                key = f"step{id_step}_q{id_question}_{question_text[:5]}"
                answer = st.session_state.get(key, "").strip()
                if answer:
                    new_answers.append({
                        "form_name": form_title,
                        "step_name": step_name,
                        "question": question_text,
                        "answer": answer
                    })

            if not new_answers:
                st.warning("No answers provided.")
                return

            # Load existing CSV if available
            if os.path.exists(csv_path):
                df_existing = pd.read_csv(csv_path)
            else:
                df_existing = pd.DataFrame(columns=["form_name", "step_name", "question", "answer"])

            # Convert both to DataFrame
            df_new = pd.DataFrame(new_answers)

            # Merge with existing: Remove duplicates (based on form_name + step_name + question)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.drop_duplicates(subset=["form_name", "step_name", "question"], keep="last", inplace=True)

            # Save updated CSV
            df_combined.to_csv(csv_path, index=False)
            st.success(f"✅ Form submitted and saved to `{csv_path}`")

    
    # *************** TAB 3: Display Saved Data ***************
    with tab3:
        if os.path.exists(csv_path):
            df_display = pd.read_csv(csv_path)
            if not df_display.empty:
                st.markdown("### 📊 Submitted Answers")
                st.dataframe(df_display)
            else:
                st.info("No data available in the CSV.")
        else:
            st.info("No submission has been made yet.")


# *************** Render Question Input ***************
def render_question_input(question: dict, step_idx: int, q_idx: int):
    question_text = question.get("question_text", "Untitled")
    question_type = question.get("question_type", "Unknown").lower().strip()
    question_description = question.get("question_description", "")
    question_example = question.get("question_example", question_description)
    options = parse_list_type_example(question_example) if isinstance(question_example, str) else question_example
    input_key = f"step{step_idx}_q{q_idx}_{question_text[:5]}"

    if question_type == "short_text":
        st.text_input(question_text, placeholder=question_example or "", key=input_key, help=question_description)

    elif question_type == "text_area_long":
        st.text_area(question_text, placeholder=question_example or "", key=input_key)

    elif question_type == "date":
        st.date_input(question_text, key=input_key, help=question_description)

    elif question_type == "time":
        st.time_input(question_text, key=input_key)

    elif question_type == "duration":
        st.text_input(f"{question_text} (e.g. 1h 30m)", key=input_key, help=question_description)

    elif question_type == "email":
        st.text_input(question_text, placeholder="example@example.com", key=input_key, help=question_description)

    elif question_type == "multiple_choice_dropdown_menu":
        st.multiselect(
            question_text, 
            options=options, 
            key=input_key,
            help=question_description
        )

    elif question_type == "dropdown_single_option":
        st.selectbox(
            question_text, 
            options=options, 
            key=input_key,
            help=question_description
        )

    elif question_type == "multiple_option":
        st.multiselect(
            question_text, 
            options=options, 
            key=input_key,
            help=question_description
        )

    elif question_type == "single_option":
        st.radio(
            question_text, 
            options=options, 
            key=input_key,
            help=question_description
        )

    elif question_type == "slider_rating":
        render_slider_rating(question_text, question_example, input_key, question_description)

    elif question_type == "upload_document":
        st.file_uploader(
            question_text, 
            type=["pdf", "docx", "txt"], 
            key=input_key,
            help=question_description
            )

    else:
        st.warning(f"{question_text} - Unsupported input type: {question_type}")


def render_slider_rating(question_text: str, question_example: str, input_key: str, question_description: str):
    if question_example:
        try:
            # Try splitting by ' - ', ',' or space
            parts = re.split(r"[,\s\-]+", question_example.strip())
            min_val = int(parts[0])
            max_val = int(parts[1]) if len(parts) > 1 else min_val + 9
        except Exception as e:
            st.warning(f"⚠️ Invalid example format for slider: '{question_example}'. Using default 1-5")
            min_val, max_val = 1, 5
    else:
        min_val, max_val = 1, 5

    st.slider(
        label=question_text,
        min_value=min_val,
        max_value=max_val,
        key=input_key,
        help=question_description
    )


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
                        st.session_state.form_result = data
                        st.session_state.form_loaded_name = file_name  # optional: track which was loaded
                    
                    st.markdown("\n")
                
    
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
