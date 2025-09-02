import os
import fitz  # PyMuPDF
from dotenv import load_dotenv
from openai import OpenAI
import requests
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pinecone import Pinecone
from app.models.rfp_models import User
import re




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
        
        -not include the repeated the headings 


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
        max_tokens=2000
    )

    return response.choices[0].message.content.strip()


def summarize_results_with_llm(all_snippets: list, rfp_company_text: str) -> str:
    """
    Combine RFP company description and web search snippets into a
    structured, executive-level analysis with 3 fixed sections.
    Ensures Submission Details & Requirements are comprehensive,
    accurate, and formatted as a bullet list with clean spacing.
    """

    combined_snippets = "\n".join(all_snippets)

    prompt = f"""
        You are a senior strategy consultant preparing a formal RFP analysis brief.
        
        Critical formatting & content rules:
        - Produce exactly 3 sections in the order below.
        - Insert a blank line between paragraphs for readability.
        - In Section 3, extract *all* requirements and details from the RFP, even if they appear in multiple places.
        - Section 3 must be presented as a bullet list with each requirement on its own line.
        - Do not paraphrase or omit submission requirements — quote or restate them faithfully.
        - Do not place deadlines or contacts in Section 1; only in Section 3.

        ---
        **Section 1: Purpose of the RFP**
        [Full paragraph explanation of why the RFP was issued, its goals, scope, and strategic drivers.
        Exclude submission deadlines and contacts here.]\n\n

        **Section 2: Company Background**
        [Full paragraph company profile combining RFP content and verified details from the web.
        Include: company name, founding year, HQ, ownership, core offerings, markets served,
        strategic initiatives, awards, major clients/partners, and market position.]\n\n

        **Section 3: Submission Details & Requirements**
        [Bullet list of every requirement and operational detail from the RFP,
        including submission due date, question deadline, contact names/emails,
        submission method, required proposal contents, eligibility criteria,
        and any special instructions or conditions. ]\n\n
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
            {
                "role": "system",
                "content": (
                    "You produce structured three-part RFP summaries. "
                    "Always include every submission detail in Section 3, formatted as a bullet list. "
                    "Maintain clear formatting with line breaks after paragraphs."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content.strip()


def extract_questions_with_llm(pdf_text: str) -> dict:
    prompt = f"""
        You are a professional RFP analysis assistant.

        Task:
        Extract every **question, instruction, or prompt** from the RFP text that requires a vendor response. 

         Do not:
        - Summarize, rewrite, shorten, or change the wording.
        - Add or infer questions that are not explicitly in the RFP.
        - Include context-only text (Introductions, Needs Statements, Goals, Overviews).
        -do not include the unnecessary questions like 'response submitted at '

        Not:
        - not include the unnecessary question like must be submitted via e-mail,

         Do:
        - Capture each item **exactly as written** in the RFP (verbatim).
        - Preserve section hierarchy and numbering.
        - If a section is "1.2 Proposal Requirements", the questions must be numbered "1.2.1", "1.2.2", etc.
        - Restart question numbering inside each section.
        - Group questions by section heading/number.
        - Always prefix questions with their section number.

        Output format:
        Strict JSON only, no Markdown or commentary.

        Example:
        {{
          "1": {{
            "section": "1.1 Scope",
            "questions": [
              "1.1.1 Define the brand's personality, values, mission, and vision.",
              "1.1.2 Describe how you will create a marketing strategy for our product suite."
            ]
          }},
          "2": {{
            "section": "2.1 Proposal Requirements",
            "questions": [
              "2.1.1 Provide your organization’s overview and differentiators.",
              "2.1.2 Explain your execution approach in detail."
            ]
          }}
        }}

        RFP Document Text:
        \"\"\"
        {pdf_text}
        \"\"\"
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert assistant trained to extract structured, "
                    "section-wise response prompts from RFP documents. "
                    "Always return clean JSON with no extra formatting. "
                    "Never modify, summarize, or rephrase the RFP text."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,  # enforce deterministic extraction
        max_tokens=2000,
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


