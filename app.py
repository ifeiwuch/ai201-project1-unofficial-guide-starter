"""
app.py — Milestone 5: Query interface (Gradio).

Wires the whole pipeline together for an end user:
    question -> retrieve (ChromaDB) -> generate (Groq, grounded) -> answer+sources

The vector store must already be built (run `python ingest.py` then
`python embed.py` first). Launch with:

    python app.py
"""

from __future__ import annotations

import gradio as gr

from generate import generate, GROQ_MODEL

EXAMPLES = [
    "Is BIG a competitive club?",
    "How many social action groups are there?",
    "Is there an event where I can find clubs?",
    "How selective are pre-professional clubs?",
    "Is there an Alexander Hamilton club at Brown?",
]


def answer_question(query: str) -> str:
    """Run the grounded RAG pipeline and render answer + source list as Markdown."""
    if not query or not query.strip():
        return "Please enter a question."

    result = generate(query.strip())

    md = result["answer"]
    if result["sources"]:
        md += "\n\n**Sources**\n"
        for s in result["sources"]:
            md += f"\n- [{s['source']}]({s['url']})"
    else:
        md += "\n\n_(No grounded sources — answer withheld.)_"
    return md


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="The Unofficial Guide — Brown Clubs") as demo:
        gr.Markdown(
            "# The Unofficial Guide to Brown Clubs\n"
            "Ask about finding and joining clubs at Brown. Answers are grounded "
            "strictly in the retrieved source documents and always list their "
            f"sources.\n\n*Generation model: `{GROQ_MODEL}` (via Groq).*"
        )
        question = gr.Textbox(
            label="Your question",
            placeholder="e.g. How selective are pre-professional clubs?",
            lines=2,
        )
        ask = gr.Button("Ask", variant="primary")
        answer = gr.Markdown(label="Answer")

        ask.click(fn=answer_question, inputs=question, outputs=answer)
        question.submit(fn=answer_question, inputs=question, outputs=answer)
        gr.Examples(examples=EXAMPLES, inputs=question)

    return demo


if __name__ == "__main__":
    build_interface().launch()
