import asyncio
import io
import json
import os
import sys
import tempfile
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("stickerly", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "stickerly.py"))
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
create_pack = _mod.create_pack
mark_pack_viewed = _mod.mark_pack_viewed
add_sticker = _mod.add_sticker
finalize_pack = _mod.finalize_pack
get_pack = _mod.get_pack
_resize_image = _mod._resize_image
count_frames = _mod.count_frames

_STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".sticker2wa.json")
_STICKER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".sticker2wa_pending")
_GALLERY_API  = "https://geometryamerica.xyz/gallery/api/posts"
_WA_API_BASE  = "http://72.61.75.113:5052"
_WA_SECRET    = "lkapi_secret_2026"
_WA_HEADERS   = {"X-API-Secret": _WA_SECRET, "Content-Type": "application/json"}
_WA_BOT_ID       = "stip"
_WA_TOKEN_CHAT   = "120363409760185880@newsletter"
_SETUP_MODE   = "setup_method"
_SETUP_NAME   = "setup_name"
_SETUP_AUTHOR = "setup_author"
_READY        = "ready"

_states: dict = {}
_locks: dict  = {}


def _load():
    global _states
    try:
        with open(_STATE_FILE, encoding="utf-8") as f:
            _states = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _states = {}


def _save():
    with open(_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(_states, f, ensure_ascii=False, indent=2)


_load()


def _user_state(conv_id: str) -> dict:
    return _states.get(conv_id, {})


def _set_user(conv_id: str, data: dict):
    _states[conv_id] = data
    _save()


def _is_private(msg: dict) -> bool:
    return not msg.get("is_group", False)


def _pending_dir(conv_id: str, kind: str) -> str:
    safe = conv_id.replace(":", "_")
    d = os.path.join(_STICKER_DIR, safe, kind)
    os.makedirs(d, exist_ok=True)
    return d



def _build_wastickers(stickers: list[bytes], name: str, author: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("author.txt", author.encode("utf-8"))
        zf.writestr("title.txt", name.encode("utf-8"))
        for i, data in enumerate(stickers):
            ts = 1785404888 + i
            zf.writestr(f"{ts}.webp", data)
    return buf.getvalue()


def _upload_gallery(data: bytes, filename: str) -> str:
    boundary = "----lttk" + os.urandom(8).hex()
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"text\"\r\n\r\n"
        f"Sticker pack\r\n"
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        _GALLERY_API, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    post = result["post"]
    return f"https://geometryamerica.xyz/gallery?post={post['id']}"



async def _download_sticker(bot, msg: dict) -> bytes | None:
    try:
        result = await bot.download(msg)
    except Exception:
        return None
    if not result:
        return None
    data, _ = result
    return data


async def _handle_stickerly(bot, conv_id: str, msg: dict, state: dict):
    step = state.get("step")

    if step == _SETUP_NAME:
        state["name"] = msg["text"].strip()
        state["step"] = _SETUP_AUTHOR
        _set_user(conv_id, state)
        await bot.send_message(conv_id=conv_id, text="Ahora el nombre del autor:")
        return

    if step == _SETUP_AUTHOR:
        state["author"] = msg["text"].strip()
        state["step"] = _READY
        state["method"] = "stickerly"
        _set_user(conv_id, state)
        await bot.send_message(
            conv_id=conv_id,
            text=(
                f"Listo! Pack configurado:\n"
                f"Nombre: {state['name']}\n"
                f"Autor: {state['author']}\n\n"
                f"De ahora en adelante cada sticker que me mandes lo subiré al pack de WhatsApp.\n"
                f"Los animados y estáticos van en packs separados, los crearé automáticamente."
            )
        )
        return


async def _handle_download(bot, conv_id: str, msg: dict, state: dict):
    step = state.get("step")

    if step == _SETUP_NAME:
        state["name"] = msg["text"].strip()
        state["step"] = _SETUP_AUTHOR
        _set_user(conv_id, state)
        await bot.send_message(conv_id=conv_id, text="Ahora el nombre del autor:")
        return

    if step == _SETUP_AUTHOR:
        state["author"] = msg["text"].strip()
        state["step"] = _READY
        state["method"] = "download"
        _set_user(conv_id, state)
        await bot.send_message(
            conv_id=conv_id,
            text=(
                f"Listo! Configurado para descarga:\n"
                f"Nombre: {state['name']}\n"
                f"Autor: {state['author']}\n\n"
                f"Mándame los stickers que quieras. Cuando termines escribe /save o /guardar y te mando el link de descarga."
            )
        )
        return


async def _do_download_export(bot, conv_id: str, state: dict):
    loop = asyncio.get_event_loop()

    async def _export(kind: str, label: str):
        d = _pending_dir(conv_id, kind)
        files = sorted(os.listdir(d))
        if not files:
            return
        stickers = [open(os.path.join(d, f), "rb").read() for f in files]
        wastickers = await loop.run_in_executor(
            None, _build_wastickers, stickers, state["name"], state["author"]
        )
        safe_name = state["name"].replace(" ", "_")
        fname = f"{safe_name}_{label}.wastickers"
        link = await loop.run_in_executor(None, _upload_gallery, wastickers, fname)
        await bot.send_message(conv_id=conv_id, text=f"Pack {label} (ábrelo en el navegador para descargarlo):\n{link}")

    animated_d = _pending_dir(conv_id, "animated")
    if not os.listdir(animated_d):
        await bot.send_message(conv_id=conv_id, text="No hay stickers guardados aún.")
        return

    await bot.send_message(conv_id=conv_id, text="Creando el pack, un momento...")
    await _export("animated", state["name"])


async def _start_whatsapp_setup(bot, conv_id: str, state: dict):
    state["method"] = "whatsapp"
    state["step"] = _READY
    state["wa_bot_id"] = _WA_BOT_ID
    state["wa_chat"] = _WA_TOKEN_CHAT
    _set_user(conv_id, state)
    await bot.send_message(conv_id=conv_id, text="Listo! Mándame tus stickers y los enviaré directo a este canal de WhatsApp:")
    await bot.send_message(conv_id=conv_id, text="https://whatsapp.com/channel/0029VbDioa16BIEldFX28N2Z")



async def _process_sticker_stickerly(bot, conv_id: str, msg: dict, state: dict):
    loop = asyncio.get_event_loop()

    raw = await _download_sticker(bot, msg)
    if not raw:
        return

    if conv_id not in _locks:
        _locks[conv_id] = asyncio.Lock()
    async with _locks[conv_id]:
        await _upload_stickerly(bot, conv_id, msg, state, raw, loop)


async def _upload_stickerly(bot, conv_id, msg, state, raw, loop):
    import uuid
    state = _user_state(conv_id)

    tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.webp")
    with open(tmp_path, "wb") as f:
        f.write(raw)

    try:
        nframes = await loop.run_in_executor(None, count_frames, tmp_path)
        is_animated = nframes >= 2
        pack_key = "pack_animated" if is_animated else "pack_static"

        if pack_key not in state:
            def _create():
                pack = create_pack(state["name"], state["author"], animated=is_animated)
                mark_pack_viewed(pack["packId"])
                return pack

            pack = await loop.run_in_executor(None, _create)
            label = "animado" if is_animated else "estático"
            state[pack_key] = {"id": pack["packId"], "url": pack["shareUrl"], "filenames": []}
            _set_user(conv_id, state)
            await bot.send_message(conv_id=conv_id, text=f"Pack {label} creado: {pack['shareUrl']}")

        pack_id = state[pack_key]["id"]

        def _upload():
            current = get_pack(pack_id)
            existing_filenames = [s["fileName"] for s in current.get("stickers", [])]
            result = add_sticker(pack_id, tmp_path, existing_filenames=existing_filenames, animated_pack=is_animated)
            finalize_pack(pack_id)
            return result

        await loop.run_in_executor(None, _upload)
    finally:
        os.unlink(tmp_path)

    await bot.send_reaction(msg=msg, emoji="❤️")


async def _process_sticker_download(bot, conv_id: str, msg: dict, state: dict):
    loop = asyncio.get_event_loop()

    raw = await _download_sticker(bot, msg)
    if not raw:
        return

    import hashlib
    import uuid as _uuid

    tmp_in = os.path.join(tempfile.gettempdir(), f"{_uuid.uuid4().hex}.webp")
    with open(tmp_in, "wb") as f:
        f.write(raw)

    try:
        resized, _ = await loop.run_in_executor(None, _resize_image, tmp_in, 512, True)
    finally:
        os.unlink(tmp_in)

    h = hashlib.md5(resized).hexdigest()
    d = _pending_dir(conv_id, "animated")
    if any(f.startswith(h) for f in os.listdir(d)):
        return

    idx = len(os.listdir(d)) + 1
    with open(os.path.join(d, f"{h}_{idx:04d}.webp"), "wb") as f:
        f.write(resized)

    await bot.send_reaction(msg=msg, emoji="❤️")


def _fit_frame(frame, size=512):
    from PIL import Image
    f = frame.copy().convert("RGBA")
    scale = size / max(f.width, f.height)
    new_w, new_h = int(f.width * scale), int(f.height * scale)
    f = f.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(f, ((size - new_w) // 2, (size - new_h) // 2), f)
    return canvas


def _to_webp_512(data: bytes) -> bytes:
    from PIL import Image, ImageSequence
    img = Image.open(io.BytesIO(data))
    frames, durations = [], []
    try:
        for frame in ImageSequence.Iterator(img):
            frames.append(_fit_frame(frame))
            durations.append(frame.info.get("duration", img.info.get("duration", 100)))
    except Exception:
        pass

    if not frames:
        frames = [_fit_frame(img)]
        durations = [100]
    buf = io.BytesIO()
    if len(frames) > 1:
        dur = durations if len(durations) == len(frames) else 100
        def _save_anim(q):
            b = io.BytesIO()
            frames[0].save(b, format="WEBP", save_all=True,
                           append_images=frames[1:], loop=0, duration=dur, quality=q)
            return b
        buf = _save_anim(80)
        if len(buf.getvalue()) > 900_000:
            for q in (60, 40, 20):
                buf = _save_anim(q)
                if len(buf.getvalue()) <= 900_000:
                    break
    else:
        frames[0].save(buf, format="WEBP", quality=80)
    return buf.getvalue()


async def _process_sticker_whatsapp(bot, conv_id: str, msg: dict, state: dict):
    loop = asyncio.get_event_loop()
    chat_jid = state.get("wa_chat")
    bot_id   = state.get("wa_bot_id", _WA_BOT_ID)

    if not chat_jid:
        await bot.send_message(conv_id=conv_id, text="Error: falta configuración de WhatsApp. Envía un sticker para configurar de nuevo.")
        return

    raw = await _download_sticker(bot, msg)
    if not raw:
        return

    import base64

    try:
        webp_bytes = await loop.run_in_executor(None, _to_webp_512, raw)
        b64 = base64.b64encode(webp_bytes).decode()

        def _send():
            payload = json.dumps({"chatJid": chat_jid, "stickerBase64": b64}).encode()
            req = urllib.request.Request(
                f"{_WA_API_BASE}/bots/{bot_id}/sendSticker",
                data=payload, method="POST",
                headers={**_WA_HEADERS, "Content-Length": str(len(payload))},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())

        result = await loop.run_in_executor(None, _send)
        if result.get("ok") or result.get("success"):
            await bot.send_reaction(msg=msg, emoji="❤️")
        else:
            await bot.send_message(conv_id=conv_id, text=f"Error al enviar a WhatsApp: {result}")
    except Exception as e:
        import traceback
        await bot.send_message(conv_id=conv_id, text=f"Error: {e}\n{traceback.format_exc()[-500:]}")


async def on_message(bot, msg: dict):
    if not _is_private(msg):
        return

    conv_id = msg["conv_id"]
    state = _user_state(conv_id)
    text = msg["text"].strip().lower()
    awe = msg.get("awe_type", 0)
    in_setup = state.get("step") in (_SETUP_MODE, _SETUP_NAME, _SETUP_AUTHOR)

    if text == "/tipo":
        if not state or state.get("step") in (None, _SETUP_MODE):
            return
        _set_user(conv_id, {"step": _SETUP_MODE})
        await bot.send_message(conv_id=conv_id, text="Envía un sticker para elegir el método.")
        return

    if text == "/newpack" and state.get("step") == _READY and state.get("method") == "stickerly":
        state.pop("pack_animated", None)
        state.pop("pack_static", None)
        _set_user(conv_id, state)
        await bot.send_message(conv_id=conv_id, text="Listo, el próximo sticker creará un pack nuevo.")
        return

    if text == "/delpack" and state.get("step") == _READY:
        for kind in ("animated", "static"):
            d = _pending_dir(conv_id, kind)
            for f in os.listdir(d):
                os.remove(os.path.join(d, f))
        await bot.send_message(conv_id=conv_id, text="Stickers borrados.")
        return

    if not in_setup and awe != 1805 and not (state.get("step") == _READY and text in ("/save", "/guardar")):
        return

    if awe == 1805 and state.get("step") in (None, _SETUP_MODE):
        _set_user(conv_id, {"step": _SETUP_MODE})
        await bot.send_message(
            conv_id=conv_id,
            text=(
                "Para pasar tus stickers a WhatsApp elige un método:\n\n"
                "1 — Crear un pack con Stickerly\n"
                "2 — Crear un pack para descargar\n"
                "3 — Envío directo a WhatsApp\n\n"
                "Responde con 1, 2 o 3."
            )
        )
        return

    if state.get("step") == _SETUP_MODE:
        if not text:
            return
        if text == "1":
            state["step"] = _SETUP_NAME
            state["method"] = "stickerly"
            _set_user(conv_id, state)
            await bot.send_message(conv_id=conv_id, text="¿Cómo se llamará el pack?")
        elif text == "2":
            state["step"] = _SETUP_NAME
            state["method"] = "download"
            _set_user(conv_id, state)
            await bot.send_message(conv_id=conv_id, text="¿Cómo se llamará el pack?")
        elif text == "3":
            await _start_whatsapp_setup(bot, conv_id, state)
        else:
            await bot.send_message(conv_id=conv_id, text="Responde con 1, 2 o 3.")
        return

    method = state.get("method")

    if state.get("step") in (_SETUP_NAME, _SETUP_AUTHOR):
        if not msg["text"].strip():
            return
        if method == "stickerly":
            await _handle_stickerly(bot, conv_id, msg, state)
        else:
            await _handle_download(bot, conv_id, msg, state)
        return

    if state.get("step") == _READY:
        if method == "download" and text in ("/save", "/guardar"):
            await _do_download_export(bot, conv_id, state)
            return

        if awe == 1805:
            if method == "stickerly":
                await _process_sticker_stickerly(bot, conv_id, msg, state)
            elif method == "download":
                await _process_sticker_download(bot, conv_id, msg, state)
            elif method == "whatsapp":
                await _process_sticker_whatsapp(bot, conv_id, msg, state)
