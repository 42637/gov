import logging
import re
import sys
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Ensure Windows stdout supports UTF-8 characters without charmap errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .config import get_settings
from .rag.loader import RagStore
from .rag.retriever import Retriever
from .schemas import AskRequest, AskResponse, Answer, AnswerSection, Source, RagChunk
from .services.gemini import GeminiService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
store = RagStore(settings.rag_path())


def sources_from(results):
    found, seen = [], set()
    for result in results:
        meta = result.metadata or {}
        title = meta.get("scheme_name") or meta.get("title") or meta.get("name")
        if not title:
            match = re.search(r'scheme_name:\s*["“]?([^"\n”]+)', result.text, re.IGNORECASE)
            if not match:
                match = re.search(r'Scheme Name:\s*([^\n\r]+)', result.text, re.IGNORECASE)
            title = match.group(1).strip(' "\'') if match else "Scheme information"

        url = meta.get("url") or meta.get("source_url") or meta.get("source")
        if url == "myscheme.gov.in" and meta.get("slug"):
            url = f"https://www.myscheme.gov.in/schemes/{meta['slug']}"

        key = (title, str(url) if url else "")
        if key not in seen:
            seen.add(key)
            found.append(Source(title=title, url=str(url) if url and str(url).startswith("http") else None))
    return found


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Loading RAG store from: %s", settings.rag_path())
        store.load()
        app.state.ready, app.state.error = True, None
        logger.info("RAG store loaded successfully (%d chunks)", len(store.chunks))
    except Exception as exc:
        logger.error("Failed to load RAG store: %s", exc)
        logger.error(traceback.format_exc())
        app.state.ready, app.state.error = False, str(exc)
    yield


app = FastAPI(title="Indian Government Schemes Assistant", lifespan=lifespan)
app.state.ready = False
app.state.error = None

# Parse and clean allowed frontend origins
_origins = set()
if settings.frontend_origin:
    for o in settings.frontend_origin.split(","):
        cleaned = o.strip().rstrip("/")
        if cleaned:
            _origins.add(cleaned)
_origins.update([
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:3000",
])
_allowed_origins = list(_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "service": "Indian Government Schemes Assistant API",
        "status": "online",
        "health": "/api/health",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    is_ready = getattr(app.state, "ready", False)
    error = getattr(app.state, "error", None)
    return {
        "status": "ready" if is_ready else "unavailable",
        "rag_ready": is_ready,
        "gemini_configured": bool(settings.gemini_api_key),
        "error": error if not is_ready else None,
    }


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(422, "Please enter a question.")
    is_ready = getattr(app.state, "ready", False)
    error = getattr(app.state, "error", None)
    if not is_ready:
        logger.error("RAG store not ready. Error: %s", error)
        raise HTTPException(
            503, f"The scheme knowledge base is currently unavailable. {error or ''}".strip()
        )

    # Step 1: Retrieve relevant chunks from local RAG model
    try:
        results = Retriever(store).search(question, settings.top_k)
    except Exception as exc:
        logger.error("RAG retrieval failed: %s", exc)
        logger.error(traceback.format_exc())
        raise HTTPException(503, "Failed to search the knowledge base. Please try again.")

    # Step 2: FIRST, PRINT the retrieved data from the RAG model to console (safe ASCII)
    try:
        print("\n" + "=" * 80)
        print(f"[RAG MODEL] Query: \"{question}\"")
        print(f"[RAG MODEL] Fetched {len(results)} chunks from local RAG store:")
        for idx, r in enumerate(results, 1):
            meta = r.metadata or {}
            scheme_title = meta.get("scheme_name") or "Scheme"
            scheme_url = meta.get("url") or "N/A"
            clean_title = scheme_title.encode("ascii", errors="replace").decode("ascii")
            print(f"  [{idx}] Scheme: {clean_title} | Score: {r.score:.4f} | URL: {scheme_url}")
            snippet = r.text[:220].replace("\n", " ").strip()
            clean_snippet = snippet.encode("ascii", errors="replace").decode("ascii")
            print(f"      Snippet: {clean_snippet}...")
        print("=" * 80 + "\n", flush=True)
    except Exception as log_err:
        logger.warning("Console print error: %s", log_err)

    # Step 3: Build rich context with scheme headers for Gemini
    context_chunks = []
    for i, r in enumerate(results):
        meta = r.metadata or {}
        scheme = meta.get("scheme_name") or "Scheme"
        url = meta.get("url") or ""
        cat = meta.get("category") or ""
        header = f"[Evidence {i + 1} | Scheme: {scheme}"
        if cat:
            header += f" | Category: {cat}"
        if url:
            header += f" | Official URL: {url}"
        header += "]"
        context_chunks.append(f"{header}\n{r.text[:3000]}")
    context = "\n\n".join(context_chunks)[:12000]

    # Build retrieved RAG items for frontend and response
    retrieved_rag_data = [
        RagChunk(
            scheme_name=str(r.metadata.get("scheme_name") or "Scheme information"),
            url=r.metadata.get("url"),
            score=round(float(r.score), 4),
            snippet=r.text[:300].strip() + ("..." if len(r.text) > 300 else ""),
        )
        for r in results
    ]

    source_list = sources_from(results)
    names = list(
        dict.fromkeys(
            source.title for source in source_list if source.title != "Scheme information"
        )
    )

    # Step 4: Classify the question via Gemini
    gemini = GeminiService(settings.gemini_api_key, settings.gemini_model)
    try:
        classification = gemini.classify(question, context)
        logger.info("Classification result: %s", classification)
    except Exception as exc:
        logger.error("Gemini classification failed: %s", exc)
        logger.error(traceback.format_exc())
        raise HTTPException(
            503,
            "AI verification is unavailable. Check the Gemini API configuration and try again.",
        )

    related = bool(classification.get("is_scheme_related"))
    sufficient = bool(classification.get("evidence_sufficient"))

    if not related:
        return AskResponse(
            status="out_of_scope",
            is_scheme_related=False,
            evidence_sufficient=sufficient,
            reason=classification.get("reason")
            or "This question is outside Indian Government Schemes.",
            sources=[],
            scheme_names=[],
            retrieved_rag_data=retrieved_rag_data,
        )

    if not sufficient:
        return AskResponse(
            status="insufficient_evidence",
            is_scheme_related=True,
            evidence_sufficient=False,
            reason=classification.get("reason")
            or "The knowledge base does not contain enough supporting information.",
            sources=source_list,
            scheme_names=names,
            retrieved_rag_data=retrieved_rag_data,
        )

    # Step 5: Generate answer via Gemini grounded in the RAG evidence
    try:
        generated = gemini.answer(question, context)
        logger.info("Answer generated successfully for: %.80s", question)
        answer = Answer(
            summary=str(generated["summary"]),
            sections=[
                AnswerSection(**section)
                for section in generated.get("sections", [])
                if section.get("heading") and section.get("content")
            ],
        )
    except Exception as exc:
        logger.error("Gemini answer generation failed: %s", exc)
        logger.error(traceback.format_exc())
        raise HTTPException(503, "AI answer generation is unavailable. Please try again.")

    return AskResponse(
        status="success",
        is_scheme_related=True,
        evidence_sufficient=True,
        answer=answer,
        sources=source_list,
        scheme_names=names,
        retrieved_rag_data=retrieved_rag_data,
    )
