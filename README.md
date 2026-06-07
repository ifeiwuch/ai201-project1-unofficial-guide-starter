# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

     My domain is "Finding and joining clubs at Brown University". This knowledge is valuable because it contains both official statistics and guidelines, as well as firsthand expereinces from clubs. Additionaly, this information is hard to find through official channels because they don't detail the application processes, club culture, or experience.

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Type | URL or file path |
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

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

Preprocessing: Before chunking, I needed to manually remove some headers and advertisements when the cleaning failed. For the activities list, I had to manually copy and paste all the clubs into a text file, as the ingest() function couldn't recognize the text because the information was in Javascript.

**Chunk size: 600**

**Overlap: 50**

**Why these choices fit your documents: The chunk size of 600 with overlap of 50 will allow for context of large paragraphs of articles to be maintained. For the activities list, however, I used a different chunking strategy based on when an email appears, since that was the only file that was manually extracted. These smaller chunks work for the activities list because it allows the chunks to be separated by club, rather than having 30 clubs in one chunk**

**Final chunk count: 539**

### Sample Chunks

| # | Source document | Chunk text (truncated) |
|---|-----------------|------------------------|
| 1 | Category Breakdown | "...There are currently 8 Campus Services & Events clubs on campus. ...There are currently 4 Comedy & Improv groups on campus..." |
| 2 | Club culture | "...Model UN accepts all students who are interested, but Gibbs says that the club is trying to make the travel team more 'competitive'..." |
| 3 | Pre-Professional Club Selectivity | "...Rathier, who is also a computer science teaching assistant, recalled several first-year students approaching him to network about internships..." |
| 4 | Student Activities List | "Japanese Cultural Association — jca@brown.edu" |
| 5 | Overview / FAQ | "Brown Muslim Students Association (BMSA). Supports Muslim students with religious, cultural, and social programming, including Iftar dinners, Eid celebrations..." |

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used: all-MiniLM-L6-v2 via sentence-transformers. I used this embedding model because it runs fast and locally with no API cost. The embeddings work well for short, paragraph-sized chunks.**

**Production tradeoff reflection: If I were deploying this for real users and cost wasn't a constraint, I would weigh accuracy on domain-specific text and context length the most. all-MiniLM-L6-v2 has a lower token limit, so Brown-specific terms and longer passages aren't always captured ideally. I would consider a larger or API-hosted model for better accuracy on domain text and a longer context window, which would likeley result in a higher latency and loss of the ability to run fully offline.**

---

## Retrieval Test Results

Each query was embedded with all-MiniLM-L6-v2 and run against ChromaDB (cosine distance, lower = more similar). Top 3 chunks shown.

**Query 1: "activities fair"**
- d=0.340 — Activities Fair Experience: "Student Activities Fair welcomes first-years with music, treats and pirate games..."
- d=0.522 — Student Activities List: "SoBear Activities Club — sobear@brown.edu"
- d=0.594 — Activities Fair Experience: "...The Activities Fair also presented an opportunity..."

*Why relevant:* The top result is the dedicated article about the Student Activities Fair, exactly the event the query is about, and it leads by a wide margin (0.34 vs 0.52). The third chunk is also from the same article, so the answer is well covered.

**Query 2: "How selective are pre-professional clubs?"**
- d=0.387 — Overview / FAQ: "...Academic & Professional Clubs..."
- d=0.427 — Application Process: "...all student groups at Brown are open to everyone. Many clubs require an application process..."
- d=0.429 — HerCampus Guide: "...Joining clubs/organizations is a valuable..."

*Why relevant:* All three are under 0.5 and speak directly to selectivity and applications — the Application Process chunk in particular explains that many clubs require an application and make cuts, which is the core of the question.

**Query 3: "Is there an Alexander Hamilton club at Brown?"**
- d=0.338 — Student Activities List: "Alexander Hamilton Society — AHSBrown@brown.edu"
- d=0.395 — Student Activities List: "Coffee Club, Brown — browncoffeeclub@brown.edu"
- d=0.412 — Student Activities List: "Chess Club, Brown University — brownchessclub@brown.edu"

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction: My system prompt tells the model to answer using ONLY the numbered context passages provided, with no outside knowledge; if the answer isn't in the context, it must reply with exactly "I don't know based on the provided sources."; it must cite the passages it uses with bracketed numbers like [1]; and it must not invent club names, numbers, or facts. On top of the prompt, I enforce grounding structurally: I run generation at temperature 0, and before calling the model I apply a relevance gate that drops any retrieved chunk with a cosine distance above 0.75. If no chunk passes the gate, the model is never called at all and the system returns the refusal — so it can only answer when grounded context actually exists.**

**How source attribution is surfaced in the response: Attribution is generated programmatically, not parsed from the model's text. After retrieval, format_sources() builds the source list (document name + URL, deduplicated) directly from the chunks that were retrieved, so every answer ends with a "Sources" list of the documents it drew from. The output format is [answer + source list], and the answer also contains inline [n] citations that map to the numbered context passages.**

