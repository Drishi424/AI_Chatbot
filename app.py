# app.py
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from dotenv import load_dotenv
import os
import json
import uuid
import google.generativeai as ai
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret")
API_KEY = os.getenv("GOOGLE_API_KEY")
ai.configure(api_key=API_KEY)

model = ai.GenerativeModel('gemini-2.0-flash')
chat_sessions = {}  # key: session_id, value: chat object

LOG_DIR = "chat_logs"
os.makedirs(LOG_DIR, exist_ok=True)

def get_session_file(session_id):
    return os.path.join(LOG_DIR, f"{session_id}.json")

def save_chat_to_file(session_id, user_msg, bot_msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "user": user_msg,
        "bot": bot_msg,
        "timestamp": timestamp
    }
    file_path = get_session_file(session_id)
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
    else:
        data = []
    data.append(entry)
    with open(file_path, "w") as file:
        json.dump(data, file, indent=2)

def load_chat_from_file(session_id):
    file_path = get_session_file(session_id)
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return json.load(file)
    return []

def get_all_sessions():
    sessions = []
    for filename in os.listdir(LOG_DIR):
        if filename.endswith(".json"):
            session_id = filename.replace(".json", "")
            file_path = get_session_file(session_id)
            with open(file_path, "r") as file:
                data = json.load(file)
                if data:
                    title = data[0]['user'][:30] + "..." if len(data[0]['user']) > 30 else data[0]['user']
                    sessions.append({"id": session_id, "title": title})
    return sessions

@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("chatbot"))

@app.route("/chat", methods=["GET", "POST"])
def chatbot():
    session_id = request.args.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        return redirect(url_for("chatbot", session_id=session_id))

    if session_id not in chat_sessions:
        chat_sessions[session_id] = model.start_chat()

    if request.method == "POST":
        user_message = request.form["message"]

        if user_message.lower() == "bye":
            bot_response = "<b>👋 Goodbye!</b><br>Hope we chat again soon!"
        else:
            raw_response = chat_sessions[session_id].send_message(user_message)
            bot_response = format_response(raw_response.text.strip())

        save_chat_to_file(session_id, user_message, raw_response.text.strip())

    full_history = load_chat_from_file(session_id)
    sidebar_titles = get_all_sessions()

    MAX_MESSAGES = 30
    recent_history = full_history[-MAX_MESSAGES:]

    return render_template("index.html", history=recent_history, chats=sidebar_titles, current_session=session_id)

@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("chatbot"))

@app.route("/load_more")
def load_more():
    session_id = request.args.get("session_id")
    offset = int(request.args.get("offset", 0))
    BATCH_SIZE = 30

    messages = load_chat_from_file(session_id)
    batch = messages[max(0, len(messages) - offset - BATCH_SIZE): len(messages) - offset]

    formatted = []
    for m in batch:
        if "user" in m:
            formatted.append({"sender": "user", "text": m["user"], "timestamp": m.get("timestamp", "")})
        if "bot" in m:
            formatted.append({"sender": "bot", "text": m["bot"], "timestamp": m.get("timestamp", "")})

    return jsonify(messages=formatted)

def format_response(text):
    lines = text.split("\n")
    formatted = ""
    for line in lines:
        if line.strip() == "":
            formatted += "<br>"
        elif line.strip().endswith(":"):
            formatted += f"<b>{line.strip()}</b><br>"
        else:
            formatted += f"{line.strip()}<br>"
    return formatted

if __name__ == "__main__":
    app.run(debug=True)
