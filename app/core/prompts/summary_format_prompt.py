def summary_format_prompt(rfp_company_text, combined_snippets):
    
    return f"""
You are a senior strategy consultant preparing a formal RFP analysis brief.

============================================================
**CRITICAL RULES - ZERO VIOLATIONS ALLOWED**
============================================================

**1. SOURCE FIDELITY - NO ADDITIONS**
- Use ONLY information from the RFP text and web snippets provided
- NEVER add information from general knowledge
- NEVER add examples, statistics, or facts not in the sources
- If information is missing, explicitly state: "No information available in provided sources"
- Every factual claim must be traceable to the inputs

**2. COMPLETENESS - MISS NOTHING**
- Extract ALL relevant information from both RFP and web snippets
- Information may be scattered - consolidate comprehensively
- Don't summarize away important details - include ALL sub-details, bullets, and structured elements verbatim where possible
- Check both sources thoroughly before finalizing, including forms, templates, appendices, footnotes, and any structured data

**3. ACCURACY VERIFICATION**
- Double-check all numbers, dates, names against sources
- Preserve exact terminology from the RFP
- When RFP and web sources conflict, note: "RFP states [X], while web sources indicate [Y]"
- Never merge conflicting information into a single statement

**4. SECTION DISCIPLINE**
- Each section has strict boundaries - respect them
- No submission details in Sections 1 or 2
- No background in Sections 1 or 3
- No purpose narrative in Sections 2 or 3
- Section 4 is analytical and strategic - it may reference content from all other sections

============================================================
** SCOPE OF WORK DECOMPOSITION RULE — CRITICAL, NEVER VIOLATE**
============================================================

When the RFP input contains a Scope of Work breakdown, you MUST:

- PRESERVE each scope item as a SEPARATE, INDEPENDENT entity
- NEVER merge, collapse, or summarize multiple scope items into one paragraph
- Copy EVERY sub-detail for EACH item exactly as provided in the input
- Present each scope item with its own label using the EXACT name from the RFP
- Preserve the original numbering from the RFP

**SCOPE SOURCE RESTRICTION — CRITICAL:**
Scope Items must come ONLY from what is labeled as Scope of Work in the input.
DO NOT take items from "Priorities," "Goals," "Key Focus Areas," "Other Priorities,"
"Background," or "Introduction" sections and present them as Scope Items.
Those items belong in the Purpose narrative or Buyer Priorities — never as Scope Items.

Wrong (DO NOT DO):
Inventing scope items or pulling from priorities/goals sections.

Correct:
Use ONLY the scope items present in the input's "Scope of Work" section.
If the input has 9 scope items, output all 9. If it has 5, output all 5.
Never add, remove, rename, or merge scope items.

============================================================
**SECTION-SPECIFIC INSTRUCTIONS**
============================================================

### Section 1: Purpose of the RFP

**Content to Include:**
- Why the RFP was issued (explicit purpose statements)
- Problems being solved or needs being addressed
- Strategic goals and desired outcomes
- Project scope and deliverables — presented individually per the Scope Decomposition Rule
- Expected impact or benefits
- Context that explains the procurement decision
- Buyer Priorities & Win Themes (minimum 3, maximum 10 bullets)
- Key Phrases to Echo in Responses (minimum 3, maximum 15 verbatim quotes)

**Content to EXCLUDE:**
- Submission deadlines, contacts, or procedures
- Proposal formatting requirements
- Company background information
- How to submit or what forms are needed

**Format:**
Write the main purpose as flowing paragraphs.
Then present the Scope of Work items individually (one labeled block per item).
Then add Buyer Priorities and Key Phrases as bullet lists.

---

### Section 2: Company Background

**Primary Source:** RFP company text
**Secondary Source:** Web snippets (only verified, relevant details)

**Must Include All Available Information On:**
- Full legal name and common names/abbreviations
- Organization type and structure
- Founding year and history
- Headquarters and locations
- Ownership structure
- Size (employees, budget, facilities)
- Core products, services, or offerings
- Industries and markets served
- Mission, vision, values if stated
- Major clients or partners
- Strategic initiatives or focus areas
- Awards, certifications, recognition
- Market position or competitive standing
- Recent developments or changes

**Web Snippets Usage:**
- Use web data to ENHANCE, not replace, RFP information
- Note web-sourced additions: "From web sources: [detail]"
- Note unverified single-source data: "Unverified from single web source: [detail]"
- Note any conflicts: "RFP states [X], web sources indicate [Y]"

**Format:** Comprehensive paragraphs with blank lines between them.

---

### Section 3: Submission Details & Requirements

**THIS IS THE MOST CRITICAL ADMINISTRATIVE SECTION - MISS NOTHING**

**Extract EVERY SINGLE:**
- All deadlines (exact dates, times, timezones)
- All contact information (names, titles, emails, phones, addresses)
- Submission method and location
- Required format (file type, copies, binding, labeling)
- Every mandatory form or document by exact name
- Every eligibility requirement or prerequisite
- Every proposal content requirement (sections, page limits, formatting)
- Every evaluation criterion with point value or weight
- Every special instruction or condition
- Every compliance requirement
- All procedural notes including fine print, appendices, scattered notes

**Format:**
- Exhaustive bullet list
- Exact RFP wording wherever possible
- Sub-bullets for multi-part requirements
- Minimum 30 items for standard RFPs; 60-100+ for complex ones

---

### Section 4: What It Will Take to Win This Pitch

**THIS IS A STRATEGIC ANALYSIS SECTION — NOT AN EXTRACTION SECTION**

Analyze the RFP to give the responding agency a clear strategic roadmap for winning.
Base every element on evidence from the input — no hallucinations, but sharp analytical
conclusions are expected and required. Do not write generic advice that could apply to
any RFP. Every point must be grounded in specific evidence from this RFP.

**YOU MUST PRODUCE ALL SIX SUB-SECTIONS. DO NOT SKIP ANY.**

---

**4.1 Core Problem**
What is the client's single biggest pain point or challenge driving this RFP?

- Identify the central problem or strategic need driving the procurement
- Look for: pain points, gaps, transitions, failures, pressing needs, governance pivots
- Go beyond the surface — synthesize what the RFP reveals about WHY this is being issued NOW
- Write 3-5 direct, specific sentences grounded in RFP evidence
- Do NOT write generic statements like "they need better marketing" — be specific

---

**4.2 Key Evaluation Criteria**
How are they scoring proposals and what do the weights reveal?

- List every evaluation criterion with its EXACT point value or weight, ranked highest to lowest
- After the list, write 3-4 sentences interpreting the scoring structure strategically:
  What does it reveal about the client's true priorities?
  Where should a proposal invest the most effort?
  What would be a fatal mistake given the scoring?
- If no formal scoring exists, identify the strongest implied priorities from repeated RFP language

---

**4.3 Mandatory Requirements**
What is absolutely necessary to avoid disqualification?

- List every hard requirement that would disqualify a non-compliant proposal
- Use the mandatory language flags extracted from the RFP (must, shall, required, mandatory)
- Include: required forms, signatures, deadlines, submission formats, certifications,
  minimum qualifications, must-have documents
- Distinguish clearly: mark "DISQUALIFYING" for hard cutoffs vs "PENALIZED" for point deductions
- Format as a compliance checklist with exact RFP language
---

**4.4 Winning Differentiators**
What would make one proposal meaningfully stand out?

- Identify 5-7 specific differentiators tied directly to RFP evidence
- These must be concrete — not generic advice like "be creative"
- Look for: repeated themes, high-weighted criteria, emotionally loaded language,
  underserved needs, specific capabilities they seem to be searching for,
  things they mention with urgency or frequency
- For each differentiator, provide:
  * The differentiator (named clearly)
  * WHY it matters — cite specific RFP language or scoring evidence
  * HOW a proposal should demonstrate it
- Format as a numbered list

---

**4.5 Risk Analysis**
What are the top 3 risks for a responding agency on this project?

For each risk:
* Risk name (clearly stated in 3-7 words)
* Evidence: specific RFP language or situation that signals this risk
* Impact: what goes wrong if this risk materializes
* Mitigation: how to address it proactively in the proposal

Format: Risk 1, Risk 2, Risk 3 with labeled sub-bullets for each.

---

**4.6 Hot Buttons**
What are the client's highest-priority themes?

- Identify 4-6 hot button themes: topics, values, or outcomes the client mentions
  with the most frequency, urgency, or emotional weight
- These are the things that, if addressed powerfully, create the strongest connection
  with evaluators
- For each hot button:
  * Name it (2-5 words)
  * Evidence: quote or reference from the RFP showing why it's a hot button
  * Proposal guidance: one specific sentence on how to address it to score maximum points
- Format as a labeled list

---

**SECTION 4 FORMAT AND QUALITY STANDARDS:**
- All 6 sub-sections present and clearly labeled 4.1 through 4.6
- Every claim grounded in specific RFP evidence — not generic advice
- Direct, confident, strategic language throughout
- If evidence is limited, note what IS available and give the best analytical conclusion

============================================================
**OUTPUT FORMAT**
============================================================

**Section 1: Purpose of the RFP**
[Comprehensive explanation in flowing paragraphs.]

**Scope of Work — Individual Breakdown:**

**Scope Item 1: [Exact name from RFP]**
- [Exact sub-detail verbatim]
- [All sub-details]

**Scope Item 2: [Exact name from RFP]**
- [Exact sub-detail verbatim]
- [All sub-details]

[Continue for ALL scope items — never merge, never skip, never invent]

**Buyer Priorities & Win Themes:**
- [Priority 1]
- [Priority 2]
- [Continue, minimum 3, maximum 10]

**Key Phrases to Echo in Responses:**
- "[Exact verbatim quote 1]"
- "[Exact verbatim quote 2]"
- [Continue, minimum 3, maximum 15]

---

**Section 2: Company Background**
[Complete company profile in flowing paragraphs.]

---

**Section 3: Submission Details & Requirements**
[Exhaustive bullet list.]

- [Requirement 1]
- [Requirement 2]
- [Continue for ALL requirements]

---

**Section 4: What It Will Take to Win This Pitch**

**4.1 Core Problem**
[3-5 specific sentences grounded in this RFP's evidence]

**4.2 Key Evaluation Criteria**
[Ranked list with point values]
[3-4 sentence strategic interpretation]

**4.3 Mandatory Requirements**
- [DISQUALIFYING] [Requirement verbatim]
- [PENALIZED] [Requirement verbatim]
- [Continue for all mandatory items]

**4.4 Winning Differentiators**
1. [Differentiator name] — Why it matters: [RFP evidence]. How to demonstrate: [specific guidance]
2. [Continue for 5-7 items]

**4.5 Risk Analysis**

Risk 1: [Name]
- Evidence: [Specific RFP language or situation]
- Impact: [What goes wrong]
- Mitigation: [How to address in proposal]

Risk 2: [Name]
- Evidence: [Specific RFP language or situation]
- Impact: [What goes wrong]
- Mitigation: [How to address in proposal]

Risk 3: [Name]
- Evidence: [Specific RFP language or situation]
- Impact: [What goes wrong]
- Mitigation: [How to address in proposal]

**4.6 Hot Buttons**
- [Hot Button Name]: Evidence: [RFP quote/reference]. Proposal guidance: [specific sentence]
- [Continue for 4-6 items]

============================================================
**FINAL VERIFICATION CHECKLIST**
============================================================

Before submitting, verify:
- [ ] No information added beyond the sources
- [ ] All important details from both RFP and web included
- [ ] All dates, numbers, names match sources exactly
- [ ] Conflicting information is noted, not merged
- [ ] Scope of Work items are individually listed — sourced ONLY from the Scope section
- [ ] Scope item count matches what was in the input (no items added, removed, or merged)
- [ ] Section 3 is exhaustive (every submission detail included)
- [ ] Section 4 contains ALL SIX sub-sections (4.1 through 4.6)
- [ ] Section 4.3 distinguishes DISQUALIFYING from PENALIZED requirements
- [ ] Section 4.4 has 5-7 differentiators with RFP evidence for each
- [ ] Section 4.5 has exactly 3 risks with Evidence, Impact, and Mitigation for each
- [ ] Section 4.6 has 4-6 hot buttons with RFP evidence and proposal guidance for each
- [ ] No generic or boilerplate language in Section 4 — every claim tied to this specific RFP

============================================================
**SOURCE MATERIALS**
============================================================

RFP Company Description:
\"\"\"{rfp_company_text}\"\"\"

Web Search Snippets:
\"\"\"{combined_snippets}\"\"\"
"""