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
import docx
from pptx import Presentation
from PyPDF2 import PdfReader


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX"))
index_ringer = pc.Index(os.getenv("PINECONE_INDEX_RINGER"))

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

        Your task is to extract and organize information from the provided RFP text into exactly **three sections**, preserving the original wording wherever possible.  

         **General Rules**
        - DO copy text verbatim whenever possible. Only merge sentences if needed for readability.  
        - DO capture *every relevant item* across the full RFP — even if details appear scattered in multiple sections.  
        - DO consolidate related information into the correct section.  
        - DO include stakeholder names, budgets, goals, and priorities in context.  
        - DO NOT add, infer, or hallucinate information.  
        - DO NOT omit details.  
        - DO NOT duplicate section headings from the RFP itself.  
        - DO NOT place submission deadlines, addresses, or instructions in Section 1 or Section 2.  

        ---

        ### Section 1: Purpose of the RFP
        - Extract the stated purpose and intent of issuing the RFP.  
        - Include goals, objectives, and desired outcomes.  
        - Capture stakeholders, sponsoring departments, or partner organizations.  
        - Mention scope of services, strategic drivers, or future plans *only if tied to purpose*.  
        - Exclude submission deadlines, contacts, or proposal instructions.  

        ### Section 2: Company Background
        - Extract **all organizational background** about the issuer. This may appear in multiple parts of the RFP.  
        - Include details such as:
        - Full name of issuing organization (legal name if provided).  
        - Location(s): headquarters, offices, or areas served.  
        - Organizational type (public, private, nonprofit, government).  
        - History, mission, vision, or strategic priorities.  
        - Size, funding levels, budgets, or resources mentioned.  
        - Services, programs, or industries the organization supports.  
        - Partnerships, stakeholders, or governance structures.  
        - Diversity, equity, or inclusion priorities (if stated).  
        - Consolidate into clear narrative paragraphs.  
        - Exclude submission instructions, requirements, or deadlines.  

        ### Section 3: Submission Details & Requirements
        - Copy verbatim **all procedural and compliance requirements**, including:  
        - Submission deadlines, times, and locations.  
        - Where and how to submit (mail, email, portal, hard copy, flash drive, etc.).  
        - Contacts for submission or questions (names, titles, phone, email).  
        - Proposal format, length limits, structure, required attachments/forms.  
        - Eligibility, compliance, or certification requirements.  
        - Contract terms, evaluation criteria, or selection process details.  
        - If requirements appear in multiple parts of the RFP, merge them into one complete section.  

        ---

         **Output Format:**
        Return the extracted content in the following exact structure:

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
        max_tokens=2200
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
        
        Critical Formatting & Content Rules:
        - Produce exactly three sections in the order specified: Purpose of the RFP, Company          Background, and Submission Details & Requirements.
        - Insert a blank line between paragraphs in Sections 1 and 2 for readability.
        - In Section 3, extract **all** submission-related details and requirements from the RFP, even if scattered across multiple sections or repeated.
        - Present Section 3 as a bullet list, with each requirement or detail on its own line, quoted or restated verbatim to preserve the original wording and intent.
        - Do not paraphrase, summarize, or omit any submission requirements in Section 3.
        - Exclude submission deadlines, contact details, or procedural instructions from Section 1 and Section 2.
        - Use information from web snippets to enhance Section 2 (Company Background) only if it is verified, relevant, and complements the RFP content.
        - If information is missing for any section, include a note stating: "No relevant information provided in the RFP or web snippets."
        - If conflicting information exists (e.g., between RFP and snippets), prioritize RFP data and note discrepancies in Section 2 (e.g., "Web snippets suggest [X], but RFP states [Y]").
        - Ensure the output is professional, concise, and avoids redundancy while maintaining all required details
        
        
        Do Not:
        - Include submission deadlines, contact details, or procedural instructions in Section 1 or Section 2.
        - Paraphrase or modify submission requirements in Section 3; use exact wording or faithful restatements.
        - Introduce speculative or unverified information not present in the RFP or web snippets.
        - Use Markdown or other formatting (e.g., bold, asterisks) in the output; use plain text with the exact section headings provided.
        - Repeat section headings within the extracted content.
        
        
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
        temperature=0.2,
        max_tokens=2200,
    )

    return response.choices[0].message.content.strip()


