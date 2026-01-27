import os,fitz,requests,re,math,docx,json,io,pytesseract
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.models.rfp_models import User,KeystoneFile
from app.config import client, index,SERPAPI_KEY
from pptx import Presentation
from PyPDF2 import PdfReader
from fastapi import HTTPException
from app.models import * 
import pandas as pd
from PIL import Image

load_dotenv()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def extract_text_from_pdf(pdf_file: bytes) -> str:
    text = ""
    with fitz.open(stream=pdf_file, filetype="pdf") as doc:
        for page in doc:
            extracted_text = page.get_text()

            if extracted_text and extracted_text.strip():
                text += extracted_text
            else:
                pix = page.get_pixmap(dpi=300)
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))
                ocr_text = pytesseract.image_to_string(image)
                text += ocr_text

    if not text.strip():
        raise ValueError("Unable to extract text from PDF: possibly fully scanned or corrupted.")

    return text

def chat_model(model: str, system_prompt: str, user_prompt: str, temperature: float , max_tokens: int) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content.strip()

def generate_search_queries(rfp_text: str) -> list:
    """
    Generate exactly 12 highly targeted Google search queries based on RFP text.
    """
    user_prompt = f"""
    You are an expert market intelligence researcher specializing in analyzing companies from Request for Proposal (RFP) documents.

    Your task: Generate exactly 12 highly targeted Google search queries based only on the RFP text below.  

    The queries must:
    - Be precise, varied, and investigative.
    - Always incorporate unique identifiers from the RFP (company name, product names, technologies, industries).
    - Cover multiple areas:  
      1. Company history and ownership  
      2. Core products, services, or solutions  
      3. Industry verticals or markets served  
      4. Partnerships, clients, and case studies  
      5. Locations and employee count  
      6. Awards, recognition, and certifications  
      7. Financials, funding, or revenue (if available)  
      8. Competitors and market positioning  
      9. Technology platforms mentioned in the RFP  
      10. Recent press releases or news coverage
      11. Proposal submission requirements for this RFP
      12. Official submission due date / deadlines for this RFP

    Format:
    - Output as a bullet list, one query per line.
    - Do not add explanations — only the search queries.

    RFP Text:
    \"\"\"
    {rfp_text}
    \"\"\"
    """

    system_prompt = "You generate Google search queries to build complete company profiles from RFPs."

    content = chat_model(
        model="gpt-4o-mini",    
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.4,
        max_tokens=2000
    )

    return [line.strip(" -•") for line in content.split("\n") if line.strip()]

