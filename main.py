from fastapi import FastAPI, Request
import requests
import os
import json

app = FastAPI()

WEBEX_BOT_TOKEN = os.getenv("WEBEX_BOT_TOKEN", "")

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

@app.post("/webex/webhook")
async def webex_webhook(request: Request):
    body = await request.json()
    print(f"[DEBUG] Incoming webhook body: {json.dumps(body)}")

    resource = body.get("resource")
    event = body.get("event")
    data = body.get("data", {})

    if event != "created":
        return {"ok": True, "ignored": True}

    if resource == "messages":
        message_id = data.get("id")
        room_id = data.get("roomId")

        if not message_id or not room_id:
            return {"ok": False, "error": "Missing message ID or room ID"}

        msg = get_message(message_id)
        text = (msg.get("text") or "").strip().lower()

        if "help" in text:
            post_webex_message(
                room_id,
                "Hi — I can help create a support ticket. Submit the card in this space to send name, company, and issue."
            )
        else:
            post_webex_message(
                room_id,
                "I saw your message. Say 'help' for instructions or use the support ticket card."
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

        post_webex_message(
            room_id,
            f"Webhook received. Name: {customer_name} | Company: {company} | Issue: {issue}"
        )
        return {"ok": True, "type": "attachmentAction"}

    return {"ok": True, "ignored": True}
