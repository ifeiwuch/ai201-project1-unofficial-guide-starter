# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->
My domain is "Finding and joining clubs at Brown University". This knowledge is valuable because it contains both official statistics and guidelines, as well as firsthand expereinces from clubs. Additionaly, this information is hard to find through official channels because they don't detail the application processes, club culture, or experience. 

---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 | Student Activities List | A list of all the current student groups at Brown | https://studentactivities.brown.edu/student-groups/undergraduate-student-groups |
| 2 | Category Breakdown | A simple breakdown of the activity and spending categories of clubs | https://www.brownucs.org/category-breakdown |
| 3 | Reddit: Club Recommendations | Students recommending specific clubs and extracurriculars to join at Brown | https://www.reddit.com/r/BrownU/comments/14dig65/any_ideas_for_clubs_to_join_or_extracurriculars/ |
| 4 | Club culture | A BDH article detailing the club culture at Brown | https://www.browndailyherald.com/article/2024/10/cutthroat-or-collaborative-is-browns-club-culture-competitive |
| 5 | Most Prestigious Clubs | Breifly describes "prestigious" clubs on campus | https://www.collegevine.com/faq/154640/what-are-the-most-prestigious-student-organizations-at-brown-university |
| 6 | HerCampus Guide | A guide on how to approach joining clubs as a woman | https://www.hercampus.com/school/brown/a-guide-to-clubs-at-brown-two-tips-for-success/ |
| 7 | Overview  | Provides an overview of clubs at brown with FAQ | https://admissionsight.com/brown-university-clubs/ |
| 8 | Application Process | Provides information of the application processes for some clubs | https://www.browndailyherald.com/article/2020/01/schmidt-21-university-student-organizations-have-room-to-be-more-inclusive |
| 9 | Pre-Professional Club Selectivity | BDH article on the influx of first-year applicants to pre-professional clubs| https://www.browndailyherald.com/article/2025/10/pre-professional-club-leaders-note-influx-of-eager-first-year-applicants |
| 10 | Activities Fair Experience | Description of how clubs present themselves and recruit new members at the activity fair | https://www.browndailyherald.com/article/2025/09/student-activities-fair-welcomes-first-years-with-music-treats-and-pirate-games |

---

## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size: 600** 

**Overlap: 50**

**Reasoning:** I'll be using recursive chunking due to the varying structures of the documents. The chunk size of 600 with overlap of 50 will allow for context of large paragraphs of articles to be maintained.

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model: all-MiniLM-L6-v2 via sentence-transformers**

**Top-k: 5**

**Production tradeoff reflection: If I was deploying this to real users, I would weigh accuracy on domain-specific text and context length the most. This is because the guide must retrive the correct information from official documentation, and it must be able to asess the context from various articles and forums in order to have the most accurate response.**

---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | Is BIG a competitive club? | Yes, there are many applicants |
| 2 | How many social action groups are there? | There are currently 30 Social Action student groups at Brown. |
| 3 | Is there an event where I can find clubs? | The activity fair|
| 4 | How selective are pre-professional clubs? | The finance and consulting pre-professional clubs are extremely competitive with hundreds of applicants each semester |
| 5 | Is there an Alexander Hamilton club at Brown| Yes, Brown has the Alexander Hamilton Society |

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1. The application process and club experienecs are only available for a few clubs, so retrieval may be vauge, or completely inacurrate due to the inconsistent documents. 

2. Some information is displayed through images rather than text, so it may not be retrieved properly. 

3. There is conflicting information between the documents (e.g. total number of clubs), which may lead to false retrieval due to the outdated information.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->
---
config:
  layout: elk
---
graph LR
    A[Document Ingestion] --> B[Chunking]
    B --> C[Embedding<br/>all-MiniLM-L6-v2]
    C --> D[Vector Store<br/>ChromaDB]
    D --> E[Retrieval]
    E --> F[Generation<br/>Groq]

![Pipeline Diagram](image.png)
---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

**Milestone 3 — Ingestion and chunking:**

I'll ask claude to implement a script that laods my documents, cleans them, and produces chunks matching my specified chunk size. Since some of them are websites, I'll also ask claude to convert unstructured text from a forum/website into a plain text file for precessing. After the text is processed, I'll ask claude to clean the files from advertisements, banners, and so on. To verify, I'll ask it to count the total amount of chunks, and see if it adds up to a reasonable amount. 

**Milestone 4 — Embedding and retrieval:**

I'll ask claude to read planning.md and focus on the Retrieval Approach section and Architecture diagram. Then, I'll tell it to implement an embed_and_store() function that takes a list of chunks from the ingestion/chunking pipeline, embeds each chunk using all-MiniLM-L6-v2, stores each chunk in ChromaDB with source metadata, using all-MiniLM-L6-v2 via sentence-transformers for embedding and ChromaDB as the vector store. Additionally, I need to make sure Claude uses the existing project structure and make sure the code integrates with whatever ingestion/chunking code already exists in this repo. To verify, I'll tell claude to ask ChromaDB for a known term (e.g. "activities fair") and confirm the correct chunks come back.

**Milestone 5 — Generation and interface:**

First, I'll tell claude to read the pipeline diagram to use the given interface template to create an interface. For the generation aspect, I'll emphasize that all generated answers are retrieved from context only, with the source attribute. Furthermore, I'll give claude the output format of the generation. Before it runs any code, I'll ask it to double-check if the system explicityly enforces grounding. To verify I'll run my test questions.

Groq initialization steps:
use Groq's  default llama-3.3-70b-versatile
itialize it with from groq import Groq and my GROQ_API_KEY from .env

Minimal working interface example:
import gradio as gr
from query import ask  # or wherever your end-to-end function lives

def handle_query(question):
    result = ask(question)
    sources = "\n".join(f"• {s}" for s in result["sources"])
    return result["answer"], sources

with gr.Blocks() as demo:
    inp = gr.Textbox(label="Your question")
    btn = gr.Button("Ask")
    answer = gr.Textbox(label="Answer", lines=8)
    sources = gr.Textbox(label="Retrieved from", lines=4)
    btn.click(handle_query, inputs=inp, outputs=[answer, sources])
    inp.submit(handle_query, inputs=inp, outputs=[answer, sources])

demo.launch()
