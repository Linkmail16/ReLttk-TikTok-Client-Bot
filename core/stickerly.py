import requests
import uuid
import os
import io
from PIL import Image

DUID = "06318e3fc7a8cac0"
AUTH = "Bearer : YkW0OjlTsmVNrnBDpfDo3qc5a4xtD/TwT58yiXb8j/p7iW4hlpuozYIIjBVzA6CHsRS8dTBvqS+npAAROhJeJutda1P1IhbltOCyzP5f1hg=\\1\\m3Ep7wgYb5kWjh/pXltC7F3txw3zX930r94pboHWb5bCjKXFrYDRrw4="
USER_AGENT = "androidapp.stickerly/3.36.0 (NX809J; U; Android 28; es-ES; us;)"
BASE_URL = "https://api.sticker.ly/v4"

BASE_HEADERS = {
    "x-duid": DUID,
    "User-Agent": USER_AGENT,
    "authorization": AUTH,
    "Host": "api.sticker.ly",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}


def _make_session():
    s = requests.Session()
    s.headers.update(BASE_HEADERS)
    return s


def create_pack(name: str, author: str, animated: bool = False) -> dict:
    """Crea un pack nuevo. Devuelve el resultado completo (incluye packId y shareUrl)."""
    boundary = str(uuid.uuid4())
    meta = (
        f'{{"packId":"","name":"{name}","authorName":"{author}",'
        f'"website":"","privatePack":false,"animated":{str(animated).lower()}}}'
    )
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"metaJson\"\r\n"
        f"Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(meta)}\r\n"
        f"\r\n"
        f"{meta}\r\n"
        f"--{boundary}--\r\n"
    )
    headers = {
        **BASE_HEADERS,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    resp = requests.post(f"{BASE_URL}/stickerPack", data=body.encode(), headers=headers)
    resp.raise_for_status()
    return resp.json()["result"]


def mark_pack_viewed(pack_id: str) -> bool:
    """Llama al endpoint /view que la app hace tras crear el pack."""
    s = _make_session()
    resp = s.post(f"{BASE_URL}/stickerPack/{pack_id}/view")
    resp.raise_for_status()
    return resp.json().get("result", {}).get("success", False)


def _fit_to_canvas(frame: Image.Image, size: int = 512) -> Image.Image:
    frame = frame.convert("RGBA")
    ratio = max(size / frame.width, size / frame.height)
    new_w = int(frame.width * ratio)
    new_h = int(frame.height * ratio)
    frame = frame.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - size) // 2
    y = (new_h - size) // 2
    return frame.crop((x, y, x + size, y + size))


def count_frames(image_path: str) -> int:
    from PIL import ImageSequence
    img = Image.open(image_path)
    return sum(1 for _ in ImageSequence.Iterator(img))


def _resize_image(image_path: str, size: int = 512, animated_pack: bool = False) -> tuple[bytes, str]:
    """Devuelve (bytes, filename) con la imagen redimensionada a size x size."""
    from PIL import ImageSequence
    img = Image.open(image_path)
    frames = []
    durations = []
    for frame in ImageSequence.Iterator(img):
        frames.append(_fit_to_canvas(frame.copy(), size))
        durations.append(frame.info.get("duration", img.info.get("duration", 100)))

    buf = io.BytesIO()
    base = os.path.splitext(os.path.basename(image_path))[0]

    if animated_pack:
        out_name = base + ".webp"
        extra = frames[1:] if len(frames) > 1 else [frames[0]]
        dur = durations if len(frames) > 1 else [500, 500]

        def _save_webp(q):
            b = io.BytesIO()
            frames[0].save(b, format="WEBP", save_all=True, append_images=extra,
                           loop=0, duration=dur, quality=q, method=4)
            return b

        buf = _save_webp(60)
        if len(buf.getvalue()) > 490_000:
            for q in (50, 40, 30, 20, 10):
                buf = _save_webp(q)
                if len(buf.getvalue()) <= 490_000:
                    break
    else:
        out_name = base + ".png"
        frames[0].save(buf, format="PNG")

    return buf.getvalue(), out_name


