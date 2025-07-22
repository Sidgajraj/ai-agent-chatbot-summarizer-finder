import streamlit as st  
import os 
import tempfile 
import fitz  
from openai import OpenAI  
from dotenv import load_dotenv 
from docx import Document 


load_dotenv()


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


st.set_page_config(page_title="Legal Summarizer")


st.title("Legal Document Summarizer")


st.markdown("Upload legal documents (PDF, DOCX, or TXT), and receive a concise summary of each.")


uploaded_files = st.file_uploader(
    "upload files",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True
)


def extract_text(file):
    if file.type == "application/pdf":
        text = ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file.read())
            doc = fitz.open(tmp.name)
            for page in doc:
                text += page.get_text()
            doc.close()
        return text

    elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(file.read())
            tmp_path = tmp.name
        try:
            doc = Document(tmp_path)
            text = "\n".join(para.text for para in doc.paragraphs)
            return text
        except Exception as e:
            print("Error reading DOCX:", e)
            return None

    elif file.type == "text/plain":
        return str(file.read(), "utf-8")

    return None  


def summarize_text(text):
    if not text or len(text.strip()) < 100:
        return "No usable content was extracted from the file."

    chunk_size = 2000
    max_chunks = 10  

    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
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
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                timeout=60  
            )
            summaries.append(response.choices[0].message.content.strip())
        except Exception as e:
            summaries.append(f"Failed to summarize chunk {idx+1}: {e}")
            break  

    final_summary = "\n\n".join(summaries)
    return final_summary


def find_answer(text, question):
    prompt = f"""
You are a legal assistant. Use the document below to answer the user's question.

Document:
\"\"\"{text}\"\"\"

Question:
\"\"\"{question}\"\"\"

Answer clearly and concisely using only the document contents.
"""
    response = client.chat.completions.create(
        model="gpt-4-0613",
        messages=[{"role":"user","content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()


if uploaded_files is not None and len(uploaded_files) > 0:
    summary_blocks = []  

    for file in uploaded_files:
        block = f" {file.name}\n\n"

        with st.spinner(f"Extracting content from {file.name}..."):
            text = extract_text(file)

            if not text:
                block += "Could not extract text from this file. \n---"
                summary_blocks.append(block)
                continue


        action = st.radio(
            f"What would you like to do with **{file.name}**?",
            ["Summarize", "Find Something"],
            key=file.name
        )
        
        if action == "Summarize":
            if st.button(f"Summarize {file.name}"):
                with st.spinner("Summarizing..."):
                    summary = summarize_text(text)
                    block += "**Summary generated:**\n\n"
                    block += summary.replace("\n"," \n") + "\n\n---"
                    summary_blocks.append(block)

        elif action == "Find Something":

            user_question = st.text_input(f"Enter your question about{file.name}:", key=f"question_{file.name}")
            if st.button(f"Find answer in {file.name}"):
                if user_question.strip():
                    with st.spinner("Searching..."):
                        answer = find_answer(text, user_question)
                        block += f"**Question:** {user_question}\n\n"
                        block += answer + "\n\n---"
                        summary_blocks.append(block)
                else:
                    block += "Please enter a question before clicking. \n---"
                    summary_blocks.append(block)


        for block in reversed(summary_blocks):
            st.markdown(block)