---

## Example Responses

**Example 1 — "How many social action groups are there?"**
> There are currently 30 Social Action student groups at Brown [1].
>
> Sources:
> - Category Breakdown — https://www.brownucs.org/category-breakdown
> - HerCampus Guide — https://www.hercampus.com/school/brown/a-guide-to-clubs-at-brown-two-tips-for-success/

**Example 2 — "Is there an Alexander Hamilton club at Brown?"**
> Yes, there is an Alexander Hamilton Society at Brown University, and they can be contacted at AHSBrown@brown.edu [1].
>
> Sources:
> - Student Activities List — https://studentactivities.brown.edu/student-groups/undergraduate-student-groups

**Out-of-scope query — "What is the capital of France?"**
> I don't know based on the provided sources.

(No sources are returned. No retrieved chunk passed the 0.75 relevance gate, so the model was never called.)

---

## Query Interface

The interface is a Gradio web app (`app.py`).

- **Input field:** a textbox where the user types a question about Brown clubs.
- **Output field:** a Markdown panel showing the generated answer followed by a **Sources** list of clickable document links (or a refusal with no sources if nothing relevant is found).

**Sample interaction transcript:**
> **Input:** Is there an event where I can find clubs?
>
> **Output:** Yes, there are events where you can find clubs, such as the Club Fair [1] and the Activities Fair [4, 5], which can help you explore and discover various clubs at Brown University.
>
> **Sources**
> - Reddit: Club Recommendations
> - Overview / FAQ
> - HerCampus Guide

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | Is BIG a competitive club? | Yes, there are many applicants | BIG saw a record number of applicants this year; noted that "competitive" isn't stated word-for-word | Relevant | Partially accurate |
| 2 | How many social action groups are there? | There are currently 30 Social Action student groups at Brown | "There are currently 30 Social Action student groups at Brown" | Relevant | Accurate |
| 3 | Is there an event where I can find clubs? | The activity fair | Yes — the Club Fair / Activities Fair | Relevant | Accurate |
| 4 | How selective are pre-professional clubs? | Finance and consulting pre-professional clubs are extremely competitive with hundreds of applicants each semester | They are competitive and selective, with application processes and cuts; used BIG's high application volume as an example | Relevant | Partially accurate |
| 5 | Is there an Alexander Hamilton club at Brown? | Yes, Brown has the Alexander Hamilton Society | "Yes, there is an Alexander Hamilton Society at Brown … AHSBrown@brown.edu" | Relevant | Accurate |

**Retrieval quality:** Relevant — for all 5 questions, the top results were under 0.5 distance and contained a chunk with the answer.
**Response accuracy:** Accurate for Q2, Q3, Q5, but partially accurate for Q1 and Q4 (the answer was correct and grounded but more general than the expected answer).

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed: "What are all the a cappella clubs at Brown?"**

**What the system returned: The model identified only one a cappella club by name ("The Intergalactic Community of A Cappella at Brown University") and expressed uncertainty about whether The Jabberwocks was even a separate club, even though multiple a cappella groups exist at Brown.**

**Root cause (tied to a specific pipeline stage): This was a retrieval problem caused by a vocabulary mismatch between the query and the source documents. Most of Brown's a cappella groups do not include the word "a cappella" anywhere in their club name. Since the Student Activities list is just bare "club name + email" pairs with no descriptions, the embeddings for those chunks don't connect to any concept of a cappella music.**

**What you would change to fix it: I would use a larger, more robust embedding model that can capture context better. Additionally, I would include a source document with the descriptions of each club.**

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation: planning.md helped me think about which source documents I should include in the RAG. This allowed me to get a more diverse array of sources.**

**One way your implementation diverged from the spec, and why: In my planning, I thought I would automate the process of extracting and cleaning the raw text for every document. As I went through the project, I realised it would just be easier if I manually cleaned some of the documents.**

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI: I asked claude to create a new cleaining function or implement it in a current function, that removes anything that isn't the substantive to the system. Remove: HTML tags, navigation menus, cookie banners, ads, footers, repeated site headers, "Read more" links, share buttons, comment counts, and any boilerplate that appears on every page.*
- *What it produced: It produced multiple cleaning functions within ingest.py that removed various types of unsubstantive information.*
- *What I changed or overrode: There was still some leftover noise in the documents that I needed to manually remove.*

**Instance 2**

- *What I gave the AI: After the retrieve() function was implemented, run 3 of my evaluation questions against the ChromaDB collection and check the distance. I told it to raise flag if any distance was above 0.5*
- *What it produced: For my "Is there an Alexander Hamilton club?" question, none of the top results even contained "Alexander Hamilton.*
- *What I changed or overrode: I prompted Claude to run a seperate chunking strategy (separating each club as a chunk) only for the activities list file.*