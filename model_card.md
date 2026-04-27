# Model Card — PawPal+ AI

---

## Model Overview

| Field | Details |
|---|---|
| **Project name** | PawPal+ AI |
| **Base model** | Google Gemini 2.0 Flash (`gemini-2.0-flash`) |
| **Embedding model** | Google `gemini-embedding-001` |
| **Framework** | LangChain (`ChatGoogleGenerativeAI`, `ChatPromptTemplate`, `StrOutputParser`) |
| **RAG store** | Chroma (persistent, local) |
| **Knowledge sources** | Humane Fort Wayne Dog-Book.pdf, Cat-Book.pdf |
| **Task** | Pet care schedule explanation, per-pet recommendation generation |
| **Output format** | Structured JSON — `reasoning`, `explanation`, `recommendations` |

---

## Intended Use

PawPal+ AI is designed to help pet owners organize daily care routines. The AI layer explains why a schedule was built the way it was, retrieves relevant guidance from a pet care knowledge base, and surfaces actionable recommendations grounded in that source material.

**Intended users:** Individual pet owners managing daily care for dogs and/or cats.

**Out-of-scope uses:** Medical diagnosis, emergency veterinary guidance, exotic or non-standard species care, multi-day planning beyond a single daily window.

---

## AI Collaboration

### One instance where AI assistance was helpful

When designing the per-pet RAG query strategy, I asked Claude to suggest an approach that would capture different angles of a pet's care needs from a single retrieval pass. It proposed a four-query template:

1. A species + task care guide query
2. A "how to properly do X for a [species]" query
3. A safety and tips query
4. A health and behavior query

This multi-query approach was directly implemented and meaningfully improved passage variety — a single query often returned only one topic, while four queries covered feeding, exercise, health, and behavior in the same retrieval pass.

### One instance where AI assistance was flawed

Early in development, Claude generated RAG setup code that included LangSmith tracing initialization:

```python
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.tracers import LangChainTracer

tracer = LangChainTracer(project_name="pawpal-plus")
```

This added an implicit dependency on a `LANGCHAIN_API_KEY` environment variable that was never mentioned in the suggestion. The code caused a silent startup failure in environments without the key, and the tracing feature added no value to the core system. The suggestion was technically valid LangChain usage but wrong for the project's simplicity and deployment requirements — it had to be removed entirely.

---

## Known Biases and Limitations

**Knowledge source bias**
All retrieved passages come exclusively from the Humane Fort Wayne Pet Care Guide. This single-organization source may reflect regional practices, specific breed assumptions, or omit guidance for less common health conditions. The model's recommendations are constrained to what the guide covers.

**Species coverage**
The RAG pipeline filters by species (`dog` or `cat`). Owners with other pets receive no retrieved context and the AI generates recommendations from general training knowledge only, which may be less reliable.

**No medical knowledge validation**
The system does not validate whether recommendations are appropriate for a specific pet's health status, age-related conditions, or medication interactions. It should never replace professional veterinary advice.

**Guardrail limitations**
The rule-based evaluator catches structural problems (skipped HIGH tasks, conflicts, utilisation extremes) but cannot detect contextually inappropriate schedules — for example, a walk scheduled during extreme heat, or feeding immediately before surgery.

**LLM output variability**
Gemini 2.0 Flash responses are non-deterministic. The same schedule may produce slightly different `reasoning` or `recommendations` text across runs. The `explanation` and `recommendations` fields are structurally validated (JSON parsing) but their content quality is not automatically verified.

---

## Testing Results

| Test | Result | Notes |
|---|---|---|
| Normal balanced day | ✅ PASS | All tasks scheduled, no issues |
| Overloaded window (HIGH tasks skipped) | ✅ PASS | Guardrail correctly flags failure |
| Conflicting time preferences | ✅ PASS | Greedy algorithm resolves cleanly |
| Empty schedule | ✅ PASS | Trivially valid |
| Low utilisation warning | ✅ PASS | Warning issued, not a hard failure |
| Determinism (same inputs → same output) | ✅ PASS | Scheduling is fully reproducible |
| RAG retrieval (dog walk + feeding) | ✅ PASS | Skipped if no key/PDFs present |
| Multi-pet scheduling | ✅ PASS | All pets' tasks considered together |

**Overall: 8/8 tests passed.**

The most significant reliability issue discovered during testing was a silent RAG failure caused by punctuation in query tokens. The relevance scoring function split text on whitespace without normalizing punctuation, meaning `"walk,"` never matched index token `"walk"`. The threshold became unreachable, returning zero passages with no error raised. This was fixed by applying a regex token normalizer (`re.sub(r"[^\w\s]", "", text)`) before splitting.

A separate bug was found in the test harness itself: the RAG test printed each passage using `p[:120]` (slicing a dict), which raises a `TypeError`. Since `retrieve_for_pet` returns `List[Dict]`, the correct access is `p['text'][:120]`. Both bugs are fixed in the current codebase.

---

## Ethical Considerations

**Risk of over-reliance**
Pet owners may treat AI recommendations as authoritative medical guidance. The prompt instructs the model to stay grounded in the retrieved care guide passages and acknowledge gaps, but this guardrail is soft — the model can still generate confident-sounding text beyond what the guide covers.

**Mitigation:** The UI should display a clear disclaimer that PawPal+ is an organizational tool, not a veterinary service. Recommendations should be framed as suggestions based on the care guide, not professional advice.

**Data privacy**
The system is entirely local — no pet data, owner data, or schedule information is sent to any external server except the Google Gemini API (for embedding and inference calls). Users should be aware that schedule context (pet names, ages, task descriptions) is included in API calls to Google.

**Misuse potential**
The system could theoretically be adapted to generate care schedules for animals in commercial or agricultural settings where individual welfare is less prioritized. The current design is scoped to companion pets with named owners and does not include batch processing or anonymized profiles.

---

## Portfolio Reflection

This project demonstrates my ability to design and build a full-stack AI system from the ground up — not just wire together existing tools, but make principled architectural decisions about where AI adds value and where deterministic logic is more appropriate. The scheduling core is intentionally rule-based and fully testable; the AI layer adds explanation and context without taking over the system's core logic. This separation — keeping the "hard" decisions in code and the "soft" explanations in the model — is the kind of design judgment that distinguishes AI engineers from prompt engineers. The semantic RAG pipeline, the per-pet retrieval isolation, and the hybrid reranking strategy all reflect genuine engineering choices made after testing simpler approaches that didn't work well enough.