def extract_company_background_from_rfp(rfp_text: str) -> str:
    """
    Extracts 3 fully detailed sections from an RFP:
    1. Purpose of the RFP (including Buyer Priorities & Win Themes)
    2. Company Background
    3. Submission Details & Requirements
    """

    user_prompt = f"""
You are a senior RFP analyst with deep expertise in procurement, compliance, and government/enterprise documentation.

Your task is to extract and reorganize information from the provided RFP text into **exactly three sections**.

============================================================
**CRITICAL EXTRACTION RULES (DO NOT VIOLATE)**  
============================================================

**1. ZERO HALLUCINATIONS - EXTRACTION ONLY**  
- You are EXTRACTING, not writing. Every word must come from the RFP text.
- If information is not present in the RFP, write "No information available" for that element.
- NEVER infer, assume, add context, or use external knowledge.
- NEVER add examples, best practices, or general advice not in the RFP.
- NEVER invent company names, dates, requirements, contact details, or any data not explicitly stated.

**2. ABSOLUTE COMPLETENESS - MISS NOTHING**  
- Read the ENTIRE RFP document from beginning to end before extracting.
- Scan ALL sections including: cover page, table of contents, main body, appendices, attachments, footnotes, headers, footers, sidebars, and exhibits.
- Information is often scattered across multiple sections - systematically gather ALL occurrences.
- For each type of information (dates, contacts, requirements), search the ENTIRE document.
- If something appears multiple times with different details, include the most complete version.
- Pay special attention to:
  * Fine print and small text
  * Tables and structured data (extract ALL rows, not samples)
  * Appendices labeled "Required Forms" or "Submission Instructions"
  * Sections near the end of the document (often contain critical deadlines)

**3. VERBATIM PRESERVATION WITH COMPLETE ACCURACY**  
- Use the RFP's exact wording, terminology, and phrasing.
- Preserve ALL technical terms, acronyms, and specific requirements exactly as written.
- Copy ALL numbers, dates, times, addresses, names, phone numbers, emails, URLs EXACTLY as they appear.
- For dates: include day of week if mentioned, timezone if specified, full year.
- For contacts: include full name, title, department, phone, email, address if provided.
- For requirements: preserve exact wording including "must," "shall," "should," "required," etc.
- Only merge sentences when absolutely necessary for flow - never change meaning or lose detail.

**4. STRICT SECTION BOUNDARIES**  
- Purpose content ONLY in Section 1
- Background content ONLY in Section 2  
- Submission/procedural content ONLY in Section 3
- NO overlap between sections
- NO duplication of information

**5. SYSTEMATIC MULTI-PASS VERIFICATION**  

**First Pass - Initial Read:**
- Read entire document once to understand structure and locate information

**Second Pass - Section-by-Section Extraction:**
- Extract Section 1 content from entire document
- Extract Section 2 content from entire document  
- Extract Section 3 content from entire document

**Third Pass - Verification:**
Before finalizing, verify each checklist:

□ Section 1 Checklist:
  - Purpose statement captured
  - Problem/need identified
  - Goals and objectives listed
  - Scope of work described
  - Expected outcomes noted
  
□ Section 2 Checklist:
  - Organization name(s) captured
  - Location information included
  - Organization type identified
  - Size/scale information noted
  - Mission/values extracted (if present)
  
□ Section 3 Checklist (MOST CRITICAL):
  - ALL deadlines captured (proposal due, questions due, pre-bid meetings, etc.)
  - ALL contact information extracted (name, title, phone, email for each person)
  - Submission method clearly stated
  - ALL required documents/forms listed
  - ALL formatting requirements noted
  - ALL eligibility criteria included
  - ALL evaluation criteria captured with point values
  - Special instructions or conditions noted

□ Final Accuracy Check:
  - All dates match original exactly
  - All numbers match original exactly
  - All names match original exactly
  - No content added that isn't in source
  - No important details omitted

============================================================
**SECTION REQUIREMENTS**
============================================================

### **Section 1: Purpose of the RFP**

**COMPREHENSIVE EXTRACTION INSTRUCTIONS:**

Extract ALL content that explains WHY this RFP exists and WHAT is being procured.

**Must Include Everything From:**
- Executive Summary sections
- Introduction or Overview sections
- Background or Context sections
- Project Description sections
- Statement of Need or Problem Statement
- Purpose or Intent statements
- Objectives or Goals sections
- Scope of Work or Scope of Services
- Project Timeline or Phases (high-level)
- Expected Deliverables or Outcomes
- Strategic rationale or business case
- Stakeholder information (who benefits, who is involved)
- Funding source or budget context (ONLY when explaining purpose, not detailed budget)
- Any narrative that explains the "why" behind the procurement

**Search These Locations:**
- First 10 pages of document
- Any section titled: Purpose, Background, Introduction, Overview, Project Description, Scope, Need, Problem, Objectives
- Preamble or cover letter from issuing organization
- Executive summary

**Must Exclude From Section 1:**
- Submission deadlines, due dates, or timelines for vendors
- How to submit proposals (email, portal, address)
- Proposal formatting requirements (fonts, margins, page limits)
- Required forms or attachments to submit
- Contact information for questions
- Evaluation criteria details or scoring
- Vendor qualifications or eligibility requirements

**If no purpose found:** "No information available on the purpose of the RFP."

---

**Then add these subsections:**

**Buyer Priorities & Win Themes:**  

Extract 3-10 bullet points that reveal what the buyer values most (or fewer if insufficient data).

**Where to Search:**
- Evaluation criteria sections (look for high-point items)
- Sections with words like: "critical," "essential," "priority," "key," "must-have," "required"
- Repeated themes mentioned 3+ times in the document
- Mission/values statements from the issuing organization
- Any section describing ideal vendor characteristics
- Scoring rubrics or rating scales

**What to Extract:**
- Capabilities the buyer emphasizes repeatedly
- Values mentioned in mission/vision statements
- High-weighted evaluation criteria
- "Must-have" requirements vs "nice-to-have"
- Strategic priorities mentioned in background sections
- Themes around: quality, innovation, cost, experience, approach, collaboration, etc.

**Format as:**
- Clear, concise statements of buyer priorities
- Use RFP's language but format as actionable priorities
- Example: "Demonstrated experience with [specific technology mentioned in RFP]"
- Example: "Commitment to [specific value the buyer emphasized]"

**If none found:** "No buyer priorities or win themes identified."

---

**Key Phrases to Echo in Responses:**  

Extract 3-15 short verbatim quotes (5-30 words each) that reveal the buyer's voice, values, and expectations.

**Where to Search:**
- Mission statement sections
- Organizational values or principles
- Evaluation criteria descriptions
- Scope of work narratives
- Any section where the issuing organization describes their work, culture, or approach
- Introduction or welcome letters
- Background sections about the organization

**What to Look For:**
- How they describe their own work (e.g., "we take a methodical approach")
- What they value (e.g., "innovation and collaboration are essential")
- How they want vendors to work (e.g., "must demonstrate flexibility")
- Their organizational culture (e.g., "we prioritize community engagement")
- Their expectations (e.g., "deliverables must be evidence-based")

**Format as:**
- Each phrase in quotation marks
- Keep quotes 5-30 words maximum
- Only use EXACT quotes from the RFP
- Include attribution if from a specific section (e.g., "From Mission Statement: '...'")

**If none found:** "No key phrases identified."

============================================================

### **Section 2: Company Background**

**COMPREHENSIVE EXTRACTION INSTRUCTIONS:**

Extract EVERY detail about the organization issuing the RFP.

**Must Include All Available Information On:**

**Identity & Structure:**
- Full legal name of organization
- Common name, abbreviations, or acronyms used
- Organization type (public sector, private company, nonprofit, government agency, etc.)
- Parent organization or governing body (if applicable)
- Organizational structure or hierarchy

**Location & Geography:**
- Headquarters address (full address if provided)
- Branch locations, satellite offices, or service areas
- Geographic regions served
- Counties, cities, or jurisdictions covered

**History & Development:**
- Founding date or year established
- Key milestones in organizational history
- Historical context or evolution
- Previous names or organizational changes

**Mission & Values:**
- Mission statement (full text if provided)
- Vision statement
- Core values or guiding principles
- Strategic priorities or focus areas
- Organizational mandates or charter

**Size & Scale:**
- Number of employees or staff count
- Annual budget or revenue (if mentioned)
- Number of facilities or locations
- Service capacity or volume metrics
- Client/customer base size

**Operations:**
- Core programs or service lines
- Departments, divisions, or units
- Key operational areas or functions
- Service delivery model
- Population or community served

**Governance & Leadership:**
- Board structure or governing body
- Leadership positions mentioned
- Key executives or administrators
- Advisory committees or councils

**Partnerships & Affiliations:**
- Partner organizations or collaborators
- Professional associations or memberships
- Network affiliations
- Industry certifications or accreditations

**Recognition & Standing:**
- Awards or recognition received
- Certifications or accreditations held
- Rankings or ratings
- Notable achievements

**Strategic Context:**
- Current strategic initiatives
- Organizational priorities or goals
- Recent developments or changes
- Future plans or direction
- DEI (Diversity, Equity, Inclusion) commitments or policies

**Search These Locations Thoroughly:**
- "About Us" sections
- "Organizational Background" sections
- Cover letters or introductory narratives
- Appendices about the organization
- Headers, footers, or letterhead information
- Organizational charts or diagrams
- Any descriptive narrative about the issuing entity
- References scattered throughout the document

**Must Exclude From Section 2:**
- Project scope details (that belongs in Section 1)
- Submission requirements or procedures
- Vendor qualifications needed
- Evaluation or selection criteria
- Deadlines or contact information

**If no background:** "No company background information available."

============================================================

### **Section 3: Submission Details & Requirements**

**THIS IS THE MOST CRITICAL SECTION - ABSOLUTE COMPLETENESS REQUIRED**

**SEARCH STRATEGY:**
You MUST search the ENTIRE document for submission-related information. It may be in:
- Dedicated "Submission Requirements" sections
- "Instructions to Bidders" sections
- Appendices or exhibits
- Fine print at the end of sections
- Footnotes or sidebars
- Mixed into other sections
- Tables or checklists
- Cover pages or final pages

**Extract EVERY SINGLE:**

**DEADLINES & CRITICAL DATES:**
- Proposal submission deadline (date, time, timezone)
- Question submission deadline (date, time, timezone)
- Pre-bid conference date/time/location
- Site visit date/time/location
- Addendum release schedule
- Award notification date
- Contract start date
- Any other dates or milestones
(For each date: include day of week if mentioned, exact time, AM/PM, timezone)

**CONTACT INFORMATION (Extract ALL):**
For each contact person, capture:
- Full name
- Title or position
- Department or division
- Phone number (with extension if provided)
- Email address
- Physical address (if provided)
- Mailing address (if different)
- Website or portal URL
- Fax number (if provided)
- Preferred contact method
- Hours of availability for questions

**SUBMISSION LOGISTICS:**
- HOW to submit (email, online portal, physical delivery, courier, etc.)
- WHERE to submit (physical address, email address, portal URL)
- WHEN to submit (exact date and time)
- Number of copies required (originals vs copies, physical vs digital)
- File formats accepted (PDF, Word, Excel, etc.)
- File size limitations
- File naming conventions required
- Email subject line requirements (if email submission)
- Packaging requirements (sealed envelope, specific labeling, etc.)
- Delivery confirmation requirements
- Late submission policy

**REQUIRED DOCUMENTS & FORMS (List ALL by name):**
- Bid forms or proposal forms (with form numbers)
- Certifications required (with specific names)
- Insurance certificates (types and coverage amounts)
- Financial statements (which years, audited vs unaudited)
- Tax documents (W-9, exemption certificates, etc.)
- References or past performance (how many, what format)
- Resumes or staff qualifications (for which positions)
- Work samples or portfolio examples (how many, what type)
- Affidavits or sworn statements
- Bond forms (bid bond, performance bond, payment bond)
- Registration certificates or licenses
- Appendices or attachments to complete
- Any other forms mentioned by name or number

**PROPOSAL CONTENT REQUIREMENTS:**
- Required sections or narratives (list each)
- Executive summary requirements (length, content)
- Technical proposal requirements
- Cost proposal requirements (separate vs combined)
- Page limits (overall and by section)
- Word count limits
- Formatting specifications:
  * Font type and size
  * Margin requirements
  * Line spacing
  * Paper size
  * Single vs double-sided
  * Binding requirements
- Table of contents requirements
- Page numbering requirements
- Section organization or order
- Cover page requirements
- Appendix limitations

**ELIGIBILITY & COMPLIANCE:**
- Vendor registration requirements (where to register, by when)
- Business licensing requirements
- Professional certifications required
- Insurance requirements (types: general liability, professional liability, workers comp, etc.)
  * Coverage amounts for each type
  * Certificate holder information
- Bonding requirements (bid bond, performance bond amounts)
- Minimum years in business
- Minimum project experience
- Geographic restrictions or preferences
- Size standards (small business, MBE/WBE, etc.)
- Conflict of interest disclosures
- Debarment certifications
- Background check requirements
- Subcontractor disclosure rules (who, when, how to disclose)
- Joint venture requirements
- Minimum qualifications checklist
- Disqualification criteria
- Mandatory requirements vs preferences

**EVALUATION & SELECTION:**
- Evaluation criteria (list each criterion)
- Point allocations or weights for each criterion
- Total points possible
- Minimum score to advance
- Scoring methodology or rubric
- Evaluation phases or stages
- Selection committee composition
- Selection process timeline
- Award decision factors
- Tie-breaking procedures
- Negotiation process (if applicable)
- Best and Final Offer (BAFO) process
- Interview or presentation requirements
- Protest procedures or appeal rights
- Award notification method

**QUESTIONS & CLARIFICATIONS:**
- How to submit questions (email, portal, written)
- Question deadline (date and time)
- Where questions will be answered (addendum, website, email)
- Format for questions
- Anonymous vs attributed questions
- Addendum release schedule
- How addenda will be distributed

**SPECIAL CONDITIONS & REQUIREMENTS:**
- Confidentiality or non-disclosure requirements
- Proprietary information marking procedures
- Public records disclosure notices
- Freedom of Information Act (FOIA) notices
- Contract terms preview or sample contract
- Payment terms (net 30, progress payments, etc.)
- Invoice requirements
- Performance requirements or KPIs
- Reporting obligations (what, when, to whom)
- Site visit requirements (mandatory vs optional)
- Attendance requirements (pre-bid conference, etc.)
- Sustainability or environmental requirements
- Local hiring or preference requirements
- Prevailing wage requirements
- Equal opportunity or affirmative action requirements
- Accessibility requirements (ADA, Section 508, etc.)
- Data security or privacy requirements
- Background check or clearance requirements
- Drug testing requirements
- Any other special terms, conditions, or requirements

**BUDGET & PRICING:**
(Only include if these are submission requirements, not project budget)
- Cost proposal format required
- Pricing sheet or template to use
- What cost elements to include/exclude
- Separate pricing for optional services
- Unit pricing requirements
- Not-to-exceed amounts or budget caps

**Format Requirements for Section 3:**
- Present as a comprehensive bullet list
- Each bullet should be a complete, clear requirement
- Use exact wording from RFP whenever possible
- Group related items together for clarity
- Include ALL details for each item (don't summarize)
- If a requirement has multiple parts, include all parts
- If unclear, include the exact RFP language

**Example Format:**
- Proposal due date: [exact date, time, timezone as stated in RFP]
- Primary contact: [Full Name, Title, Phone, Email as stated]
- Submission method: [exact method as described in RFP]
- Required documents: [list each by exact name]
- Insurance required: [exact types and amounts as stated]
- Evaluation criteria: [each criterion with point value]
- [Continue for ALL requirements found]

**If any requirement is unclear or ambiguous:** Include it anyway using the exact RFP language.

**If no details found:** "No submission details or requirements available."

============================================================
**OUTPUT FORMAT (STRICT)**
============================================================

Section 1: Purpose of the RFP  
[Comprehensive, detailed extraction of why this RFP was issued and what is being procured. Written in flowing paragraphs using the RFP's own language. Include ALL relevant context from the entire document.]

Buyer Priorities & Win Themes:  
- [Priority 1 - based on RFP text with specific examples]  
- [Priority 2 - based on RFP text with specific examples]  
- [Continue for all priorities identified, minimum 3, maximum 10]

Key Phrases to Echo in Responses:  
- "[Exact verbatim quote 1 from RFP]"  
- "[Exact verbatim quote 2 from RFP]"  
- [Continue for all key phrases found, minimum 3, maximum 15]

Section 2: Company Background  
[Comprehensive, detailed extraction of ALL information about the issuing organization. Written in flowing paragraphs. Cover every aspect listed in the requirements. Leave no detail unmentioned.]

Section 3: Submission Details & Requirements  
[Exhaustive bullet list of EVERY procedural, administrative, and compliance requirement found in the entire document. Each requirement stated clearly and completely. Nothing omitted. Organized by category for clarity.]

- [Requirement 1 with full details]
- [Requirement 2 with full details]
- [Requirement 3 with full details]
- [Continue for ALL requirements - typically 30-100+ items for comprehensive RFPs]

============================================================
**FINAL PRE-SUBMISSION VERIFICATION**
============================================================

Before submitting your extraction, answer these questions:

1. Did you read the ENTIRE RFP document from first page to last page? □
2. Did you check ALL appendices and attachments? □
3. Did you extract information from tables and structured data? □
4. Did you capture ALL dates mentioned anywhere in the document? □
5. Did you capture ALL contact information from anywhere in the document? □
6. Is Section 3 exhaustive (not just a sample of requirements)? □
7. Did you preserve exact wording for all critical details? □
8. Did you verify all numbers, dates, and names against the source? □
9. Did you avoid adding ANY information not in the source? □
10. Did you check that each section contains ONLY its designated content type? □

If any answer is NO, review the document again before finalizing.

============================================================
**SOURCE RFP TEXT**
============================================================
\"\"\"{rfp_text}\"\"\"

CRITICAL REMINDER: 
- You are EXTRACTING existing content, not creating new content.
- Every fact, date, name, number must come from the source text.
- Section 3 must be EXHAUSTIVE - this is where 70% of critical information lives.
- Missing a single deadline or requirement could disqualify a proposal.
- Your extraction must be so complete that someone could respond to this RFP using ONLY your output.
"""

    system_prompt = (
        "You are a meticulous RFP extraction specialist with perfect attention to detail. "
        "Your extractions are comprehensive, accurate, and complete. You NEVER add information "
        "not present in the source document. You NEVER miss important details. You read entire "
        "documents systematically and extract every relevant piece of information. Your Section 3 "
        "extractions are especially thorough, capturing every single submission requirement. "
        "You work methodically through checklists to ensure nothing is overlooked."
    )

    return chat_model(
        model="gpt-4o-mini",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=4000  # Increased to handle comprehensive extractions
    )


