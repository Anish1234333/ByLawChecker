"""Shared logic for BylawCheck-Lite: index loading, the two LangGraph graphs, run_ask(), run_report()."""
import os
from functools import lru_cache
from typing import TypedDict

from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.graph import END, StateGraph

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(HERE, "index")
EMBED_MODEL = "BAAI/bge-small-en-v1.5"       # 512-token window, fits ~500-token chunks
GROQ_MODEL = "llama-3.3-70b-versatile"       # swap the model here (see get_llm)
ABSTAIN_THRESHOLD = 0.65                     # FAISS L2 distance on normalised bge vectors; higher = less similar
REFUSAL = "I can't find this in the provided regulations."
DISCLAIMER = "*Pre-check only. Confirm with the municipal authority or an architect.*"

RULES = (
    "You answer questions about building regulations for Delhi, Mumbai and Hyderabad. "
    "Answer ONLY from the provided context. Cite every claim as [City, p.X] using the labels in the context. "
    "Never invent numbers: if a number is not in the context, do not state it. "
    f"If the context does not contain the answer, reply exactly: {REFUSAL}"
)

ASK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", RULES + " Be concise and use markdown."),
    ("human", "Context:\n{context}\n\nQuestion: {question}"),
])

REPORT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", RULES + """

You are writing a short plan pre-check report for the city given in the plan. Output markdown only:
Line 1 exactly: Rating: Looks Good   OR   Rating: Needs Changes   OR   Rating: Not Enough Info
Then these four sections, in this order, as '## ' headings:
## Applicable rules   (the rules found in the context, each with a [City, p.X] citation)
## Looks fine         (plan values that meet a rule; quote both the value and the limit)
## Needs attention    (plan values that break or come close to a rule; quote both)
## Could not check    (anything marked 'not provided', or any rule missing from the context)
Rating guide: Needs Changes if any value breaks a rule; Not Enough Info if the key checks cannot be done; otherwise Looks Good.
Do not add a disclaimer. Use 'None' under a heading with nothing to report."""),
    ("human", "Plan details:\n{plan}\n\nContext:\n{context}"),
])

# one retrieval query per topic; {…} are filled from the plan form
TOPICS = {
    "FSI": "floor space index FSI permissible for {use} building on plot area {plot_area} sq m",
    "height vs road width": "maximum building height permitted with road width {road_width} m for {use} building",
    "setbacks / open space": "front side rear setbacks open space margins for {use} plot {plot_area} sq m height {height} m",
    "parking": "parking requirement number of car parking spaces for {use} building",
    "other": "ground coverage permissible number of storeys {floors} floors {use} building",
}


# ---------- LLM and index ----------

def _groq_key():
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    # Streamlit Cloud also exposes secrets as env vars; only touch st.secrets when a secrets file exists
    if any(os.path.exists(p) for p in [os.path.expanduser("~/.streamlit/secrets.toml"), ".streamlit/secrets.toml"]):
        import streamlit as st
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    raise RuntimeError("GROQ_API_KEY is not set (environment variable or Streamlit secret).")


@lru_cache(maxsize=1)
def get_llm():
    """The only place the LLM is configured; swap the class/model here."""
    from langchain_groq import ChatGroq
    return ChatGroq(model=GROQ_MODEL, temperature=0, api_key=_groq_key())


def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL, encode_kwargs={"normalize_embeddings": True})


@lru_cache(maxsize=1)
def load_index():
    return FAISS.load_local(INDEX_DIR, get_embeddings(), allow_dangerous_deserialization=True)


def index_stats():
    """{city: {"chunks": n, "pages": n}} for the About panel."""
    stats = {}
    for doc in load_index().docstore._dict.values():
        s = stats.setdefault(doc.metadata["city"], {"chunks": 0, "pages": set()})
        s["chunks"] += 1
        s["pages"].add(doc.metadata["page"])
    return {c: {"chunks": s["chunks"], "pages": len(s["pages"])} for c, s in stats.items()}


def search(query, city, k):
    """Top-k (Document, L2 distance) pairs, optionally restricted to one city."""
    store = load_index()
    flt = None if city == "All" else {"city": city}
    return store.similarity_search_with_score(query, k=k, filter=flt, fetch_k=store.index.ntotal)


# ---------- formatting helpers ----------

def format_context(docs):
    return "\n\n".join(f"[{d.metadata['city']}, p.{d.metadata['page']}]\n{d.page_content}" for d in docs)


def to_sources(docs):
    """Unique (city, page) pairs with a short snippet."""
    seen, out = set(), []
    for d in docs:
        key = (d.metadata["city"], d.metadata["page"])
        if key not in seen:
            seen.add(key)
            snippet = " ".join(d.page_content.split())[:220]
            out.append({"city": key[0], "page": key[1], "snippet": snippet})
    return out


def _val(v):
    return "not provided" if v in (None, "") else str(v)


# ---------- ask_graph: retrieve -> check_relevance -> (generate_answer | abstain) -> END ----------

class AskState(TypedDict, total=False):
    question: str
    city: str
    k: int
    hits: list
    relevant: bool
    answer: str
    sources: list
    abstained: bool


def retrieve(s: AskState):
    return {"hits": search(s["question"], s["city"], s["k"])}


def check_relevance(s: AskState):
    # FAISS returns distances, so the best hit is the smallest one
    best = min((score for _, score in s["hits"]), default=float("inf"))
    return {"relevant": best <= ABSTAIN_THRESHOLD}


def generate_answer(s: AskState):
    docs = [d for d, _ in s["hits"]]
    msg = (ASK_PROMPT | get_llm()).invoke({"context": format_context(docs), "question": s["question"]})
    answer = msg.content.strip()
    if "can't find this in the provided regulations" in answer.lower():
        return {"answer": REFUSAL, "sources": [], "abstained": True}
    return {"answer": answer, "sources": to_sources(docs), "abstained": False}


def abstain(s: AskState):
    return {"answer": REFUSAL, "sources": [], "abstained": True}


def build_ask_graph():
    g = StateGraph(AskState)
    for name, fn in [("retrieve", retrieve), ("check_relevance", check_relevance),
                     ("generate_answer", generate_answer), ("abstain", abstain)]:
        g.add_node(name, fn)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "check_relevance")
    g.add_conditional_edges("check_relevance", lambda s: "generate_answer" if s["relevant"] else "abstain")
    g.add_edge("generate_answer", END)
    g.add_edge("abstain", END)
    return g.compile()


# ---------- report_graph: retrieve (one query per topic) -> generate_report -> END ----------

class ReportState(TypedDict, total=False):
    plan: dict
    docs: list
    answer: str
    sources: list
    abstained: bool


def plan_text(plan):
    extras = plan.get("extras") or {}
    rows = [("City", plan.get("city")), ("Use", plan.get("use")), ("Plot area (sq m)", plan.get("plot_area")),
            ("Road width (m)", plan.get("road_width")), ("Floors", plan.get("floors")),
            ("Building height (m)", plan.get("height"))]
    rows += [(k.replace("_", " ").capitalize(), v) for k, v in extras.items()]
    return "\n".join(f"- {k}: {_val(v)}" for k, v in rows)


def retrieve_topics(s: ReportState):
    plan = s["plan"]
    fields = {f: _val(plan.get(f)) for f in ["use", "plot_area", "road_width", "floors", "height"]}
    docs, seen = [], set()
    for query in TOPICS.values():
        for d, _ in search(query.format(**fields), plan["city"], 3):
            key = (d.metadata["city"], d.metadata["page"], d.page_content[:60])
            if key not in seen:
                seen.add(key)
                docs.append(d)
    return {"docs": docs}


def generate_report(s: ReportState):
    docs = s["docs"]
    msg = (REPORT_PROMPT | get_llm()).invoke({"plan": plan_text(s["plan"]), "context": format_context(docs)})
    return {"answer": msg.content.strip() + "\n\n" + DISCLAIMER, "sources": to_sources(docs), "abstained": False}


def build_report_graph():
    g = StateGraph(ReportState)
    g.add_node("retrieve", retrieve_topics)
    g.add_node("generate_report", generate_report)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "generate_report")
    g.add_edge("generate_report", END)
    return g.compile()


# ---------- entry points ----------

@lru_cache(maxsize=1)
def get_graphs():
    load_index()  # fail early if the index is missing
    return build_ask_graph(), build_report_graph()


def _clean(out):
    return {"answer": out["answer"], "sources": out["sources"], "abstained": out["abstained"]}


def run_ask(question, city="All", k=5):
    ask_graph, _ = get_graphs()
    return _clean(ask_graph.invoke({"question": question, "city": city, "k": k}))


def run_report(plan):
    _, report_graph = get_graphs()
    return _clean(report_graph.invoke({"plan": plan}))
