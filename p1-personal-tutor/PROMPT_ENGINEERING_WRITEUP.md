# Prompt Engineering for a Finance Learning Tutor
**P1 — Personal Learning Tutor | May 2026**

---

I built P1 as a conversational finance tutor that teaches through Socratic dialogue — it asks questions instead of just explaining things. The prompt is the core of it: everything about how the tutor behaves, how it structures a lesson, how it adapts to the learner is in the system prompt.

This documents what I tested, what broke, and what I fixed.

---

## The experiment

I ran two back-to-back tests:

1. **Pattern comparison** — four prompting strategies on the same question: "explain gross margin"
2. **Teaching quality audit** — P1's actual system prompt across five finance topics, graded on whether it felt like a teacher or a chatbot

---

## Test 1: four ways to prompt the same question

The four strategies I tested, in order from simplest to most complex:

| Pattern | System prompt |
|---|---|
| Zero-shot | "You are a helpful assistant." |
| Few-shot (3 examples) | Three worked examples in the user turn |
| CoT + role prompting | Finance professor persona + 5 numbered output steps |
| P1 system prompt | Full identity, pedagogy rules, learner profile |

Full outputs are in [prompt_patterns_log.md](prompt_patterns_log.md).

---

### What actually happened

**Zero-shot** gave a textbook explanation — technically correct, formula included, worked example at the end. Completely fine if you want an encyclopedia entry. It never once asked me anything, which is the whole point of a tutor.

**Few-shot** gave the shortest response of the four, which surprised me. I'd written crisp 2-3 sentence examples to demonstrate the format, and the model learned "this length = correct" and matched it. That's the thing about few-shot: you're teaching the model what the output *looks like* just as much as what it *says*. My examples were brief, so the output was brief. Useful when you want consistent structure (JSON, SQL, tables) — not when you want depth.

**CoT with role prompting** was clearly the best. Giving it a persona ("finance professor, 20 years, MBA students") shifted it toward higher-quality explanations, and the five numbered steps acted as a hard output template — problem first, plain English definition, worked example, common mistake, diagnostic question. It followed all five in order. The diagnostic question it generated was actually good: compute COGS given gross margin % and revenue, not just "does this make sense to you?"

**P1's system prompt** was the most personalized. It picked up the learner's industrial engineering background and used a process efficiency analogy for gross margin, which was genuinely useful. But it closed with: *"Want to see how this changes if we adjust COGS or revenue?"* — which is a menu option, not a question. A student who doesn't realize they need that will just say no.

---

### The thing I actually learned

Role prompting tells the model *who* to be. Chain-of-thought tells it *how* to think. You need both.

P1 had a strong identity — the tutor persona, detailed pedagogy principles, a learner profile — but the pedagogy section was written as prose guidelines. The CoT prompt had numbered output steps. The model treats a numbered list as a template it has to follow; prose principles are more like suggestions. That's why the CoT output was more structurally consistent even though P1's prompt is richer overall.

---

## Test 2: five topics through the actual P1 prompt

I ran the tutor through these in order: gross margin, ROE, DuPont decomposition, time value of money, DCF. Then I ran a second GPT-4o call as an automated evaluator to grade each response and find the line where it stopped feeling like a teacher.

Full results are in [tutor_topic_audit.md](tutor_topic_audit.md).

---

### Two bugs

**Bug 1 — the prompt was leaking into the output.**

DuPont and TVM responses came back looking like this:

```
1. IDENTIFY the concept: DuPont decomposition breaks down ROE into...
2. CHECK learner history: Since you're new to financial statement analysis...
3. Run a one-module mini-lesson:
   - Build Task: Let's take a hypothetical company...
```

The `<explain_mode>` section of my system prompt had six numbered steps. The model read them and produced six numbered steps in the output. It doesn't distinguish between "steps I should reason through internally" and "steps I should write for the user." They look identical in the prompt.

Fix: add one sentence that makes the distinction explicit — *"follow this sequence internally, do not output these as headers or labels."*

**Bug 2 — "want to see how this changes?" is not a retrieval challenge.**

Several topics ended with a passive offer. My pedagogy block says "RETRIEVAL OVER RECOGNITION" but the `<explain_mode>` last step said "OFFER a what-if," which the model treated as a valid alternative. The problem is I never told it what *disqualifies* as retrieval. "Ends with a question" is not the same as "forces the learner to produce an answer."

Fix: replace the vague step with a hard rule — *"close with an open-ended retrieval question the learner must answer from memory. Never substitute a passive offer for a real retrieval challenge."*

---

### Before vs. after — DuPont

**Before:**
```
1. IDENTIFY the concept: DuPont decomposition breaks down ROE into three
   parts: Profit Margin, Asset Turnover, and Financial Leverage...
2. CHECK learner history: Since you're new to financial statement analysis,
   I will assume this concept hasn't appeared in a prior session.
3. Run a one-module mini-lesson:
   - Build Task: Let's take a hypothetical company with the following data...
```

**After:**
> The DuPont decomposition breaks down Return on Equity into three components — profit margin, asset turnover, and financial leverage — so you can trace *which part* of the business is driving the return, not just that the return is high or low. Think of it like a supply chain audit: you're not just measuring throughput, you're finding which node is the bottleneck.
>
> **Can you explain how improving asset turnover would affect ROE, and which industries you'd expect to compete on that lever vs. the others?**

The numbered steps are gone. The analogy is there. The question requires real reasoning.

---

### What the automated evaluator missed

GPT-4o scored every response 5/5 before and after the fix. It was checking surface features — does a question appear? is there a background analogy? — and both were present even in the broken responses. "Ends with a question" isn't the same as "forces retrieval," but my rubric didn't draw that line.

If you're using an LLM to evaluate another LLM's output, the rubric needs to test the thing you actually care about, not a proxy for it. A better criterion here: *can the closing question be answered yes/no? If yes, it's not a retrieval challenge.*

---

## What's still not fixed

A few things I identified but didn't address in this session:

**No problem-first opening.** Every response still opens with a definition. The pedagogy block says "PROBLEM FIRST" but it's a guideline. A real fix would add a hard constraint: *"your first sentence must name the business decision this concept helps make."*

**DCF is underscaffolded.** It got the shortest response of any topic despite being the most complex. The model seems to allocate depth by topic name length, not conceptual difficulty.

**"Check learner history" is a dead branch.** In a stateless API call there's no session history. That step will always fall through to "no prior session." It'll only be useful once the tutor is passing SQLite profile data into context.

---

## Key takeaways

Numbered steps in a system prompt are output templates, not just instructions. If you don't want them echoed, say so.

Prose principles are aspirational. Explicit constraints are enforced. "RETRIEVAL OVER RECOGNITION" as a label doesn't tell the model what violates it.

Few-shot shapes form as much as content. Design your examples at the depth you want, not just the format.

Role + CoT beats role alone. The identity sets the prior; the numbered steps enforce the reasoning path.

LLM evaluators need rubrics that test the specific thing you care about. "Ends with a question" will pass broken prompts.
