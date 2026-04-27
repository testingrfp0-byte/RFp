def questions_grouped_prompt(rfp_text: str, custom_message: str = None):
    """
    Generate questions using base RFP + admin custom instructions
    """
    custom_instruction = ""

    if custom_message and custom_message.strip():
        custom_instruction = f"""
        ADMIN CUSTOM REQUIREMENTS:
        The admin has requested the following preferences for question generation:
        "{custom_message}"

        You MUST adapt question generation accordingly:
        - Prioritize topics mentioned by admin
        - Include sections/topics explicitly requested
        - Exclude irrelevant/general questions if admin narrowed scope
        - Maintain RFP context while aligning with admin intent
        """

    return f"""
    You are an ADVANCED RFP QUESTION GENERATOR.

    Your job is to extract ONLY high-quality proposal questions.

    {custom_instruction}

    CORE RULES:
    - Extract ONLY questions requiring written proposal responses
    - Questions must be strategic, not generic
    - Focus on:
        • Approach
        • Methodology
        • Execution plan
        • Deliverables
    - Avoid:
        • Instructions
        • Legal text
        • Definitions
        • Admin requirements

    SMART ADAPTATION:
    - If admin message exists → bias output toward those areas
    - If admin says "focus on AI" → prioritize AI-related questions
    - If admin says "exclude finance" → remove finance questions

    FORMAT RULES:
    - Group by section
    - Number properly (1.1, 1.2...)
    - Questions must end with ?

    OUTPUT STRICT JSON:
    {{
        "1": {{
            "section": "Section Name",
            "questions": [
                "1.1 Question?",
                "1.2 Question?"
            ]
        }}
    }}

    SOURCE RFP:
    \"\"\"{rfp_text}\"\"\"
    """
