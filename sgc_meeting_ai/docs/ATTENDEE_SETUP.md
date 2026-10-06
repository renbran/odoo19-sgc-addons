# Attendee bot setup (free, self-hosted meeting recorder)

`sgc_meeting_ai` can send an AI notetaker bot into Google Meet / Zoom calls using
[**Attendee**](https://github.com/attendee-labs/attendee) — an open-source,
self-hostable alternative to Recall.ai. Attendee joins the call, records it, and
transcribes it (via Deepgram). This module then ingests the transcript and runs
the LLM-notes step automatically.

The Odoo side is already wired:

- `sgc.meeting.session.action_dispatch_bot` → calls Attendee `POST /api/v1/bots`.
- Cron **"SGC Meeting AI: Poll Attendee bots"** (every 2 min) → polls each bot,
  and when the meeting ends pulls the transcript + recording and generates notes.
- Until an API key is set, dispatch degrades gracefully (records intent only),
  so nothing breaks.

## 1. Run Attendee (self-hosted = free)

On a host that can reach the internet (each bot runs a headless Chrome, so give
it ≥2 vCPU / 4 GB RAM per concurrent meeting):

```bash
git clone https://github.com/attendee-labs/attendee.git
cd attendee
# Build + start (Postgres + Redis are included in the compose file)
docker compose -f dev.docker-compose.yaml build
docker compose -f dev.docker-compose.yaml up -d
docker compose -f dev.docker-compose.yaml exec attendee-app-local \
    python manage.py migrate
```

Then open the Attendee web UI (default `http://<host>:8000`), create an account,
and configure:

- **Deepgram API key** — for transcription (Deepgram has a free tier, no card).
- **Google Meet**: a Google account the bot uses to join calls.
- **Zoom** (optional): Zoom OAuth Client ID/Secret in the UI.
- **Recording storage**: S3 (or S3-compatible like Cloudflare R2 / MinIO).

Finally, generate an **API key** in the Attendee UI.

> For production, put Attendee behind HTTPS (reverse proxy) and use a managed
> Postgres + object storage rather than the bundled dev compose.

## 2. Point Odoo at your Attendee instance

Settings → Technical → System Parameters (or run in `odoo shell`):

| Key | Value |
|---|---|
| `sgc_meeting_ai.attendee_base_url` | `https://your-attendee-host` (default `https://app.attendee.dev`) |
| `sgc_meeting_ai.attendee_api_key` | the API key from the Attendee UI |
| `sgc_meeting_ai.attendee_bot_name` | optional, default `SGC AI Notetaker` |
| `sgc_meeting_ai.attendee_bot_email` | the bot Google account's email — auto-invited to each meeting so it skips the waiting room |

Shell one-liners:

```python
icp = env["ir.config_parameter"].sudo()
icp.set_param("sgc_meeting_ai.attendee_base_url", "https://your-attendee-host")
icp.set_param("sgc_meeting_ai.attendee_api_key", "att_xxxxxxxx")
env.cr.commit()
```

## 3. How it flows

1. Salesperson books a meeting on an opportunity → `sgc.meeting.session` created
   with `bot_enabled=True`, and `action_dispatch_bot` runs.
2. If a video link is present and Attendee is configured, a bot is dispatched and
   `bot_id` / `bot_state` are stored.
3. The poll cron watches the bot; when the meeting **ends**, it ingests the
   transcript (and downloads the recording), then generates AI notes posted to
   the meeting chatter.

## Notes / caveats

- **Google Meet** needs a real Google account for the bot to be admitted.
- Meeting-platform UIs change occasionally and can break any bot — that's the
  maintenance cost of the free/self-hosted route.
- No Whisper/Groq key is needed for Attendee meetings — its Deepgram transcript
  is ingested directly. (The in-module Whisper path still exists for manually
  uploaded recordings.)
- Hosted option: you can instead use `https://app.attendee.dev` with a paid key
  and skip self-hosting — same Odoo config, just a different base URL + key.
