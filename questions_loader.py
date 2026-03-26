import json
from pathlib import Path


QUESTIONS_FILE = Path("data/questions.json")


def load_questions():
    if not QUESTIONS_FILE.exists():
        return []

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = []
    for item in data:
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()

        if question and answer:
            questions.append({
                "question": question,
                "answer": answer
            })

    return questions