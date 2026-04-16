from fastapi import FastAPI, Request
import requests
import os

app = FastAPI()

WEBEX_BOT_TOKEN = os.getenv("WEBEX_BOT_TOKEN", "")
WEBEX_ROOM_ID = os.getenv("WEBEX_ROOM_ID", "")
REVIO_BASE_URL = os.getenv("REVIO_BASE_URL", "")
REVIO_BASIC_AUTH = os.getenv("REVIO_BASIC_AUTH", "")
REVIO_API_KEY = os.getenv("REVIO_API_KEY", "")

WEBEX_HEADERS = {
    "Authorization": f"Bearer {WEBEX_BOT_TOKEN}",
    "Content-Type": "application/json"
}


@app.get("/")
def home():
    return {"ok": True, "message": "Webex support bot is running"}


@app.get("/health")
def health():
    return {"ok": True}


def get_attachment_action(action_id: str):
    r = requests.get(
        f"https://webexapis.com/v1/attachment/actions/{action_id}",
        headers={"Authorization": f"Bearer {WEBEX_BOT_TOKEN}"},
        timeout=30
    )
    r.raise_for_status()
    return r.json()


def post_webex_message(room_id: str, text: str):
    payload = {
        "roomId": room_id,
        "text": text
    }
    r = requests.post(
        "https://webexapis.com/v1/messages",
        headers=WEBEX_HEADERS,
        json=payload,
        timeout=30
    )
    r.raise_for_status()
    return r.json()


def create_revio_ticket(customer_name: str, company: str, issue: str):
    """
    Replace the endpoint and payload below with your exact Rev.io ticket API details.
    REVIO_BASIC_AUTH should already include the word 'Basic' in Render.
    Example:
    REVIO_BASIC_AUTH = Basic abc123...
    """
    headers = {
        "Authorization": REVIO_BASIC_AUTH,
        "Content-Type": "application/json"
    }

    if REVIO_API_KEY:
        headers["x-api-key"] = REVIO_API_KEY

    payload = {
        "customer_name": customer_name,
        "company": company,
        "description": issue,
        "subject": f"Support Ticket - {company} - {customer_name}"
    }

    r = requests.post(
        f"{REVIO_BASE_URL}/Tickets",
        headers=headers,
        json=payload,
        timeout=30
    )
    r.raise_for_status()
    return r.json()


@app.post("/webex/webhook")
async def webex_webhook(request: Request):
    body = await request.json()

    resource = body.get("resource")
    event = body.get("event")
    data = body.get("data", {})

    if resource != "attachmentActions" or event != "created":
        return {"ok": True, "ignored": True}

    action_id = data.get("id")
    if not action_id:
        return {"ok": False, "error": "Missing action ID"}

    action = get_attachment_action(action_id)
    inputs = action.get("inputs", {})
    room_id = action.get("roomId")

    customer_name = inputs.get("customer_name", "").strip()
    company = inputs.get("company", "").strip()
    issue = inputs.get("issue", "").strip()

    if not customer_name or not company or not issue:
        post_webex_message(
            room_id,
            "Ticket not created. Name, company, and issue are all required."
        )
        return {"ok": False, "error": "Missing required fields"}

    try:
        ticket = create_revio_ticket(customer_name, company, issue)
        ticket_id = ticket.get("id", "created")

        post_webex_message(
            room_id,
            f"Ticket created successfully for {customer_name} at {company}. Ticket ID: {ticket_id}"
        )
        return {"ok": True, "ticket": ticket}

    except Exception as e:
        post_webex_message(
            room_id,
            f"Ticket creation failed for {customer_name} at {company}. Error: {str(e)[:400]}"
        )
        return {"ok": False, "error": str(e)}