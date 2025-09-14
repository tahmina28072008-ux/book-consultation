from flask import Flask, request, jsonify
import logging
import os
from datetime import datetime
from twilio.rest import Client
import firebase_admin
from firebase_admin import credentials, firestore
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

# --- Twilio Setup ---
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_client = Client(account_sid, auth_token) if account_sid and auth_token else None

# --- Firestore Setup ---
db = None
try:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except ValueError:
    try:
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            cred = credentials.Certificate(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
            firebase_admin.initialize_app(cred)
            db = firestore.client()
        else:
            logging.warning("No GOOGLE_APPLICATION_CREDENTIALS found. Running without Firestore.")
    except Exception as e:
        logging.error(f"Error initializing Firebase: {e}")

# --- Dummy Data ---
DOCTORS = {
    "Miss Tasha Gandamihardja": {
        "specialty": "General Surgery, Breast Surgery",
        "locations": ["Nuffield Health Brentwood Hospital", "The Holly Hospital"],
        "fees": {"Initial consultation": 300},
        "available_dates": {
            "Nuffield Health Brentwood Hospital": [
                {"date": "2025-09-18", "times": ["16:30", "16:45"]},
                {"date": "2025-09-25", "times": ["16:30", "16:45"]},
            ],
            "The Holly Hospital": [
                {"date": "2025-09-22", "times": ["17:00", "18:30"]},
                {"date": "2025-09-26", "times": ["17:00", "18:30"]},
            ]
        }
    },
    "Dr. Alice Smith": {
        "specialty": "Cardiology",
        "locations": ["Nuffield Health Brentwood Hospital"],
        "fees": {"Initial consultation": 350},
        "available_dates": {
            "Nuffield Health Brentwood Hospital": [
                {"date": "2025-09-19", "times": ["10:00", "10:30", "11:00"]},
                {"date": "2025-09-26", "times": ["10:00", "10:30", "11:00"]},
            ]
        }
    },
    "Dr. Ben Carter": {
        "specialty": "Neurology",
        "locations": ["The Holly Hospital"],
        "fees": {"Initial consultation": 320},
        "available_dates": {
            "The Holly Hospital": [
                {"date": "2025-09-20", "times": ["14:00", "14:30"]},
                {"date": "2025-09-27", "times": ["14:00", "14:30"]},
            ]
        }
    },
    "Dr. Emily Davis": {
        "specialty": "Dermatology",
        "locations": ["Nuffield Health Brentwood Hospital", "The Holly Hospital"],
        "fees": {"Initial consultation": 280},
        "available_dates": {
            "Nuffield Health Brentwood Hospital": [
                {"date": "2025-09-17", "times": ["09:00", "09:30", "10:00"]},
                {"date": "2025-09-24", "times": ["09:00", "09:30", "10:00"]},
                {"date": "2025-10-01", "times": ["09:00", "09:30"]},
            ],
            "The Holly Hospital": [
                {"date": "2025-09-16", "times": ["13:00", "13:30", "14:00"]},
                {"date": "2025-09-23", "times": ["13:00", "13:30", "14:00"]},
            ]
        }
    },
    "Dr. Frank Green": {
        "specialty": "Orthopaedic Surgery",
        "locations": ["The Holly Hospital"],
        "fees": {"Initial consultation": 400},
        "available_dates": {
            "The Holly Hospital": [
                {"date": "2025-09-18", "times": ["11:00", "11:30", "12:00"]},
                {"date": "2025-09-25", "times": ["11:00", "11:30", "12:00"]},
                {"date": "2025-10-02", "times": ["11:00", "11:30"]},
            ]
        }
    }
}
HOSPITALS = {
    "The Holly Hospital": {
        "city": "London",
        "postcode": "IG9 5HX",
        "address": "High Road, Buckhurst Hill, Essex",
        "phone": "020 8505 3311"
    },
    "Nuffield Health Brentwood Hospital": {
        "city": "Brentwood",
        "postcode": "CM15 8EH",
        "address": "Shenfield Road, Brentwood",
        "phone": "01277 695695"
    }
}

# --- Helper Functions ---
def send_whatsapp_message(to_number, message_body):
    from_number = "whatsapp:+14155238886"
    if not twilio_client:
        logging.error("Twilio client not initialized.")
        return False, "Twilio client not initialized."
    try:
        twilio_client.messages.create(
            to=f"whatsapp:{to_number}",
            from_=from_number,
            body=message_body
        )
        return True, "Message sent successfully."
    except Exception as e:
        logging.error(f"Failed to send WhatsApp message: {e}")
        return False, f"Failed to send message: {e}"

def send_email(to_email, subject, plain_body, html_body):
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASSWORD")
    if not sender_email or not sender_password:
        logging.error("Email credentials not found.")
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(plain_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False

# --- Webhook ---
@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    tag = req.get("fulfillmentInfo", {}).get("tag")
    params = req.get("sessionInfo", {}).get("parameters", {})

    logging.info(f"Webhook called. Tag: {tag}, Params: {params}")

    # --- Tag: Get Doctor List ---
    if tag == "get_doctor_list":
        city = params.get("city")
        postcode = params.get("postcode")
        specialty = params.get("specialty")

        available = []
        for doctor_name, details in DOCTORS.items():
            if specialty and specialty.lower() not in details["specialty"].lower():
                continue
            for loc in details["locations"]:
                hospital = HOSPITALS.get(loc, {})
                if city and city.lower() not in hospital.get("city", "").lower():
                    continue
                if postcode and postcode.lower() != hospital.get("postcode", "").lower():
                    continue
                available.append({"name": doctor_name, "specialty": details["specialty"], "location": loc})

        if available:
            doctor_names = ", ".join([doc["name"] for doc in available])
            response_text = f"Here are available {specialty} doctors in {city or postcode}: {doctor_names}. Please select one."
        else:
            response_text = f"Sorry, no {specialty} doctors found in {city or postcode}."

        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [response_text]}}
                ]
            }
        })

    # --- Tag: Confirm Booking ---
    elif tag == "confirm_booking":
        name = params.get("person_name", {})
        first_name = name.get("first") if isinstance(name, dict) else name
        mobile = params.get("phone_number")
        email = params.get("email")
        tour_datetime = params.get("tour_datetime")
        doctor_name = params.get("doctor_name")

        if not doctor_name or doctor_name not in DOCTORS:
            return jsonify({
                "fulfillment_response": {
                    "messages": [{"text": {"text": ["Doctor not found."]}}]
                }
            })

        location_name = DOCTORS[doctor_name]["locations"][0]
        hospital_info = HOSPITALS.get(location_name, {})

        formatted_date_time = "your selected date and time"
        if tour_datetime:
            try:
                dt_obj = datetime.fromisoformat(tour_datetime)
                formatted_date_time = dt_obj.strftime("%A, %d %B %Y at %I:%M %p")
            except Exception:
                pass

        confirmation_message_plain = (
            f"Booking Confirmed!\n\n"
            f"Doctor: {doctor_name}\n"
            f"Specialty: {DOCTORS[doctor_name]['specialty']}\n"
            f"Location: {location_name}\n"
            f"Address: {hospital_info.get('address', 'N/A')}\n"
            f"Phone: {hospital_info.get('phone', 'N/A')}\n"
            f"Date & Time: {formatted_date_time}\n\n"
            f"A confirmation has been sent to your email ({email}) and WhatsApp ({mobile})."
        )

        confirmation_message_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color:#2a7ae2;">✅ Your Consultation is Confirmed</h2>
                <p>Dear {first_name or 'Patient'},</p>
                <p>We are pleased to confirm your consultation:</p>
                <table style="border-collapse: collapse; width: 100%; margin: 20px 0;">
                    <tr><td><b>👨‍⚕️ Doctor:</b></td><td>{doctor_name}</td></tr>
                    <tr><td><b>🔬 Specialty:</b></td><td>{DOCTORS[doctor_name]['specialty']}</td></tr>
                    <tr><td><b>🏥 Hospital:</b></td><td>{location_name}</td></tr>
                    <tr><td><b>📍 Address:</b></td><td>{hospital_info.get('address', 'N/A')}</td></tr>
                    <tr><td><b>📞 Hospital Phone:</b></td><td>{hospital_info.get('phone', 'N/A')}</td></tr>
                    <tr><td><b>🗓 Date & Time:</b></td><td>{formatted_date_time}</td></tr>
                </table>
                <p>We’ve also sent a copy to your WhatsApp at <b>{mobile}</b>.</p>
                <p style="margin-top:20px;">If you have any questions, feel free to reply to this email.</p>
                <p style="color:#555;">Warm regards,<br>Nuffield Health Team</p>
            </body>
        </html>
        """

        # Send email & WhatsApp
        if email:
            send_email(email, "✅ Consultation Confirmed", confirmation_message_plain, confirmation_message_html)
        if mobile:
            send_whatsapp_message(mobile, confirmation_message_plain)

        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [confirmation_message_plain]}}
                ]
            }
        })

    # --- Default Handler ---
    return jsonify({
        "fulfillment_response": {
            "messages": [
                {"text": {"text": ["Sorry, I couldn’t process that."]}}
            ]
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
