import json
from pathlib import Path


QUESTIONS_FILE = Path("data/questions.json")


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _extract_distractors(item):
    raw = item.get("distractors")
    if raw is None:
        raw = item.get("fake_answers")
    if raw is None:
        raw = item.get("choices")

    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []

    cleaned = []
    seen = set()
    for value in raw:
        text = _clean_text(value)
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text)
    return cleaned


def load_questions():
    if not QUESTIONS_FILE.exists():
        return []

    with QUESTIONS_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        return []

    questions = []
    for item in data:
        if not isinstance(item, dict):
            continue

        question = _clean_text(item.get("question"))
        answer = _clean_text(item.get("answer"))
        distractors = _extract_distractors(item)

        if not question or not answer:
            continue

        questions.append(
            {
                "question": question,
                "answer": answer,
                "distractors": distractors,
            }
        )

    return questions
