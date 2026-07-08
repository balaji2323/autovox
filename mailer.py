import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()


def send_password_reset_otp(recipient_email, recruiter_name, otp_code):
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_password = os.getenv("EMAIL_APP_PASSWORD", "").strip()

    if not sender_email or not sender_password:
        return "Error: Email credentials not found in .env file."

    if not recipient_email:
        return "Error: No valid recipient email was provided."

    msg = EmailMessage()
    msg["Subject"] = "RecruitAI password reset OTP"
    msg["From"] = sender_email
    msg["To"] = recipient_email

    body = f"""Hello {recruiter_name},

We received a password reset request for your RecruitAI account.

Your one-time password (OTP) is: {otp_code}

This OTP is valid for 10 minutes. If you did not request a password reset, please ignore this message.

Best regards,
RecruitAI Security Team
"""
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        return f"Success: Password reset OTP sent to {recipient_email}"
    except Exception as e:
        return f"SMTP Error: {e}"

def send_interview_email(candidate_email, candidate_name, job_title="the open role"):
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_password = os.getenv("EMAIL_APP_PASSWORD", "").strip()

    if not sender_email or not sender_password:
        return "Error: Email credentials not found in .env file."
    
    if not candidate_email or candidate_email.lower() == "unknown":
         return f"Error: No valid email found for {candidate_name}."

    msg = EmailMessage()
    msg['Subject'] = f"Interview Invitation: Your application for {job_title}"
    msg['From'] = sender_email
    msg['To'] = candidate_email

    body = f"""Hello {candidate_name},

Our AI-driven Applicant Tracking System has reviewed your resume and determined that your skills are an excellent match for our team. 

We would love to schedule a technical interview with you. Please reply to this email with your availability for next week.

Best regards,
Talent Acquisition Team
"""
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        return f"Success: Interview email sent to {candidate_email}"
    except Exception as e:
        return f"SMTP Error: {e}"
