import os
import re
from urllib.parse import urljoin

from dotenv import load_dotenv
from flask import Flask, request
from fpdf import FPDF
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import OpenAI
from twilio.rest import Client
from twilio.twiml.voice_response import Gather, VoiceResponse

from mysql_db import save_interview_transcript

load_dotenv()

app = Flask(__name__)
active_interviews = {}

if not os.path.exists("Transcripts"):
    os.makedirs("Transcripts")


def using_gemini():
    return os.getenv("AI_PROVIDER", "gemini").strip().lower() == "gemini"


def generate_pdf(candidate_name, messages, final_score=None, status=None):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=16, style="B")
        pdf.cell(200, 10, txt=f"Live Interview Transcript: {candidate_name}", ln=True, align="C")

        if final_score is not None:
            pdf.set_font("Arial", size=14, style="I")
            pdf.cell(200, 10, txt=f"Final Result: {status} ({final_score}/5 Correct)", ln=True, align="C")

        pdf.ln(10)

        for msg in messages:
            if isinstance(msg, SystemMessage):
                continue
            role = "AI Recruiter" if isinstance(msg, AIMessage) else "Candidate"
            clean_text = msg.content.encode("latin-1", "replace").decode("latin-1")
            pdf.set_font("Arial", style="B", size=12)
            pdf.cell(0, 8, txt=f"{role}:", ln=True)
            pdf.set_font("Arial", style="", size=12)
            pdf.multi_cell(0, 8, txt=clean_text)
            pdf.ln(5)

        pdf.output(f"Transcripts/{candidate_name}_Transcript.pdf")
    except Exception as e:
        print(f"PDF Generation Error: {e}")


def build_transcript_text(messages):
    lines = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            continue
        role = "AI Recruiter" if isinstance(msg, AIMessage) else "Candidate"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def persist_transcript(session):
    candidate_id = session.get("candidate_id")
    if not candidate_id:
        return
    save_interview_transcript(
        candidate_id,
        build_transcript_text(session["messages"]),
        session.get("interview_result"),
        session.get("score"),
    )


def build_public_url(path):
    base_url = os.getenv("NGROK_URL", "").strip().rstrip("/")
    if base_url:
        return f"{base_url}{path}"
    return urljoin(request.url_root, path.lstrip("/"))


def generate_interview_questions(candidate_name, jd_text, resume_text):
    client = None if using_gemini() else OpenAI()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash") if using_gemini() else os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = f"""
You are an expert technical recruiter.
Create exactly 5 short spoken interview questions for this candidate.

Candidate: {candidate_name}
Job Description: {jd_text}
Resume: {resume_text}

Rules:
- Return exactly 5 questions.
- Each question must be one sentence.
- Focus on technical fit for the role.
- Plain English only.
- Do not number the questions.
- Separate each question with a new line.
"""
    try:
        if using_gemini():
            response = ChatGoogleGenerativeAI(model=model, temperature=0.2).invoke(prompt)
            raw_content = response.content
        else:
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_content = response.choices[0].message.content
        lines = [line.strip("- ").strip() for line in raw_content.splitlines() if line.strip()]
        questions = [line for line in lines if "?" in line or len(line.split()) > 5]
        questions = [question if question.endswith("?") else f"{question}?" for question in questions[:5]]
        if len(questions) >= 5:
            return questions[:5]
    except Exception as e:
        print(f"Question Generation Error: {e}")

    return [
        f"Can you walk me through a recent project that makes you a strong fit for this role, {candidate_name}?",
        "Which technical skills do you use most often in your current work?",
        "How would you troubleshoot a production issue in your main area of expertise?",
        "Tell me about a difficult bug or blocker and how you resolved it.",
        "Why do you believe you are a strong fit for this position?",
    ]


def evaluate_interview(session):
    client = None if using_gemini() else OpenAI()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash") if using_gemini() else os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    qa_blocks = []
    for index, answer in enumerate(session["answers"], start=1):
        question = session["questions"][index - 1] if index - 1 < len(session["questions"]) else f"Question {index}"
        qa_blocks.append(f"Question {index}: {question}\nAnswer {index}: {answer}")

    prompt = f"""