def summarize_results_with_llm(all_snippets: list, rfp_company_text: str) -> str:
    """
    Combine RFP company description and web search snippets into a
    structured, executive-level analysis with 3 fixed sections.
    
    """

    combined_snippets = "\n".join(all_snippets)

    user_prompt = f"""
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
- Check both sources thoroughly before finalizing, including forms, templates, appendices, footnotes, and any structured data like bid contracts
- For universal applicability: Treat all RFP structures (e.g., forms, tables, scattered notes) as critical - extract every detail regardless of format

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

============================================================
**SECTION-SPECIFIC INSTRUCTIONS**
============================================================

### Section 1: Purpose of the RFP

**Content to Include:**
- Why the RFP was issued (explicit purpose statements)
- Problems being solved or needs being addressed
- Strategic goals and desired outcomes
- Project scope and deliverables expected - include ALL details from Scope of Work sections, including sub-bullets, phases, and specific requirements verbatim
- Expected impact or benefits
- Context that explains the procurement decision
- Buyer Priorities & Win Themes: Extract and list ALL (up to 10) as bullets, including any inferred from evaluation criteria, repeated themes, or requirements
- Key Phrases to Echo in Responses: Extract and list ALL (up to 15) verbatim quotes as bullets

**Content to EXCLUDE:**
- Submission deadlines, contacts, or procedures
- Proposal formatting requirements
- Company background information
- How to submit or what forms are needed

**Format:** 
Write the main purpose as flowing paragraphs with blank lines between them.
Then, add the Buyer Priorities & Win Themes and Key Phrases subsections as bullet lists.
Be comprehensive - do not condense; include every sub-detail from the source.

### Section 2: Company Background

**Primary Source:** RFP company text
**Secondary Source:** Web snippets (only verified, relevant details)

**Must Include All Available Information On:**
- Full legal name and any common names/abbreviations
- Organization type and structure
- Founding year and history
- Headquarters and locations
- Ownership structure (public/private/government)
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
- Add web information if it appears in at least one snippet and is relevant/complements RFP data - note the source (e.g., "From web sources: [detail]")
- If unverified or from a single source, still include but note: "Unverified from single web source: [detail]"
- If web data conflicts with RFP, note the discrepancy
- For universal RFPs: If RFP lacks background, use web snippets to build a complete profile where possible

**Format:**
Write as comprehensive paragraphs with blank lines between them.
Create a complete company profile.

### Section 3: Submission Details & Requirements

**THIS IS THE MOST CRITICAL SECTION - MISS NOTHING**

**Extract EVERY SINGLE:**
- Deadline (proposal due, questions due, any other dates)
- Contact (names, titles, emails, phones, addresses, hours of availability)
- Submission method (email, portal, physical, courier)
- Required format (file type, number of copies, binding, labeling)
- Mandatory form or document by name - include ALL sub-details and fields from forms/templates (e.g., bid contract fields like bidder type, options, signatures)
- Eligibility requirement or prerequisite
- Proposal content requirement (sections, page limits, formatting) - include ALL sub-requirements for each section
- Evaluation criterion or scoring factor - include weights and descriptions
- Special instruction or condition (e.g., cancellation policies, payment terms, tax exemptions)
- Compliance requirement
- Any other procedural notes, including from forms, fine print, or scattered sections

**Search thoroughly:**
- Main submission sections
- Fine print and footnotes
- Appendices about submission
- Scattered procedural notes throughout RFP, including bid forms and contracts
- Integrate relevant web snippets (e.g., updated deadlines from official sites) and note: "From web sources: [detail]"

**Format Requirements:**
- Present as a bullet list
- Each bullet should be a complete requirement, using exact wording from RFP when possible
- Group related items for clarity (e.g., sub-bullets for form fields)
- Be exhaustive - include every detail, aiming for 30-100+ items if present in complex RFPs
- If a requirement has multiple parts, use sub-bullets

**If any requirement is unclear:** Include it anyway with the exact RFP language

============================================================
**OUTPUT FORMAT**
============================================================

**Section 1: Purpose of the RFP**
[Comprehensive explanation of why this RFP exists, what it aims to achieve, and what is being procured. Written in flowing paragraphs. Include ALL scope details.]

Buyer Priorities & Win Themes:  
- [Priority 1 - based on RFP text with specific examples]  
- [Priority 2 - based on RFP text with specific examples]  
- [Continue for all priorities identified, minimum 3, maximum 10]

Key Phrases to Echo in Responses:  
- "[Exact verbatim quote 1 from RFP]"  
- "[Exact verbatim quote 2 from RFP]"  
- [Continue for all key phrases found, minimum 3, maximum 15]

**Section 2: Company Background**
[Complete company profile combining RFP content and verified web data. Covers organization name, type, size, history, offerings, markets, strategic direction, and market position. Written in flowing paragraphs.]

**Section 3: Submission Details & Requirements**
[Exhaustive bullet list of every procedural, administrative, and compliance requirement. Each requirement clearly stated.]

- [Requirement 1]
- [Requirement 2]
- [Requirement 3]
[... continue for ALL requirements found]

============================================================
**FINAL VERIFICATION CHECKLIST**
============================================================

Before submitting, verify:
- [ ] No information added beyond the sources
- [ ] All important details from both RFP and web included, including all sub-details and forms
- [ ] All dates, numbers, names match sources exactly
- [ ] Conflicting information is noted, not merged
- [ ] Section 3 is exhaustive (every submission detail included)
- [ ] Plain text formatting (no markdown bold/asterisks except in output headers)
- [ ] Blank lines between paragraphs in Sections 1 and 2
- [ ] Universal handling: All RFP elements (forms, scattered info) extracted

============================================================
**SOURCE MATERIALS**
============================================================

RFP Company Description:
\"\"\"{rfp_company_text}\"\"\"

Web Search Snippets:
\"\"\"{combined_snippets}\"\"\"
"""

    system_prompt = (
        "You are a meticulous RFP analyst who produces structured three-section summaries. "
        "You extract and organize information with perfect accuracy, never adding content not in the sources. "
        "You ensure Section 3 captures every single submission requirement without exception. "
        "Your output is comprehensive, accurate, and properly formatted for any RFP document."
    )

    return chat_model(
        model="gpt-4o-mini",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.5,  # Increased for better synthesis without hallucinations
        max_tokens=4000   # Increased to handle larger RFPs
    )


