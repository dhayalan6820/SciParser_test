import io
import requests
from pypdf import PdfReader
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class ReadPdfFromUrlSchema(BaseModel):
    url: str = Field(..., description="The direct URL to the PDF file.")

def read_pdf_from_url(url: str) -> str:
    """Download a PDF from a URL and extract its text content."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Check if it actually looks like a PDF
        if b"%PDF" not in response.content[:10]:
            return "Error: URL did not return a valid PDF file."

        reader = PdfReader(io.BytesIO(response.content))
        text_content = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text_content.append(f"--- Page {i + 1} ---\n{text}")
        
        if not text_content:
            return "PDF downloaded successfully, but no text could be extracted (it might be scanned images)."
            
        return "\n\n".join(text_content)
    except requests.exceptions.RequestException as e:
        return f"Error downloading PDF: {str(e)}"
    except Exception as e:
        return f"Error parsing PDF: {str(e)}"

def create_read_pdf_from_url_tool() -> StructuredTool:
    return StructuredTool(
        name="read_pdf_from_url",
        description="Download a PDF file from a direct URL and extract its text content. Use this to read online PDF documents that the browser cannot parse as DOM text.",
        args_schema=ReadPdfFromUrlSchema,
        func=read_pdf_from_url
    )
