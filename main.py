import os
import re
import tempfile
from datetime import datetime, timedelta
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from random import randint
import requests

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from ats_scorer import score_resumes
from mailer import send_interview_email, send_password_reset_otp
from mysql_db import (
    authenticate_recruiter,
    get_candidate_by_id,
    get_candidate_by_retell_call_id,
    get_all_candidates,
    get_recruiter_by_email,
    get_recruiter_by_username,
    init_mysql_db,
    save_candidate_info,
    save_interview_transcript,
    store_password_reset_otp,
    update_candidate_retell_call_id,
    update_recruiter_password_by_email,
    update_recruiter_credentials,
    update_recruiter_profile,
    verify_recruiter_reset_otp,
)
from pdf_processor import process_resume_files
from retell_call import (
    build_retell_transcript,
    evaluate_retell_transcript,
    extract_analysis_result,
    extract_retell_candidate_id,
    make_retell_call,
)
from twilio_server import respond as twilio_respond
from twilio_server import start_phone_interview, voice as twilio_voice
from vector_db import store_resumes_in_db

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_EXTENSIONS = {".pdf"}

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "recruitai-dev-secret")
sns.set_theme(style="whitegrid")


def current_user():
    username = session.get("username")
    if not username:
        return None
    recruiter = get_recruiter_by_username(username)
    if not recruiter:
        return None
    return {
        "id": recruiter["id"],
        "username": recruiter["username"],
        "name": recruiter.get("name", ""),
        "role": recruiter.get("role", "Recruiter"),
        "email": recruiter.get("email", ""),
        "phone": recruiter.get("phone", ""),
        "company": recruiter.get("company", ""),
        "location": recruiter.get("location", ""),
        "experience": recruiter.get("experience", ""),
        "access_level": recruiter.get("access_level", "Administrator"),
        "status": recruiter.get("status", "Active"),
    }


def require_auth():
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "Authentication required."}), 401
    return None


def require_page_auth():
    if not current_user():
        return redirect(url_for("index"))
    return None


def extract_job_role(job_description):
    lines = [line.strip() for line in str(job_description or "").splitlines() if line.strip()]
    if not lines:
        return "General Role"

    patterns = [
        r"^(?:job\s*title|role|position)\s*[:\-]\s*(.+)$",
        r"^(?:hiring\s*for|looking\s*for|opening\s*for)\s*[:\-]?\s*(.+)$",
    ]

    for line in lines[:6]:
        for pattern in patterns:
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if match:
                return clean_job_role(match.group(1))

    first_line = clean_job_role(lines[0])
    if first_line:
        return first_line

    return "General Role"


def clean_job_role(raw_role):
    role = re.sub(r"\b(job description|responsibilities|requirements)\b.*$", "", str(raw_role), flags=re.IGNORECASE).strip()
    role = re.sub(r"^[\-\*\•\d\.\)\s]+", "", role).strip(" :-")
    return role[:80] if role else ""


def serialize_candidates(candidates):
    payload = []
    for candidate_id, name, email, score, job_description, transcript, interview_result, interview_score in candidates:
        numeric_score = int(score) if score is not None else 0
        ats_decision = "QUALIFIED" if numeric_score >= 85 else "NOT QUALIFIED"
        qualification_status = interview_result or "Pending"
        if qualification_status == "Pending":
            qualification_status = "AWAITING INTERVIEW"
        job_role = extract_job_role(job_description)
        transcript_preview = ""
        interview_reason = ""
        if transcript:
            summary_match = re.search(r"(?im)^Interview Summary:\s*(.+)$", transcript)
            if summary_match:
                interview_reason = summary_match.group(1).strip()
            candidate_lines = [line for line in transcript.splitlines() if line.startswith("Candidate: ")]
            if interview_reason:
                transcript_preview = interview_reason[:160]
            elif candidate_lines:
                transcript_preview = candidate_lines[-1].replace("Candidate: ", "", 1)[:120]
        payload.append(
            {
                "id": candidate_id,
                "name": name or "Unknown",
                "email": email or "Unknown",
                "score": numeric_score,
                "job_role": job_role,
                "ats_decision": ats_decision,
                "has_transcript": bool(transcript),
                "transcript_preview": transcript_preview,
                "interview_reason": interview_reason,
                "transcript": transcript or "",
                "interview_result": interview_result or "Pending",
                "qualification_status": qualification_status,
                "interview_score": int(interview_score) if interview_score is not None else None,
            }
        )
    return payload


