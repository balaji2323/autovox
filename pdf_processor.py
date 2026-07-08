import os
import pdfplumber

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    return text

def process_resume_files(file_paths):
    resumes_data = []
    
    # Loop through the exact files the user selected
    for filepath in file_paths:
        filename = os.path.basename(filepath)
        content = extract_text_from_pdf(filepath)
        
        if content.strip():
            # Store the text and the filename
            resumes_data.append({"filename": filename, "content": content})
            
    return resumes_data