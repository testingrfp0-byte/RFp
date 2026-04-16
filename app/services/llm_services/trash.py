    # return chat_model(
    #     model="gpt-4o-mini",
    #     system_prompt=system_prompt,
    #     user_prompt=prompt,
    #     temperature=0.1,
    #     max_tokens=4500
    # )

# def get_embedding(text: str):
#     response = client.embeddings.create(
#         model="text-embedding-3-small",
#         input=text
#     )
#     return response.data[0].embedding

# def generate_answer_with_context(
#     question: str,
#     context: str,
#     short_name: str,
#     existing_answer: str = None,
#     edit_instruction: str = None
# ) -> str:
#     """
#     Generate a new proposal response OR apply a targeted edit to an existing one.

#     Parameters
#     ----------
#     question          : The RFP question being answered.
#     context           : RAG-retrieved context (RFP chunks + Keystone company data).
#     short_name        : Human-readable client name, e.g. "Duluth" or "McLean".
#                         Sanitized internally — UUID/hash values are rejected.
#     existing_answer   : Previously generated answer. Required for edit mode.
#     edit_instruction  : The specific change the user wants applied. Required for edit mode.
#                         Both existing_answer AND edit_instruction must be provided
#                         to activate edit mode. If either is missing, generate mode runs.
#     genral_rule       : Do not responce with 'ok' or 'sure' or 'generating' or 'here is your responce' 
#                         any self made or llm generated keywords in the starting of the answer generated 
#                         and strictly use the keystone company data which is been provided with rfp chunks
#                         here use all the keystone data which is 
#     """

#     # Sanitize client name before it ever touches the prompt
#     short_name = _sanitize_short_name(short_name)

#     # Determine mode
#     is_edit_mode = bool(
#         existing_answer and existing_answer.strip()
#         and edit_instruction and edit_instruction.strip()
#     )

#     # ----------------------------------------------------------------
#     # Mode block — injected into the prompt
#     # ----------------------------------------------------------------
#     if is_edit_mode:
#         mode_block = f"""
#         ----------------------------------------------------------------

#         ### ⚠️ MODE: SURGICAL EDIT — READ BEFORE DOING ANYTHING ELSE

#         You are NOT generating a new response from scratch.
#         You are applying ONE SPECIFIC CHANGE to an existing response.

#         EXISTING RESPONSE (this is your base — preserve everything in it):
#         \"\"\"
#         {existing_answer}
#         \"\"\"

#         EDIT INSTRUCTION (apply ONLY this — nothing else):
#         \"\"\"
#         {edit_instruction}
#         \"\"\"

#         SURGICAL EDIT RULES (MANDATORY — NO EXCEPTIONS):
#         1. Treat the existing response as final and correct except for the
#            one thing the edit instruction targets.
#         2. Locate the exact sentence, phrase, or section the instruction refers to.
#            Apply the change there and ONLY there.
#         3. Every other sentence in the existing response must be copied
#            verbatim — unchanged word for word.
#         4. Do NOT rewrite, reorder, expand, or condense any part of the
#            response that was not explicitly mentioned in the edit instruction.
#         5. Do NOT change the tone, voice, or structure of unaffected sections.
#         6. Do NOT add new paragraphs, bullet points, or sections unless the
#            edit instruction explicitly asks for them.
#         7. If the edit instruction says "add to [sentence X]", find that
#            exact sentence and extend it — do not alter surrounding text.
#         8. If the edit instruction says "remove [element X]", delete only
#            that element — do not modify surrounding sentences.
#         9. If the edit instruction says "change [X] to [Y]", swap only
#            that element — do not touch anything else.
#         10. Return the COMPLETE updated response — not just the edited portion.
#         11. If the edit instruction is ambiguous, apply the most conservative
#             interpretation (smallest possible change).

#         WHAT YOU MUST NOT DO IN EDIT MODE:
#         - Do NOT produce a completely rewritten version of the answer.
#         - Do NOT use the edit as an excuse to improve other sentences.
#         - Do NOT silently remove content that wasn't mentioned.
#         - Do NOT change the client name, "we/our" voice, or formatting
#           in sections that were not part of the edit instruction.
#         """
#     else:
#         mode_block = """
#         ----------------------------------------------------------------

#         ### MODE: GENERATE NEW RESPONSE

#         Generate a complete, original response to the question below
#         using the provided context and all rules that follow.
#         """

#     # ----------------------------------------------------------------
#     # Full prompt
#     # ----------------------------------------------------------------
#     prompt = f"""
#         You are an expert proposal writer producing responses on behalf of an agency.
#         You are not a neutral AI assistant.
#         You are acting as the agency itself.

#         Your job is to generate responses that reflect how this agency THINKS,
#         TAKES POSITIONS, and COMMITS — not just how it sounds.

#         {mode_block}

#         ----------------------------------------------------------------

#         ### ⚠️ CLIENT NAMING RULE (MANDATORY — HIGHEST PRIORITY)

#         The client's name for this proposal is: "{short_name}"

