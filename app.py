import os
import requests
import json
import pandas as pd
import streamlit as st
import openai

# CONFIGURATION
CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL")
ACCESS_TOKEN   = os.getenv("CANVAS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
openai.api_key = OPENAI_API_KEY

# SYNTHETIC DATA
SYNTHETIC_DATA = {
    "student_id": 1001,
    "name": "Alice Example",
    "courses": [
        {"course_id": 101, "name": "Intro to AI", "assignments": [
            {"assignment_id": 1, "name": "Essay 1", "due_at": "2025-06-15", "submission": {"score": 85}},
            {"assignment_id": 2, "name": "Quiz 1",  "due_at": "2025-06-20", "submission": {"score": 90}},
        ]},
        {"course_id": 102, "name": "Python Programming", "assignments": [
            {"assignment_id": 3, "name": "Lab 1", "due_at": "2025-06-17", "submission": {"score": 78}},
            {"assignment_id": 4, "name": "Lab 2", "due_at": "2025-06-22", "submission": {"score": 82}},
        ]},
    ]
}

# API FUNCTIONS
def get_courses():
    resp = requests.get(f"{CANVAS_BASE_URL}/api/v1/courses", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def get_assignments(course_id):
    resp = requests.get(f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def get_submission(course_id, assignment_id, user_id):
    resp = requests.get(
        f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}",
        headers=HEADERS
    )
    resp.raise_for_status()
    return resp.json()

def fetch_student_overview(user_id):
    overview = {"student_id": user_id, "courses": []}
    for c in get_courses():
        cd = {"course_id": c["id"], "name": c["name"], "assignments": []}
        for a in get_assignments(c["id"]):
            try:
                sub = get_submission(c["id"], a["id"], user_id)
            except:
                sub = {"status": "not available"}
            cd["assignments"].append({
                "assignment_id": a["id"],
                "name": a["name"],
                "due_at": a.get("due_at"),
                "submission": sub
            })
        overview["courses"].append(cd)
    return overview

@st.cache_data
def get_dashboard_data(source, canvas_data=None):
    data = canvas_data if source=="canvas" and canvas_data else SYNTHETIC_DATA
    rows = []
    for course in data["courses"]:
        for a in course["assignments"]:
            rows.append({
                "Course": course["name"],
                "Assignment": a["name"],
                "Due Date": a.get("due_at"),
                "Score": a.get("submission",{}).get("score")
            })
    return pd.DataFrame(rows)

def ask_study_buddy(prompt, context_json):
    messages = [
        {"role": "system", "content": (
            "You are StudyBuddy, an AI tutor trained on the student's Canvas data. "
            "Use the provided JSON context to answer questions and suggest study tips."
        )},
        {"role": "user", "content": (
            f"Context:\n{json.dumps(context_json, indent=2)}\n\n"
            f"Student asks: {prompt}"
        )}
    ]
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=300
    )
    return resp.choices[0].message.content.strip()

# STREAMLIT UI
st.set_page_config(page_title="Study Buddy Dashboard", layout="wide")
st.title("📚 Study Buddy")

source = st.sidebar.selectbox("Data source", ["synthetic", "canvas"])
if source == "canvas":
    try:
        profile = requests.get(f"{CANVAS_BASE_URL}/api/v1/users/self/profile", headers=HEADERS).json()
        ctx = fetch_student_overview(profile["id"])
        st.sidebar.success("Loaded real Canvas data.")
    except Exception as e:
        st.sidebar.error(f"Canvas load failed: {e}")
        ctx = SYNTHETIC_DATA
else:
    ctx = SYNTHETIC_DATA
    st.sidebar.info("Using synthetic data.")

df = get_dashboard_data(source, canvas_data=ctx)
st.dataframe(df)

st.header("Ask your Study Buddy")
user_q = st.text_input("Your question:")
if st.button("Ask AI") and user_q:
    with st.spinner("Thinking..."):
        answer = ask_study_buddy(user_q, ctx)
    st.markdown(f"**StudyBuddy:** {answer}")