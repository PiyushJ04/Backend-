import pdfplumber
from pathlib import Path
class PDFService:
    @staticmethod
    def extract_text(path:Path):
        text=[]
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages:
                text.append(p.extract_text() or "")
        return "\n".join(text)
