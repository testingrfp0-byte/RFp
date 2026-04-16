def search_queries_prompt(rfp_text: str):
    return f"""
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