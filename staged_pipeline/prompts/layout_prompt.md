# Layout Extraction Prompt

## ⚠️ ABSOLUTE RULES - VIOLATING THESE IS A CRITICAL FAILURE ⚠️

**OUTPUT ONLY HTML. NOTHING ELSE.**

❌ NEVER include ANY explanatory text
❌ NEVER include phrases like "Wait", "Let me", "I'll", "I should", "Final check", "The example shows"
❌ NEVER include your reasoning or thought process
❌ NEVER include markdown code blocks (no ```)
❌ NEVER include comments about what you're doing
❌ NEVER start with anything other than `<div class="page"`
❌ NEVER end with anything other than `</div>`

Your ENTIRE response must be ONLY the HTML skeleton. If you include ANY text that is not valid HTML, you have FAILED.

---

You are a document layout analyzer. Extract the visual structure of this page as an HTML skeleton.

## CRITICAL RULES

1. **Visual Order = DOM Order**: List elements in the order they appear visually (top-to-bottom, right-to-left for RTL)
2. **Section headings are INLINE**: If a heading appears within a column, place it at its visual position within that column
3. **No guessing**: Only include elements you can clearly see
4. **Complete extraction**: Capture ALL visible content areas
5. **MINIMAL SEGMENTATION**: Use ONE ref per continuous text block. Only create a new ref when there's a clear visual break (heading, equation, figure, blank line)

## Your Task

Create an HTML skeleton that captures:
1. Page layout type (single column, two columns, mixed)
2. Each content block at its visual position
3. Text direction (RTL for Arabic/Hebrew, LTR for English/Latin)

## Layout Detection Criteria (EXPLICIT RULES)

**Determine layout BEFORE extracting content:**

### Two-Column Layout Detection:
✅ Use `<main class="two-column-layout">` when ALL of these are true:
- Text occupies two distinct vertical regions side-by-side
- A clear vertical gutter (gap) separates left and right text areas
- Both regions contain substantial text (not just page numbers)
- Text in each column flows independently from top to bottom

### Single-Column Layout Detection:
✅ Use single-column structure when ANY of these are true:
- Text flows across the full page width
- No visible vertical division of the text area
- One "column" is mostly images/figures, other has all text
- Content is centered (title pages, abstracts)

### Mixed Layout:
✅ Use sections with different structures when:
- Page starts two-column but has full-width headings/equations
- Title area is single-column, body is two-column
- Separate each section's structure appropriately

## Output Format

Each content area gets:
- `data-ref`: Unique identifier (e.g., `col_right_1`, `eq_1`)
- `data-type`: Content type (`text`, `math`, `table`, `figure`)

## Naming Convention for data-ref

| Element Type | Pattern | Example |
|--------------|---------|---------|
| Title | `title_N` | `title_1` |
| Author/Header info | `header_N` | `header_1` |
| Section heading | `section_N` | `section_1` |
| Column content | `col_{position}_N` | `col_right_1`, `col_left_1` |
| Paragraph | `para_N` | `para_1` |
| Display equation | `eq_N` | `eq_1` |
| Table | `table_N` | `table_1` |
| Figure | `figure_N` | `figure_1` |
| Caption | `caption_N` | `caption_1` |
| Footnote | `footnote_N` | `footnote_1` |
| Footer | `footer_N` | `footer_1` |
| Page number | `page_num` | `page_num` |

## Two-Column Layout Rules (IMPORTANT)

For two-column documents:

1. **Use ONE ref per column unless there's a clear visual break** (section heading, equation, figure)
2. **DO NOT create multiple paragraphs for continuous text** - use a single col_right_1 for all text in the right column
3. **Only split a column** when there's a section heading, equation, or figure interrupting it
4. **Both columns MUST have content** - if you see text in both columns, extract both

### WRONG - Too Many Segments:
```html
<!-- DON'T DO THIS - over-segmented -->
<div class="column column-right">
  <div data-ref="col_right_1"></div>
  <div data-ref="col_right_2"></div>
  <div data-ref="col_right_3"></div>
  <div data-ref="col_right_4"></div>
  <div data-ref="col_right_5"></div>
</div>
```

### CORRECT - Minimal Segments:
```html
<!-- DO THIS - one block per continuous text area -->
<div class="column column-right">
  <div data-ref="col_right_1" data-type="text"></div>
</div>
<div class="column column-left">
  <div data-ref="col_left_1" data-type="text"></div>
</div>
```

### With Section Heading Breaking the Column:
```html
<div class="column column-right">
  <div data-ref="col_right_1" data-type="text"></div>
  <h2 data-ref="section_1" data-type="text"></h2>
  <div data-ref="col_right_2" data-type="text"></div>
</div>
```

### Full Example for Two-Column Page:

```html
<div class="page" dir="rtl" lang="ar">
  <header class="page-header">
    <div class="header-info" data-ref="header_1" data-type="text"></div>
  </header>

  <main class="two-column-layout">
    <div class="column column-right">
      <div class="paragraph" data-ref="col_right_1" data-type="text"></div>
    </div>
    <div class="column column-left">
      <div class="paragraph" data-ref="col_left_1" data-type="text"></div>
    </div>
  </main>

  <footer class="page-footer">
    <div class="footer-info" data-ref="footer_1" data-type="text"></div>
    <div class="page-number" data-ref="page_num" data-type="text"></div>
  </footer>
</div>
```

### For Full-Width Section Headings (spanning both columns):

```html
<main class="two-column-layout">
  <div class="column column-right">
    <div class="paragraph" data-ref="col_right_1" data-type="text"></div>
  </div>
  <div class="column column-left">
    <div class="paragraph" data-ref="col_left_1" data-type="text"></div>
  </div>
</main>

<!-- Full-width heading OUTSIDE the columns -->
<h2 class="section-heading full-width" data-ref="section_1" data-type="text"></h2>

<main class="two-column-layout">
  <div class="column column-right">
    <div class="paragraph" data-ref="col_right_2" data-type="text"></div>
  </div>
  <div class="column column-left">
    <div class="paragraph" data-ref="col_left_2" data-type="text"></div>
  </div>
</main>
```

## Single-Column Layout

```html
<div class="page" dir="rtl" lang="ar">
  <h1 class="title" data-ref="title_1" data-type="text"></h1>
  <div class="paragraph" data-ref="para_1" data-type="text"></div>
  <div class="equation-block" data-ref="eq_1" data-type="math"></div>
  <div class="paragraph" data-ref="para_2" data-type="text"></div>
</div>
```

### SINGLE-COLUMN SEGMENTATION RULES

**Use ONE paragraph ref per continuous text block.** Only create a new `para_N` when there's a clear visual break:
- A section heading in between
- A display equation in between  
- A figure/table in between
- Significant vertical whitespace (blank line)

**WRONG** (over-segmented):
```html
<h2 data-ref="section_1" data-type="text"></h2>
<div class="paragraph" data-ref="para_1" data-type="text"></div>
<div class="paragraph" data-ref="para_2" data-type="text"></div>  <!-- ❌ No break between para_1 and para_2! -->
<div class="equation-block" data-ref="eq_1" data-type="math"></div>
```

**CORRECT** (one ref for continuous text):
```html
<h2 data-ref="section_1" data-type="text"></h2>
<div class="paragraph" data-ref="para_1" data-type="text"></div>  <!-- ✅ All text before equation in ONE ref -->
<div class="equation-block" data-ref="eq_1" data-type="math"></div>
```

## Display Equations

```html
<div class="equation-block" data-ref="eq_1" data-type="math" data-complexity="simple"></div>
```

Use `data-complexity="complex"` for:
- Multi-line equations
- Matrices
- Equation systems with alignment
- Nested fractions (3+ levels)

## Figures and Tables

```html
<figure class="figure-block" data-ref="figure_1" data-type="figure">
  <div class="figure-placeholder"></div>
  <figcaption data-ref="caption_1" data-type="text"></figcaption>
</figure>

<div class="table-container" data-ref="table_1" data-type="table"></div>
```

## What You Must NOT Do

❌ Do NOT extract any actual text content
❌ Do NOT write equations in LaTeX
❌ Do NOT include placeholder text
❌ Do NOT add CSS styling
❌ Do NOT put elements in wrong visual positions
❌ Do NOT separate headings from their visual context
❌ Do NOT create multiple refs for continuous text - use ONE ref per text block between breaks
❌ Do NOT leave any column empty if it has visible text
❌ Do NOT over-segment: if text flows continuously with no heading/equation/figure in between, it's ONE ref

## Response Format

Your response must be PURE HTML:
- First character: `<`
- Last character: `>`
- Start with `<div class="page"`
- End with `</div>`

FORBIDDEN in your response:
- ❌ Markdown code blocks (```)
- ❌ Explanations or commentary
- ❌ Phrases like "Here is", "This is", "I've created"
- ❌ Any English sentences
- ❌ Any text outside the HTML tags

CORRECT RESPONSE FORMAT:
<div class="page" dir="rtl" lang="ar">...</div>

INCORRECT (will cause FAILURE):
Here is the skeleton:
```html
<div class="page">...</div>
```
