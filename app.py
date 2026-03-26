from aiohttp import web
import aiohttp_jinja2
import jinja2
import io
import socket
import segno

from room_manager import RoomManager
from questions_loader import load_questions


questions = load_questions()
room_manager = RoomManager(questions)


def detect_local_ip():
    candidates = []

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        candidates.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    try:
        host_ip = socket.gethostbyname(socket.gethostname())
        candidates.append(host_ip)
    except Exception:
        pass

    for ip in candidates:
        if ip and not ip.startswith("127.") and ip != "0.0.0.0":
            return ip

    return "127.0.0.1"


@aiohttp_jinja2.template("host.html")
async def host_page(request):
    return {
        "local_ip": detect_local_ip()
    }


@aiohttp_jinja2.template("join.html")
async def join_page(request):
    return {}


async def create_room(request):
    room = room_manager.create_room()
    return web.json_response({"success": True, "room": room})


async def join_room(request):
    data = await request.post()
    name = str(data.get("name", "")).strip()

    result = room_manager.add_player(name)
    return web.json_response(result)


async def start_game(request):
    result = room_manager.start_game()
    return web.json_response(result)


async def next_round(request):
    result = room_manager.start_next_round()
    return web.json_response(result)


async def submit_answer(request):
    data = await request.post()
    player_id = str(data.get("player_id", "")).strip()
    answer = str(data.get("answer", "")).strip()

    result = room_manager.submit_fake_answer(player_id, answer)
    return web.json_response(result)


async def submit_vote(request):
    data = await request.post()
    player_id = str(data.get("player_id", "")).strip()
    option_id = str(data.get("option_id", "")).strip()

    result = room_manager.submit_vote(player_id, option_id)
    return web.json_response(result)


async def get_state(request):
    state = room_manager.get_public_state()
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

    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader("templates")
    )

    app.router.add_get("/", home)
    app.router.add_get("/host", host_page)
    app.router.add_get("/join", join_page)

    app.router.add_post("/host/create-room", create_room)
    app.router.add_post("/host/start-game", start_game)
    app.router.add_post("/host/next-round", next_round)

    app.router.add_post("/player/join", join_room)
    app.router.add_post("/player/submit-answer", submit_answer)
    app.router.add_post("/player/submit-vote", submit_vote)

    app.router.add_get("/api/state", get_state)
    app.router.add_get("/qr.png", qr_code)

    app.router.add_static("/static/", path="static", name="static")

    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8000)