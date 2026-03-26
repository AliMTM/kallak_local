import random
import time
import uuid


def normalize_arabic_text(text: str) -> str:
    text = text.strip()
    text = " ".join(text.split())
    text = text.lower()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


class RoomManager:
    def __init__(self, questions):
        self.questions = questions
        self.submit_duration = 30
        self.vote_duration = 20
        self.results_duration = 12
        self.reset_all()

    def reset_all(self):
        self.room = {
            "room_code": None,
            "players": [],
            "status": "LOBBY",
            "question_index": -1,
            "current_question": None,
            "current_answer": None,
            "submissions": {},
            "vote_options": [],
            "votes": {},
            "round_results": [],
            "phase_end_time": None
        }

    def create_room(self):
        room_code = str(uuid.uuid4())[:6].upper()
        self.room["room_code"] = room_code
        self.room["players"] = []
        self.room["status"] = "LOBBY"
        self.room["question_index"] = -1
        self.room["current_question"] = None
        self.room["current_answer"] = None
        self.room["submissions"] = {}
        self.room["vote_options"] = []
        self.room["votes"] = {}
        self.room["round_results"] = []
        self.room["phase_end_time"] = None
        return self.room

    def get_room(self):
        return self.room

    def get_player(self, player_id):
        for player in self.room["players"]:
            if player["id"] == player_id:
                return player
        return None

    def add_player(self, name: str):
        name = name.strip()

        if not self.room["room_code"]:
            return {"success": False, "message": "لا توجد غرفة حالياً"}

        if self.room["status"] != "LOBBY":
            return {"success": False, "message": "بدأت اللعبة بالفعل"}

        if not name:
            return {"success": False, "message": "الاسم مطلوب"}

        if len(name) > 20:
            return {"success": False, "message": "الاسم طويل جداً"}

        existing_names = [player["name"] for player in self.room["players"]]
        if name in existing_names:
            return {"success": False, "message": "الاسم مستخدم بالفعل"}

        player = {
            "id": str(uuid.uuid4()),
            "name": name,
            "score": 0
        }

        self.room["players"].append(player)
        return {"success": True, "player": player}

    def set_phase_timer(self, seconds: int):
        self.room["phase_end_time"] = int(time.time()) + seconds

    def get_remaining_seconds(self):
        end_time = self.room.get("phase_end_time")
        if not end_time:
            return None
        remaining = end_time - int(time.time())
        return max(0, remaining)

    def start_game(self):
        if len(self.room["players"]) < 2:
            return {"success": False, "message": "يجب وجود لاعبين على الأقل"}
        return self.start_next_round()

    def start_next_round(self):
        if not self.questions:
            return {"success": False, "message": "لا توجد أسئلة متوفرة"}

        self.room["question_index"] += 1

        if self.room["question_index"] >= len(self.questions):
            self.room["status"] = "GAME_OVER"
            self.room["phase_end_time"] = None
            return {"success": True, "status": "GAME_OVER"}

        item = self.questions[self.room["question_index"]]
        self.room["current_question"] = item["question"]
        self.room["current_answer"] = item["answer"]
        self.room["submissions"] = {}
        self.room["vote_options"] = []
        self.room["votes"] = {}
        self.room["round_results"] = []
        self.room["status"] = "SUBMIT"
        self.set_phase_timer(self.submit_duration)

        return {"success": True, "status": "SUBMIT"}

    def submit_fake_answer(self, player_id, answer_text):
        self.check_and_advance_phase()

        if self.room["status"] != "SUBMIT":
            return {"success": False, "message": "مرحلة الإجابات غير متاحة الآن"}

        player = self.get_player(player_id)
        if not player:
            return {"success": False, "message": "اللاعب غير موجود"}

        if player_id in self.room["submissions"]:
            return {"success": False, "message": "تم إرسال إجابتك بالفعل"}

        answer_text = answer_text.strip()
        if not answer_text:
            return {"success": False, "message": "الإجابة مطلوبة"}

        if len(answer_text) > 100:
            return {"success": False, "message": "الإجابة طويلة جداً"}

        submitted_normalized = normalize_arabic_text(answer_text)
        correct_normalized = normalize_arabic_text(self.room["current_answer"])

        if submitted_normalized == correct_normalized:
            return {
                "success": False,
                "message": "هذه هي الإجابة الصحيحة، اكتب إجابة مضللة"
            }

        existing_normalized = [
            normalize_arabic_text(v) for v in self.room["submissions"].values()
        ]
        if submitted_normalized in existing_normalized:
            return {
                "success": False,
                "message": "هذه الإجابة مكررة، اكتب إجابة مختلفة"
            }

        self.room["submissions"][player_id] = answer_text

        if len(self.room["submissions"]) == len(self.room["players"]):
            self.prepare_vote_options()

        return {"success": True}

    def prepare_vote_options(self):
        options = []

        for player_id, text in self.room["submissions"].items():
            options.append({
                "id": str(uuid.uuid4()),
                "text": text,
                "owner": player_id
            })

        options.append({
            "id": str(uuid.uuid4()),
            "text": self.room["current_answer"],
            "owner": "TRUTH"
        })

        random.shuffle(options)
        self.room["vote_options"] = options
        self.room["status"] = "VOTE"
        self.set_phase_timer(self.vote_duration)

    def submit_vote(self, player_id, option_id):
        self.check_and_advance_phase()

        if self.room["status"] != "VOTE":
            return {"success": False, "message": "مرحلة التصويت غير متاحة الآن"}

        player = self.get_player(player_id)
        if not player:
            return {"success": False, "message": "اللاعب غير موجود"}

        if player_id in self.room["votes"]:
            return {"success": False, "message": "تم إرسال تصويتك بالفعل"}

        selected_option = None
        for option in self.room["vote_options"]:
            if option["id"] == option_id:
                selected_option = option
                break

        if not selected_option:
            return {"success": False, "message": "الخيار غير صالح"}

        if selected_option["owner"] == player_id:
            return {"success": False, "message": "لا يمكنك اختيار إجابتك"}

        self.room["votes"][player_id] = option_id

        if len(self.room["votes"]) == len(self.room["players"]):
            self.calculate_scores()

        return {"success": True}

    def calculate_scores(self):
        fooled_counts = {player["id"]: 0 for player in self.room["players"]}
        round_results = []

        for voter_id, option_id in self.room["votes"].items():
            voter = self.get_player(voter_id)
            selected_option = next(
                (opt for opt in self.room["vote_options"] if opt["id"] == option_id),
                None
            )

            if not voter or not selected_option:
                continue

            if selected_option["owner"] == "TRUTH":
                voter["score"] += 2
                round_results.append({
                    "player_name": voter["name"],
                    "action": "اختار الإجابة الصحيحة",
                    "points": 2
                })
            else:
                fooled_counts[selected_option["owner"]] += 1
                round_results.append({
                    "player_name": voter["name"],
                    "action": f"اختار إجابة مضللة",
                    "points": 0
                })

        for owner_id, count in fooled_counts.items():
            if count > 0:
                owner_player = self.get_player(owner_id)
                if owner_player:
                    owner_player["score"] += count
                    round_results.append({
                        "player_name": owner_player["name"],
                        "action": f"خدع {count} لاعب/لاعبين",
                        "points": count
                    })

        self.room["round_results"] = round_results
        self.room["status"] = "RESULTS"
        self.set_phase_timer(self.results_duration)

    def force_advance_after_timeout(self):
        status = self.room["status"]

        if status == "SUBMIT":
            self.prepare_vote_options()
        elif status == "VOTE":
            self.calculate_scores()
        elif status == "RESULTS":
            self.start_next_round()

    def check_and_advance_phase(self):
        remaining = self.get_remaining_seconds()
        if remaining is not None and remaining <= 0:
            self.force_advance_after_timeout()

    def get_public_state(self):
        self.check_and_advance_phase()

        return {
            "room_code": self.room["room_code"],
            "status": self.room["status"],
            "players": self.room["players"],
            "question": self.room["current_question"],
            "vote_options": self.room["vote_options"] if self.room["status"] in ["VOTE", "RESULTS"] else [],
            "round_results": self.room["round_results"],
            "remaining_seconds": self.get_remaining_seconds()
        }