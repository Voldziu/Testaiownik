import pdfplumber
import re
from typing import List

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts all text from a PDF file."""
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

def chunk_text(text: str, min_chunk_size: int = 500) -> List[str]:
    """Chunks the text into larger fragments of at least `min_chunk_size` characters."""
    chunks = []
    start_idx = 0

    while start_idx < len(text):
        # Find the next reasonable split point (either by space or the `min_chunk_size`)
        end_idx = start_idx + min_chunk_size
        if end_idx >= len(text):
            chunks.append(text[start_idx:])
            break

        # Find the last space within the chunk to avoid cutting off in the middle of a word
        if text[end_idx] != ' ':
            space_idx = text.rfind(' ', start_idx, end_idx)
            if space_idx != -1:
                end_idx = space_idx
        
        # Append the chunk
        chunks.append(text[start_idx:end_idx].strip())
        start_idx = end_idx
    
    return chunks
