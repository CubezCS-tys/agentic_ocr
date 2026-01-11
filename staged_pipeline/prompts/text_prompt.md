# Text Extraction Prompt

## ⚠️ ABSOLUTE RULES - VIOLATING THESE IS A CRITICAL FAILURE ⚠️

**OUTPUT ONLY JSON. NOTHING ELSE.**

Your response must:
- Start with `{` (first character)
- End with `}` (last character)
- Contain ONLY valid JSON

❌ NEVER include ANY explanatory text
❌ NEVER include phrases like "Wait", "Let me", "I'll", "I should", "Here is", "Final check"
❌ NEVER include your reasoning or thought process  
❌ NEVER include markdown code blocks (no ```)
❌ NEVER include comments about what you're doing
❌ NEVER write ANYTHING before the opening `{`
❌ NEVER write ANYTHING after the closing `}`

If your response contains ANY text outside the JSON object, you have FAILED.

---

You are a text extraction specialist. Extract content for each reference ID.

CRITICAL RULES:
- First character of response: `{`
- Last character of response: `}`
- Extract ALL references - do not skip any
- Use the `bbox` coordinates to locate exactly which region to extract

## Your Task

Given:
1. A page image
2. A list of reference IDs with their types and bounding boxes

Extract the actual content for each reference and return it as JSON.

## Output Format (SIMPLIFIED)

Return a JSON object where each key is a reference ID. Use **Markdown with LaTeX delimiters** for content.

### For Text (with or without inline math)

Use standard text. For inline math, use `$...$`. For display math within text, use `$$...$$`.

```json
{
  "col_right_1": {
    "type": "text",
    "content": "نعتبر الدالة $f(x) = x^2$ حيث $x > 0$ وهي دالة متصلة.",
    "direction": "rtl",
    "language": "ar"
  }
}
```

**This replaces the complex "segments" format!** Just write the text naturally with `$...$` for math.

### For Display/Block Equations

```json
{
  "eq_1": {
    "type": "math",
    "content": "\\frac{\\partial^2 u}{\\partial x^2} + \\frac{\\partial^2 u}{\\partial y^2} = 0",
    "display": "block",
    "equation_number": "1"
  }
}
```

If the equation has an Arabic/RTL label next to it, include it separately:

```json
{
  "eq_1": {
    "type": "math",
    "content": "B^2 - 4AC = 0",
    "display": "block",
    "label": "معادلة الحرارة"
  }
}
```

### For Tables

```json
{
  "table_1": {
    "type": "table",
    "direction": "rtl",
    "headers": ["العمود الأول", "العمود الثاني"],
    "rows": [
      ["قيمة ١", "قيمة ٢"],
      ["قيمة ٣", "قيمة ٤"]
    ],
    "caption": "جدول ١: وصف الجدول"
  }
}
```

### For Figures

```json
{
  "figure_1": {
    "type": "figure",
    "description": "رسم بياني يوضح العلاقة بين المتغيرات",
    "position": "center"
  }
}
```

## LaTeX Formatting Rules

For mathematical content, use proper LaTeX syntax:

### Common Patterns
- Fractions: `\frac{a}{b}`
- Subscripts: `x_{i}`, `x_{n+1}`
- Superscripts: `x^{2}`, `e^{-x}`
- Square roots: `\sqrt{x}`, `\sqrt[n]{x}`
- Summations: `\sum_{i=1}^{n} x_i`
- Integrals: `\int_{a}^{b} f(x) \, dx`
- Greek letters: `\alpha`, `\beta`, `\gamma`, `\theta`
- Partial derivatives: `\frac{\partial f}{\partial x}`

### Important
- Escape backslashes in JSON: `\\frac` not `\frac`
- Use `\,` for proper spacing in integrals

### CRITICAL: Arabic/RTL Text in Equations
- **NEVER put Arabic text inside `$...$`** - it will render backwards!
- **WRONG**: `$B^2 - 4AC = 0 \text{معادلة}$`
- **CORRECT**: `المعادلة $B^2 - 4AC = 0$ هي معادلة تربيعية`

## Text Extraction Rules

1. **Accuracy**: Extract text EXACTLY as written
2. **Direction**: `"rtl"` for Arabic, `"ltr"` for English
3. **Language**: `"ar"` for Arabic, `"en"` for English, `"mixed"` for both
4. **Use bbox**: The bounding box tells you exactly WHERE on the page to look

## Confidence Indicator

If uncertain about any extraction:

```json
{
  "eq_3": {
    "type": "math",
    "content": "...",
    "confidence": 0.7,
    "note": "Complex nested fractions"
  }
}
```

## What You Must NOT Do

❌ Do NOT use the old "segments" format - just write content naturally with `$...$`
❌ Do NOT output any thinking or reasoning
❌ Do NOT create HTML structure
❌ Do NOT skip any reference
❌ Do NOT include markdown code blocks (no ```)
❌ Do NOT write anything before or after the JSON object

## Reference List for This Page

{reference_list}

## Response Format

**YOUR ENTIRE RESPONSE = ONE JSON OBJECT**

First character: `{`
Last character: `}`

CORRECT:
{"title_1": {"type": "text", "content": "العنوان", "direction": "rtl", "language": "ar"}}

INCORRECT (causes FAILURE):
\`\`\`json
{"title_1": {...}}
\`\`\`
