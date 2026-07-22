from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from lexrag.llm.groq_client import stream_answer
from lexrag.retrieval.mapping import load_mapping
from lexrag.retrieval.retriever import Retriever, RetrievedSection

app = FastAPI(title="LexRAG — IPC/BNS research assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your deployed frontend origin before production use
    allow_methods=["*"],
    allow_headers=["*"],
)

_retriever = Retriever()
_concordance = load_mapping()

_STATIC_DIR = Path(__file__).resolve().parent / "static"


class ChatRequest(BaseModel):
    query: str


def _section_to_dict(s: RetrievedSection) -> dict:
    return {
        "act": s.act,
        "section_no": s.section_no,
        "section_title": s.section_title,
        "chapter_no": s.chapter_no,
        "chapter_title": s.chapter_title,
        "score": s.score,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/sections/{act}/{section_no}")
def get_section(act: str, section_no: str) -> dict:
    section = _retriever.get_section(act.upper(), section_no)
    if not section:
        raise HTTPException(status_code=404, detail=f"{act.upper()} Section {section_no} not found")
    return {**_section_to_dict(section), "text": section.text}


@app.get("/mapping/{act}/{section_no}")
def get_mapping(act: str, section_no: str) -> dict:
    act = act.upper()
    entries = _concordance.bns_for_ipc(section_no) if act == "IPC" else _concordance.ipc_for_bns(section_no)
    return {
        "act": act,
        "section_no": section_no,
        "mappings": [
            {
                "ipc_section": e.ipc_section,
                "bns_section": e.bns_section,
                "status": e.status,
                "notes": e.notes,
            }
            for e in entries
        ],
    }


@app.post("/chat")
def chat(req: ChatRequest):
    result = _retriever.retrieve(req.query)

    def event_stream():
        yield {
            "event": "sections",
            "data": json.dumps(
                {
                    "mode": result.mode,
                    "sections": [_section_to_dict(s) for s in result.sections],
                    "notes": result.mapping_notes,
                }
            ),
        }
        try:
            for token in stream_answer(req.query, result):
                yield {"event": "token", "data": token}
        except Exception as exc:  # noqa: BLE001 — surface to the client instead of dropping the connection
            yield {"event": "error", "data": str(exc)}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_stream())


if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(_STATIC_DIR / "index.html"))
