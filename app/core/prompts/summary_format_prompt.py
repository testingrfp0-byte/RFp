def summary_format_prompt(section_num: int, rfp_company_text: str, combined_snippets: str) -> str:
    
    base_sources = f"""
SOURCE MATERIALS:
RFP Company Description: \"\"\"{rfp_company_text}\"\"\"
Web Search Snippets: \"\"\"{combined_snippets}\"\"\"
"""
    
    sections = {
        1: f"""
You are a senior RFP analyst. Extract ONLY Section 1 from the sources below.

OUTPUT: Section 1: Purpose of the RFP
- Why the RFP was issued, problems being solved, strategic goals
- Scope of Work items individually (ONLY from Scope of Work section, never from Priorities/Goals)
- Buyer Priorities & Win Themes (3-10 bullets)
- Key Phrases to Echo (3-15 verbatim quotes)

RULES:
- NO submission details, NO company background
- Never merge scope items
- Only use information from the sources

{base_sources}
""",
        2: f"""
You are a senior RFP analyst. Extract ONLY Section 2 from the sources below.

OUTPUT: Section 2: Company Background
- Full legal name, org type, founding year, headquarters, size
- Core products/services, markets served, mission/vision
- Major clients, partnerships, awards, certifications
- Label web-sourced additions as "From web sources: [detail]"

RULES:
- NO submission details, NO purpose narrative
- Only use information from the sources

{base_sources}
""",
        3: f"""
You are a senior RFP analyst. Extract ONLY Section 3 from the sources below.

OUTPUT: Section 3: Submission Details & Requirements
- Every deadline with exact dates, times, timezones
- All contact information
- Submission method, format, required documents
- Evaluation criteria with point values
- Every compliance requirement
- Minimum 30 bullet points, use exact RFP wording

RULES:
- NO company background, NO purpose narrative
- Miss nothing — check appendices, footnotes, fine print

{base_sources}
""",
        4: f"""
You are a senior RFP strategy consultant. Produce ONLY Section 4 from the sources below.

OUTPUT: Section 4: What It Will Take to Win This Pitch
You MUST produce ALL SIX sub-sections:

4.1 Core Problem — 3-5 sentences on the central challenge
4.2 Key Evaluation Criteria — ranked list with point values + 3-4 sentence interpretation
4.3 Mandatory Requirements — mark each [DISQUALIFYING] or [PENALIZED]
4.4 Winning Differentiators — 5-7 items with WHY and HOW
4.5 Risk Analysis — exactly 3 risks with Evidence, Impact, Mitigation
4.6 Hot Buttons — 4-6 themes with RFP evidence and proposal guidance

RULES:
- Every claim grounded in specific RFP evidence
- Do NOT skip any sub-section

{base_sources}
"""
    }
    
    return sections[section_num]