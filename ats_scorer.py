import os
import json
import time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import OpenAI
from vector_db import get_vector_db
from retell_call import make_retell_call

load_dotenv()


def using_gemini():
    return os.getenv("AI_PROVIDER", "gemini").strip().lower() == "gemini"


def score_resumes(job_description, match_threshold=85):
    if using_gemini() and not os.getenv("GOOGLE_API_KEY"):
        return {"error": "GOOGLE_API_KEY is missing in .env."}

    if not using_gemini() and not os.getenv("OPENAI_API_KEY"):
        return {"error": "OPENAI_API_KEY is missing in .env."}

    db = get_vector_db()
    if not db:
        return {"error": "Vector database not found. Please upload resumes first."}

    max_matches = int(os.getenv("ATS_MAX_MATCHES", "1") or 1)
    retriever = db.as_retriever(search_kwargs={"k": max(1, max_matches)})
    matched_docs = retriever.invoke(job_description)

    if not matched_docs:
        return {"error": "No matching resumes found."}

    client = None if using_gemini() else OpenAI()
    model = (
        os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if using_gemini()
        else os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )

    results = []

    unique_docs = {}
    for doc in matched_docs:
        source = doc.metadata.get("source", "Unknown")
        if source not in unique_docs:
            unique_docs[source] = doc

    request_delay_seconds = float(os.getenv("ATS_SCORE_DELAY_SECONDS", "0") or 0)

    for doc in unique_docs.values():
        try:
            filename = doc.metadata.get("source", "Unknown")

            prompt = f"""
Analyze this resume against the job description.

Job Description:
{job_description}

Resume File: {filename}
Resume Content:
{doc.page_content}

Evaluate the candidate and provide a strict ATS score out of 100 based on skills, experience, and match.
Extract the candidate's name, email address, and phone number from the resume text.

Return JSON exactly in this shape:
{{
  "filename": "{filename}",
  "candidate_name": "Extracted Name or Unknown",
  "candidate_email": "Extracted Email or Unknown",
  "candidate_phone": "Extracted Phone Number with country code (e.g. +91...) or Unknown",
  "score": 90,
  "reasoning": "A brief 1-sentence explanation of the score."
}}
"""

            if using_gemini():
                llm = ChatGoogleGenerativeAI(model=model, temperature=0.1)
                response = llm.invoke(
                    "You are an expert Applicant Tracking System. Return only valid JSON.\n\n"
                    f"{prompt}"
                )
                raw_content = (
                    response.content
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )
            else:
                response = client.chat.completions.create(
                    model=model,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an expert Applicant Tracking System. "
                                "Return only valid JSON with the requested fields."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                raw_content = response.choices[0].message.content

            start_idx = raw_content.find("{")
            end_idx = raw_content.rfind("}")

            if start_idx == -1 or end_idx == -1:
                print(f"Warning: Could not find valid JSON in LLM response for {filename}")
                continue

            result_dict = json.loads(raw_content[start_idx:end_idx + 1])

            result_dict["resume_text"] = doc.page_content

            use_retell = os.getenv("USE_RETELL", "false").lower() == "true"
            candidate_score = int(result_dict.get("score", 0))
            candidate_phone = result_dict.get("candidate_phone", "Unknown")
            candidate_name = result_dict.get("candidate_name", "Candidate")

            if use_retell and candidate_score >= match_threshold:
                if candidate_phone != "Unknown" and candidate_phone.startswith("+"):
                    try:
                        call_result = make_retell_call(
                            name=candidate_name,
                            phone=candidate_phone,
                            ats_score=candidate_score
                        )

                        result_dict["retell_call_status"] = "Call Triggered"
                        result_dict["retell_call_response"] = call_result

                        print("Retell call triggered:", call_result)

                    except Exception as call_error:
                        result_dict["retell_call_status"] = "Call Failed"
                        result_dict["retell_call_error"] = str(call_error)
                        print("Retell call failed:", call_error)
                else:
                    result_dict["retell_call_status"] = "Invalid or missing phone number"
            else:
                result_dict["retell_call_status"] = "Not Triggered"

            results.append(result_dict)

            if request_delay_seconds > 0:
                print(f"Pausing for {request_delay_seconds:g} seconds to prevent API limits...")
                time.sleep(request_delay_seconds)

        except Exception as e:
            error_text = str(e)
            print(f"Error processing {doc.metadata.get('source')}: {error_text}")

            if (
                "RESOURCE_EXHAUSTED" in error_text
                or "429" in error_text
                or "quota" in error_text.lower()
            ):
                return {
                    "error": (
                        "AI provider quota or rate limit is exhausted for now. "
                        "Wait for the quota window to reset, reduce ATS_MAX_MATCHES, "
                        "or use a paid/API plan."
                    )
                }

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results