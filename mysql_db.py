import os
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv, find_dotenv

# Force load the .env file
load_dotenv(find_dotenv())

DEFAULT_RECRUITER = {
    "username": "balaji",
    "password": "Balaji@970",
    "name": "Balaji",
    "role": "Senior AI Recruiter",
    "email": "k.balaji2312@gmail.com",
    "phone": "+91 9704403064",
    "company": "RecruitAI Workspace",
    "location": "Hyderabad, India",
    "experience": "5+ years in technical recruitment",
}

def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DB", "ats_database")
        )
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def init_mysql_db():
    # Connect without a specific database to create it if needed
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", "")
        )
        cursor = conn.cursor()
        
        db_name = os.getenv("MYSQL_DB", "ats_database")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.execute(f"USE {db_name}")
        
        # Create the table to store candidate progress and interview transcripts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                email VARCHAR(255),
                ats_score INT,
                job_description TEXT,
                interview_transcript TEXT,
                interview_result VARCHAR(64),
                interview_score INT,
                retell_call_id VARCHAR(255)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recruiters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                role VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(64),
                company VARCHAR(255),
                location VARCHAR(255),
                experience VARCHAR(255),
                reset_otp VARCHAR(16),
                reset_otp_expiry DATETIME,
                access_level VARCHAR(64) DEFAULT 'Administrator',
                status VARCHAR(64) DEFAULT 'Active'
            )
        """)
        try:
            cursor.execute("ALTER TABLE candidates ADD COLUMN interview_result VARCHAR(64)")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE candidates ADD COLUMN interview_score INT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE candidates ADD COLUMN retell_call_id VARCHAR(255)")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE recruiters ADD COLUMN access_level VARCHAR(64) DEFAULT 'Administrator'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE recruiters ADD COLUMN status VARCHAR(64) DEFAULT 'Active'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE recruiters ADD COLUMN reset_otp VARCHAR(16)")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE recruiters ADD COLUMN reset_otp_expiry DATETIME")
        except Exception:
            pass
        cursor.execute("SELECT id FROM recruiters WHERE username = %s", (DEFAULT_RECRUITER["username"],))
        recruiter = cursor.fetchone()
        if not recruiter:
            cursor.execute(
                """
                INSERT INTO recruiters
                (username, password, name, role, email, phone, company, location, experience, access_level, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    DEFAULT_RECRUITER["username"],
                    DEFAULT_RECRUITER["password"],
                    DEFAULT_RECRUITER["name"],
                    DEFAULT_RECRUITER["role"],
                    DEFAULT_RECRUITER["email"],
                    DEFAULT_RECRUITER["phone"],
                    DEFAULT_RECRUITER["company"],
                    DEFAULT_RECRUITER["location"],
                    DEFAULT_RECRUITER["experience"],
                    "Administrator",
                    "Active",
                ),
            )
        conn.commit()
        cursor.close()
        conn.close()
        print("MySQL Database Initialized successfully.")
    except Exception as e:
        print(f"Database Initialization Error: {e}")

def save_candidate_info(name, email, score, jd):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO candidates (name, email, ats_score, job_description)
            VALUES (%s, %s, %s, %s)
        """, (name, email, int(score), jd))
        conn.commit()
        candidate_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return candidate_id
    return None

def save_interview_transcript(candidate_id, transcript, interview_result=None, interview_score=None):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        if interview_result is None and interview_score is None:
            cursor.execute("""
                UPDATE candidates 
                SET interview_transcript = %s 
                WHERE id = %s
            """, (transcript, candidate_id))
        else:
            cursor.execute("""
                UPDATE candidates 
                SET interview_transcript = %s,
                    interview_result = %s,
                    interview_score = %s
                WHERE id = %s
            """, (transcript, interview_result, interview_score, candidate_id))
        conn.commit()
        cursor.close()
        conn.close()

def update_candidate_retell_call_id(candidate_id, retell_call_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE candidates
            SET retell_call_id = %s,
                interview_result = %s
            WHERE id = %s
            """,
            (retell_call_id, "In Progress", candidate_id),
        )
        conn.commit()
        cursor.close()
        conn.close()


