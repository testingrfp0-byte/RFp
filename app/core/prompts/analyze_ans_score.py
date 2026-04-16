
def generate_score_prompt(question_text: str, answer_text: str) -> str:
    return f"""
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