def build_recent_activity(candidates):
    activity = []
    for index, candidate in enumerate(candidates[:5]):
        candidate_id, name, _email, score, job_description, transcript, interview_result, interview_score = candidate
        role_label = extract_job_role(job_description)
        title = f"{name or 'Unknown candidate'} processed"
        detail = f"{role_label} ATS score recorded at {int(score) if score is not None else 0}."
        if transcript:
            result_text = interview_result or "Pending"
            detail = f"Interview transcript available for candidate #{candidate_id}. Result: {result_text}."
        activity.append(
            {
                "title": title,
                "detail": detail,
                "time": f"{index + 1} hr ago",
            }
        )

    if not activity:
        activity = [
            {
                "title": "Workspace ready",
                "detail": "Upload resumes and run ATS analysis to populate dashboard activity.",
                "time": "Now",
            }
        ]
    return activity


def render_chart_base64(builder):
    figure = builder()
    buffer = BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight", dpi=150, facecolor=figure.get_facecolor())
    plt.close(figure)
    buffer.seek(0)
    return f"data:image/png;base64,{b64encode(buffer.read()).decode('utf-8')}"


def build_donut_chart(scores):
    def _builder():
        figure, axis = plt.subplots(figsize=(4.2, 3.1), facecolor="#ffffff")
        chart_scores = scores if scores else [1]
        colors = sns.color_palette(["#22c55e", "#3b82f6", "#f59e0b", "#ec4899"])[: len(chart_scores)]
        axis.pie(
            chart_scores,
            startangle=90,
            colors=colors,
            wedgeprops={"width": 0.28, "edgecolor": "#ffffff"},
        )
        avg_score = round(sum(scores) / len(scores)) if scores else 0
        axis.text(0, 0.08, f"{avg_score}", ha="center", va="center", fontsize=28, fontweight="bold", color="#111827")
        axis.text(0, -0.18, "ATS Score", ha="center", va="center", fontsize=11, color="#6b7280")
        axis.set(aspect="equal")
        axis.set_title("Resume Analysis Overview", loc="left", fontsize=12, fontweight="bold", color="#111827", pad=14)
        return figure

    return render_chart_base64(_builder)


def build_distribution_chart(scores):
    def _builder():
        figure, axis = plt.subplots(figsize=(5.4, 3.1), facecolor="#ffffff")
        values = scores if scores else [20, 45, 68, 82]
        labels = ["0-24", "25-49", "50-74", "75-100"]
        counts = [0, 0, 0, 0]
        for score in values:
            if score < 25:
                counts[0] += 1
            elif score < 50:
                counts[1] += 1
            elif score < 75:
                counts[2] += 1
            else:
                counts[3] += 1

        palette = ["#f87171", "#fb923c", "#60a5fa", "#a78bfa"]
        sns.barplot(x=labels, y=counts, hue=labels, palette=palette, legend=False, ax=axis)
        axis.set_title("Score Distribution", loc="left", fontsize=12, fontweight="bold", color="#111827", pad=14)
        axis.set_xlabel("")
        axis.set_ylabel("")
        axis.tick_params(colors="#6b7280", labelsize=9)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#e5e7eb")
        axis.spines["bottom"].set_color("#e5e7eb")
        return figure

    return render_chart_base64(_builder)