def query_vector_db(question: str, top_k=8):
    """
    Query the vector database for relevant context.
    """
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
    """
    Build a prompt to summarize all available Ringer details.
    """
    return f"""
    You are Ringer's Senior Proposal Assistant. 
    Summarize ALL available details about Ringer clearly, concisely, and professionally. 

    Context includes past proposals, service offerings, methodologies, playbooks, 
    case studies, pricing estimates, and SEO/social media support. 
    Extract and include everything relevant to demonstrate Ringer’s full capabilities.

    Also:
    - Extract the client name (and email/contact if available) from the RFP context. 
    - Present Ringer’s capabilities in a polished background section. 
    - Emphasize consulting services, media planning, playbook development, 
      social media strategy, SEO, analytics, reporting, and training. 
    - Integrate relevant past work examples (from the context).
    - Avoid repetition — make it narrative and professional.

    Context:
    {chr(10).join(company_context)}

    provide short and consice summary 

    Provide the final output as a professional "Company Background & Capabilities" 
    section suitable for an RFP proposal.
    """


def build_proposal_prompt(rfp_text: str, company_context: str, case_studies: list[str] = None) -> str:
    """
    Build a structured proposal prompt to generate a concise, persuasive proposal.
    Includes Ringer’s service details and optional case studies.
    """
    case_study_text = "\n".join(case_studies) if case_studies else "No case studies provided."

    return f"""
    You are a senior proposal writer creating a complete, professional, and concise RFP response. 
    Use the RFP extract, enriched company background, and case studies (if available).
    Do NOT include an Executive Summary (it will be added separately).

    --- RFP Extract ---
    {rfp_text}

    --- Enriched Company Background (from vector DB) ---
    {company_context}

    --- Case Studies (Optional) ---
    {case_study_text}

    Write a structured, **short and direct** proposal with the following sections:

    1. Strategic Approach  
       - Clear methodology to meet client goals.  
       - Cover creative, media, SEO, compliance, performance tracking.  
       - Show Ringer’s workshops, phased strategies, co-creation.  

    2. Scope of Work  
       - List service modules (media planning, content, playbooks, SEO, training).  
       - For each: Tasks, Outcomes, Compliance notes.  
       - Reference past successes where relevant.  

    3. Timeline  
       - Use phases (Discovery, Development, Launch, Optimization).  
       - Give estimated weeks/months + milestones.  

    4. Budget & Investment  
       - Show ranges (not exact).  
       - Link investments to services.  
       - Explain ROI/value.  
       - Emphasize flexibility.  

    5. Why Us  
       - Highlight Ringer’s strengths + differentiators.  
       - Insert case studies where relevant.  
       - Stress expertise in media, social, SEO, training, analytics.  

    6. Next Steps  
       - Suggest clear follow-up actions (e.g., discovery call).  
       - Leave placeholders for contact info.  

    Notes:  
    - Tone: Professional, persuasive, client-focused.  
    - Keep sentences concise and avoid redundancy.  
    - Always deliver a complete proposal.  
    - Align with client’s language where possible.  
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

def query_company_background(company_name: str, top_k=5):
    """
    Query the vector DB for company-specific background and capabilities.
    """
    question = f"Provide background, capabilities, and relevant details about {company_name}"
    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    ).data[0].embedding

    results = index.query(
        vector=emb,
        top_k=top_k,
        include_metadata=True,
        filter={"company_name": company_name}  
    )

    return [match['metadata']['text'] for match in results['matches']]

def summarize_company_background(company_name: str, context_chunks: list[str]) -> str:
    """
    Summarize retrieved chunks into a clean Company Background section.
    """
    joined_context = "\n".join(context_chunks)

    prompt = f"""
    You are a proposal assistant. Summarize the following context into a concise,
    professional company background and capabilities section for {company_name}.
    
    Context:
    {joined_context}

    Provide a clear and polished summary in paragraph form.
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()










