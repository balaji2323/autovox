import os
from dotenv import load_dotenv, find_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv(find_dotenv())

class AIInterviewer:
    def __init__(self, candidate_name, job_description, resume_text):
        # We use Gemini for chat interactions as it handles context well
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
        self.candidate_name = candidate_name
        self.job_description = job_description
        self.resume_text = resume_text
        
        self.chat_history = []
        
        # The AI's Rules of Engagement (Now highly personalized)
        system_prompt = f"""
        You are an expert Technical Recruiter conducting an initial technical screen with {self.candidate_name}.
        
        Here is the Job Description they applied for:
        {self.job_description}
        
        Here is the Candidate's actual Resume:
        {self.resume_text}
        
        CRITICAL RULES:
        1. Ask exactly ONE question at a time. Do NOT list multiple questions.
        2. Wait for the candidate's answer.
        3. TAILOR YOUR QUESTIONS: Do not just ask generic job questions. Look at their resume and ask them to explain how their specific past projects or skills map to the job description requirements. 
           (Example: "I see on your resume you used Python for a web scraper. How would you apply that Python knowledge to the data pipeline role we are hiring for?")
        4. Evaluate their answer strictly. If they miss important details, ask a probing follow-up question.
        5. Keep your responses concise (under 3 sentences). Do not break character.
        
        Start the interview now by introducing yourself and asking the very first targeted technical question.
        """
        
        self.chat_history.append(SystemMessage(content=system_prompt))

    def get_agent_response(self, user_input=None):
        if user_input:
            self.chat_history.append(HumanMessage(content=user_input))
            
        # Send the whole conversation to the LLM
        response = self.llm.invoke(self.chat_history)
        self.chat_history.append(AIMessage(content=response.content))
        
        return response.content
        
    def get_full_transcript(self):
        # Helper to grab the whole chat to save to MySQL
        transcript = ""
        for msg in self.chat_history:
            if isinstance(msg, AIMessage):
                transcript += f"AI: {msg.content}\n\n"
            elif isinstance(msg, HumanMessage):
                transcript += f"Candidate: {msg.content}\n\n"
        return transcript