def build_dashboard_payload():
    candidates_data = get_all_candidates()
    serialized = serialize_candidates(candidates_data)
    scores = [candidate["score"] for candidate in serialized if candidate["score"] is not None]
    total = len(serialized)
    high_scorers = sum(1 for score in scores if score >= 85)
    avg_score = round(sum(scores) / len(scores)) if scores else 0
    transcripts = sum(1 for candidate in serialized if candidate["has_transcript"])
    hires_made = sum(1 for candidate in serialized if candidate["interview_result"] == "QUALIFIED")
    top_analysis_candidates = sorted(serialized, key=lambda candidate: candidate["score"], reverse=True)[:5]

    return {
        "stats": {
            "jobs_posted": max(total, 1) if total else 0,
            "resumes_uploaded": total,
            "interviews_completed": transcripts,
            "hires_made": hires_made,
            "average_score": avg_score,
            "high_scorers": high_scorers,
        },
        "charts": {
            "overview": build_donut_chart(scores[:4]),
            "distribution": build_distribution_chart(scores),
        },
        "recent_activity": build_recent_activity(candidates_data),
        "analysis_results": top_analysis_candidates,
        "candidates": serialized[:8],
    }


def start_ai_interview_call(candidate_phone, candidate_name, ats_score, jd_text, resume_text, candidate_id):
    provider = os.getenv("INTERVIEW_CALL_PROVIDER", "retell").strip().lower()
    if provider == "twilio":
        return start_phone_interview(
            candidate_phone=candidate_phone,
            candidate_name=candidate_name,
            jd_text=jd_text,
            resume_text=resume_text,
            candidate_id=candidate_id,
        )

    retell_response = make_retell_call(
        name=candidate_name,
        phone=candidate_phone,
        ats_score=ats_score,
        candidate_id=candidate_id,
        jd_text=jd_text,
        resume_text=resume_text,
    )
    if not retell_response.get("ok"):
        return f"Retell call error: {retell_response.get('error', 'Unable to start call.')}"

    retell_call_id = retell_response.get("call_id") or retell_response.get("id")
    if retell_call_id:
        update_candidate_retell_call_id(candidate_id, retell_call_id)
        return f"Retell call initiated! Call ID: {retell_call_id}"
    return "Retell call initiated."


def process_uploaded_pdfs(files):
    saved_paths = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for uploaded_file in files:
            filename = secure_filename(uploaded_file.filename or "")
            suffix = Path(filename).suffix.lower()
            if not filename or suffix not in UPLOAD_EXTENSIONS:
                continue

            target_path = Path(temp_dir) / filename
            uploaded_file.save(target_path)
            saved_paths.append(str(target_path))

        if not saved_paths:
            return []

        return process_resume_files(saved_paths)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/forgot-password")
def forgot_password_page():
    return render_template("forgot_password_email.html")


@app.route("/forgot-password/verify")
def forgot_password_verify_page():
    reset_email = session.get("password_reset_email")
    if not reset_email:
        return redirect(url_for("forgot_password_page"))
    return render_template("forgot_password_verify.html", reset_email=reset_email)


@app.route("/forgot-password/new-password")
def forgot_password_new_password_page():
    reset_email = session.get("password_reset_email")
    if not reset_email or not session.get("password_reset_verified"):
        return redirect(url_for("forgot_password_page"))
    return render_template("forgot_password_new_password.html", reset_email=reset_email)


@app.route("/recruitment-operations")
def recruitment_operations_page():
    auth_redirect = require_page_auth()
    if auth_redirect:
        return auth_redirect
    return render_template("operations.html")


@app.route("/resumes")
def resumes_page():
    auth_redirect = require_page_auth()
    if auth_redirect:
        return auth_redirect
    return render_template("resumes.html")


@app.route("/interviews")
def interviews_page():
    auth_redirect = require_page_auth()
    if auth_redirect:
        return auth_redirect
    return render_template(
        "candidate_list.html",
        page_title="Interviews",
        heading="Interview Qualified Candidates",
        description="Only candidates who qualified in the interview stage appear in this section.",
        view_mode="interview_qualified",
    )


