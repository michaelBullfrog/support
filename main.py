from fastapi import FastAPI, Request
import requests
import os
import json

app = FastAPI()

WEBEX_BOT_TOKEN = os.getenv("WEBEX_BOT_TOKEN", "")
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
    print(f"[DEBUG] Fetching attachment action: {action_id}")
    r = requests.get(
        f"https://webexapis.com/v1/attachment/actions/{action_id}",
        headers={"Authorization": f"Bearer {WEBEX_BOT_TOKEN}"},
        timeout=30
    )
    print(f"[DEBUG] Attachment action status: {r.status_code}")
    print(f"[DEBUG] Attachment action response: {r.text[:1000]}")
    r.raise_for_status()
    return r.json()


def post_webex_message(room_id: str, text: str):
    print(f"[DEBUG] Posting message to room: {room_id}")
    print(f"[DEBUG] Message text: {text}")
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
    print(f"[DEBUG] Post message status: {r.status_code}")
    print(f"[DEBUG] Post message response: {r.text[:1000]}")
    r.raise_for_status()
    return r.json()


def create_revio_ticket(customer_name: str, company: str, issue: str):
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

    print(f"[DEBUG] Rev.io URL: {REVIO_BASE_URL}/Tickets")
    print(f"[DEBUG] Rev.io payload: {json.dumps(payload)}")

    r = requests.post(
        f"{REVIO_BASE_URL}/Tickets",
        headers=headers,
        json=payload,
        timeout=30
    )
    print(f"[DEBUG] Rev.io status: {r.status_code}")
    print(f"[DEBUG] Rev.io response: {r.text[:1000]}")
    r.raise_for_status()
    return r.json()


@app.post("/webex/webhook")
async def webex_webhook(request: Request):
    body = await request.json()
    print(f"[DEBUG] Incoming webhook body: {json.dumps(body)}")

    resource = body.get("resource")
    event = body.get("event")
    data = body.get("data", {})

    if resource != "attachmentActions" or event != "created":
        print("[DEBUG] Ignored non-attachmentActions event")
        return {"ok": True, "ignored": True}

    action_id = data.get("id")
    if not action_id:
        print("[ERROR] Missing action ID")
        return {"ok": False, "error": "Missing action ID"}

    try:
        action = get_attachment_action(action_id)
        inputs = action.get("inputs", {})
        room_id = action.get("roomId")

        print(f"[DEBUG] Parsed inputs: {json.dumps(inputs)}")
        print(f"[DEBUG] Parsed room_id: {room_id}")

        customer_name = inputs.get("customer_name", "").strip()
        company = inputs.get("company", "").strip()
        issue = inputs.get("issue", "").strip()

        if not room_id:
            print("[ERROR] No roomId returned from attachment action")
            return {"ok": False, "error": "Missing roomId"}

        if not customer_name or not company or not issue:
            post_webex_message(
                room_id,
                "Ticket not created. Name, company, and issue are all required."
            )
            return {"ok": False, "error": "Missing required fields"}

        # TEMP TEST: comment out Rev.io until Webex reply works
        post_webex_message(
            room_id,
            f"Webhook received. Name: {customer_name} | Company: {company} | Issue: {issue}"
        )
        return {"ok": True, "message": "Debug reply sent"}

        # When Webex reply works, switch to this:
        # ticket = create_revio_ticket(customer_name, company, issue)
        # ticket_id = ticket.get("id", "created")
        # post_webex_message(
        #     room_id,
        #     f"Ticket created successfully for {customer_name} at {company}. Ticket ID: {ticket_id}"
        # )
        # return {"ok": True, "ticket": ticket}

    except Exception as e:
        print(f"[ERROR] Exception in webhook handler: {str(e)}")
        return {"ok": False, "error": str(e)}