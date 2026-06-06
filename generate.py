"""
generate.py — Milestone 5: Grounded generation (Groq).

Pipeline stages implemented here (see planning.md → Architecture):
    Retrieval  ->  Generation (Groq)

What this script does:
    1. retrieve top-k chunks for a question (from embed.py / ChromaDB),
    2. build a prompt = strict system prompt + retrieved context + question,
    3. call the Groq chat API to write an answer grounded in that context,
    4. return [answer + source list], where the source list is built
       programmatically from the retrieved chunks — never parsed from the
       model's text — so attribution is guaranteed.

Grounding is enforced two ways:
    * Structural gate: if no retrieved chunk is relevant enough (distance under
      RELEVANCE_THRESHOLD), the model is NOT called at all — we return a fixed
      "not in the sources" answer with no sources. The model can therefore only
      ever speak when grounded context exists.
    * Prompt instruction: the system prompt forbids outside knowledge and
      requires "I don't know based on the provided sources." when the answer
      isn't in the context, with low temperature for determinism.

Run:
    python generate.py                  # answer the 5 planning.md eval questions
    python generate.py --query "..."    # answer a single question
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from groq import Groq

from embed import retrieve, TOP_K

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# Groq-hosted model (override with GROQ_MODEL in .env if this id changes).
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Cosine distance above which a retrieved chunk is considered irrelevant.
# Calibrated from the Milestone-4 evaluation: correct answers came back at
# ~0.34–0.49, while off-target chunks sat at ~0.8. Anything past this gate is
# treated as "not found" so the model is never asked to answer ungrounded.
RELEVANCE_THRESHOLD = 0.75

REFUSAL = "I don't know based on the provided sources."

SYSTEM_PROMPT = (
    "You are a helpful guide answering questions about finding and joining "
    "clubs at Brown University.\n"
    "Rules:\n"
    "1. Answer using ONLY the numbered context passages provided below. Do not "
    "use any prior or outside knowledge.\n"
    "2. If the answer is not contained in the context, reply with exactly this "
    f"sentence and nothing else: \"{REFUSAL}\"\n"
    "3. Support each claim with bracketed citations like [1] or [2] that refer "
    "to the numbered passages you used.\n"
    "4. Be concise and do not invent club names, numbers, or facts that are not "
    "in the context."
)


# --------------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------------- #

def build_context(chunks: list[dict]) -> str:
    """Render retrieved chunks as a numbered context block for the prompt."""
    blocks = []
    for i, c in enumerate(chunks, 1):
        blocks.append(f"[{i}] (Source: {c['source']})\n{c['text']}")
    return "\n\n".join(blocks)


def format_sources(chunks: list[dict]) -> list[dict]:
    """Build the source list from the chunks actually used — deduplicated by
    (source name, url), order preserved. This is the programmatic guarantee of
    attribution: it is derived from retrieval, not from the model's output."""
    seen: set[tuple[str, str]] = set()
    sources: list[dict] = []
    for c in chunks:
        key = (c["source"], c["url"])
        if key not in seen:
            seen.add(key)
            sources.append({"source": c["source"], "url": c["url"]})
    return sources


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #

_client: Groq | None = None


def get_client() -> Groq:
    """Create (once) the Groq client from GROQ_API_KEY in the environment."""
    global _client
    if _client is None:
        load_dotenv()
        key = os.getenv("GROQ_API_KEY")
        if not key or key == "your_key_here":
            print("GROQ_API_KEY is not set. Copy .env.example to .env and add "
                  "your key from https://console.groq.com", file=sys.stderr)
            sys.exit(1)
        _client = Groq(api_key=key)
    return _client


def generate(query: str, k: int = TOP_K) -> dict:
    """Answer a question grounded strictly in retrieved context.

    Returns a dict: {answer: str, sources: list[{source, url}], grounded: bool}.
    `sources` is always derived from the retrieved chunks (never from the model
    text), so attribution is guaranteed whenever an answer is produced.
    """
    results = retrieve(query, k=k)

    # Structural grounding gate: keep only sufficiently-relevant chunks. If none
    # qualify, refuse WITHOUT calling the model — no context, no answer.
    relevant = [r for r in results if r["distance"] <= RELEVANCE_THRESHOLD]
    if not relevant:
        return {"answer": REFUSAL, "sources": [], "grounded": False}

    context = build_context(relevant)
    user_message = (
        f"Context passages:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer using only the context above, with bracketed citations."
    )

    completion = get_client().chat.completions.create(
        model=GROQ_MODEL,
        temperature=0,  # deterministic, reduces drift from the context
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    answer = completion.choices[0].message.content.strip()

    # If the model refused, there is nothing grounded to attribute.
    if REFUSAL.lower() in answer.lower():
        return {"answer": REFUSAL, "sources": [], "grounded": False}

    return {
        "answer": answer,
        "sources": format_sources(relevant),
        "grounded": True,
    }


def format_response(result: dict) -> str:
    """Render the [answer + source list] output format."""
    out = result["answer"]
    if result["sources"]:
        lines = "\n".join(
            f"- {s['source']} — {s['url']}" for s in result["sources"]
        )
        out += f"\n\nSources:\n{lines}"
    return out


# --------------------------------------------------------------------------- #
# CLI (verification)
# --------------------------------------------------------------------------- #

EVAL_QUESTIONS = [
    "Is BIG a competitive club?",
    "How many social action groups are there?",
    "Is there an event where I can find clubs?",
    "How selective are pre-professional clubs?",
    "Is there an Alexander Hamilton club at Brown?",
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="Grounded generation with Groq.")
    parser.add_argument("--query", help="answer a single question")
    args = parser.parse_args()

    questions = [args.query] if args.query else EVAL_QUESTIONS
    for q in questions:
        print("\n" + "=" * 84)
        print(f"Q: {q}")
        print("-" * 84)
        print(format_response(generate(q)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