@app.route("/shortlisted")
def shortlisted_page():
    auth_redirect = require_page_auth()
    if auth_redirect:
        return auth_redirect
    return render_template(
        "candidate_list.html",
        page_title="Shortlisted Candidates",
        heading="Resume Screening Qualified Candidates",
        description="Only candidates who qualified in resume screening appear in this section.",
        view_mode="resume_qualified",
    )


@app.route("/rejected-candidates")
def rejected_candidates_page():
    auth_redirect = require_page_auth()
    if auth_redirect:
        return auth_redirect
    return render_template(
        "candidate_list.html",
        page_title="Rejected Candidates",
        heading="Rejected Candidates",
        description="Candidates rejected in resume screening or in the interview stage appear in this section.",
        view_mode="rejected",
    )


@app.route("/settings")
def settings_page():
    auth_redirect = require_page_auth()
    if auth_redirect:
        return auth_redirect
    return render_template("settings.html")


@app.route("/api/session", methods=["GET"])
def session_info():
    user = current_user()
    if not user:
        return jsonify({"ok": True, "authenticated": False})
    return jsonify({"ok": True, "authenticated": True, "user": user})


@app.route("/api/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", ""))

    recruiter = authenticate_recruiter(username, password)
    if not recruiter:
        return jsonify({"ok": False, "error": "Invalid username or password."}), 401

    session["username"] = username
    return jsonify({"ok": True, "user": current_user()})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/forgot-password/request", methods=["POST"])
def request_password_reset():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "Please enter your email address."}), 400

    recruiter = get_recruiter_by_email(email)
    if not recruiter:
        return jsonify({"ok": False, "error": "No recruiter account was found for that email."}), 404

    otp_code = f"{randint(100000, 999999)}"
    expiry_time = datetime.utcnow() + timedelta(minutes=10)
    stored = store_password_reset_otp(email, otp_code, expiry_time)
    if not stored:
        return jsonify({"ok": False, "error": "Unable to generate password reset OTP."}), 500

    email_status = send_password_reset_otp(email, recruiter.get("name", "Recruiter"), otp_code)
    if not email_status.startswith("Success:"):
        return jsonify({"ok": False, "error": email_status}), 500

    session["password_reset_email"] = email
    session["password_reset_verified"] = False

    return jsonify(
        {
            "ok": True,
            "message": "OTP sent to your email. Please verify it to continue.",
            "redirect_url": url_for("forgot_password_verify_page"),
        }
    )


@app.route("/api/forgot-password/verify", methods=["POST"])
def verify_password_reset_otp():
    payload = request.get_json(silent=True) or {}
    otp_code = str(payload.get("otp", "")).strip()
    email = session.get("password_reset_email") or str(payload.get("email", "")).strip().lower()

    if not email or not otp_code:
        return jsonify({"ok": False, "error": "Email and OTP are required."}), 400

    result = verify_recruiter_reset_otp(email, otp_code)
    if not result["ok"]:
        return jsonify(result), 400

    session["password_reset_email"] = email
    session["password_reset_verified"] = True
    return jsonify(
        {
            "ok": True,
            "message": "OTP verified successfully.",
            "redirect_url": url_for("forgot_password_new_password_page"),
        }
    )


@app.route("/api/forgot-password/reset", methods=["POST"])
def reset_password():
    payload = request.get_json(silent=True) or {}
    email = session.get("password_reset_email") or str(payload.get("email", "")).strip().lower()
    new_password = str(payload.get("new_password", ""))
    confirm_password = str(payload.get("confirm_password", ""))

    if not email or not new_password or not confirm_password:
        return jsonify({"ok": False, "error": "New password and confirm password are required."}), 400
    if not session.get("password_reset_verified"):
        return jsonify({"ok": False, "error": "Please verify your OTP first."}), 400
    if new_password != confirm_password:
        return jsonify({"ok": False, "error": "New password and confirm password do not match."}), 400

    result = update_recruiter_password_by_email(email, new_password)
    if not result["ok"]:
        return jsonify(result), 400

    session.pop("password_reset_email", None)
    session.pop("password_reset_verified", None)
    return jsonify(
        {
            "ok": True,
            "message": "Password reset successful. You can now sign in with your new password.",
            "redirect_url": url_for("index"),
        }
    )