You are an expert technical recruiter evaluating a phone interview.

Candidate: {session['name']}
Job Description: {session['job_description']}

Interview transcript:
{chr(10).join(qa_blocks)}

Return strict JSON only:
{{
  "score": 0 to 5,
  "result": "QUALIFIED" or "NOT QUALIFIED",
  "summary": "one short sentence for HR"
}}
"""
    try:
        if using_gemini():
            response = ChatGoogleGenerativeAI(model=model, temperature=0.1).invoke(
                "Return only valid JSON for the interview evaluation.\n\n"
                f"{prompt}"
            )
            raw_text = response.content
        else:
            response = client.chat.completions.create(
                model=model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "Return only valid JSON for the interview evaluation.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            raw_text = response.choices[0].message.content
        score_match = re.search(r'"score"\s*:\s*(\d+)', raw_text)
        result_match = re.search(r'"result"\s*:\s*"([^"]+)"', raw_text)
        summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', raw_text)
        score = int(score_match.group(1)) if score_match else 0
        result = result_match.group(1).strip().upper() if result_match else "NOT QUALIFIED"
        summary = summary_match.group(1).strip() if summary_match else "Interview completed."
        return max(0, min(score, 5)), result, summary
    except Exception as e:
        print(f"Interview Evaluation Error: {e}")

    heuristic_score = 0
    for answer in session["answers"]:
        if len(answer.split()) >= 8:
            heuristic_score += 1
    heuristic_result = "QUALIFIED" if heuristic_score >= 3 else "NOT QUALIFIED"
    return heuristic_score, heuristic_result, "Evaluation completed using fallback scoring."


def start_phone_interview(candidate_phone, candidate_name, jd_text, resume_text, candidate_id=None):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_number = re.sub(r"\s+", "", os.getenv("TWILIO_PHONE_NUMBER", ""))
    candidate_phone = re.sub(r"\s+", "", str(candidate_phone or ""))
    ngrok_url = os.getenv("NGROK_URL", "").strip().rstrip("/")

    if not all([account_sid, auth_token, twilio_number, ngrok_url]):
        return "Error: Twilio credentials or NGROK_URL missing in .env"

    questions = generate_interview_questions(candidate_name, jd_text, resume_text)
    system_prompt = f"""You are an expert technical recruiter conducting a phone interview with {candidate_name}.
Job Description: {jd_text}
Candidate Resume: {resume_text}

