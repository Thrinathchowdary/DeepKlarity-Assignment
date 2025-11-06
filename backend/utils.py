# utils.py
def normalize_payload(raw: dict) -> dict:
    key_entities = raw.get("key_entities") or {}
    for k in ("people", "organizations", "locations"):
        key_entities.setdefault(k, [])

    sections = raw.get("sections") or []
    related = raw.get("related_topics") or []

    quiz = []
    for q in (raw.get("quiz") or [])[:10]:
        prompt = q.get("prompt") or q.get("question") or ""
        options = q.get("options") or []
        answer = q.get("answer") or ""
        explanation = q.get("explanation") or ""
        difficulty = (q.get("difficulty") or "").lower() or None
        if prompt and options and answer:
            quiz.append({
                "prompt": prompt.strip(),
                "options": options[:4],
                "answer": answer.strip(),
                "explanation": explanation.strip(),
                "difficulty": difficulty if difficulty in {"easy","medium","hard"} else None
            })

    return {
        "title": raw.get("title") or "",
        "summary": raw.get("summary") or "",
        "key_entities": key_entities,
        "sections": sections,
        "quiz": quiz,
        "related_topics": related
    }