@app.route("/api/recruiter/profile", methods=["POST"])
def save_recruiter_profile():
    auth_error = require_auth()
    if auth_error:
        return auth_error

    user = current_user()
    payload = request.get_json(silent=True) or {}
    profile_data = {
        "name": str(payload.get("name", "")).strip(),
        "role": str(payload.get("role", "")).strip(),
        "email": str(payload.get("email", "")).strip(),
        "phone": str(payload.get("phone", "")).strip(),
        "company": str(payload.get("company", "")).strip(),
        "location": str(payload.get("location", "")).strip(),
        "experience": str(payload.get("experience", "")).strip(),
    }
    if not profile_data["name"]:
        return jsonify({"ok": False, "error": "Recruiter name is required."}), 400

    updated = update_recruiter_profile(user["username"], profile_data)
    if not updated:
        return jsonify({"ok": False, "error": "Unable to update recruiter profile."}), 500

    return jsonify({"ok": True, "message": "Recruiter profile updated successfully.", "user": current_user()})


@app.route("/api/recruiter/credentials", methods=["POST"])
def save_recruiter_credentials():
    auth_error = require_auth()
    if auth_error:
        return auth_error

    user = current_user()
    payload = request.get_json(silent=True) or {}
    new_username = str(payload.get("username", "")).strip().lower()
    new_password = str(payload.get("password", ""))
    confirm_password = str(payload.get("confirm_password", ""))

    if not new_username:
        return jsonify({"ok": False, "error": "Username is required."}), 400
    if new_password and new_password != confirm_password:
        return jsonify({"ok": False, "error": "Password and confirm password do not match."}), 400

    result = update_recruiter_credentials(user["username"], new_username, new_password)
    if not result["ok"]:
        return jsonify(result), 400

    session["username"] = result["username"]
    return jsonify({"ok": True, "message": "Login credentials updated successfully.", "user": current_user()})


@app.route("/api/upload-resumes", methods=["POST"])
def upload_resumes():
    auth_error = require_auth()
    if auth_error:
        return auth_error

    files = request.files.getlist("resumes")
    if not files:
        return jsonify({"ok": False, "error": "Please choose one or more PDF resumes."}), 400

    resumes_data = process_uploaded_pdfs(files)
    if not resumes_data:
        return jsonify({"ok": False, "error": "No valid PDF resume text could be extracted."}), 400

    store_resumes_in_db(resumes_data)
    filenames = [resume["filename"] for resume in resumes_data]
    return jsonify(
        {
            "ok": True,
            "message": f"Stored {len(resumes_data)} resume(s) in the vector database.",
            "files": filenames,
        }
    )


