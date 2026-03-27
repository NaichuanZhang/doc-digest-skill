---
name: doc-digest
description: Transform documents (PDF, markdown) into interactive, human-digestible webpages with AI-powered section-based chat. This skill should be used when the user wants to make a report or document more digestible, create an interactive reader for a PDF, or build a chat interface around document content. Triggers on requests like "digest this PDF", "make this report readable", "create an interactive viewer for this document".
---

# Doc Digest

Transform any document into a beautiful, interactive webpage with an AI-powered chat panel for section-based Q&A, fact-checking, and follow-up generation.

## Core Principles

1. **Templateized Output** — Webpage and chat server are generated from reusable templates
2. **Document-Agnostic Server** — The chat server reads structured JSON, works with any document
3. **Combined Chat UI** — Floating side panel + select-to-chat for natural document exploration
4. **Anti-AI-Slop Design** — Distinctive typography and layouts, no generic aesthetics

---

## Phase 0: Detect Input

Determine the input document type:

- **PDF** (.pdf) — Go to Phase 1 with PDF extraction
- **Markdown** (.md, .markdown) — Go to Phase 1 with markdown parsing
- **Other** — Inform user of supported formats (PDF, markdown)

Verify the file exists and is readable before proceeding.

---

## Phase 1: Process Document

### Step 1.1: Install dependencies (if needed)

```bash
pip install pymupdf4llm pyyaml
```

### Step 1.2: Extract document

Run the extraction script:

```bash
python scripts/extract_document.py <input_file> <output_dir>
```

This produces `<output_dir>/document_data.json` containing structured sections.

### Step 1.3: Confirm with user

Present a summary of extracted sections (titles, word counts) and ask for confirmation before proceeding. Use AskUserQuestion:

**Question** (header: "Sections"): "The document has been processed into N sections. Does this look correct?"
Options: "Looks good" / "Re-extract with different settings"

---

## Phase 2: Style Discovery

A lighter version of style discovery — document layouts, not slides.

### Step 2.0: Style Path

Ask via AskUserQuestion (header: "Style"):
- "Show me options (Recommended)" — Generate 2 preview snippets
- "I know what I want" — Pick a preset directly

### Step 2.1: Choose Preset

4 document presets available:

| Preset | Fonts | Colors | Character |
|--------|-------|--------|-----------|
| **Research Paper** | Fraunces + Work Sans | Cream/warm white, dark text, burgundy accent | Academic, thoughtful |
| **Technical Report** | IBM Plex Mono + IBM Plex Sans | Dark bg (#1a1a2e), cyan accent (#00d4ff) | Developer-focused, precise |
| **Executive Brief** | Clash Display + Satoshi | White, charcoal, electric blue accent | Bold, confident, minimal |
| **Magazine Feature** | Playfair Display + Source Sans 3 | Off-white, deep navy, coral accent | Editorial, engaging |

Ask via AskUserQuestion (header: "Preset"):
Options: Research Paper / Technical Report / Executive Brief / Magazine Feature

### Step 2.2: Preview (if "Show me options")

Generate 2 small HTML preview snippets showing the first section styled in different presets. Save to `.claude-design/doc-previews/` and open for the user.

---

## Phase 3: Generate Webpage

### Step 3.1: Read template files

Read all three template files:
- [assets/webapp-template/index.html](assets/webapp-template/index.html) — HTML structure with placeholder comments
- [assets/webapp-template/styles.css](assets/webapp-template/styles.css) — Base CSS (to be inlined)
- [assets/webapp-template/chat.js](assets/webapp-template/chat.js) — Chat panel logic (to be inlined)

### Step 3.2: Generate the HTML

Create a single self-contained HTML file by:

1. **Override `:root` variables** in styles.css to match the chosen preset (colors, fonts, font links)
2. **Inline styles.css** into the `<style>` block (with preset overrides applied)
3. **Inline chat.js** into a `<script>` block
4. **Fill placeholders** in index.html:
   - `<!-- === DOCUMENT TITLE === -->` — Set `<title>` and `<h1>` from metadata
   - `<!-- === FONT LINKS === -->` — Add Google Fonts/Fontshare links for the preset
   - `<!-- === TABLE OF CONTENTS === -->` — Generate `.toc-link` elements from sections
   - `<!-- === SECTIONS === -->` — Generate `<section>` elements with markdown rendered as HTML
   - `<!-- === SERVER URL CONFIG === -->` — Set `window.DOC_DIGEST_SERVER_URL`
5. **Write** the final `index.html` to the output directory

### Step 3.3: Open in browser

```bash
open <output_dir>/index.html
```

---

## Phase 4: Configure Chat Server

### Step 4.1: Copy server template

Copy all files from `assets/server-template/` to `<output_dir>/server/`:
- server.py, agent.py, tools.py, models.py, requirements.txt

### Step 4.2: Copy document data

Copy `document_data.json` into the server directory.

### Step 4.3: Start the server

For reference on Strands SDK patterns, read [references/strands-patterns.md](references/strands-patterns.md).

Run the server launcher:

```bash
python scripts/start_server.py <output_dir>/server/
```

### Step 4.4: Verify

Confirm the server is running:

```bash
curl http://localhost:8765/api/health
```

---

## Phase 5: Delivery

Summarize for the user:

1. **File location** — Path to the generated `index.html`
2. **Chat server** — Running at `http://localhost:8765`
3. **Navigation** — Scroll through sections, use the sidebar ToC
4. **Chat** — Click the chat bubble (bottom-right) to open the panel
5. **Select-to-chat** — Highlight any text to get Ask / Fact check / Summarize buttons
6. **Conversation** — Chat history is preserved within the session
7. **Customization** — Edit `:root` CSS variables for colors, swap font links for typography

---

## Supporting Files

| File | Purpose | When to Read |
|------|---------|-------------|
| [scripts/extract_document.py](scripts/extract_document.py) | PDF/MD extraction to structured JSON | Phase 1 |
| [scripts/start_server.py](scripts/start_server.py) | Chat server launcher with venv setup | Phase 4 |
| [assets/webapp-template/](assets/webapp-template/) | HTML/CSS/JS templates for the webpage | Phase 3 |
| [assets/server-template/](assets/server-template/) | FastAPI + Strands chat server files | Phase 4 |
| [references/strands-patterns.md](references/strands-patterns.md) | Strands SDK quick reference | Phase 4 (if customizing) |
