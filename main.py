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

BOT_PERSON_ID = None


@app.get("/")
def home():
    return {"ok": True, "message": "Webex support bot is running"}


@app.get("/health")
def health():
    return {"ok": True}


def get_me():
    global BOT_PERSON_ID
    r = requests.get(
        "https://webexapis.com/v1/people/me",
        headers={"Authorization": f"Bearer {WEBEX_BOT_TOKEN}"},
        timeout=30
    )
    print(f"[DEBUG] get_me status: {r.status_code}")
    print(f"[DEBUG] get_me response: {r.text[:1000]}")
    r.raise_for_status()
    me = r.json()
    BOT_PERSON_ID = me.get("id")
    return me


def post_webex_message(room_id: str, text: str):
    r = requests.post(
        "https://webexapis.com/v1/messages",
        headers=WEBEX_HEADERS,
        json={"roomId": room_id, "text": text},
        timeout=30
    )
    print(f"[DEBUG] Post message status: {r.status_code}")
    print(f"[DEBUG] Post message response: {r.text[:1000]}")
    r.raise_for_status()
    return r.json()


def post_support_card(room_id: str):
    card_payload = {
        "roomId": room_id,
        "text": "Support ticket form",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.3",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Bullfrog Support",
                            "weight": "Bolder",
                            "size": "Large"
                        },
                        {
                            "type": "TextBlock",
                            "text": "Submit a support ticket",
                            "wrap": True,
                            "spacing": "Small"
                        },
                        {
                            "type": "Input.Text",
                            "id": "customer_name",
                            "label": "Name",
                            "placeholder": "Enter your full name"
                        },
                        {
                            "type": "Input.Text",
                            "id": "company",
                            "label": "Company",
                            "placeholder": "Enter your company name"
                        },
                        {
                            "type": "Input.Text",
                            "id": "issue",
                            "label": "Issue",
                            "placeholder": "Describe the problem",
                            "isMultiline": True
                        }
                    ],
                    "actions": [
                        {
                            "type": "Action.Submit",
                            "title": "Submit Ticket",
                            "data": {
                                "action": "create_support_ticket"
                            }
                        }
                    ]
                }
            }
        ]
    }

    r = requests.post(
        "https://webexapis.com/v1/messages",
        headers=WEBEX_HEADERS,
        json=card_payload,
        timeout=30
    )
    print(f"[DEBUG] Post card status: {r.status_code}")
    print(f"[DEBUG] Post card response: {r.text[:1000]}")
    r.raise_for_status()
    return r.json()


def get_message(message_id: str):
    r = requests.get(
        f"https://webexapis.com/v1/messages/{message_id}",
        headers={"Authorization": f"Bearer {WEBEX_BOT_TOKEN}"},
        timeout=30
    )
    print(f"[DEBUG] Get message status: {r.status_code}")
    print(f"[DEBUG] Get message response: {r.text[:1000]}")
    r.raise_for_status()
    return r.json()


def get_attachment_action(action_id: str):
    r = requests.get(
        f"https://webexapis.com/v1/attachment/actions/{action_id}",
        headers={"Authorization": f"Bearer {WEBEX_BOT_TOKEN}"},
        timeout=30
    )
    print(f"[DEBUG] Attachment action status: {r.status_code}")
    print(f"[DEBUG] Attachment action response: {r.text[:1000]}")
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
        "priority_id": 1
    }

    url = f"{REVIO_BASE_URL}/Tickets"
    print(f"[DEBUG] Rev.io URL: {url}")
    print(f"[DEBUG] Rev.io payload: {json.dumps(payload)}")

    r = requests.post(url, headers=headers, json=payload, timeout=30)

    print(f"[DEBUG] Rev.io status: {r.status_code}")
    print(f"[DEBUG] Rev.io response: {r.text[:4000]}")

    if not r.ok:
        raise Exception(f"Rev.io {r.status_code}: {r.text[:1000]}")

    return r.json()


@app.on_event("startup")
def startup_event():
    try:
        get_me()
        print(f"[DEBUG] BOT_PERSON_ID: {BOT_PERSON_ID}")
    except Exception as e:
        print(f"[ERROR] Failed to get bot identity on startup: {e}")


@app.post("/webex/webhook")
async def webex_webhook(request: Request):
    global BOT_PERSON_ID

    body = await request.json()
    print(f"[DEBUG] Incoming webhook body: {json.dumps(body)}")

    resource = body.get("resource")
    event = body.get("event")
    data = body.get("data", {})

    if event != "created":
        return {"ok": True, "ignored": True}

    if not BOT_PERSON_ID:
        get_me()

    if resource == "messages":
        message_id = data.get("id")
        room_id = data.get("roomId")
        sender_id = data.get("personId")

        # Ignore the bot's own messages
        if sender_id == BOT_PERSON_ID:
            print("[DEBUG] Ignoring bot's own message")
            return {"ok": True, "ignored": "self_message"}

        if not message_id or not room_id:
            return {"ok": False, "error": "Missing message ID or room ID"}

        msg = get_message(message_id)
        text = (msg.get("text") or "").strip().lower()

        if "help" in text:
            post_support_card(room_id)
        else:
            post_webex_message(
                room_id,
                "Say 'help' and I’ll send the support ticket form."
            )

        return {"ok": True, "type": "message"}

    if resource == "attachmentActions":
        action_id = data.get("id")
        if not action_id:
            return {"ok": False, "error": "Missing action ID"}

        action = get_attachment_action(action_id)
        inputs = action.get("inputs", {})
        room_id = action.get("roomId")

        customer_name = inputs.get("customer_name", "").strip()
        company = inputs.get("company", "").strip()
        issue = inputs.get("issue", "").strip()

        if not room_id:
            return {"ok": False, "error": "Missing roomId"}

        if not customer_name or not company or not issue:
            post_webex_message(
                room_id,
                "Ticket not created. Name, company, and issue are all required."
            )
            return {"ok": False, "error": "Missing required fields"}

        try:
            ticket = create_revio_ticket(customer_name, company, issue)
            ticket_id = ticket.get("id") or ticket.get("ticket_id") or "created"

            post_webex_message(
                room_id,
                f"Ticket created successfully for {customer_name} at {company}. Ticket ID: {ticket_id}"
            )
            return {"ok": True, "type": "attachmentAction", "ticket": ticket}

        except Exception as e:
            print(f"[ERROR] Rev.io ticket creation failed: {e}")
            post_webex_message(
                room_id,
                f"Ticket creation failed for {customer_name} at {company}. Error: {str(e)[:400]}"
            )
            return {"ok": False, "error": str(e)}

    return {"ok": True, "ignored": True}