def search_with_serpapi(query: str):
    url = "https://serpapi.com/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY
    }
    res = requests.get(url, params=params)
    data = res.json()

    results = []
    if "organic_results" in data:
        for item in data["organic_results"][:5]:
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet")
            })
    return results

def extract_questions_with_llm(pdf_text: str) -> dict:
    prompt = f"""
You are an RFP Proposal Response Extraction Specialist.

Extract ONLY the **questions that require the vendor to write a narrative answer** in the proposal.

 Must Include:
- “Please explain…”
- “Describe…”
- “Provide details…”
- “How will you…”
- “What is your approach…”
- Response instructions inside Proposal Requirements sections

 Must NOT Include:
- Any operational capabilities explanations
- Any vendor qualifications like “Vendor must have…”
- Any instructions not requiring a written answer
- Submission/admin details
- Repetitive generic requirements

 Mandatory Formatting Rules:
- Group by correct RFP sections
- Only include sections that contain QUESTIONS
- Number questions sequentially inside each section:
  Example: 1.1, 1.2, 1.3 … then 2.1, 2.2 …
- Questions MUST be **full sentences** ending with a '?'

 Required JSON Output ONLY:
{{
  "1": {{
    "section": "Section Title",
    "questions": [
      "1.1 Actual question text?",
      "1.2 Another question?"
    ]
  }}
}}

 Source RFP Text:
\"\"\"{pdf_text}\"\"\"
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
             "content": "Return ONLY strict valid JSON. No markdown. No commentary."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=3000,
    )

    content = response.choices[0].message.content.strip()
    content = content.replace("```json", "").replace("```", "").strip()

    try:
        grouped_questions = json.loads(content)
    except Exception:
        raise HTTPException(status_code=500,
                            detail="AI returned invalid JSON for extracted questions.")

    if not isinstance(grouped_questions, dict):
        raise HTTPException(status_code=500,
                            detail="Questions JSON must be an object.")

    for k, v in grouped_questions.items():
        if not isinstance(v, dict):
            raise HTTPException(status_code=500,
                                detail=f"Invalid section {k}")
        if "section" not in v or "questions" not in v:
            raise HTTPException(status_code=500,
                                detail=f"Missing keys in section {k}")

    return grouped_questions

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password):
    return pwd_context.hash(password)

def get_similar_context(question: str, rfp_id: int, top_k: int = 5):
    """
    Retrieve RFP-specific chunks from Pinecone using file_id metadata filter.
    """
    try:
        embedding = client.embeddings.create(
            input=[question],
            model="text-embedding-3-small"
        ).data[0].embedding

        results = index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            filter={"file_id": str(rfp_id)}
        )

        context_texts = [match["metadata"]["text"] for match in results["matches"]]
        sources = [
            {
                "score": match["score"],
                "file_id": match["metadata"].get("file_id"),
                "chunk_index": match["metadata"].get("chunk_index"),
                "snippet": match["metadata"].get("text")[:300],
            }
            for match in results["matches"]
        ]

        return "\n".join(context_texts), sources

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pinecone retrieval failed: {str(e)}")

def generate_answer_with_context(question: str, context: str, short_name: str) -> str:
    prompt = f"""
    You are an expert proposal writer. You write RFP responses using the provided context and verified company information if available.

    ### ⭐ Keystone Data Rule (IMPORTANT)
    - If the context includes a section titled "Company Information", 
      then use that information to support factual company details (e.g., legal name, number of employees, certifications).
    - Incorporate this information naturally into the response when relevant.
    - Do NOT hallucinate or invent company information. Use only what is explicitly provided.

    ### Mandatory RFP Usage Rule
    - Always reference and pull specific details from the provided RFP context.
    - Use the RFP's exact requirements, instructions, constraints, and expectations whenever answering.
    - Answers MUST be specific and directly tied to what {short_name} is asking for in the RFP.
    - Do not give generic responses. Always anchor your answer to the RFP text.

    ### Client Name Rule (MANDATORY)
    - Refer to the issuer exclusively as "{short_name}".
    - Never use “the client”.
    - Never guess or invent a different name.

    ### Voice & Point of View (MANDATORY)
    - Use “we” or “our”.
    - Never use “I”.
    - Never refer to Ringer in third person.

    ### Pricing Rules (MANDATORY)
    - Ringer uses flat-rate pricing only.
    - Never mention hourly rates, per-hour billing, or hourly estimates.
    - Do NOT generate or assume any hourly cost structure.
    - If the context mentions hourly pricing, rewrite it into a flat-rate model without creating specific prices.

    ### Subcontractor / Vendor Operating Model (MANDATORY)
    - Ringer delivers services through subcontractors and external vendors.
    - This is a core part of how Ringer operates.
    - When describing service delivery, staffing, capabilities, or processes:
        - reflect that subcontractors/vendors are used.
        - never imply Ringer relies solely on in-house full-time staff.

    ### Accuracy Rules
    - Use ONLY the information in the context and Company Information.
    - If the context lacks the information, write:
      “We do not have enough information to provide that detail based on the available context and company data.”

    ### Tone & Style
    - Professional, concise, confident, accurate and covers all important points.
    - No vague marketing language.

    ### Concise Writing Rules
    - Short, direct sentences.
    - Active voice.
    - No filler phrases.

    ### Formatting
    - No bullet points unless context explicitly requires it.
    - Do NOT mention “context” or “question”.

    ----
    
    Context:
    {context}

    Question:
    {question}

    Final Answer:
    """
 
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional highly skilled RFP response specialist who strictly follows instructions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")

def analyze_answer_score_only(question_text: str, answer_text: str) -> float:
    prompt = f"""
