from docx import Document
import pdfplumber

from pptx import Presentation

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts all text from a PDF file."""
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

def extract_text_from_txt(txt_path: str) -> str:
    """Extracts all text from a TXT file."""
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            text = file.read()
        return text
    except Exception as e:
        print(f"Error reading the text file: {e}")
        return ""
    
def extract_text_from_pptx(pptx_path: str) -> str:
        """Extracts text from a PPTX file."""
        text = ""
        try:
            presentation = Presentation(pptx_path)
            for slide in presentation.slides:
                for shape in slide.shapes:
                    if hasattr(shape, 'text'):  # Check if the shape has text
                        text += shape.text + "\n"  # Add the text from the shape to the final text
            return text.strip()
        except Exception as e:
            print(f"Błąd podczas wczytywania pliku PPTX: {e}")
            return ""
        

def extract_text_from_docx(docx_path: str) -> str:
    """Extracts text from a DOCX file."""
    try:
        # Open the DOCX file
        doc = Document(docx_path)
        
        # Extract text from each paragraph in the DOCX file
        text = '\n'.join([para.text for para in doc.paragraphs])
        
        return text
    except Exception as e:
        print(f"Błąd podczas wczytywania pliku DOCX: {e}")
        return ""