CRITICAL RULES FOR SPOKEN AUDIO:
1. Keep responses very brief and conversational.
2. Speak in plain English only.
3. Do not reveal pass or fail status during the call.
4. End by telling the candidate that the team will get back to them."""

    session = {
        "name": candidate_name,
        "candidate_id": candidate_id,
        "messages": [SystemMessage(content=system_prompt)],
        "q_count": 0,
        "score": 0,
        "interview_result": "In Progress",
        "job_description": jd_text,
        "questions": questions,
        "answers": [],
        "evaluation_summary": "",
    }

    client = Client(account_sid, auth_token)
    try:
        call = client.calls.create(
            to=candidate_phone,
            from_=twilio_number,
            url=f"{ngrok_url}/voice",
        )
        active_interviews[call.sid] = session
        return f"Call initiated! SID: {call.sid}"
    except Exception as e:
        return f"Error initiating call: {e}"


@app.route("/voice", methods=["GET", "POST"])
def voice():
    response = VoiceResponse()
    try:
        call_sid = request.values.get("CallSid")
        session = active_interviews.get(call_sid)

        if not session:
            response.say("The interview session could not be found. Please reconnect with the recruiter team. Goodbye.", language="en-US")
            return str(response)

        ai_text = (
            f"Hello {session['name']}. This is an AI recruiter calling for your technical interview. "
            "Are you ready to begin? Press 1 for yes, or 2 to reschedule."
        )
        session["messages"].append(AIMessage(content=ai_text))
        generate_pdf(session["name"], session["messages"])
        persist_transcript(session)

        gather = Gather(
            input="speech dtmf",
            action=build_public_url("/respond"),
            timeout=10,
            speechTimeout="auto",
            numDigits=1,
            language="en-IN",
            speechModel="phone_call",
        )
        gather.say(ai_text, language="en-IN", voice="alice")
        response.append(gather)
        response.redirect(build_public_url("/voice"))
        return str(response)
    except Exception as e:
        print(f"Voice Route Error: {e}")
        response.say("We could not continue the interview right now. Please try again later.", language="en-US")
        response.hangup()
        return str(response)


@app.route("/respond", methods=["GET", "POST"])
def respond():
    response = VoiceResponse()
    try:
        call_sid = request.values.get("CallSid")
        user_speech = request.values.get("SpeechResult", "").strip()
        digits = request.values.get("Digits", "").strip()

        session = active_interviews.get(call_sid)
        if not session:
            response.say("Session lost. Goodbye.", language="en-US")
            response.hangup()
            return str(response)

        if digits and not user_speech:
            if session["q_count"] == 0:
                user_speech = "yes" if digits == "1" else "no"
            else:
                user_speech = "Please repeat the question."

        if user_speech:
            print(f"\n--- {session['name']} SAID: {user_speech} ---")
            session["messages"].append(HumanMessage(content=user_speech))

            if session["q_count"] == 0:
                declined = any(word in user_speech.lower() for word in ["no", "reschedule", "later", "busy"])
                if declined:
                    ai_text = "No problem at all. We will reach out to reschedule. Thank you and have a great day!"
                    session["messages"].append(AIMessage(content=ai_text))
                    persist_transcript(session)
                    response.say(ai_text, language="en-IN", voice="alice")
                    response.hangup()
                    return str(response)

                session["q_count"] = 1
                ai_text = f"Question 1 of 5. {session['questions'][0]}"
                session["messages"].append(AIMessage(content=ai_text))

            elif session["q_count"] < 5:
                session["answers"].append(user_speech)
                question_index = session["q_count"]
                ai_text = f"Question {question_index + 1} of 5. {session['questions'][question_index]}"
                session["q_count"] += 1
                session["messages"].append(AIMessage(content=ai_text))

            else:
                session["answers"].append(user_speech)
                final_score, status, summary = evaluate_interview(session)
                session["score"] = final_score
                session["interview_result"] = status
                session["evaluation_summary"] = summary

                ai_text = "Thank you for your time today. We will get back to you within 2 to 3 business days. Goodbye."
                session["messages"].append(AIMessage(content=ai_text))
                generate_pdf(session["name"], session["messages"], final_score=final_score, status=status)
                persist_transcript(session)

                print(f"\n*** FINAL RESULT: {status} ({final_score}/5) ***\n")
                response.say(ai_text, language="en-IN", voice="alice")
                response.hangup()
                return str(response)

            generate_pdf(session["name"], session["messages"])
            persist_transcript(session)
        else:
            ai_text = "I didn't quite catch that. Could you please speak your answer or press a key?"
            session["messages"].append(AIMessage(content=ai_text))
            persist_transcript(session)

        gather = Gather(
            input="speech dtmf",
            action=build_public_url("/respond"),
            timeout=10,
            speechTimeout="auto",
            numDigits=1,
            language="en-IN",
            speechModel="phone_call",
        )
        gather.say(ai_text, language="en-IN", voice="alice")
        response.append(gather)
        response.redirect(build_public_url("/respond"))
        return str(response)
    except Exception as e:
        print(f"Respond Route Error: {e}")
        response.say("We could not continue the interview right now. Our recruiting team will follow up with you soon. Goodbye.", language="en-US")
        response.hangup()
        return str(response)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