You are acting as a strict RFP evaluator.

Your task:
- Carefully read the question and the provided answer.
- Judge how well the answer directly addresses the question.
- Give a score from 0.0 to 10.0 based on relevance, clarity, and completeness.

Scoring Rules:
- 0.0 → No relevance or completely incorrect
- 1.0-3.0 → Very poor / barely addresses the question
- 4.0-6.0 → Partially addresses the question, with gaps
- 7.0-8.5 → Good, mostly complete but could be stronger
- 9.0-10.0 → Excellent, fully relevant and comprehensive

 Output Instruction:
Return ONLY the numeric score as a float (e.g., `7.5`, `9.0`, `0.0`). 
Do NOT include words, labels, or explanations.

Question: {question_text}

Answer: {answer_text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    score_text = response.choices[0].message.content.strip()
    try:
        return float(score_text)
    except ValueError:
        return None

def parse_rfp_summary(summary_text: str):
    """
    Convert LLM markdown summary into structured JSON:
    {
      "purpose": "...",
      "company_background": "...",
      "submission_details": {
          "text": "...",
          "bullets": ["...", "...", ...]
      }
    }
    """
    summary_text = re.sub(r"^#+\s*RFP Analysis Brief\s*", "", summary_text, flags=re.IGNORECASE)

    sections = re.split(r"####\s*Section\s*\d:\s*", summary_text)
    sections = [s.strip() for s in sections if s.strip()]

    if len(sections) < 3:
        return {
            "purpose": summary_text,
            "company_background": "",
            "submission_details": {"text": "", "bullets": []}
        }

    submission_text = sections[2]
    bullet_lines = re.findall(r"-\s\*\*(.*?)\*\*|-\s+(.*)", submission_text)

    bullets = []
    for b1, b2 in bullet_lines:
        bullet = b1 if b1 else b2
        if bullet and bullet.strip():
            bullets.append(bullet.strip())

    return {
        "purpose": sections[0],
        "company_background": sections[1],
        "submission_details": {
            "text": submission_text,
            "bullets": bullets
        }
    }

def extract_text_from_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    text = ""

    if ext == ".pdf":
        reader = PdfReader(file_path)
        text = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
    elif ext == ".docx":
        doc = docx.Document(file_path)
        text = " ".join([p.text for p in doc.paragraphs])
    elif ext == ".pptx":
        prs = Presentation(file_path)
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + " "
    elif ext in [".xls", ".xlsx"]:
            xls = pd.ExcelFile(file_path)
            for sheet in xls.sheet_names:
                df = xls.parse(sheet)
                text += "\n".join(
                    df.fillna("").astype(str).agg(" ".join, axis=1)
                ) + "\n" 
    return text.strip()

def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def generate_summary(text: str) -> str:
    """Generate summary of an RFP using LLM."""
    prompt = f"Summarize the following RFP in 3-5 paragraphs:\n\n{text[:8000]}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an RFP summarizer."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def delete_rfp_embeddings(file_id: int):
    try:
        results = index.query(
            vector=[0.0] * 1536,
            top_k=10000,   
            include_metadata=False,
            filter={"file_id": str(file_id)}
        )

        vector_ids = [match["id"] for match in results.get("matches", [])]
        if vector_ids:
            index.delete(ids=vector_ids)
            print(f" Deleted {len(vector_ids)} Pinecone vectors for file_id {file_id}")
        else:
            print(f" No Pinecone vectors found for file_id {file_id}")

    except Exception as e:
        print(f" Error deleting embeddings for RFP {file_id}: {e}")

def get_short_name(filename: str) -> str:
    """
    Extract short client name from PDF filename.
    Examples:
        'McLean_Hospital_RFP.pdf' -> 'McLean'
        'Acme_Inc_Submission.pdf' -> 'Acme'
        'State_of_California_Dept_Health.pdf' -> 'California'
    """
    name = filename.rsplit('.', 1)[0]

    name = name.replace('_', ' ').replace('-', ' ')

    tokens = name.split()

    noise = {
        "hospital", "inc", "llc", "ltd", "company", "co", "services",
        "dept", "department", "state", "university", "institute",
        "health", "center", "centre", "proposal", "rfp", "submission"
    }

    cleaned = [t for t in tokens if t.lower() not in noise]

    if not cleaned:
        return "the organization"
    return cleaned[0].title()

def bump_version(version: str) -> str:
    if not isinstance(version, str) or not version.strip():
        return None

    parts = version.strip().split(".")

    if not all(p.isdigit() for p in parts):
        return None

    if len(parts) == 1:
        (major,) = map(int, parts)
        return str(major + 1)

    if len(parts) == 2:
        major, minor = map(int, parts)
        return f"{major}.{minor + 1}"

    if len(parts) == 3:
        major, minor, patch = map(int, parts)
        return f"{major}.{minor}.{patch + 1}"

    return None

def get_next_index(rfp_id: int, user_id: int, question: str, db: Session) -> float:
    last_question = (
        db.query(RFPQuestion)
        .filter(
            RFPQuestion.rfp_id == rfp_id,
            RFPQuestion.admin_id == user_id
        )
        .order_by(RFPQuestion.id.desc())
        .first() 
    ).question_text

    index = last_question.split(" ")[0] if last_question else None

    new_index = None
    if index:
        try:
            new_index = bump_version(index)
        except Exception as e:
            new_index = ""
    
    return f"{new_index} {question}"

def clean_extracted_text(text: str) -> str:
    """
    Clean up common PDF/OCR noise so LLM gets better input.
    - Removes obvious page markers
    - Normalizes line breaks and extra spaces
    """
    text = re.sub(r"Page\s+\d+\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()

def get_active_keystone_text(db: Session, admin_id: int) -> str:
    keystone = db.query(KeystoneFile).filter(
        KeystoneFile.admin_id == admin_id,
        KeystoneFile.is_active == True
    ).first()

    if not keystone:
        raise HTTPException(
            status_code=400,
            detail="Keystone Data not uploaded. Please upload Keystone XLS."
        )

    return keystone.extracted_text

def extract_xls_text(file_path: str) -> str:
    sheets = pd.read_excel(file_path, sheet_name=None)
    output = []

    for sheet_name, df in sheets.items():
        output.append(f"\n=== {sheet_name} ===\n")
        for _, row in df.iterrows():
            row_text = " | ".join(
                str(cell) for cell in row if pd.notna(cell)
            )
            if row_text.strip():
                output.append(row_text)

    return "\n".join(output)
