import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


PROJECT_DIR = Path(__file__).resolve().parent.parent
CGI_DIR = PROJECT_DIR / "cgi-bin"
sys.path.insert(0, str(CGI_DIR))

from auth_utils import verifikasi_token


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
ALLOWED_SCRIPTS = {
    "detail_tfidf",
    "get_akurasi",
    "hapus",
    "login",
    "proses",
    "proses_pre",
    "proses_svm",
    "tampil",
    "uji_sentimen",
}
ADMIN_SCRIPTS = {"hapus", "proses", "proses_pre", "proses_svm"}


def _parse_cgi_output(stdout):
    text = stdout.decode("utf-8", "replace")
    parts = re.split(r"\r?\n\r?\n", text, maxsplit=1)
    if len(parts) != 2:
        raise RuntimeError("Respons CGI tidak valid.")

    headers = {}
    for line in parts[0].splitlines():
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    return headers, parts[1]


def _run_cgi(script, method, body, query_string, content_type):
    env = os.environ.copy()
    env.update({
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": content_type or "application/json",
        "PYTHONIOENCODING": "utf-8",
        "QUERY_STRING": query_string,
        "REQUEST_METHOD": method,
        "SCRIPT_NAME": f"/cgi-bin/{script}.py",
    })
    result = subprocess.run(
        [sys.executable, str(CGI_DIR / f"{script}.py")],
        cwd=str(PROJECT_DIR),
        env=env,
        input=body,
        capture_output=True,
        timeout=285,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(detail[-1200:] or "Proses Python berhenti tidak normal.")
    return _parse_cgi_output(result.stdout)


@app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def handler(request: Request, path: str):
    if request.query_params.get("health") == "1":
        return {"status": "ok", "runtime": "python"}

    script = request.query_params.get("script", "")
    if script not in ALLOWED_SCRIPTS:
        return JSONResponse({"status": "error", "message": "Endpoint tidak ditemukan."}, status_code=404)

    if script in ADMIN_SCRIPTS:
        authorization = request.headers.get("authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else ""
        if not verifikasi_token(token):
            return JSONResponse(
                {"status": "error", "message": "Sesi admin tidak valid atau sudah berakhir. Silakan login kembali."},
                status_code=401,
            )

    body = await request.body()
    query_items = [(key, value) for key, value in request.query_params.multi_items() if key not in {"script", "health"}]
    query_string = urlencode(query_items)

    try:
        headers, content = await asyncio.to_thread(
            _run_cgi,
            script,
            request.method,
            body,
            query_string,
            request.headers.get("content-type", ""),
        )
        response_headers = {"Cache-Control": headers.get("cache-control", "no-store")}
        return Response(
            content=content,
            media_type=headers.get("content-type", "application/json"),
            headers=response_headers,
        )
    except subprocess.TimeoutExpired:
        return JSONResponse({"status": "error", "message": "Proses melewati batas waktu server."}, status_code=504)
    except Exception as error:
        return JSONResponse({"status": "error", "message": f"Server Python gagal: {error}"}, status_code=500)