@app.route("/api/analyze", methods=["POST"])
def analyze():
    auth_error = require_auth()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    job_description = str(payload.get("job_description", "")).strip()
    if not job_description:
        return jsonify({"ok": False, "error": "Please enter a job description first."}), 400

    results = score_resumes(job_description=job_description)
    if isinstance(results, dict) and "error" in results:
        return jsonify({"ok": False, "error": results["error"]}), 400

    logs = []
    saved_candidates = []
    automated_action = None

    for match in results:
        score = int(match.get("score", 0))
        name = match.get("candidate_name", "Unknown")
        email = match.get("candidate_email", "Unknown")
        phone = match.get("candidate_phone", "Unknown")
        resume_text = match.get("resume_text", "")

        logs.append(f"Candidate: {name} | ATS score: {score} | Phone: {phone}")
        candidate_id = save_candidate_info(name, email, score, job_description)
        logs.append(f"Saved to MySQL with candidate id {candidate_id}.")

        saved_candidates.append(
            {
                "id": candidate_id,
                "name": name,
                "email": email,
                "phone": phone,
                "score": score,
                "job_role": extract_job_role(job_description),
                "ats_decision": "QUALIFIED" if score >= 85 else "NOT QUALIFIED",
                "interview_result": "Pending",
                "qualification_status": "AWAITING INTERVIEW",
                "reasoning": match.get("reasoning", ""),
            }
        )

        if score >= 85:
            logs.append("Score is 85 or higher. Sending interview email.")
            email_status = send_interview_email(candidate_email=email, candidate_name=name)
            logs.append(email_status)

            call_status = "Skipped phone interview because no valid phone number was found."
            if phone and str(phone).lower() != "unknown":
                logs.append(f"Starting AI phone interview for {phone}.")
                call_status = start_ai_interview_call(
                    candidate_phone=phone,
                    candidate_name=name,
                    ats_score=score,
                    jd_text=job_description,
                    resume_text=resume_text,
                    candidate_id=candidate_id,
                )
                logs.append(call_status)

            automated_action = {
                "candidate_name": name,
                "email_status": email_status,
                "call_status": call_status,
            }
            saved_candidates[-1]["email_status"] = email_status
            saved_candidates[-1]["call_status"] = call_status
            break

        logs.append(f"Score below 85. No automated action for {name}.")

    for log_line in logs:
        print(f"[analyze] {log_line}")

    return jsonify(
        {
            "ok": True,
            "results": saved_candidates,
            "logs": logs,
            "automated_action": automated_action,
        }
    )


@app.route("/api/candidates", methods=["GET"])
def candidates():
    auth_error = require_auth()
    if auth_error:
        return auth_error

    candidates_data = get_all_candidates()
    total = len(candidates_data)
    high_scorers = sum(1 for row in candidates_data if row[3] and int(row[3]) >= 85)
    average_score = round(sum(int(row[3]) for row in candidates_data if row[3]) / total) if total else 0

    return jsonify(
        {
            "ok": True,
            "stats": {
                "total": total,
                "high_scorers": high_scorers,
                "average_score": average_score,
            },
            "candidates": serialize_candidates(candidates_data),
        }
    )

def extract_drive_file_id(resume_link):
    match = re.search(r"/d/([^/]+)", resume_link)
    if match:
        return match.group(1)

    match = re.search(r"id=([^&]+)", resume_link)
    if match:
        return match.group(1)

    return None


