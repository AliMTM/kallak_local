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
    RECONNECT_WINDOW = 25
    INTRO_DURATION = 4

    def __init__(self, questions):
        self.questions = questions
        self.default_submit_duration = 30
        self.default_vote_duration = 20
        self.default_results_duration = 12
        self.reset_all()

    def reset_all(self):
        self.room = {
            "room_code": None,
            "players": [],
            "status": "LOBBY",
            "round_number": 0,
            "current_question": None,
            "current_answer": None,
            "current_distractors": [],
            "submissions": {},
            "vote_options": [],
            "votes": {},
            "round_results": {},
            "phase_end_time": None,
            "submit_duration": self.default_submit_duration,
            "vote_duration": self.default_vote_duration,
            "results_duration": self.default_results_duration,
            "unused_question_indices": [],
            "final_ranking": [],
        }

    def create_room(self):
        self.reset_all()
        self.room["room_code"] = str(uuid.uuid4())[:6].upper()
        self.room["unused_question_indices"] = list(range(len(self.questions)))
        return self.room

    def now(self):
        return int(time.time())

    def mark_inactive_players(self):
        now = self.now()
        for player in self.room["players"]:
            player["connected"] = (now - player["last_seen"]) <= self.RECONNECT_WINDOW

    def get_player(self, player_id=None, token=None):
        for player in self.room["players"]:
            if player_id and player["id"] == player_id:
                return player
            if token and player["token"] == token:
                return player
        return None

    def touch_player(self, player_id=None, token=None):
        player = self.get_player(player_id=player_id, token=token)
        if player:
            player["last_seen"] = self.now()
            player["connected"] = True
        return player

    def get_sorted_players(self):
        self.mark_inactive_players()
        return sorted(
            self.room["players"],
            key=lambda player: (-player["score"], player["name"]),
        )

    def _public_player(self, player):
        return {
            "id": player["id"],
            "name": player["name"],
            "score": player["score"],
            "connected": player["connected"],
        }

    def add_player(self, name: str, token: str):
        name = " ".join(name.strip().split())
        token = token.strip()

        if not self.room["room_code"]:
            return {"success": False, "message": "ما فيه غرفة مفتوحة الآن."}

        if not name:
            return {"success": False, "message": "اكتب اسمك أول شيء."}

        if len(name) > 20:
            return {"success": False, "message": "الاسم طويل شوي، خله أخف."}

        if not token:
            return {"success": False, "message": "تعذّر تثبيت هويتك، حدّث الصفحة وجرب من جديد."}

        player = self.touch_player(token=token)
        if player:
            if self.room["status"] == "LOBBY":
                normalized_new_name = normalize_arabic_text(name)
                for other in self.room["players"]:
                    if other["id"] == player["id"]:
                        continue
                    if normalize_arabic_text(other["name"]) == normalized_new_name:
                        return {"success": False, "message": "الاسم هذا مأخوذ، زد له لمسة بسيطة."}
                player["name"] = name
            return {"success": True, "player": self._public_player(player), "reconnected": True}

        normalized_name = normalize_arabic_text(name)
        for existing in self.room["players"]:
            if normalize_arabic_text(existing["name"]) == normalized_name:
                return {"success": False, "message": "الاسم هذا مأخوذ، جرّب لقبًا مختلفًا."}

        if self.room["status"] != "LOBBY":
            return {"success": False, "message": "الجولة بدأت، ارجع بنفس الجهاز إذا كنت داخل أصلًا."}

        now = self.now()
        player = {
            "id": str(uuid.uuid4()),
            "token": token,
            "name": name,
            "score": 0,
            "connected": True,
            "last_seen": now,
            "joined_at": now,
        }
        self.room["players"].append(player)
        return {"success": True, "player": self._public_player(player), "reconnected": False}

    def set_durations(self, submit_duration, vote_duration, results_duration):
        if self.room["status"] != "LOBBY":
            return {"success": False, "message": "عدّل الأوقات قبل ما تبدأ السهرة."}

        try:
            submit_duration = int(submit_duration)
            vote_duration = int(vote_duration)
            results_duration = int(results_duration)
        except Exception:
            return {"success": False, "message": "الأوقات المدخلة غير صالحة."}

        if not (5 <= submit_duration <= 300):
            return {"success": False, "message": "وقت الإجابات لازم يكون بين 5 و300 ثانية."}

        if not (5 <= vote_duration <= 300):
            return {"success": False, "message": "وقت التصويت لازم يكون بين 5 و300 ثانية."}

        if not (3 <= results_duration <= 120):
            return {"success": False, "message": "وقت النتائج لازم يكون بين 3 و120 ثانية."}

        self.room["submit_duration"] = submit_duration
        self.room["vote_duration"] = vote_duration
        self.room["results_duration"] = results_duration
        return {"success": True}

    def set_phase(self, status, seconds=None):
        self.room["status"] = status
        self.room["phase_end_time"] = self.now() + seconds if seconds is not None else None

    def get_remaining_seconds(self):
        end_time = self.room.get("phase_end_time")
        if end_time is None:
            return None
        return max(0, end_time - self.now())

    def start_game(self):
        if len(self.room["players"]) < 2:
            return {"success": False, "message": "نحتاج لاعبين على الأقل عشان تبدأ الخدعة."}

        if not self.questions:
            return {"success": False, "message": "ما عندي أسئلة جاهزة الآن."}

        if not self.room["unused_question_indices"]:
            self.room["unused_question_indices"] = list(range(len(self.questions)))

        return self.start_next_round()

    def start_next_round(self):
        if not self.questions:
            return {"success": False, "message": "ما عندي أسئلة جاهزة الآن."}

        if not self.room["unused_question_indices"]:
            self.room["status"] = "GAME_OVER"
            self.room["phase_end_time"] = None
            self.room["final_ranking"] = self.get_sorted_players()
            return {"success": True, "status": "GAME_OVER"}

        chosen_index = random.choice(self.room["unused_question_indices"])
        self.room["unused_question_indices"].remove(chosen_index)
        item = self.questions[chosen_index]

        self.room["round_number"] += 1
        self.room["current_question"] = item["question"]
        self.room["current_answer"] = item["answer"]
        self.room["current_distractors"] = item.get("distractors", [])
        self.room["submissions"] = {}
        self.room["vote_options"] = []
        self.room["votes"] = {}
        self.room["round_results"] = {}
        self.set_phase("INTRO", self.INTRO_DURATION)
        return {"success": True, "status": "INTRO"}

    def begin_submit_phase(self):
        self.room["submissions"] = {}
        self.room["votes"] = {}
        self.room["vote_options"] = []
        self.set_phase("SUBMIT", self.room["submit_duration"])

    def _normalize_existing_round_answers(self):
        normalized = {
            normalize_arabic_text(self.room["current_answer"]),
        }
        for text in self.room["submissions"].values():
            normalized.add(normalize_arabic_text(text))
        return normalized

    def _required_players_for_action(self, action_map):
        self.mark_inactive_players()
        required = []
        for player in self.room["players"]:
            already_done = player["id"] in action_map
            if player["connected"] or already_done:
                required.append(player)
        return required

    def submit_fake_answer(self, player_id, token, answer_text):
        self.check_and_advance_phase()

        if self.room["status"] != "SUBMIT":
            return {"success": False, "message": "مو وقت الإجابات الآن."}

        player = self.touch_player(player_id=player_id, token=token)
        if not player:
            return {"success": False, "message": "هذا اللاعب غير معروف عندي."}

        if player["id"] in self.room["submissions"]:
            return {"success": False, "message": "إجابتك وصلت بالفعل."}

        answer_text = " ".join(answer_text.strip().split())
        if not answer_text:
            return {"success": False, "message": "اكتب خدعة أولًا."}

        if len(answer_text) > 100:
            return {"success": False, "message": "الإجابة طويلة جدًا، اختصرها."}

        submitted_normalized = normalize_arabic_text(answer_text)
        if submitted_normalized == normalize_arabic_text(self.room["current_answer"]):
            return {"success": False, "message": "هذه هي الحقيقة نفسها... نريد خدعة أذكى."}

        existing_normalized = self._normalize_existing_round_answers()
        if submitted_normalized in existing_normalized:
            return {"success": False, "message": "هذه الخدعة موجودة بالفعل، جرّب غيرها."}

        self.room["submissions"][player["id"]] = answer_text

        required_players = self._required_players_for_action(self.room["submissions"])
        if required_players and len(self.room["submissions"]) >= len(required_players):
            self.prepare_vote_options()

        return {"success": True}

    def _make_vote_option(self, text, owner, option_type):
        return {
            "id": str(uuid.uuid4()),
            "text": text,
            "owner": owner,
            "type": option_type,
        }

    def prepare_vote_options(self):
        normalized_texts = set()
        options = []

        for player_id, text in self.room["submissions"].items():
            normalized = normalize_arabic_text(text)
            if normalized in normalized_texts:
                continue
            normalized_texts.add(normalized)
            options.append(self._make_vote_option(text, player_id, "player"))

        truth_normalized = normalize_arabic_text(self.room["current_answer"])
        normalized_texts.add(truth_normalized)
        options.append(self._make_vote_option(self.room["current_answer"], "TRUTH", "truth"))

        desired_option_count = min(6, max(4, len(self.room["players"]) + 1))
        distractors = list(self.room["current_distractors"])
        random.shuffle(distractors)

        for text in distractors:
            normalized = normalize_arabic_text(text)
            if normalized in normalized_texts:
                continue
            options.append(self._make_vote_option(text, "HOUSE", "house"))
            normalized_texts.add(normalized)
            if len(options) >= desired_option_count:
                break

        random.shuffle(options)
        self.room["vote_options"] = options
        self.set_phase("VOTE", self.room["vote_duration"])

    def submit_vote(self, player_id, token, option_id):
        self.check_and_advance_phase()

        if self.room["status"] != "VOTE":
            return {"success": False, "message": "التصويت مقفّل الآن."}

        player = self.touch_player(player_id=player_id, token=token)
        if not player:
            return {"success": False, "message": "هذا اللاعب غير معروف عندي."}

        if player["id"] in self.room["votes"]:
            return {"success": False, "message": "صوتك وصل بالفعل."}

        selected_option = next(
            (option for option in self.room["vote_options"] if option["id"] == option_id),
            None,
        )
        if not selected_option:
            return {"success": False, "message": "الخيار الذي اخترته غير صالح."}

        if selected_option["owner"] == player["id"]:
            return {"success": False, "message": "لا يمكنك التصويت لخدعتك."}

        self.room["votes"][player["id"]] = option_id

        required_players = self._required_players_for_action(self.room["votes"])
        if required_players and len(self.room["votes"]) >= len(required_players):
            self.calculate_scores()

        return {"success": True}

    def calculate_scores(self):
        players_before = self.get_sorted_players()
        before_positions = {
            player["id"]: index + 1
            for index, player in enumerate(players_before)
        }
        round_points = {player["id"]: 0 for player in self.room["players"]}
        fooled_map = {player["id"]: [] for player in self.room["players"]}
        correct_pickers = []
        house_hits = []

        for voter_id, option_id in self.room["votes"].items():
            voter = self.get_player(player_id=voter_id)
            selected_option = next(
                (option for option in self.room["vote_options"] if option["id"] == option_id),
                None,
            )
            if not voter or not selected_option:
                continue

            if selected_option["type"] == "truth":
                voter["score"] += 2
                round_points[voter["id"]] += 2
                correct_pickers.append(voter["name"])
            elif selected_option["type"] == "player":
                owner = self.get_player(player_id=selected_option["owner"])
                if owner:
                    owner["score"] += 1
                    round_points[owner["id"]] += 1
                    fooled_map[owner["id"]].append(voter["name"])
            else:
                house_hits.append(
                    {
                        "player_name": voter["name"],
                        "picked_text": selected_option["text"],
                    }
                )

        players_after = self.get_sorted_players()
        ranking_changes = []
        for index, player in enumerate(players_after):
            before_rank = before_positions.get(player["id"], index + 1)
            after_rank = index + 1
            movement = before_rank - after_rank
            ranking_changes.append(
                {
                    "player_name": player["name"],
                    "before_rank": before_rank,
                    "after_rank": after_rank,
                    "movement": movement,
                }
            )

        fooled_details = []
        for option in self.room["vote_options"]:
            if option["type"] != "player":
                continue
            owner = self.get_player(player_id=option["owner"])
            if not owner:
                continue
            fooled_names = fooled_map.get(owner["id"], [])
            if not fooled_names:
                continue
            fooled_details.append(
                {
                    "player_name": owner["name"],
                    "answer_text": option["text"],
                    "fooled_names": fooled_names,
                    "points": len(fooled_names),
                }
            )

        point_rows = []
        for player in players_after:
            point_rows.append(
                {
                    "player_name": player["name"],
                    "points": round_points[player["id"]],
                    "total_score": player["score"],
                }
            )

        self.room["round_results"] = {
            "question": self.room["current_question"],
            "correct_answer": self.room["current_answer"],
            "correct_pickers": correct_pickers,
            "fooled_details": fooled_details,
            "house_hits": house_hits,
            "point_rows": point_rows,
            "ranking_changes": ranking_changes,
        }
        self.set_phase("RESULTS", self.room["results_duration"])

    def skip_current_phase(self):
        if self.room["status"] in {"LOBBY", "GAME_OVER"}:
            return {"success": False, "message": "لا يوجد طور نشط لتخطيه الآن."}
        self.force_advance_after_timeout()
        return {"success": True, "status": self.room["status"]}

    def force_advance_after_timeout(self):
        status = self.room["status"]
        if status == "INTRO":
            self.begin_submit_phase()
        elif status == "SUBMIT":
            self.prepare_vote_options()
        elif status == "VOTE":
            self.calculate_scores()
        elif status == "RESULTS":
            self.start_next_round()

    def check_and_advance_phase(self):
        remaining = self.get_remaining_seconds()
        if remaining is not None and remaining <= 0:
            self.force_advance_after_timeout()

    def get_phase_copy(self, status):
        copies = {
            "LOBBY": {
                "label": "الاستعداد",
                "title": "جهّز الفريق وابدأ الجولة",
                "hint": "انضموا أولًا، ثم خلي المضيف يطلق أول سؤال.",
            },
            "INTRO": {
                "label": "بداية الجولة",
                "title": "سؤال جديد داخل بقوة",
                "hint": "احفظ السؤال جيدًا... وبعد لحظات تبدأ الخدع.",
            },
            "SUBMIT": {
                "label": "وقت الخدعة",
                "title": "اكتب إجابة تبدو مقنعة",
                "hint": "لا تكتب الحقيقة، واكسب من يصدقك.",
            },
            "VOTE": {
                "label": "وقت الشك",
                "title": "من صاحب الحقيقة؟",
                "hint": "اختر الإجابة الصح... أو انخدع مثل البقية.",
            },
            "RESULTS": {
                "label": "كشف الأوراق",
                "title": "شوف من كشف الحقيقة ومن لخبط الكل",
                "hint": "النقاط تحسم هنا، والترتيب يتقلب بسرعة.",
            },
            "GAME_OVER": {
                "label": "النهاية",
                "title": "خلصت السهرة",
                "hint": "هذا هو ترتيب الأبطال بعد آخر خدعة.",
            },
        }
        return copies.get(status, copies["LOBBY"])

    def get_public_state(self, player_id=None, token=None):
        player = None
        if player_id or token:
            player = self.touch_player(player_id=player_id, token=token)

        self.check_and_advance_phase()
        self.mark_inactive_players()

        player_state = {
            "joined": bool(player),
            "player_id": player["id"] if player else "",
            "name": player["name"] if player else "",
            "has_submitted": player["id"] in self.room["submissions"] if player else False,
            "has_voted": player["id"] in self.room["votes"] if player else False,
            "connected": player["connected"] if player else False,
        }

        focus_map = {
            "LOBBY": "join",
            "INTRO": "intro",
            "SUBMIT": "answer" if player_state["joined"] and not player_state["has_submitted"] else "wait",
            "VOTE": "vote" if player_state["joined"] and not player_state["has_voted"] else "wait",
            "RESULTS": "results",
            "GAME_OVER": "results",
        }
        player_state["focus"] = focus_map.get(self.room["status"], "wait")

        return {
            "room_code": self.room["room_code"],
            "status": self.room["status"],
            "phase_copy": self.get_phase_copy(self.room["status"]),
            "players": [self._public_player(player) for player in self.get_sorted_players()],
            "question": self.room["current_question"],
            "vote_options": self.room["vote_options"] if self.room["status"] in {"VOTE", "RESULTS"} else [],
            "round_results": self.room["round_results"],
            "remaining_seconds": self.get_remaining_seconds(),
            "submit_duration": self.room["submit_duration"],
            "vote_duration": self.room["vote_duration"],
            "results_duration": self.room["results_duration"],
            "final_ranking": [self._public_player(player) for player in self.room["final_ranking"]],
            "round_number": self.room["round_number"],
            "player_state": player_state,
        }
