import streamlit as st
import os
import tempfile
import fitz
from openai import OpenAI
from dotenv import load_dotenv
from docx import Document
from rag import chunk_text, embed_chunks, save_to_faiss, search_faiss
import numpy as np 

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Legal Summarizer")
st.title("Legal Document Summarizer")
st.markdown("Upload legal documents (PDF, DOCX, or TXT), and receive a concise summary or find answers to speciic questions.")

uploaded_files = st.file_uploader("Upload files", type=["pdf", "docx", "txt"], accept_multiple_files=True)

def extract_text(file):
    if file.type == "application/pdf":
        text = ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=tempfile.gettempdir()) as tmp:
            tmp.write(file.read())
            tmp_path = tmp.name  

        doc = fitz.open(tmp_path)
        for page in doc:
            text += page.get_text()
        doc.close()

        os.remove(tmp_path)  
        return text

    elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx", dir=tempfile.gettempdir()) as tmp:
            tmp.write(file.read())
            tmp_path = tmp.name  

        try:
            doc = Document(tmp_path)
            text = "\n".join(para.text for para in doc.paragraphs)
        except Exception as e:
            print("Error reading DOCX:", e)
            text = None

        os.remove(tmp_path)  
        return text

    elif file.type == "text/plain":
        return str(file.read(), "utf-8")

    return None


def summarize_text(text):
    if not text or len(text.strip()) < 100:
        return "No usable content was extracted from the file."
    
    chunks = chunk_text(text, chunk_size=1000)
    max_chunks = 15
    summaries = []

    for idx, chunk in enumerate(chunks[:max_chunks]):
        prompt = f"""
You are a helpful legal assistant. Summarize the following portion of a legal document in clear and concise language.
Focus on key events, involved parties, dates, and outcomes if mentioned.

Document Chunk {idx+1}:
\"\"\"{chunk}\"\"\"
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4-0613",
                messages=[{"role":"user","content": prompt}],
                temperature=0.3,
                timeout=60
            )
            summaries.append(response.choices[0].message.content.strip())
        except Exception as e:
            summaries.append(f"Failed to summarize chunk {idx+1}: {e}")
            break
        return "\n\n".join(summaries)
    

def find_answer(question, file_name):
    top_chunks = search_faiss(question, faiss_path=file_name) 
    context = "\n\n".join(top_chunks) 
    prompt = f"""
You are a legal assistant. Use the context below to answer the user's question.

Context:
\"\"\"{context}\"\"\"

Question:
\"\"\"{question}\"\"\"

Answer clearly and concisely using only the document contents.
"""
    response = client.chat.completions.create(
        model = "gpt-4-0613",
        messages=[{"role":"user","content":prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

if uploaded_files:
    summary_blocks = []
    for file in uploaded_files:
        block = f"**File: {file.name}**\n\n"
        with st.spinner(f"Extracting content from {file.name}..."):
            text = extract_text(file)
            if not text:
                block += "Could not extract text from this file. \n---"
                summary_blocks.append(block)
                continue
        with st.spinner("Preparing for question answering..."):
            chunks = chunk_text(text)
            embeddings = embed_chunks(chunks)
            base_name = os.path.splitext(file.name)[0]
            temp_index_path = os.path.join(tempfile.gettempdir(), base_name)
            save_to_faiss(chunks, np.array(embeddings), faiss_path=temp_index_path)

        action = st.radio(f"What would you ike to do with **{file.name}**?",["Summarize","Find Something"], key=file.name)

        if action == "Summarize":
            if st.button(f"Summarize {file.name}"):
                with st.spinner("Summarizing..."):
                    summary = summarize_text(text)
                    block += summary.replace("\n"," \n") + "\n\n---"
                    summary_blocks.append(block)

        elif action == "Find Something":
            user_question = st.text_input(f"Enter your question about{file.name}:", key = f"question_{file.name}")
            if st.button(f"Find answer in {file.name}"):
                if user_question.strip():
                    with st.spinner("Searching..."):
                        answer = find_answer(user_question, file.name)
                        block += f"**Question:** {user_question} \n\n"
                        block += answer + "\n\n----"
                        summary_blocks.append(block)
                else:
                    block += "Please enter a question before clicking. \n---"
                    summary_blocks.append(block)

    for block in reversed(summary_blocks):
        st.markdown(block)