@app.route("/analyze-candidate", methods=["POST"])
def analyze_candidate():
    try:
        data = request.get_json(silent=True) or {}

        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip()
        phone = str(data.get("phone_number", "")).strip()
        resume_link = str(data.get("resume_link", "")).strip()
        job_description = str(data.get("job_description", "")).strip()

        if not name or not email or not phone or not resume_link or not job_description:
            return jsonify({
                "ok": False,
                "status": "error",
                "message": "name, email, phone_number, resume_link and job_description are required."
            }), 400

        if not phone.startswith("+"):
            phone = "+91" + phone

        file_id = extract_drive_file_id(resume_link)
        if not file_id:
            return jsonify({
                "ok": False,
                "status": "error",
                "message": "Invalid Google Drive resume link."
            }), 400

        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        response = requests.get(download_url, timeout=30)
        if response.status_code != 200:
            return jsonify({
                "ok": False,
                "status": "error",
                "message": "Could not download resume PDF. Make sure the Drive file is shared publicly."
            }), 400

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(response.content)
            temp_pdf_path = temp_pdf.name

        resumes_data = process_resume_files([temp_pdf_path])

        if not resumes_data:
            return jsonify({
                "ok": False,
                "status": "error",
                "message": "Could not extract text from resume PDF."
            }), 400

        store_resumes_in_db(resumes_data)

        old_use_retell = os.getenv("USE_RETELL")
        os.environ["USE_RETELL"] = "false"

        results = score_resumes(job_description=job_description)

        if old_use_retell is not None:
            os.environ["USE_RETELL"] = old_use_retell

        if isinstance(results, dict) and "error" in results:
            return jsonify({
                "ok": False,
                "status": "error",
                "message": results["error"]
            }), 400

        best = results[0]
        ats_score = int(best.get("score", 0))
        reason = best.get("reasoning", "")
        resume_text = best.get("resume_text", "")

        candidate_id = save_candidate_info(name, email, ats_score, job_description)

        call_status = "Not called"
        final_status = "not_selected"

        if ats_score >= 85:
            final_status = "selected"

            call_status = start_ai_interview_call(
                candidate_phone=phone,
                candidate_name=name,
                ats_score=ats_score,
                jd_text=job_description,
                resume_text=resume_text,
                candidate_id=candidate_id,
            )

        return jsonify({
            "ok": True,
            "candidate_id": candidate_id,
            "name": name,
            "email": email,
            "phone_number": phone,
            "resume_link": resume_link,
            "ats_score": ats_score,
            "reason": reason,
            "status": final_status,
            "call_status": call_status
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/api/dashboard", methods=["GET"])
def dashboard_data():
    auth_error = require_auth()
    if auth_error:
        return auth_error

    payload = build_dashboard_payload()
    return jsonify({"ok": True, **payload})


@app.route("/voice", methods=["GET", "POST"])
def voice_webhook():
    return twilio_voice()


@app.route("/respond", methods=["GET", "POST"])
def respond_webhook():
    return twilio_respond()


@app.route("/retell-webhook", methods=["POST"])
def retell_webhook():
    payload = request.get_json(silent=True) or {}
    event = str(payload.get("event") or "").strip()
    call = payload.get("call") or {}
    retell_call_id = call.get("call_id") or call.get("id") or ""

    candidate_id = extract_retell_candidate_id(call)
    candidate = get_candidate_by_id(candidate_id) if candidate_id else None

    if not candidate and retell_call_id:
        candidate = get_candidate_by_retell_call_id(retell_call_id)

    if not candidate:
        print(f"[retell-webhook] Candidate not found for event={event} call_id={retell_call_id}")
        return jsonify({"ok": True, "message": "Webhook received; candidate not found."})

    transcript = build_retell_transcript(call)

    if event in {"call_ended", "transcript_updated"} and transcript:
        save_interview_transcript(candidate["id"], transcript, "In Progress", None)

    if event == "call_analyzed":
        result, score, summary = extract_analysis_result(call)

        if not result or score is None:
            score, result, summary = evaluate_retell_transcript(
                candidate.get("name") or "Candidate",
                candidate.get("job_description") or "",
                transcript,
            )

        transcript_with_summary = transcript
        if summary:
            transcript_with_summary = f"{transcript}\n\nInterview Summary: {summary}".strip()

        save_interview_transcript(candidate["id"], transcript_with_summary, result, score)

        pass_fail = "PASS" if str(result).upper() == "QUALIFIED" else "FAIL"

        n8n_url = os.getenv("N8N_RETELL_RESULT_WEBHOOK")

        if n8n_url:
            try:
                n8n_payload = {
                    "name": candidate.get("name"),
                    "email": candidate.get("email"),
                    "phone_number": candidate.get("phone"),
                    "ats_score": candidate.get("score"),
                    "result": pass_fail,
                    "reason": summary or result or "Interview completed"
                }

                n8n_response = requests.post(
                    n8n_url,
                    json=n8n_payload,
                    timeout=10
                )

                print("[retell-webhook] Sent result to n8n:", n8n_response.status_code)

            except Exception as n8n_error:
                print("[retell-webhook] Failed to send result to n8n:", n8n_error)

        print(f"[retell-webhook] Final interview result: {pass_fail}")

    return jsonify({"ok": True})


if __name__ == "__main__":
    init_mysql_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