def add_sticker(pack_id: str, image_path: str, existing_filenames: list[str] = None, tray_filename: str = None, animated_pack: bool = False) -> dict:
    """
    Sube una imagen al pack. Redimensiona a 512x512 antes de subir.
    existing_filenames: nombres de los stickers ya subidos al pack (para el tagMap acumulado).
    tray_filename: icono del pack (por defecto el primer sticker subido).
    animated_pack: si True, convierte imágenes estáticas a WebP animado.
    """
    import json as _json
    boundary = str(uuid.uuid4())
    image_data, filename = _resize_image(image_path, animated_pack=animated_pack)
    if existing_filenames is None:
        existing_filenames = []
    all_filenames = existing_filenames + [filename]
    if tray_filename is None:
        tray_filename = all_filenames[0]

    meta = _json.dumps({
        "packId": pack_id,
        "tagMap": [{name: []} for name in all_filenames],
        "trayFileName": tray_filename,
    }, separators=(",", ":"))

    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"resources\"; filename=\"{filename}\"\r\n"
        f"Content-Type: image/*\r\n"
        f"Content-Length: {len(image_data)}\r\n"
        f"\r\n"
    ).encode() + image_data + (
        f"\r\n--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"metaJson\"\r\n"
        f"Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(meta)}\r\n"
        f"\r\n"
        f"{meta}\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    headers = {
        **BASE_HEADERS,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    resp = requests.post(f"{BASE_URL}/sticker", data=body, headers=headers)
    if "result" not in resp.json():
        raise ValueError(f"Error al subir {filename}: {resp.text}")
    resp.raise_for_status()
    return resp.json()["result"]


def finalize_pack(pack_id: str) -> bool:
    """Dispara la conversión de imágenes del pack (paso final)."""
    s = _make_session()
    s.headers.update({"Content-Type": "application/json; charset=UTF-8"})
    resp = s.post(
        f"{BASE_URL}/stickerPack/imageConversion",
        json={"packIds": [pack_id]},
    )
    resp.raise_for_status()
    return resp.json().get("result", {}).get("success", False)


def get_pack(pack_id: str) -> dict:
    """Obtiene el estado actual del pack con sus stickers."""
    s = _make_session()
    resp = s.get(f"{BASE_URL}/stickerPack/{pack_id}", params={"needRelation": "true"})
    resp.raise_for_status()
    return resp.json()["result"]


def create_sticker_pack(
    name: str,
    author: str,
    image_paths: list[str],
    animated: bool = False,
    pack_id: str = None,
) -> dict:
    """
    Sube imágenes a un pack nuevo o existente y finaliza.
    - pack_id: si se pasa, añade a ese pack en vez de crear uno nuevo.
    """
    if pack_id:
        existing = get_pack(pack_id)
        existing_filenames = [s["fileName"] for s in existing.get("stickers", [])]
        share_url = existing["shareUrl"]
        print(f"Añadiendo al pack existente: {pack_id} -> {share_url}")
        mark_pack_viewed(pack_id)
    else:
        pack = create_pack(name, author, animated=animated)
        pack_id = pack["packId"]
        share_url = pack["shareUrl"]
        existing_filenames = []
        print(f"Pack creado: {pack_id} -> {share_url}")
        mark_pack_viewed(pack_id)

    for path in image_paths:
        result = add_sticker(pack_id, path, existing_filenames=existing_filenames, animated_pack=animated)
        existing_filenames = [s["fileName"] for s in result.get("stickers", [])]
        print(f"Sticker subido: {os.path.basename(path)} ({len(existing_filenames)} en el pack)")

    finalize_pack(pack_id)
    print("Pack finalizado.")

    return get_pack(pack_id)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Crea un sticker pack en Sticker.ly")
    parser.add_argument("--name", required=True, help="Nombre del pack")
    parser.add_argument("--author", default="laguencio983", help="Nombre del autor")
    parser.add_argument("--images", nargs="+", required=True, help="Rutas a las imágenes (PNG o WebP)")
    parser.add_argument("--animated", action="store_true", help="Pack animado (WebP)")
    parser.add_argument("--pack-id", default=None, help="ID de pack existente para añadir stickers")
    args = parser.parse_args()

    result = create_sticker_pack(
        name=args.name,
        author=args.author,
        image_paths=args.images,
        animated=args.animated,
        pack_id=args.pack_id,
    )
    print(f"\nShareUrl: {result['shareUrl']}")
    print(f"Stickers: {len(result['stickers'])}")
