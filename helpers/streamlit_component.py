# *************** IMPORT LIBRARY ***************
import streamlit as st
import re
from datetime import date, time

from setup import LOGGER

# *************** Input Render Functions ***************
def render_short_text(label: str, key: str, help_text: str, options=None):
    st.text_input(label, placeholder=help_text or "", key=key, help=help_text)

def render_text_area_long(label: str, key: str, help_text: str, options=None):
    st.text_area(label, placeholder=help_text or "", key=key, help=help_text)


def render_date_input(label: str, key: str, help_text: str, options=None):
    try:
        # ****** Try to use session state if available ******
        default_date = st.session_state.get(key, date.today())

        # ****** Validate the default_date to ensure it's actually a date ******
        if not isinstance(default_date, date):
            default_date = date.today()

        # ****** Safe rendering of date input ******
        st.date_input(label, value=default_date, key=key, help=help_text)

    except Exception as error_date:
        LOGGER.warning(f"Error rendering date input: {error_date}")
        st.date_input(label, value=date.today(), key=key)

def render_time_input(label: str, key: str, help_text: str, options=None):
    try:
        # ****** Check session value for time input ******
        default_time = st.session_state.get(key, time(9, 0))  # Default: 9:00 AM

        # ****** Ensure it's a valid time object ******
        if not isinstance(default_time, time):
            default_time = time(9, 0)

        st.time_input(label, value=default_time, key=key, help=help_text)

    except Exception as e:
        st.warning(f"Error rendering time input: {e}")
        st.time_input(label, value=time(9, 0), key=key, help=help_text)

def render_duration(label: str, key: str, help_text: str, options=None):
    st.text_input(f"{label} (e.g. 1h 30m)", key=key, help=help_text)

def render_email_input(label: str, key: str, help_text: str, options=None):
    st.text_input(label, placeholder="example@example.com", key=key, help=help_text)

def render_multiselect(label: str, key: str, help_text: str, options):
    st.multiselect(label, options=options or [], key=key, help=help_text)

def render_selectbox(label: str, key: str, help_text: str, options):
    st.selectbox(label, options=options or [], key=key, help=help_text)

def render_radio(label: str, key: str, help_text: str, options):
    st.radio(label, options=options or [], key=key, help=help_text)

def render_slider_rating(question_text: str, input_key: str, question_description: str, question_example: str):
    # ****** Try to extract min and max from example ******
    if question_example:
        try:
            parts = re.split(r"[,\s\-]+", question_example.strip())
            min_val = int(parts[0])
            max_val = int(parts[1]) if len(parts) > 1 else min_val + 9
        except Exception:
            st.warning(
                f"Invalid example format for slider: '{question_example}'. Required format like '1-5'. Using default 1-5.",
                icon="⚠️"
            )
            min_val, max_val = 1, 5
    else:
        min_val, max_val = 1, 5

    # ****** Try rendering the slider safely ******
    try:
        # Check if session value is valid
        value = st.session_state.get(input_key, min_val)
        if not isinstance(value, int) or not (min_val <= value <= max_val):
            value = min_val

        st.slider(
            label=question_text,
            min_value=min_val,
            max_value=max_val,
            value=value,
            key=input_key,
            help=question_description,
        )

    except Exception as e:
        st.warning(f"Error rendering slider: {e}")
        st.slider(
            label=question_text,
            min_value=min_val,
            max_value=max_val,
            value=min_val,
            key=input_key,
            help=question_description,
        )

def render_upload_document(label: str, key: str, help_text: str, options=None):
    st.file_uploader(label, type=["pdf", "docx", "txt"], key=key, help=help_text)
