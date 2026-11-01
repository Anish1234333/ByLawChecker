# BylawCheck-Lite

A small RAG assistant over three building-regulation PDFs (Delhi UBBL 2016, Mumbai DCPR 2034, Hyderabad Revised Building Rules 2006).

- **Quick Check**: ask a question, get an answer with `[City, p.X]` citations and source snippets. If the regulations do not contain the answer it refuses: "I can't find this in the provided regulations."
- **Plan Review**: fill in a short form, get a report with applicable rules, what looks fine, what needs attention, what could not be checked, and a rating (Looks Good / Needs Changes / Not Enough Info).

Pre-check only. Confirm with the municipal authority or an architect.

## Layout

```
data/            delhi.pdf  mumbai.pdf  hyderabad.pdf   (not committed)
index/           FAISS index built by build_index.py     (committed, see size note)
build_index.py   PDF -> pages -> chunks -> embeddings -> FAISS
pipeline.py      index loading, ask_graph, report_graph, run_ask(), run_report(), get_llm()
api.py           FastAPI wrapper (/health, /ask, /report)
app.py           Streamlit UI (in-process, or via API_URL)
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY=your_key        # free key from console.groq.com
python build_index.py               # once; writes index/
```

## Run

Streamlit alone (graphs run in-process):

```bash
streamlit run app.py
```

FastAPI:

```bash
uvicorn api:app --port 8000
curl localhost:8000/health
curl -X POST localhost:8000/ask -H 'content-type: application/json' \
     -d '{"question": "What is the minimum front setback?", "city": "Mumbai"}'
```

Streamlit against the API:

```bash
API_URL=http://localhost:8000 streamlit run app.py
```

## Deploy on Streamlit Cloud

1. Push this folder to GitHub (include `index/`, exclude `data/*.pdf`).
2. On share.streamlit.io create an app with `app.py` as the entry point.
3. In **Settings > Secrets** add `GROQ_API_KEY = "your_key"`.

No `API_URL` is set there, so the app runs the graphs in-process.

## UI overview

- **Two modes** switched with a segmented control: Quick Check (chat) and Plan Review (form and report).
- **City selector** (Delhi / Mumbai / Hyderabad / All) in the header. Plan Review pre-selects it, and uses one city per review.
- **Dark mode** toggle in the header. Both palettes are CSS variables, so every element switches together.
- **Sidebar** holds only advanced settings: top-k slider and an About panel (pages and chunks per city, in-process or API mode).
- **Sources** appear in an expander under each answer and report as small cards (city, page, snippet).

## Notes

- Page numbers in citations are PDF page indexes (page 1 = first page of the file), not the printed page numbers.
- Chunks never cross page boundaries, so every citation points to exactly one page.
- `ABSTAIN_THRESHOLD` in `pipeline.py` controls when retrieval is judged too far from the question. It is an L2 distance on normalised bge-small vectors; raise it to answer more, lower it to refuse more.
- Swap the LLM in `get_llm()` in `pipeline.py`. The fine-tuned LoRA models from the Kaggle notebook are not loaded here (too heavy for Streamlit Cloud).
- Index size is printed by `build_index.py`; it is small enough for GitHub (well under 100 MB per file).