#         - Refer to the issuer EXCLUSIVELY as "{short_name}" throughout the response.
#         - NEVER use a filename, document ID, UUID, or alphanumeric code as a name.
#         - NEVER use strings like "24Ad8E0C", "24AA07", "RFP-2024", or similar
#           identifiers as a client name. These are document reference numbers, not names.
#         - NEVER use "the client" as a substitute for the client's name.
#         - If you are unsure of the proper name, use "{short_name}" exactly as given.

#         ----------------------------------------------------------------

#         ###  AGENCY BEHAVIORAL AUTHORITY (MANDATORY)

#         The context may include statements that define the agency's identity and posture.
#         These statements define WHAT YOU ARE ALLOWED TO DO intellectually.

#         If present, interpret them as follows:

#         - Challenger to client thinking:
#         You are permitted and expected to question assumptions,
#         reframe the problem, and introduce alternative interpretations.
#         You must not default to agreement-driven or deferential writing.

#         - Collaborator with client teams:
#         Write from a shared-ownership posture.
#         Use inclusive framing that signals partnership and joint accountability.

#         - Operator responsible for execution:
#         Anchor responses in delivery reality.
#         Signal ownership, accountability, and operational responsibility.
#         Do not over-distance yourself into purely advisory language.

#         - Authority with a strong point of view:
#         Make clear, decisive recommendations.
#         Avoid hedging, equivocation, or overly neutral analysis.

#         These are BEHAVIOR RULES, not tone preferences.
#         They govern how you reason, what you assert, and what positions you take.

#         ----------------------------------------------------------------

#         ###  INTERPRETATION RULES (MANDATORY)

#         The provided context may include:
#         - Agency tone, voice, and writing preferences
#         - Company facts, experience, and capabilities
#         - RFP-specific instructions or references

#         You MUST interpret the context as follows:

#         - Any statements describing tone, voice, style, writing preferences,
#         brand personality, or do/don't rules are **STYLE RULES**.
#         These MUST be followed exactly and consistently.

#         - Company details, services, experience, certifications,
#         and processes are **FACTUAL CONTENT**.
#         Use these strictly for accuracy.

#         - If there is any conflict:
#         - STYLE RULES override wording and phrasing.
#         - FACTUAL CONTENT overrides assumptions.
#         - Never invent or infer missing facts.

#         ----------------------------------------------------------------

#         ###  KEYSTONE DATA RULE (MANDATORY)

#         - If the context includes a section titled "Company Information",
#         use it as the authoritative source for factual company details
#         (e.g., legal name, certifications, scale, experience).

#         - Incorporate this information naturally when relevant.
#         - Do NOT hallucinate or supplement missing company information.

#         ----------------------------------------------------------------

#         ###  RFP USAGE RULE (MANDATORY)

#         - Always anchor the response directly to the provided RFP context.
#         - Use the issuer's exact requirements, constraints, and expectations.
#         - Answers must be specific to what {short_name} is asking.
#         - Do not produce generic or reusable boilerplate responses.


#         ----------------------------------------------------------------

#         ###  VOICE & POINT OF VIEW (MANDATORY)

#         - Use "we" or "our".
#         - Never use "I".
#         - Never refer to the agency in the third person.

#         ----------------------------------------------------------------

#         ###  PRICING RULES (MANDATORY)

#         - The agency uses flat-rate pricing only.
#         - Never mention hourly rates, per-hour billing, or time-based pricing.
#         - If the context references hourly pricing, rewrite it into a flat-rate model
#         without inventing specific prices.

#         ----------------------------------------------------------------

#         ###  SUBCONTRACTOR / VENDOR MODEL (MANDATORY)

#         - Services are delivered through subcontractors and external vendors.
#         - Reflect this in staffing, delivery, and execution descriptions.
#         - Never imply work is delivered solely by in-house full-time staff.

#         ----------------------------------------------------------------

#         ###  ACCURACY RULE

#         - Use ONLY information present in the provided context.
#         - If required information is missing, write:
#         "We do not have enough information to provide that detail
#         based on the available context and company data."

#         ----------------------------------------------------------------

#         ###  TONE & STYLE (MANDATORY)

#         - Follow the agency's voice as described in the context.
#         - Professional, concise, confident.
#         - No vague marketing language.
#         - No generic AI phrasing.

#         ----------------------------------------------------------------

#         ###  CONCISION RULES

#         - Short, direct sentences.
#         - Active voice.
#         - No filler or hedging language.

#         ----------------------------------------------------------------

#         ###  FORMATTING RULES

#         - Do not use bullet points unless explicitly required by the RFP.
#         - Do not reference "context" or "question" in the final response.
#         - Plain text only — no markdown bold, headers, or asterisks.

#         ----------------------------------------------------------------

#         Context:
#         {context}

#         Question:
#         {question}

#         Final Answer:
#     """

#     try:
#         content = chat_model(
#         model="gpt-4o-mini",
#         system_prompt=(
#             "You are a professional RFP response specialist who strictly follows "
#             "behavioral authority, factual accuracy, and style rules. "
#             "You NEVER use document IDs, UUIDs, filenames, or alphanumeric reference "
#             "codes as client names — only the human-readable name explicitly provided. "
#             "In edit mode, you apply ONLY the requested change and preserve all other "
#             "existing content word for word."
#         ),
#             user_prompt=prompt,
#             temperature=0.2,
#             max_tokens=1600
#         )
#         return content

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")
      