def get_candidate_by_id(candidate_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, name, email, ats_score, job_description, interview_transcript,
                   interview_result, interview_score, retell_call_id
            FROM candidates
            WHERE id = %s
            """,
            (candidate_id,),
        )
        candidate = cursor.fetchone()
        cursor.close()
        conn.close()
        return candidate
    return None


def get_candidate_by_retell_call_id(retell_call_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, name, email, ats_score, job_description, interview_transcript,
                   interview_result, interview_score, retell_call_id
            FROM candidates
            WHERE retell_call_id = %s
            """,
            (retell_call_id,),
        )
        candidate = cursor.fetchone()
        cursor.close()
        conn.close()
        return candidate
    return None

def get_all_candidates():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # Show the newest candidates first so fresh interview transcripts appear at the top.
        cursor.execute("""
            SELECT id, name, email, ats_score, job_description, interview_transcript, interview_result, interview_score
            FROM candidates
            ORDER BY id DESC
        """)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    return []


def get_recruiter_by_username(username):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, username, password, name, role, email, phone, company, location, experience, access_level, status
                 , reset_otp, reset_otp_expiry
            FROM recruiters
            WHERE username = %s
            """,
            (username,),
        )
        recruiter = cursor.fetchone()
        cursor.close()
        conn.close()
        return recruiter
    return None


def get_recruiter_by_email(email):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, username, password, name, role, email, phone, company, location, experience,
                   access_level, status, reset_otp, reset_otp_expiry
            FROM recruiters
            WHERE email = %s
            """,
            (email,),
        )
        recruiter = cursor.fetchone()
        cursor.close()
        conn.close()
        return recruiter
    return None


def authenticate_recruiter(username, password):
    recruiter = get_recruiter_by_username(username)
    if recruiter and recruiter["password"] == password:
        return recruiter
    return None


def update_recruiter_profile(current_username, profile_data):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE recruiters
            SET name = %s,
                role = %s,
                email = %s,
                phone = %s,
                company = %s,
                location = %s,
                experience = %s
            WHERE username = %s
            """,
            (
                profile_data.get("name", ""),
                profile_data.get("role", ""),
                profile_data.get("email", ""),
                profile_data.get("phone", ""),
                profile_data.get("company", ""),
                profile_data.get("location", ""),
                profile_data.get("experience", ""),
                current_username,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    return False


def update_recruiter_credentials(current_username, new_username, new_password):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        normalized_username = new_username.strip().lower()
        cursor.execute("SELECT id, username FROM recruiters WHERE username = %s", (normalized_username,))
        existing = cursor.fetchone()
        if existing and existing["username"] != current_username:
            cursor.close()
            conn.close()
            return {"ok": False, "error": "Username is already in use."}

        update_parts = ["username = %s"]
        values = [normalized_username]
        if new_password:
            update_parts.append("password = %s")
            values.append(new_password)
        values.append(current_username)

        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE recruiters SET {', '.join(update_parts)} WHERE username = %s",
            tuple(values),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"ok": True, "username": normalized_username}
    return {"ok": False, "error": "Unable to update recruiter credentials."}


def store_password_reset_otp(email, otp_code, expiry_time):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE recruiters
            SET reset_otp = %s,
                reset_otp_expiry = %s
            WHERE email = %s
            """,
            (otp_code, expiry_time, email),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        cursor.close()
        conn.close()
        return updated
    return False


def verify_recruiter_reset_otp(email, otp_code):
    recruiter = get_recruiter_by_email(email)
    if not recruiter:
        return {"ok": False, "error": "No recruiter account was found for that email."}

    stored_otp = str(recruiter.get("reset_otp") or "").strip()
    expiry = recruiter.get("reset_otp_expiry")
    if not stored_otp or not expiry:
        return {"ok": False, "error": "No active OTP was found. Please request a new OTP."}

    if stored_otp != str(otp_code).strip():
        return {"ok": False, "error": "Invalid OTP entered."}

    if isinstance(expiry, str):
        expiry = datetime.fromisoformat(expiry)
    if expiry < datetime.utcnow():
        return {"ok": False, "error": "OTP has expired. Please request a new OTP."}

    return {"ok": True}


def update_recruiter_password_by_email(email, new_password):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE recruiters
            SET password = %s,
                reset_otp = NULL,
                reset_otp_expiry = NULL
            WHERE email = %s
            """,
            (new_password, email),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        cursor.close()
        conn.close()
        if updated:
            return {"ok": True}
        return {"ok": False, "error": "No recruiter account was found for that email."}
    return {"ok": False, "error": "Unable to reset recruiter password."}
