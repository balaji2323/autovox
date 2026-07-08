import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# The folder where ChromaDB will save your vectors locally
CHROMA_PATH = "chroma_storage"

def get_embedding_model():
    # This downloads a fast, lightweight embedding model the first time you run it
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def store_resumes_in_db(resumes_data):
    docs = []
    for resume in resumes_data:
        # Convert our dictionaries into LangChain Document objects
        doc = Document(
            page_content=resume["content"], 
            metadata={"source": resume["filename"]}
        )
        docs.append(doc)
    
    embedding_model = get_embedding_model()
    
    # Create the Chroma database and persist it to the disk
    db = Chroma.from_documents(
        documents=docs,
        embedding=embedding_model,
        persist_directory=CHROMA_PATH
    )
    
    print(f"Successfully embedded and saved {len(docs)} resumes to ChromaDB.")
    return db

def get_vector_db():
    # Helper function to load the database later when we need to query it
    if os.path.exists(CHROMA_PATH):
        embedding_model = get_embedding_model()
        return Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_model)
    return None