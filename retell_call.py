import json
import os
import re

import requests
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import OpenAI

load_dotenv()


def using_gemini():
    return os.getenv("AI_PROVIDER", "gemini").strip().lower() == "gemini"


def make_retell_call(name, phone, ats_score, candidate_id=None, jd_text="", resume_text=""):
    url = "https://api.retellai.com/v2/create-phone-call"
    api_key = os.getenv("RETELL_API_KEY", "").strip()
    from_number = os.getenv("RETELL_FROM_NUMBER", "").strip()
    agent_id = os.getenv("RETELL_AGENT_ID", "").strip()

    if not all([api_key, from_number, agent_id, phone]):
        return {
            "ok": False,
            "error": "Retell API key, from number, agent id, or candidate phone is missing.",
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    dynamic_variables = {
        "candidate_name": name,
        "ats_score": str(ats_score),
        "candidate_id": str(candidate_id or ""),
    }
    payload = {
        "from_number": from_number,
        "to_number": phone,
        "agent_id": agent_id,
        "retell_llm_dynamic_variables": dynamic_variables,
        "metadata": {
            "candidate_id": str(candidate_id or ""),
            "candidate_name": name,
        },
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()
    except Exception as exc:
        return {"ok": False, "error": f"Retell call failed: {exc}"}

    if response.status_code >= 400:
        return {
            "ok": False,
            "error": data.get("message") or data.get("error") or f"Retell returned HTTP {response.status_code}.",
            "raw": data,
        }

    data["ok"] = True
    return data


def extract_retell_candidate_id(call):
    for container_name in ("metadata", "retell_llm_dynamic_variables", "dynamic_variables"):
        container = call.get(container_name) or {}
        candidate_id = container.get("candidate_id")
        if candidate_id:
            return str(candidate_id).strip()
    return ""


def build_retell_transcript(call):
    transcript = call.get("transcript") or call.get("scrubbed_transcript") or ""
    if transcript:
        return normalize_retell_roles(transcript)

    utterances = call.get("transcript_object") or call.get("scrubbed_transcript_object") or []
    lines = []
    for item in utterances:
        role = str(item.get("role") or item.get("speaker") or "").strip().lower()
        text = str(item.get("content") or item.get("text") or item.get("words") or "").strip()
        if not text:
            continue
        label = "Candidate" if role in {"user", "customer", "caller"} else "AI Recruiter"
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


def normalize_retell_roles(transcript):
    replacements = {
        "Agent:": "AI Recruiter:",
        "Assistant:": "AI Recruiter:",
        "User:": "Candidate:",
        "Customer:": "Candidate:",
        "Caller:": "Candidate:",
    }
    normalized = transcript
    for source, target in replacements.items():
        normalized = re.sub(rf"(?m)^{re.escape(source)}", target, normalized)
    return normalized.strip()


def extract_analysis_result(call):
    analysis = call.get("call_analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}
    haystack = [custom, analysis]

    result = ""
    for data in haystack:
        result = find_value_by_key(data, ("qualification", "qualified", "result", "status", "decision"))
        if result:
            break

    score = None
    for data in haystack:
        score = find_value_by_key(data, ("score", "rating", "interview_score"))
        if score is not None:
            break

    summary = analysis.get("call_summary") or analysis.get("summary") or custom.get("summary") or ""
    return normalize_result(result), normalize_score(score), summary


def find_value_by_key(value, key_fragments):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).lower()
            if any(fragment in normalized_key for fragment in key_fragments):
                return item
        for item in value.values():
            found = find_value_by_key(item, key_fragments)
            if found is not None and found != "":
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_value_by_key(item, key_fragments)
            if found is not None and found != "":
                return found
    return None


def normalize_result(value):
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if text in {"TRUE", "YES", "PASS", "PASSED", "QUALIFIED", "SELECTED", "SHORTLISTED"}:
        return "QUALIFIED"
    if text in {"FALSE", "NO", "FAIL", "FAILED", "REJECTED", "NOT QUALIFIED", "UNQUALIFIED"}:
        return "NOT QUALIFIED"
    if "NOT" in text and "QUAL" in text:
        return "NOT QUALIFIED"
    if "QUAL" in text or "PASS" in text or "SELECT" in text:
        return "QUALIFIED"
    if "REJECT" in text or "FAIL" in text:
        return "NOT QUALIFIED"
    return ""


def normalize_score(value):
    if value is None or value == "":
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    score = int(match.group(0))
    if score > 5:
        score = round(score / 20)
    return max(0, min(score, 5))


def evaluate_retell_transcript(candidate_name, job_description, transcript):
    if not transcript.strip():
        return 0, "NOT QUALIFIED", "No completed transcript was available."

    prompt = f"""
You are an expert technical recruiter evaluating a completed Retell phone interview.

Candidate: {candidate_name}
Job Description: {job_description}

Transcript:
{transcript}

Return strict JSON only:
{{
  "score": 0 to 5,
  "result": "QUALIFIED" or "NOT QUALIFIED",
  "summary": "one short sentence for HR"
}}
"""
    try:
        if using_gemini():
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            raw_text = ChatGoogleGenerativeAI(model=model, temperature=0.1).invoke(prompt).content
        else:
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            response = OpenAI().chat.completions.create(
                model=model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
            )
            raw_text = response.choices[0].message.content
        parsed = json.loads(raw_text)
        score = normalize_score(parsed.get("score"))
        result = normalize_result(parsed.get("result"))
        summary = str(parsed.get("summary") or "Interview completed.").strip()
        return score if score is not None else 0, result or "NOT QUALIFIED", summary
    except Exception as exc:
        print(f"Retell transcript evaluation error: {exc}")

    candidate_words = sum(len(line.split()) for line in transcript.splitlines() if line.startswith("Candidate:"))
    score = 3 if candidate_words >= 80 else 2 if candidate_words >= 35 else 1
    result = "QUALIFIED" if score >= 3 else "NOT QUALIFIED"
    return score, result, "Evaluation completed using fallback transcript scoring."
