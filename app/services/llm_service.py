import os
import fitz  # PyMuPDF
from dotenv import load_dotenv
from openai import OpenAI
import requests
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pinecone import Pinecone
from app.models.rfp_models import User





load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX"))

def extract_text_from_pdf(pdf_file: bytes) -> str:
    text = ""
    with fitz.open(stream=pdf_file, filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def generate_search_queries(rfp_text: str) -> list:
    prompt = f"""
        You are a professional market research analyst specializing in company profiling from Request for Proposal (RFP) documents.

Your task is to generate **exactly 12 highly specific Google search queries** based solely on the RFP content provided below.

The queries must:
- Be **specific and targeted** — avoid generic terms like "about the company" or "services."
- Include **product names**, **digital platforms**, **industry-specific terms**, or **unique phrases** found in the RFP.
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
- **Additionally**, include **two targeted queries** to verify:
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
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You generate Google search queries to build complete company profiles from RFPs."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=1000
    )

    content = response.choices[0].message.content
    return [line.strip(" -•") for line in content.strip().split("\n") if line.strip()]


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



def extract_company_background_from_rfp(rfp_text: str) -> str:
    """
    Extracts 3 fully detailed sections from an RFP:
    1. Purpose of the RFP
    2. Company Background
    3. Submission Details & Requirements
    """

    prompt = f"""
You are an expert RFP analyst.

From the provided RFP text, extract **exactly three sections** in the specified order.
Do not summarize — copy the original wording wherever possible, merging sentences if needed.
NEVER place submission deadlines, contact details, or proposal instructions in Section 1 or Section 2.

### Section 1: Purpose of the RFP
- Explain why this RFP was issued.
- Include all stated and implied goals.
- Mention stakeholders or departments involved.
- Include timelines, deliverables, or strategic drivers ONLY if related to the purpose — NOT submission deadlines.

### Section 2: Company Background
- Include all background details about the issuing organization from across the document:
  - Company name
  - History and founding year
  - Locations and service areas
  - Size, ownership, or affiliations
  - Products, services, and solutions
  - Industry sectors served
  - Mission, vision, values
  - Awards, recognition, partnerships, major clients
  - Any strategic initiatives or expansions
- No submission instructions or deadlines here.

### Section 3: Submission Details & Requirements
- Copy verbatim all details about:
  - Submission due date and time
  - Deadline for submitting questions
  - Names, emails, and phone numbers for submission or questions
  - Submission method (email, portal, etc.)
  - Proposal format, structure, or mandatory contents
  - Eligibility criteria
  - Compliance or certification requirements
  - Any required attachments or forms
- If a detail is missing, explicitly state: "Not specified in RFP."

---
Section 1: Purpose of the RFP
[content]

Section 2: Company Background
[content]

Section 3: Submission Details & Requirements
[content]
---

RFP Text:
\"\"\"
{rfp_text}
\"\"\"
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You extract purpose, background, and submission details from RFPs into separate sections."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=1800
    )

    return response.choices[0].message.content.strip()




def summarize_results_with_llm(all_snippets: list, rfp_company_text: str) -> str:
    """
    Combine RFP company description and web search snippets into a
    structured, executive-level analysis with 3 fixed sections.
    """

    combined_snippets = "\n".join(all_snippets)

    prompt = f"""
You are a senior strategy consultant preparing a formal RFP analysis brief.

You are given:
1. **Company Description & Purpose** extracted from the RFP.
2. **Web search snippets** gathered from authoritative sources.

Your job: Produce a **three-part structured brief** in the exact format below.
Do not merge submission deadlines into the Purpose section — they must be in Section 3.

---
Section 1: Purpose of the RFP
[Full paragraph explanation of why the RFP was issued, its goals, scope, and strategic drivers.
Do not include submission deadlines or contacts here.]

Section 2: Company Background
[Full paragraph company profile combining RFP content and verified details from the web.
Include: company name, founding year, HQ, ownership, core offerings, markets served,
strategic initiatives, awards, major clients/partners, and market position.]

Section 3: Submission Details & Requirements
[List all operational details exactly as given in the RFP: submission due date, question deadline,
contact names/emails, submission method, required proposal contents, eligibility criteria,
special requirements. If not mentioned, write "Not specified in RFP."]
---

RFP Company Description:
\"\"\"
{rfp_company_text}
\"\"\"

Web Search Snippets:
\"\"\"
{combined_snippets}
\"\"\"
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You produce structured three-part RFP summaries with clear separation of purpose, background, and submission details."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2000
    )

    return response.choices[0].message.content.strip()



def extract_questions_with_llm(pdf_text: str) -> dict:
    prompt = f"""
You are a professional RFP analysis assistant.

Your task is to carefully review the full RFP text provided below and extract **every question, instruction, or prompt** that asks the vendor to provide a response — whether explicitly or implicitly. Focus on identifying **all response-required elements**.

###  What to extract:
- your task is extract the question section wise 
- Any question (e.g., “What is your timeline?”)
- Any instruction (e.g., “Provide your pricing breakdown.”)
- Any implied prompt (e.g., “Include case studies…” even if not phrased as a question)

###  How to organize:
Group all extracted items **by the section heading or number** (like "1.1 Scope", "2.1 What Should Your Response Contain", etc.). For each group:
- Use a clear `"section"` title from the RFP
- List response-required items using structured numbering like `"1.1"`, `"1.2"`, `"2.1"` etc. — restart numbering for each section.

