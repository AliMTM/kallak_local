import io
import socket

from aiohttp import web
import aiohttp_jinja2
import jinja2
import segno

from questions_loader import load_questions
from room_manager import RoomManager


questions = load_questions()
room_manager = RoomManager(questions)


def detect_local_ip():
    candidates = []

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("10.255.255.255", 1))
        candidates.append(sock.getsockname()[0])
        sock.close()
    except Exception:
        pass

    try:
        candidates.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    except Exception:
        pass

    for ip in candidates:
        if ip and not ip.startswith("127.") and ip != "0.0.0.0":
            return ip

    return "127.0.0.1"


@aiohttp_jinja2.template("host.html")
async def host_page(request):
    return {"local_ip": detect_local_ip()}


@aiohttp_jinja2.template("join.html")
async def join_page(request):
    return {}


async def create_room(request):
    room = room_manager.create_room()
    return web.json_response({"success": True, "room": room})


async def join_room(request):
    data = await request.post()
    name = str(data.get("name", "")).strip()
    token = str(data.get("token", "")).strip()
    return web.json_response(room_manager.add_player(name, token))


async def start_game(request):
    return web.json_response(room_manager.start_game())


async def next_round(request):
    return web.json_response(room_manager.start_next_round())


async def skip_phase(request):
    return web.json_response(room_manager.skip_current_phase())


async def set_durations(request):
    data = await request.post()
    submit_duration = data.get("submit_duration", "30")
    vote_duration = data.get("vote_duration", "20")
    results_duration = data.get("results_duration", "12")
    return web.json_response(
        room_manager.set_durations(submit_duration, vote_duration, results_duration)
    )


async def submit_answer(request):
    data = await request.post()
    player_id = str(data.get("player_id", "")).strip()
    token = str(data.get("token", "")).strip()
    answer = str(data.get("answer", "")).strip()
    return web.json_response(room_manager.submit_fake_answer(player_id, token, answer))


async def submit_vote(request):
    data = await request.post()
    player_id = str(data.get("player_id", "")).strip()
    token = str(data.get("token", "")).strip()
    option_id = str(data.get("option_id", "")).strip()
    return web.json_response(room_manager.submit_vote(player_id, token, option_id))


async def get_state(request):
    player_id = str(request.query.get("player_id", "")).strip()
    token = str(request.query.get("token", "")).strip()
    state = room_manager.get_public_state(player_id=player_id, token=token)
    state["join_url"] = f"http://{detect_local_ip()}:8000/join"
    return web.json_response(state)


async def qr_code(request):
    join_url = f"http://{detect_local_ip()}:8000/join"
    qr = segno.make(join_url)
    buffer = io.BytesIO()
    qr.save(buffer, kind="png", scale=6)
    return web.Response(body=buffer.getvalue(), content_type="image/png")


async def home(request):
    raise web.HTTPFound("/host")


def create_app():
    app = web.Application()

    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("templates"))

    app.router.add_get("/", home)
    app.router.add_get("/host", host_page)
    app.router.add_get("/join", join_page)

    app.router.add_post("/host/create-room", create_room)
    app.router.add_post("/host/start-game", start_game)
    app.router.add_post("/host/next-round", next_round)
    app.router.add_post("/host/skip-phase", skip_phase)
    app.router.add_post("/host/set-durations", set_durations)

    app.router.add_post("/player/join", join_room)
    app.router.add_post("/player/submit-answer", submit_answer)
    app.router.add_post("/player/submit-vote", submit_vote)

    app.router.add_get("/api/state", get_state)
    app.router.add_get("/qr.png", qr_code)

    app.router.add_static("/static/", path="static", name="static")
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8000)