def extract_questions_with_llm(pdf_text: str) -> dict:
    prompt = f"""
    You are a professional RFP analysis assistant with expertise in extracting precise information from complex documents.

    Task:
    Extract every **question, instruction, or prompt** from the RFP text that explicitly requires a vendor response. Each extracted item must be a verbatim question or directive as written in the RFP.

    Do not:
    - Summarize, rewrite, shorten, or modify the wording of any question or instruction.
    - Infer or add questions that are not explicitly stated in the RFP text.
    - Include context-only text, such as introductions, needs statements, goals, background information, or overviews, unless they contain an explicit question or instruction requiring a response.
    - Include requests for references, such as "Provide three references," "List client references," "Include customer references," "Conflicts of Interest," or "Marketing Services Team."
    - Include administrative or procedural instructions, such as "Response must be submitted by [date]," "Submit via email," or "Include a cover letter."
    - Include vague or rhetorical questions that do not clearly require a vendor response (e.g., "Why is this important?").

    Do:
    - Extract each question or instruction **exactly as written** in the RFP (verbatim), preserving all punctuation, capitalization, and formatting.
    - Preserve the section hierarchy and numbering as they appear in the RFP.
    - Number questions sequentially within each section, extending the section's numbering format:
        * For a section like "1.2 Proposal Requirements," number questions as "1.2.1", "1.2.2", etc.
        * For Roman numeral sections like "III.A," number questions as "III.A.1", "III.A.2", etc.
        * For sections like "I," number questions as "I.1", "I.2", etc.
    - Restart question numbering (starting from 1) within each new section.
    - Group questions by their respective section heading and number, exactly as provided in the RFP.
    - Always prefix each question with its full section-based number (e.g., "1.2.1" or "III.A.1").
    - If a section contains no questions or instructions requiring a response, do not include it in the output.
    - Handle nested sections correctly, preserving the exact numbering format (e.g., "1.2.3.1" if the RFP uses such a format).
    - If the RFP uses bullet points, tables, or other formatting for questions, extract the text of each question or instruction as a single string, ignoring formatting unless it impacts the question's meaning.

    Edge Cases:
    - If a section contains a mix of questions and non-questions, only extract the explicit questions or instructions requiring a response.
    - If a question is phrased as a statement but implies a response (e.g., "The vendor shall provide a detailed implementation plan"), treat it as an instruction requiring a response.
    - If the RFP uses inconsistent numbering or formatting, follow the most logical interpretation of the hierarchy while preserving the original section titles and numbers.
    - If no section headings or numbers are provided, group questions under a default section labeled "General Questions" with numbering like "G.1", "G.2", etc.

    Output Format:
    Return a strict JSON object, with no Markdown, commentary, or additional text. The JSON should group questions by section, with each section identified by a unique key (starting from "1" and incrementing sequentially). Each section object must contain:
    - "section": The exact section title and number as written in the RFP (e.g., "1.1 Scope" or "III.A Technical Requirements").
    - "questions": A list of verbatim questions or instructions, each prefixed with their section-based number.

    Example Output:
    ```json
    {{
      "1": {{
        "section": "1.1 Scope",
        "questions": [
          "1.1.1 Define the brand’s personality, values, mission, and vision.",
          "1.1.2 Describe how you will create a marketing strategy for our product suite."
        ]
      }},
      "2": {{
        "section": "2.1 Proposal Requirements",
        "questions": [
          "2.1.1 Provide your organization’s overview and differentiators.",
          "2.1.2 Explain your execution approach in detail."
        ]
      }},
      "3": {{
        "section": "I Purpose",
        "questions": [
          "I.1 Provide your organization’s overview and differentiators.",
          "I.2 Explain your execution approach in detail."
        ]
      }},
      "4": {{
        "section": "III.A Technical Requirements",
        "questions": [
          "III.A.1 Describe your software architecture.",
          "III.A.2 Explain your data security approach.",
          "III.A.3 Provide details of your support model."
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
        temperature=0.0,  
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


def get_similar_context(question: str, top_k: int = 5):
    embedding = client.embeddings.create(
        input=[question],
        model="text-embedding-3-small" 
    ).data[0].embedding

    results = index.query(
        vector=embedding,
        top_k=top_k,
        include_metadata=True
    )
    contexts = [match['metadata']['text'] for match in results['matches']]
    sources = [
        {
            "score": match["score"],
            "document_id": match["metadata"].get("document_id"),
            "filename": match["metadata"].get("filename"),
            "category": match["metadata"].get("category"),
            "snippet": match["metadata"].get("text")
        }
        for match in results["matches"]
    ]
    return "\n".join(contexts), sources 

def generate_answer_with_context(question: str, context: str) -> str:
    prompt = f"""
    Answer the following question based only on the context below:

    Context:
    {context}

    Question: {question}
    Answer:
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant generating answers for RFP questions."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=800
    )
    return response.choices[0].message.content.strip()


def query_vector_db(question: str, top_k=8):
    """
    Query the ringerinfo vector database for relevant context.
    """
    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    ).data[0].embedding

    results = index_ringer.query(
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
    return text.strip()

def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding







