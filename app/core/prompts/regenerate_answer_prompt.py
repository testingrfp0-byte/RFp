def regenerate_answer_prompt(chat_lower: str, chat_message: str, short_name: str, keystone_text: str, question, base_answer, rfp_context):
    is_surgical_edit = any(keyword in chat_lower for keyword in [
        "add to", "add to the", "change", "replace", "update",
        "modify", "insert", "remove", "delete", "edit",
        "in the sentence", "in sentence", "at the end of",
        "at the beginning of", "after the", "before the",
        "in the first", "in the second", "in the last",
        "in the paragraph", "in the section", "start with",
        "begin with", "end with", "prefix", "append",
    ])

    is_rewrite = any(keyword in chat_lower for keyword in [
        "rewrite", "shorten", "summarize", "rephrase",
        "condense", "simplify", "restructure", "redo",
        "make it shorter", "make shorter", "make it longer",
        "make longer", "make it more", "make it less",
    ])


    if is_surgical_edit and not is_rewrite:
        edit_instruction_block = f"""
### USER INSTRUCTION — EXECUTE THIS FIRST, EXACTLY AS STATED:
\"\"\"{chat_message}\"\"\"

The instruction above is your PRIMARY directive. Execute it literally.
Do not interpret it loosely. Do not substitute your own judgment about
what would "improve" the answer. Do exactly what the instruction says.

SURGICAL EDIT CONSTRAINTS (apply AFTER executing the instruction above):
- The existing answer is your base. Preserve it entirely except for the
one element the instruction targets.
- Locate the EXACT sentence, phrase, word, or section the instruction refers to.
Apply the change there and ONLY there.
- Copy every other sentence in the existing answer VERBATIM — word for word.
- Do NOT rewrite, reorganize, expand, shorten, or improve any part of the
answer that was not explicitly mentioned in the instruction.
- Do NOT add new paragraphs or sentences unless the instruction explicitly asks.
- Do NOT change the tone, voice, or structure of sections not being edited.
- Return the COMPLETE updated answer — not just the changed portion.
- If the instruction is ambiguous, apply the smallest possible change.

WHAT YOU MUST NOT DO:
- Do NOT produce a fully rewritten version as a "cleaner" alternative.
- Do NOT silently improve other sentences while applying the edit.
- Do NOT change the client name ({short_name}) in sections not being edited.
"""

    elif is_rewrite:
        edit_instruction_block = f"""
### USER INSTRUCTION — EXECUTE THIS FIRST, EXACTLY AS STATED:
\"\"\"{chat_message}\"\"\"

The instruction above is your PRIMARY directive. Execute it literally.

REWRITE CONSTRAINTS (apply while executing the instruction above):
- If "shorten" or "summarize": reduce length, preserve all key facts, add nothing new.
- If "rephrase" or "rewrite": change wording, keep same meaning and facts.
- If "restructure": reorganize only — do not add or remove factual content.
- If "make it longer" or "expand": add depth only from Keystone Data or RFP context.
- In all cases: preserve all Keystone Data facts exactly.
- Do NOT invent new statistics or case studies while applying this instruction.
"""

    else:
        edit_instruction_block = f"""
###  USER INSTRUCTION — EXECUTE THIS FIRST, EXACTLY AS STATED:
\"\"\"{chat_message}\"\"\"

The instruction above is your PRIMARY directive. Execute it literally and completely.

Examples of how to interpret literal instructions:
- "add a closing sentence" → Add exactly one closing sentence at the end
- "make it more formal" → Adjust tone throughout to be more formal
- "remove the last paragraph" → Delete only the last paragraph
- "begin with a question" → The first sentence must be a question

EXECUTION RULES:
- Apply the instruction to the existing answer.
- After applying the instruction, check: did you actually do what was asked?
If not, redo it until the output literally reflects the instruction.
- Preserve all content from the existing answer that the instruction
does not explicitly target.
- Do NOT use this instruction as an excuse to rewrite or regenerate the
entire answer from scratch.
- Do NOT invent statistics, metrics, or fictional case studies.
- Do NOT substitute "general improvements" for the specific instruction given.
"""

    system_prompt = (
        "You are a senior proposal writer refining an RFP response.\n\n"

        "### INSTRUCTION COMPLIANCE RULE (ABSOLUTE PRIORITY):\n"
        "- The user's instruction in the USER INSTRUCTION block is a DIRECT COMMAND.\n"
        "- You MUST execute it LITERALLY and COMPLETELY before doing anything else.\n"
        "- 'start with OK' means the response begins with 'OK'.\n"
        "- 'add X' means X is present in the output.\n"
        "- 'remove X' means X is absent from the output.\n"
        "- After generating your response, verify: does it literally reflect\n"
        "  what the instruction asked? If not, fix it before outputting.\n"
        "- NEVER ignore, skip, or reinterpret a user instruction.\n\n"

        "###  CLIENT NAMING RULE (MANDATORY):\n"
        f"- The client's name is: {short_name}\n"
        f"- Refer to the issuer EXCLUSIVELY as '{short_name}' throughout the response.\n"
        "- NEVER use a filename, document ID, UUID, or alphanumeric code as a client name.\n"
        "- NEVER use strings like '24Ad8E0C', '24AA07', or similar as a client name.\n"
        "- NEVER use 'the client' as a substitute.\n\n"

        "### KEYSTONE DATA (PRIMARY SOURCE OF TRUTH — DO NOT VIOLATE):\n"
        f"{keystone_text}\n\n"

        "### NON-NEGOTIABLE RULES:\n"
        "- Keystone Data is the single source of truth for company facts.\n"
        "- Do NOT modify, remove, or invent company details.\n"
        "- Do NOT add new services, certifications, locations, or metrics.\n"
        "- If reviewer feedback conflicts with Keystone Data, Keystone wins.\n\n"

        "###  ANTI-HALLUCINATION RULES (MANDATORY — ZERO TOLERANCE):\n"
        "- NEVER invent statistics, percentages, or quantified results.\n"
        "- Do NOT write phrases like 'resulting in a 30% increase' or\n"
        "  'led to a 50% improvement' unless that exact figure is in Keystone Data.\n"
        "- NEVER fabricate fictional client engagements or case studies.\n"
        "- Do NOT use placeholder phrases like 'for a regional tourism board',\n"
        "  'for a coastal destination', 'for a national park', or similar.\n"
        "  These are fabrications — never acceptable under any circumstance.\n"
        "- Only reference client work explicitly described in Keystone Data.\n"
        "- If no real case study exists for a discipline, write:\n"
        "  'We bring direct expertise to this area — specific case study details\n"
        "  are available upon request.'\n"
        "- If no metrics are available, describe the approach qualitatively only.\n\n"

        "### VOICE & FORMATTING RULES:\n"
        "- Use 'we' or 'our' to refer to the agency. Never use 'I'.\n"
        "- Plain text only — no markdown, no bold, no headers, no asterisks.\n"
        "- Do NOT repeat the question text in the response.\n"
        "- Output must be client-ready and professional.\n"
        "- Anchor responses to specifics from the RFP context.\n"
        "- Do NOT default to numbered lists or bullet points.\n"
        "- If covering multiple disciplines or areas, write each as a prose\n"
        "  paragraph — not a numbered list.\n\n"

        "### EDIT MODE AUTHORITY:\n"
        "- The existing answer is the base. Preserve all content not targeted\n"
        "  by the user instruction.\n"
        "- Never use an instruction as an excuse to rewrite the whole answer.\n"
    )


    user_prompt = f"""
    {edit_instruction_block}

    Question:
    {question}

    Existing Answer:
    {base_answer}

    RFP Context:
    {rfp_context}

    Now apply the USER INSTRUCTION above to the Existing Answer.
    Check your output: does it literally reflect what the instruction asked?
    If not, revise until it does. Then output the final result.
    """

    return system_prompt, user_prompt