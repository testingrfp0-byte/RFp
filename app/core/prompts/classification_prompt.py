def classification_prompt(rfp_text, selected_sections = None, proposal_instructions= None):
    sections_block = ""
    
    if selected_sections:  # handles None AND empty list
        sections_str = "\n- " + "\n- ".join(selected_sections)
        sections_block = f"""
            IMPORTANT FILTER:
            Only process items that belong to the following sections:
            {sections_str}

            Ignore any items that fall outside these sections.
            """

    return  f"""You are simultaneously two roles:

            ROLE A: An EVALUATOR scoring proposals before contract award.
            ROLE B: A CONTRACT MANAGER overseeing delivery after award.

            {sections_block}

            Ignore any items that fall outside these sections.

            Your task is to classify each numbered scope and Proposal Response and Submission Instructions item extracted from
            this RFP as one of three categories:
            [I] INSTRUCTION  — operational directive, performed after hiring
            [Q] QUESTION     — proposal deliverable, demonstrated before award
            [B] BOTH         — requires a proposal answer AND contract delivery

            ───────────────────────────────────────────────────────────────────
            CLASSIFICATION STEPS — apply in order for every item
            ───────────────────────────────────────────────────────────────────

            STEP 1 — DUAL-READER TEST
            For each item ask both questions:
            A) Does the PROPOSER need to write a strategic answer to this
                item in their proposal? (Yes/No)
            B) Does the CONTRACTOR need to physically perform or deliver
                this after being hired? (Yes/No)

            Only A = Yes  →  lean [Q]
            Only B = Yes  →  lean [I]
            Both   = Yes  →  lean [B]

            STEP 2 — VERB SIGNAL
            Extract the first main verb and map it:

            attend / staff / remove / package / monitor / coordinate /
            respond / maintain / track / manage / ensure / take
            → lean [I]

            develop / create / recommend / suggest / design / improve /
            project manage / increase / provide [research or strategy] /
            set / execute / participate / engage
            → lean [B]

            provide [named people] / identify [personnel] /
            submit [qualifications] / propose [staff]
            → lean [Q]

            If verb is ambiguous, look at the object of the verb:
            - verb + [a person or team]      → lean [Q]
            - verb + [a deliverable or plan] → lean [B]
            - verb + [a physical action]     → lean [I]

            STEP 3 — CROSS-REFERENCE CHECK
            Check the proposal_instructions section provided below.
            For each scope item ask:
            Does any entry in proposal_instructions.sections[].required_items
            reference or cover this scope item's topic?

            YES → upgrade classification to [B] or [Q], never leave as [I]
            NO  → keep your Step 1 + Step 2 result

            STEP 4 — DECISION TREE (use only for items still ambiguous after Steps 1-3)
            Answer these 3 questions IN ORDER. Do not skip.

            Q1: Would an EVALUATOR score the proposer's written answer
                to this item?
                → NO:  go to Q2
                → YES: go to Q3

            Q2: Is this a physical or operational task performed post-hire?
                → YES: classify [I]
                → NO:  examine the surrounding subsection context

            Q3: Is the contractor also legally obligated to PERFORM this
                under the contract?
                → YES: classify [B]
                → NO:  classify [Q]

            ───────────────────────────────────────────────────────────────────
            INPUT DATA
            ───────────────────────────────────────────────────────────────────

            Raw text:
            {rfp_text}

            ───────────────────────────────────────────────────────────────────
            OUTPUT RULES
            ───────────────────────────────────────────────────────────────────

            Return a single JSON object only. No prose. No explanation outside
            the JSON. No markdown fences.

            Use exactly this structure:

            {{
            "classification_results": [
                {{
                "item_number": 1,
                "item_text": "verbatim text of the requirement",
                "section_number": "number of the section this item belongs to",
                "section": "section title this item belongs to",
                "subsection": "subsection title this item belongs to",
                "subsection_number": "number of the subsection this item belongs to",
                "classification": "I",
                "step_that_decided": "Step 2 — verb signal",
                "dual_reader": {{
                    "proposer_must_answer": false,
                    "contractor_must_perform": true
                }},
                "verb_extracted": "attend",
                "cross_reference_match": false,
                "reason": "one sentence explaining the classification"
                }}
            ],
            "summary": {{
                "total_items": 0,
                "instruction_count": 0,
                "question_count": 0,
                "both_count": 0,
                "ambiguous_resolved_by_step4": 0
            }}
            }}

            FIELD RULES:
            - item_number       → integer from the original numbered list
            - item_text         → copy the requirement verbatim, do not paraphrase
            - subsection        → the sub-section heading this item falls under
                                e.g. "Marketing & Advertising" or "Key Personnel"
            - classification    → exactly one of: "I", "Q", "B"
            - step_that_decided → which step produced the final answer,
                                e.g. "Step 2 — verb signal" or
                                "Step 3 — cross-reference upgrade" or
                                "Step 4 — decision tree"
            - verb_extracted    → the first main verb you identified
            - cross_reference_match → true if Step 3 found a match in
                                    proposal_instructions, false otherwise
            - reason            → one sentence max, plain English, explains why
            - summary counts    → must add up to total_items exactly
            """