"""Provider Letter Generator — FastAPI backend.

Flow:
  1. Staff upload a signed disbursement PDF + case number.
  2. POST /api/process       -> extract providers + pre-fill case data from Supabase.
  3. Staff review/edit everything in the browser.
  4. POST /api/generate      -> one .docx payment letter per provider.
  5. GET  /api/download/...   -> download individual letters or a ZIP of all.

Nothing is auto-sent or auto-mailed; staff review the final drafts.
"""

from __future__ import annotations

import datetime
import io
import logging
import os
import tempfile
import uuid
import zipfile

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.services import docx_generator
from app.services.extraction import extract_providers
from app.services.supabase_client import lookup_case

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Provider Letter Generator")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
GEN_ROOT = os.path.join(tempfile.gettempdir(), "provider_letters")
os.makedirs(GEN_ROOT, exist_ok=True)


def _today_letter_date() -> str:
    # e.g. "June 11, 2026"
    return datetime.date.today().strftime("%B %-d, %Y") if os.name != "nt" else (
        datetime.date.today().strftime("%B %d, %Y")
    )


# --------------------------------------------------------------------------- #
# Step 1+2: process uploaded disbursement
# --------------------------------------------------------------------------- #

@app.post("/api/process")
async def process_disbursement(
    file: UploadFile,
    case_number: str = Form(""),
):
    if file is None:
        raise HTTPException(status_code=400, detail="No file uploaded.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        extraction = extract_providers(data)
    except Exception as exc:
        logger.exception("Extraction failed")
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}")

    case = lookup_case(case_number)

    # Client name precedence: Supabase value if present, else extracted name.
    client_name = case.client_name or extraction.client_name

    return JSONResponse(
        {
            "case": {
                "case_number": case.case_number,
                "client_name": client_name,
                "date_of_birth": case.date_of_birth,
                "date_of_loss": case.date_of_incident,
                "found": case.found,
                "error": case.error,
            },
            "extracted_client_name": extraction.client_name,
            "supabase_client_name": case.client_name,
            "client_name_mismatch": bool(
                case.client_name
                and extraction.client_name
                and case.client_name.strip().lower()
                != extraction.client_name.strip().lower()
            ),
            "letter_date": _today_letter_date(),
            "providers": [p for p in extraction.to_dict()["providers"]],
            "used_llm": extraction.used_llm,
        }
    )


# --------------------------------------------------------------------------- #
# Step 4: generate letters
# --------------------------------------------------------------------------- #

class ProviderIn(BaseModel):
    provider_name: str = ""
    address_line1: str = ""
    address_line2: str = ""
    account_number: str = ""
    payment_amount: str = ""
    check_number: str = ""


class GenerateRequest(BaseModel):
    letter_date: str = ""
    client_name: str = ""
    date_of_birth: str = ""
    date_of_loss: str = ""
    providers: list[ProviderIn] = []


@app.post("/api/generate")
def generate(req: GenerateRequest):
    providers = [p for p in req.providers if p.provider_name.strip()]
    if not providers:
        raise HTTPException(status_code=400, detail="No providers to generate.")

    gen_id = uuid.uuid4().hex
    gen_dir = os.path.join(GEN_ROOT, gen_id)
    os.makedirs(gen_dir, exist_ok=True)

    letter_date = req.letter_date.strip() or _today_letter_date()
    files = []
    used_names: set[str] = set()

    for idx, p in enumerate(providers):
        filename = docx_generator.output_filename(req.client_name, p.provider_name)
        # Avoid collisions if two providers share a name.
        base, ext = os.path.splitext(filename)
        unique = filename
        n = 2
        while unique in used_names:
            unique = f"{base} ({n}){ext}"
            n += 1
        used_names.add(unique)

        out_path = os.path.join(gen_dir, unique)
        docx_generator.generate_letter(
            output_path=out_path,
            letter_date=letter_date,
            provider_name=p.provider_name,
            address_line1=p.address_line1,
            address_line2=p.address_line2,
            client_name=req.client_name,
            account_number=p.account_number,
            date_of_birth=req.date_of_birth,
            date_of_loss=req.date_of_loss,
            check_number=p.check_number,
            payment_amount=p.payment_amount,
        )
        files.append(
            {
                "index": idx,
                "provider_name": p.provider_name,
                "filename": unique,
                "download_url": f"/api/download/{gen_id}/{idx}",
            }
        )

    return JSONResponse(
        {
            "generation_id": gen_id,
            "files": files,
            "zip_url": f"/api/download/{gen_id}/all.zip",
        }
    )


def _gen_dir(gen_id: str) -> str:
    safe = os.path.basename(gen_id)
    gen_dir = os.path.join(GEN_ROOT, safe)
    if not os.path.isdir(gen_dir):
        raise HTTPException(status_code=404, detail="Generation not found or expired.")
    return gen_dir


@app.get("/api/download/{gen_id}/all.zip")
def download_zip(gen_id: str):
    gen_dir = _gen_dir(gen_id)
    docx_files = sorted(f for f in os.listdir(gen_dir) if f.lower().endswith(".docx"))
    if not docx_files:
        raise HTTPException(status_code=404, detail="No files to download.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in docx_files:
            zf.write(os.path.join(gen_dir, name), arcname=name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="Payment Letters.zip"'},
    )


@app.get("/api/download/{gen_id}/{index}")
def download_file(gen_id: str, index: int):
    gen_dir = _gen_dir(gen_id)
    docx_files = sorted(f for f in os.listdir(gen_dir) if f.lower().endswith(".docx"))
    if index < 0 or index >= len(docx_files):
        raise HTTPException(status_code=404, detail="File not found.")
    name = docx_files[index]
    return FileResponse(
        os.path.join(gen_dir, name),
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        filename=name,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Frontend
# --------------------------------------------------------------------------- #

@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
