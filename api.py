"""FastAPI wrapper over pipeline.py. Run: uvicorn api:app --port 8000"""
from typing import Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import pipeline

app = FastAPI(title="BylawCheck-Lite")


class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    city: str = "All"          # Delhi | Mumbai | Hyderabad | All
    k: int = Field(5, ge=1, le=10)


class ReportRequest(BaseModel):
    city: str                  # Delhi | Mumbai | Hyderabad
    plot_area: Optional[float] = None
    road_width: Optional[float] = None
    floors: Optional[int] = None
    height: Optional[float] = None
    use: Optional[str] = None
    extras: Dict[str, Optional[Union[str, float]]] = {}   # fsi, front_setback, parking_spaces, notes ...


class Source(BaseModel):
    city: str
    page: int
    snippet: str


class Reply(BaseModel):
    answer: str
    sources: List[Source]
    abstained: bool


def check_city(city, allow_all):
    if city not in ["Delhi", "Mumbai", "Hyderabad"] + (["All"] if allow_all else []):
        raise HTTPException(422, f"Unknown city: {city}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=Reply)
def ask(req: AskRequest):
    check_city(req.city, allow_all=True)
    return pipeline.run_ask(req.question, req.city, req.k)


@app.post("/report", response_model=Reply)
def report(req: ReportRequest):
    check_city(req.city, allow_all=False)
    return pipeline.run_report(req.model_dump())
