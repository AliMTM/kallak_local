import random
import uuid


class RoomManager:
    def __init__(self, questions):
        self.questions = questions
        self.reset_all()

    def reset_all(self):
        self.room = {
            "room_code": None,
            "players": [],
            "status": "LOBBY",
            "question_index": -1,
            "current_question": None,
            "current_answer": None,
            "submissions": {},   # player_id -> fake answer
            "vote_options": [],  # list of {"id", "text", "owner"}
            "votes": {},         # voter_id -> option_id
            "round_results": []
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
        return self.room

    def get_room(self):
        return self.room

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
            return {"success": True, "status": "GAME_OVER"}

        item = self.questions[self.room["question_index"]]
        self.room["current_question"] = item["question"]
        self.room["current_answer"] = item["answer"]
        self.room["submissions"] = {}
        self.room["vote_options"] = []
        self.room["votes"] = {}
        self.room["round_results"] = []
        self.room["status"] = "SUBMIT"

        return {"success": True, "status": "SUBMIT"}

    def get_player(self, player_id):
        for player in self.room["players"]:
            if player["id"] == player_id:
                return player
        return None

    def submit_fake_answer(self, player_id, answer_text):
        if self.room["status"] != "SUBMIT":
            return {"success": False, "message": "مرحلة الإجابات غير متاحة الآن"}

        player = self.get_player(player_id)
        if not player:
            return {"success": False, "message": "اللاعب غير موجود"}

        answer_text = answer_text.strip()
        if not answer_text:
            return {"success": False, "message": "الإجابة مطلوبة"}

        if len(answer_text) > 100:
            return {"success": False, "message": "الإجابة طويلة جداً"}

        self.room["submissions"][player_id] = answer_text

        if len(self.room["submissions"]) == len(self.room["players"]):
            self.prepare_vote_options()

        return {"success": True}

    def prepare_vote_options(self):
        options = []

        # fake answers
        for player_id, text in self.room["submissions"].items():
            options.append({
                "id": str(uuid.uuid4()),
                "text": text,
                "owner": player_id
            })

        # real answer
        options.append({
            "id": str(uuid.uuid4()),
            "text": self.room["current_answer"],
            "owner": "TRUTH"
        })

        random.shuffle(options)
        self.room["vote_options"] = options
        self.room["status"] = "VOTE"

    def submit_vote(self, player_id, option_id):
        if self.room["status"] != "VOTE":
            return {"success": False, "message": "مرحلة التصويت غير متاحة الآن"}

        player = self.get_player(player_id)
        if not player:
            return {"success": False, "message": "اللاعب غير موجود"}

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
        fooled_counts = {}

        for player in self.room["players"]:
            fooled_counts[player["id"]] = 0

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
                    "action": f"اختار إجابة لاعب آخر: {selected_option['text']}",
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

    def get_public_state(self):
        return {
            "room_code": self.room["room_code"],
            "status": self.room["status"],
            "players": self.room["players"],
            "question": self.room["current_question"],
            "vote_options": self.room["vote_options"] if self.room["status"] in ["VOTE", "RESULTS"] else [],
            "round_results": self.room["round_results"]
        }