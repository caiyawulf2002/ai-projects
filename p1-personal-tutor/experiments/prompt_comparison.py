"""
Task 1 — Prompt Pattern Comparison
Compares 4 prompting strategies on the same finance topic: "explain gross margin"
Run from repo root: python p1-personal-tutor/experiments/prompt_comparison.py
"""

import os
import sys
import textwrap
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load .env from p1-personal-tutor/
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Import P1's actual system prompt
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.prompts import TUTOR_SYSTEM_PROMPT

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

TOPIC = "explain gross margin"
MODEL = "gpt-4o"

# ─── Prompt Definitions ────────────────────────────────────────────────────────

PROMPTS = {
    "1_zero_shot": {
        "system": "You are a helpful assistant.",
        "user": "Explain gross margin.",
    },
    "2_few_shot": {
        "system": "You are a helpful assistant.",
        "user": textwrap.dedent("""\
            Here are examples of how to explain finance concepts clearly:

            Example 1 — Net income:
            Net income is what's left after a company pays ALL its costs — COGS,
            operating expenses, interest, and taxes. It's the famous "bottom line."

            Example 2 — Revenue:
            Revenue is every dollar that comes in from selling your product or service
            before a single cost is subtracted. It's the top line of the income statement.

            Example 3 — Operating income:
            Operating income (EBIT) is revenue minus COGS and operating expenses,
            but before interest and taxes. It shows how profitable the core business is
            independent of how it's financed.

            Now explain gross margin the same way."""),
    },
    "3_chain_of_thought_role": {
        "system": textwrap.dedent("""\
            You are a finance professor with 20 years of experience teaching MBA students.
            When you explain a concept, you:
            1. Start with the concrete business problem the concept solves
            2. Define it in plain English before any formula
            3. Walk through the formula step-by-step with a real example
            4. Name the one thing a beginner always gets wrong
            5. Close with a diagnostic question to test understanding"""),
        "user": "Explain gross margin.",
    },
    "4_p1_system_prompt": {
        "system": TUTOR_SYSTEM_PROMPT.replace(
            "{learner_profile}",
            textwrap.dedent("""\
                Background: industrial engineer, worked at Walmart on process efficiency,
                built GenAI tools at a supply chain company. Comfortable with systems
                thinking and process flows. New to financial statement analysis.
                Learning style: sees end-to-end first, then digs into details (VARK: A).
                Theory-application score: 2/5 (prefers application first).
                Session cadence: 90-min sessions, 3x per week."""),
        ),
        "user": "Explain gross margin.",
    },
}

# ─── Runner ───────────────────────────────────────────────────────────────────

def run_prompt(name: str, system: str, user: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=600,
    )
    return response.choices[0].message.content


def divider(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    results = {}

    for name, config in PROMPTS.items():
        label = name.replace("_", " ").upper()
        divider(label)
        print(f"\n[SYSTEM PROMPT — first 200 chars]\n{config['system'][:200]}...\n")
        print(f"[USER]\n{config['user'][:200]}\n")
        print("[RESPONSE]")

        output = run_prompt(name, config["system"], config["user"])
        results[name] = output
        print(output)

    # ─── Write prompt_patterns_log.md ─────────────────────────────────────────
    log_path = Path(__file__).parent.parent / "prompt_patterns_log.md"
    verdicts = {
        "1_zero_shot": "Use this when you need a quick, unbiased baseline — no steering, no examples.",
        "2_few_shot": "Use this when the model needs to match a specific format or tone you've already defined.",
        "3_chain_of_thought_role": "Use this when reasoning quality and teaching structure matter more than brevity.",
        "4_p1_system_prompt": "Use this for P1 — it combines role + pedagogy + learner profile for the highest contextual relevance.",
    }

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("# Prompt Patterns Comparison Log\n\n")
        f.write(f"**Topic tested:** {TOPIC}  \n")
        f.write(f"**Model:** {MODEL}  \n")
        f.write(f"**Temperature:** 0.3\n\n---\n\n")

        for name, output in results.items():
            label = name.replace("_", " ").title()
            config = PROMPTS[name]
            f.write(f"## {label}\n\n")
            f.write(f"**Pattern:** `{name}`\n\n")
            f.write(f"**System prompt used:**\n```\n{config['system'][:300]}...\n```\n\n")
            f.write(f"**User message:** `{config['user'][:100]}`\n\n")
            f.write(f"**Full output:**\n\n{output}\n\n")
            f.write(f"**Verdict:** {verdicts[name]}\n\n---\n\n")

    print(f"\n\nLog written to: {log_path}")


if __name__ == "__main__":
    main()
