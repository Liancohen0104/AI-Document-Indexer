import pdfplumber
from docx import Document
import nltk
from typing import List
from google import genai
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Gemini הגדרת מפתח ל
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# DB חיבור ל
def get_db_connection():
    try:
        postgres_url = os.getenv("POSTGRES_URL")
        if not postgres_url:
            raise ValueError("POSTGRES_URL is not set in environment variables")

        return psycopg2.connect(postgres_url)

    except Exception as e:
        print(f"[DB ERROR] Failed to connect to database: {e}")
        raise

# NLTK הורדת משאבים נדרשים
nltk.download("punkt")
nltk.download("punkt_tab")

# PDF חילוץ טקסט מקובץ 
def extract_text_from_pdf(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")
    
    text = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)

    except Exception as e:
        print(f"[PDF ERROR] Failed to extract text from PDF: {e}")

    return "\n".join(text)

# DOCX חילוץ טקסט מקובץ 
def extract_text_from_docx(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"DOCX file not found: {file_path}")
    
    text = []

    try:
        document = Document(file_path)
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text)

    except Exception as e:
        print(f"[DOCX ERROR] Failed to extract text from DOCX: {e}")

    return "\n".join(text)

# חלוקת טקסט לפי משפטים
def chunk_text_by_sentence(text: str) -> List[str]:
    if not text.strip():
        return []
    
    try:
        sentences = nltk.sent_tokenize(text)
        return [s.strip() for s in sentences if s.strip()]

    except Exception as e:
        print(f"[CHUNKING ERROR] Failed to split text into sentences: {e}")
        return []

# למקטע Embedding יצירת 
def create_embedding(text: str) -> list:
    if not text.strip():
        return None
    
    try:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text
        )
        return result.embeddings[0].values

    except Exception as e:
        print(f"[EMBEDDING ERROR] Failed to create embedding: {e}")
        return None

# DB שמירת מקטע ל 
def save_chunk_to_db(chunk_text: str, embedding: list, filename: str, strategy: str):
    if embedding is None:
        return

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO document_chunks (chunk_text, embedding, filename, strategy_split)
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(query, (chunk_text, embedding, filename, strategy))
        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB INSERT ERROR] Failed to save chunk: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# עיבוד קובץ
def process_file(file_path: str, strategy_name: str):
    # קביעת סוג הקובץ
    if file_path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    elif file_path.lower().endswith(".docx"):
        text = extract_text_from_docx(file_path)
    else:
        print(f"[SKIP] Unsupported file type: {file_path}")
        return

    if not text.strip():
        print(f"[SKIP] No text extracted from {file_path}")
        return

    chunks = chunk_text_by_sentence(text)

    if not chunks:
        print(f"[SKIP] No chunks created for {file_path}")
        return

    for chunk in chunks:
        embedding = create_embedding(chunk)
        save_chunk_to_db(
            chunk_text=chunk,
            embedding=embedding,
            filename=os.path.basename(file_path),
            strategy=strategy_name
        )

    print(f"[DONE] Processed file: {file_path}")

# נקודת כניסה ראשית
if __name__ == "__main__":
    files_to_process = [
        "sample.pdf",
        "sample.docx"
    ]

    strategy_name = "Sentence-based splitting"

    for file_path in files_to_process:
        process_file(file_path, strategy_name)