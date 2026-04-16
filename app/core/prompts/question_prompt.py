def question_prompt(pdf_text):

    return f"""
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