###  Output Format:
{{
  "1": {{
    "section": "1.1",
    "questions": [
      "1.1 Define the brand's personality, values, mission, and vision.",
      "1.2 Describe how you will create a marketing strategy for our product suite.",
      ...
    ]
  }},
  "2": {{
    "section": "2.1 What Should Your Response Contain",
    "questions": [
      "2.1 Provide your organization’s overview and differentiators.",
      "2.2 Explain your execution approach in detail.",
      ...
    ]
  }},
  ...
}}

###  Very Important:
- Cover **all** sections that request input from vendors, including sections like “Scope,” “Proposal Requirements,” “Submission,” and “Response Format.”
- Do **not skip or summarize**. Extract each individual question/prompt explicitly.
- Do **not add** questions that are not in the text.
- Focus only on **questions/prompts meant for vendor responses**.

###  RFP Document Text:
\"\"\"
{pdf_text}
\"\"\"
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an expert assistant trained to extract structured, section-wise response prompts from RFP documents."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=2000
    )

    content = response.choices[0].message.content

    try:
        import json
        grouped_questions = json.loads(content)
    except Exception:
        grouped_questions = {"raw_text": content}

    return grouped_questions


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password):
    return pwd_context.hash(password)


def get_similar_context(question: str, top_k: int = 5) -> str:
    embedding = client.embeddings.create(
        input=[question],
        model="text-embedding-ada-002"
    ).data[0].embedding

    results = index.query(vector=embedding, top_k=top_k, include_metadata=True)

    contexts = [match['metadata']['text'] for match in results['matches']]
    return "\n".join(contexts)

def generate_answer_with_context(question: str, context: str) -> str:
    prompt = f"""Answer the following question based only on the context below:\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant generating answers for RFP questions."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=500
    )

    return response.choices[0].message.content.strip()




def query_vector_db(question: str, top_k=3):
    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    ).data[0].embedding

    results = index.query(
        vector=emb,
        top_k=top_k,
        include_metadata=True
    )
    return [match['metadata']['text'] for match in results['matches']]

def build_company_background_prompt(company_context: list[str]) -> str:
    return f"""
    You are Ringer's Assitant give the company details.

    Context:
    {chr(10).join(company_context)}
    """

def build_proposal_prompt(rfp_text: str, company_context: list[str]) -> str:
    return f"""
    You are a senior proposal writer preparing a professional response to an RFP. Base your writing on the RFP details below and our company background context. Do NOT include an Executive Summary section, as it will be provided separately.

    RFP Extract:
    {rfp_text}

    Company Knowledge Context:
    {chr(10).join(company_context)}

    Write a well-structured, persuasive proposal document with the following sections, modeled after a detailed and service-specific proposal style (e.g., clear service descriptions, cost estimates, and timeframes for each deliverable):

    1. Strategic Approach
       - Outline a methodology to meet the RFP objectives, integrating creative development, media strategy, audience research, and performance measurement.
       - Emphasize targeting diverse audiences with cultural relevance and inclusivity.
       - Highlight how the approach aligns with the client’s mission and goals.

    2. Scope of Work
       - Provide a detailed breakdown of deliverables aligned with the RFP requirements.
       - Structure deliverables as distinct services (e.g., media planning, content creation, social media consulting, playbook development, SEO support) with clear descriptions.
       - For each service, include:
         - Specific tasks or activities (e.g., market research, campaign management, content audits).
         - Expected outcomes (e.g., increased engagement, improved brand visibility).
         - Compliance considerations, if applicable (e.g., state-level regulations for social media).
       - Ensure deliverables are actionable and tailored to the client’s needs.

    3. Timeline
       - Outline high-level phases (e.g., Discovery, Development, Launch, Optimization).
       - Provide estimated durations for each phase (e.g., weeks or months).
       - Include milestones for key deliverables (e.g., playbook completion, campaign launch).

    4. Budget & Investment
       - Provide an estimated cost range for each service or deliverable, ensuring realism and transparency.
       - Avoid exact figures; use ranges or qualitative descriptions (e.g., “$5,000–$10,000” or “investment based on scope”).
       - Emphasize return on investment (ROI) and value for money, linking costs to expected outcomes.

    5. Why Us
       - Highlight key reasons to choose our company, emphasizing expertise, past successes, and unique differentiators.
       - Include 1–2 relevant case studies or success stories, if available, that align with the RFP’s goals.
       - Demonstrate alignment with the client’s mission, values, and commitment to equity or community impact.

    6. Next Steps
       - Provide a clear call-to-action for moving forward (e.g., scheduling a meeting, discussing the proposal).
       - Include placeholder contact information (e.g., [Your Company Email], [Your Company Phone Number]).

    Ensure the tone is professional, concise, and persuasive. Structure the response to resemble a service-focused proposal with itemized deliverables, cost estimates, and timeframes, similar to a consulting proposal for media planning, social media management, or playbook development. Avoid redundancy with any separately provided executive summary.
    """


def analyze_answer_score_only(question_text: str, answer_text: str) -> float:
    prompt = f"""
You are acting as a strict RFP evaluator.

Your task:
- Carefully read the question and the provided answer.
- Judge how well the answer directly addresses the question.
- Give a score from 0.0 to 10.0 based on relevance, clarity, and completeness.

Scoring Rules:
- 0.0 → No relevance or completely incorrect
- 1.0–3.0 → Very poor / barely addresses the question
- 4.0–6.0 → Partially addresses the question, with gaps
- 7.0–8.5 → Good, mostly complete but could be stronger
- 9.0–10.0 → Excellent, fully relevant and comprehensive

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

import re

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