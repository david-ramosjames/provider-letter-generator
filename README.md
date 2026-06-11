# Provider Letter Generator

Generates Word draft payment letters for medical providers from a signed
settlement disbursement PDF, using the firm's existing Word template.

When staff upload a signed disbursement, the app extracts the providers the firm
is paying, pulls case data from Supabase, lets staff review and edit everything,
and generates **one `.docx` payment letter per provider**. Nothing is sent or
mailed automatically — staff review the final drafts.

## How it works

1. Staff upload the signed disbursement PDF and enter the case number.
2. The app extracts the providers under **"Medical Providers Paid by Firm"**.
   - Ignores "Reduced from" amounts, parenthetical amounts, `$0.00` payments,
     providers "Paid/Adjusted by MAP Insurance", and providers "Given Directly
     to Client".
3. The app looks up the case in Supabase (`cases.case_number`) and pre-fills
   client name, date of birth (`cases.date_of_birth`), and date of loss
   (`cases.date_of_incident`). All fields stay editable.
   - If the disbursement's client name differs from Supabase (e.g. a case with
     multiple clients), both are shown and generation is **not** blocked.
4. Staff review and edit case fields and per-provider rows (name, address,
   account number, payment amount, check number).
5. The app generates one Word draft per provider, named
   `[Client Name] - [Provider Name] - Payment Letter.docx`, downloadable
   individually or as a ZIP.

## Extraction

Provider extraction uses **Claude** (`claude-opus-4-8` by default) when
`ANTHROPIC_API_KEY` is set — this handles the disbursement's nuances (sections,
reduced-from amounts, parentheticals) robustly. If no key is configured, a
built-in heuristic parser is used as a fallback and staff are prompted to
double-check the results.

## The Word template

`app/templates/payment_letter_template.docx` is the firm's letter template with
Jinja placeholders (`{{ client_name }}`, `{{ payment_amount }}`, etc.) inserted
into the original document — the letterhead, fonts, and layout are unchanged.
Filled fields: letter date, provider name/address, client name, account number,
date of birth, date of loss, check number, payment amount.

To swap in an updated template, keep the same `{{ ... }}` placeholder names.

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Enables AI extraction (recommended). |
| `ANTHROPIC_MODEL` | Optional model override. Default `claude-opus-4-8`. |
| `SUPABASE_URL` | Supabase project URL. |
| `SUPABASE_KEY` | Service-role or anon key with read access to `cases`. |

## Run locally

```bash
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)   # or set env vars yourself
uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Deploy on Railway

1. Push this repo to GitHub and create a Railway project from it.
2. Railway auto-detects Python (Nixpacks) and runs the start command in
   `Procfile` / `railway.json`:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Set the environment variables above in the Railway service settings.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/process` | multipart `file` + `case_number` → extracted providers + pre-filled case data. |
| `POST` | `/api/generate` | JSON case + providers → generated letters. |
| `GET` | `/api/download/{id}/{index}` | Download one letter. |
| `GET` | `/api/download/{id}/all.zip` | Download all letters as a ZIP. |
| `GET` | `/api/health` | Health check. |

## Notes & future enhancements

- Generated files are stored in a temp directory for download; on Railway's
  ephemeral filesystem they don't persist across restarts (download promptly).
- Possible follow-ups: save letters back to the case file, track generated
  date/user, audit log of extracted vs. edited values, and confidence flags
  when extraction is uncertain.
