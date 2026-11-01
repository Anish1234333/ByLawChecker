"""Build the FAISS index from data/*.pdf and save it in index/ (run once, then commit index/)."""
import os

import fitz  # PyMuPDF
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pipeline import INDEX_DIR, get_embeddings

HERE = os.path.dirname(os.path.abspath(__file__))
PDFS = {"Delhi": "delhi.pdf", "Mumbai": "mumbai.pdf", "Hyderabad": "hyderabad.pdf"}
CHUNK_CHARS, OVERLAP_CHARS = 2000, 320   # ~500 and ~80 tokens at ~4 chars per token
MIN_CHARS_PER_PAGE = 50                  # below this average the PDF is treated as scanned


def page_text(page, ocr):
    if ocr:
        return page.get_textpage_ocr(full=True).extractText()  # needs Tesseract installed
    return page.get_text()


def load_pages(city, path):
    """One Document per PDF page; page numbers are 1-based PDF page indexes."""
    pdf = fitz.open(path)
    texts = [p.get_text() for p in pdf]
    ocr = sum(len(t) for t in texts) < MIN_CHARS_PER_PAGE * len(texts)
    if ocr:
        print(f"{city}: no text layer found, falling back to OCR (slow)")
        texts = [page_text(p, True) for p in pdf]
    return [Document(page_content=t, metadata={"city": city, "page": i + 1, "source": os.path.basename(path)})
            for i, t in enumerate(texts) if t.strip()]


def main():
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_CHARS, chunk_overlap=OVERLAP_CHARS)
    chunks = []
    for city, name in PDFS.items():
        pages = load_pages(city, os.path.join(HERE, "data", name))
        city_chunks = [c for c in splitter.split_documents(pages) if len(c.page_content.strip()) > 80]
        print(f"{city}: {len(pages)} pages -> {len(city_chunks)} chunks")
        chunks += city_chunks
    store = FAISS.from_documents(chunks, get_embeddings())
    store.save_local(INDEX_DIR)
    size = sum(os.path.getsize(os.path.join(INDEX_DIR, f)) for f in os.listdir(INDEX_DIR)) / 1e6
    print(f"Saved {len(chunks)} chunks to {INDEX_DIR} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
