# Prompt Patterns Comparison Log

**Topic tested:** explain gross margin  
**Model:** gpt-4o  
**Temperature:** 0.3

---

## 1 Zero Shot

**Pattern:** `1_zero_shot`

**System prompt used:**
```
You are a helpful assistant....
```

**User message:** `Explain gross margin.`

**Full output:**

Gross margin is a financial metric that represents the difference between a company's revenue and its cost of goods sold (COGS), expressed as a percentage of revenue. It measures how efficiently a company is producing and selling its goods by indicating the portion of sales revenue that exceeds the costs directly associated with producing the goods sold.

The formula for calculating gross margin is:

\[ \text{Gross Margin} = \left( \frac{\text{Revenue} - \text{Cost of Goods Sold (COGS)}}{\text{Revenue}} \right) \times 100 \]

Here's a breakdown of the components:

- **Revenue**: The total income generated from the sale of goods or services.
- **Cost of Goods Sold (COGS)**: The direct costs attributable to the production of the goods sold by a company. This typically includes the cost of materials and labor directly used to create the product.

Gross margin is an important indicator of a company's financial health and operational efficiency. A higher gross margin means that a company retains more money from each dollar of sales to cover other operating expenses and profit. Conversely, a lower gross margin indicates that a larger portion of sales revenue is consumed by production costs, leaving less for other expenses and profit.

For example, if a company has $1,000,000 in revenue and $600,000 in COGS, the gross margin would be:

\[ \text{Gross Margin} = \left( \frac{1,000,000 - 600,000}{1,000,000} \right) \times 100 = 40\% \]

This means that 40% of the company's revenue is retained after covering the cost of goods sold, which can then be used to pay for other expenses, taxes, and profit.

**Verdict:** Use this when you need a quick, unbiased baseline — no steering, no examples.

---

## 2 Few Shot

**Pattern:** `2_few_shot`

**System prompt used:**
```
You are a helpful assistant....
```

**User message:** `Here are examples of how to explain finance concepts clearly:

Example 1 — Net income:
Net income is`

**Full output:**

Gross margin is the portion of revenue left after subtracting the cost of goods sold (COGS). It shows how much a company earns from selling its products or services before accounting for other expenses like operating costs, interest, and taxes. It's a key indicator of a company's production efficiency and profitability.

**Verdict:** Use this when the model needs to match a specific format or tone you've already defined.

---

## 3 Chain Of Thought Role

**Pattern:** `3_chain_of_thought_role`

**System prompt used:**
```
You are a finance professor with 20 years of experience teaching MBA students.
When you explain a concept, you:
1. Start with the concrete business problem the concept solves
2. Define it in plain English before any formula
3. Walk through the formula step-by-step with a real example
4. Name the one...
```

**User message:** `Explain gross margin.`

**Full output:**

Certainly! Let's dive into the concept of gross margin, which is a crucial metric for assessing a company's financial health and operational efficiency.

1. **Concrete Business Problem:**
   Imagine you're running a retail business, and you want to understand how efficiently you're turning your sales into profit. You're interested in knowing how much money you have left from sales after covering the direct costs of producing or purchasing the goods you sell. This is where gross margin comes into play.

2. **Plain English Definition:**
   Gross margin is the percentage of sales revenue that exceeds the cost of goods sold (COGS). It represents the portion of sales revenue that is available to cover other business expenses and contribute to profit. Essentially, it tells you how much of each dollar earned from sales is left after paying for the goods sold.

3. **Formula and Real Example:**
   The formula for gross margin is:

   \[
   \text{Gross Margin} = \left( \frac{\text{Sales Revenue} - \text{Cost of Goods Sold (COGS)}}{\text{Sales Revenue}} \right) \times 100
   \]

   Let's say your company sells $100,000 worth of products in a month, and the cost of goods sold is $60,000. Plug these numbers into the formula:

   \[
   \text{Gross Margin} = \left( \frac{100,000 - 60,000}{100,000} \right) \times 100 = 40\%
   \]

   This means that 40% of your sales revenue is left after covering the direct costs of the goods sold, which can then be used to cover other expenses like marketing, salaries, and rent, or contribute to profit.

4. **Common Beginner Mistake:**
   A common mistake beginners make is confusing gross margin with net profit margin. Gross margin only accounts for the cost of goods sold, while net profit margin considers all expenses, including operating expenses, taxes, and interest. It's important to remember that gross margin is just one part of the profitability picture.

5. **Diagnostic Question:**
   If a company has a gross margin of 50% and its sales revenue is $200,000, what is the cost of goods sold? 

   To solve this, rearrange the gross margin formula to find COGS:

   \[
   \text{COGS} = \text{Sales Revenue} - (\text{Gross Margin} \times \text{Sales Revenue})
   \]

   Plug in the numbers:

   \[
   \text{COGS} = 200,000 - (0.50 \times 200,000) = 200,000 - 100,000 = 100,000
   \]

   This means the cost of goods sold is $100,000.

**Verdict:** Use this when reasoning quality and teaching structure matter more than brevity.

---

## 4 P1 System Prompt

**Pattern:** `4_p1_system_prompt`

**System prompt used:**
```
"
<identity>
You are P1 — a personal learning tutor and the natural language interface
for a multi-agent financial AI system. You operate in two modes:

TEACH MODE: When the user wants to learn something. Generate syllabi, run
Socratic sessions, quiz, track gaps, resurface weak concepts.

EXPLAIN MO...
```

**User message:** `Explain gross margin.`

**Full output:**

Gross margin is a financial metric that shows the percentage of revenue that exceeds the cost of goods sold (COGS). It essentially measures how efficiently a company is producing and selling its products. 

To calculate gross margin, you subtract the COGS from total revenue and then divide that number by total revenue. The result is expressed as a percentage. Here's the formula:

\[ \text{Gross Margin} = \left(\frac{\text{Revenue} - \text{COGS}}{\text{Revenue}}\right) \times 100 \]

This percentage tells you how much of each dollar of revenue is left over after covering the direct costs associated with producing the goods or services sold. A higher gross margin indicates that a company is retaining more revenue as profit, which can be used to cover other expenses or reinvest in the business.

Given your background in industrial engineering and process efficiency, think of gross margin as a measure of how well a company is managing its production processes and cost controls. If a company can produce goods more efficiently, it can lower its COGS and increase its gross margin.

Want to see how this changes if we adjust the COGS or revenue?

**Verdict:** Use this for P1 — it combines role + pedagogy + learner profile for the highest contextual relevance.

---

