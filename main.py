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
    "Mr Md Zaker Ullah": {
        "specialty": "General Surgery, Breast Surgery",
        "qualifications": "FRCS, MBBS, FRCSEd",
        "gmcNumber": "4368515",
        "practisingSince": 1987,
        "locations": ["The Holly Hospital"],
        "fees": {"Initial consultation": 300},
        "available_dates": {
            "The Holly Hospital": [
                {"date": "2025-09-16", "times": ["15:45"]},
                {"date": "2025-09-18", "times": ["10:15", "10:45", "11:00"]},
                {"date": "2025-09-23", "times": ["14:45", "15:15", "15:30"]},
            ]
        },
        "services": ['Breast Cancer Diagnosis', 'Cosmetic Breast Surgery', 'Hernia Repair']
    },
    "Miss Tasha Gandamihardja": {
        "specialty": "General Surgery, Breast Surgery",
        "qualifications": "MBBS, FRACS, Grad Dip Clin Epi, FRCPSG",
        "gmcNumber": "1234567",
        "practisingSince": 2008,
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
        },
        "services": ['Breast Reconstruction', 'Breast Cancer Surgery', 'Oncoplastic Surgery']
    },
    "Dr. Alice Smith": {
        "specialty": "Cardiology",
        "qualifications": "MD, FACC",
        "gmcNumber": "7890123",
        "practisingSince": 2001,
        "locations": ["Nuffield Health Brentwood Hospital"],
        "fees": {"Initial consultation": 350},
        "available_dates": {
            "Nuffield Health Brentwood Hospital": [
                {"date": "2025-09-19", "times": ["10:00", "10:30", "11:00"]},
                {"date": "2025-09-26", "times": ["10:00", "10:30", "11:00"]},
            ]
        },
        "services": ['Heart Health Consultation', 'Echocardiograms', 'Blood Pressure Monitoring']
    },
    "Dr. Ben Carter": {
        "specialty": "Neurology",
        "qualifications": "MD, PhD, FRCP",
        "gmcNumber": "8901234",
        "practisingSince": 2012,
        "locations": ["The Holly Hospital"],
        "fees": {"Initial consultation": 320},
        "available_dates": {
            "The Holly Hospital": [
                {"date": "2025-09-20", "times": ["14:00", "14:30"]},
                {"date": "2025-09-27", "times": ["14:00", "14:30"]},
            ]
        },
        "services": ['Stroke Prevention', 'Headache Management', 'Epilepsy Treatment']
    },
    "Dr. Emily Davis": {
        "specialty": "Dermatology",
        "qualifications": "MBBS, MRCP",
        "gmcNumber": "9012345",
        "practisingSince": 2010,
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
        },
        "services": ['Acne Treatment', 'Mole Checks', 'Skin Cancer Screening']
    },
    "Dr. Frank Green": {
        "specialty": "Orthopaedic Surgery",
        "qualifications": "MD, FACS",
        "gmcNumber": "1234567",
        "practisingSince": 2005,
        "locations": ["The Holly Hospital"],
        "fees": {"Initial consultation": 400},
        "available_dates": {
            "The Holly Hospital": [
                {"date": "2025-09-18", "times": ["11:00", "11:30", "12:00"]},
                {"date": "2025-09-25", "times": ["11:00", "11:30", "12:00"]},
                {"date": "2025-10-02", "times": ["11:00", "11:30"]},
            ]
        },
        "services": ['Knee Arthroscopy', 'Hip Replacement', 'Sports Injuries']
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

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID") # Replace with your Account SID
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN") # Replace with your Auth Token
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER") # Replace with your Twilio phone number

def format_phone_number(phone_number):
    """
    Formats a phone number to E.164 format.
    Handles common UK number formats (e.g., '07...' or '447...').
    """
    phone_number = phone_number.replace(' ', '').replace('-', '')
    if not phone_number.startswith('+'):
        if phone_number.startswith('0'):
            # This is the fix for your specific error.
            # It handles numbers starting with '0' by removing the '0' and adding '+44'
            return f'+44{phone_number[1:]}'
        elif phone_number.startswith('44'):
            # Assumes UK number and adds the '+'
            return f'+{phone_number}'
        else:
            # Fallback for other formats, might need to be more specific
            logging.warning(f"Could not reliably format phone number: {phone_number}")
            return f'+{phone_number}'
    return phone_number

def send_whatsapp_message(to_number, body):
    """Sends a WhatsApp message using the Twilio API."""
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        formatted_to_number = format_phone_number(to_number)

        # Log the numbers to confirm correct formatting before sending
        logging.info(f"Attempting to send message from {TWILIO_PHONE_NUMBER} to {formatted_to_number}")

        message = client.messages.create(
            from_=f'whatsapp:{TWILIO_PHONE_NUMBER}',
            body=body,
            to=f'whatsapp:{formatted_to_number}'
        )
        logging.info(f"WhatsApp message sent to {formatted_to_number}: {message.sid}")
        return message.sid

    except Exception as e:
        # A more specific error log with the phone number that failed
        logging.error(f"Failed to send WhatsApp message to {to_number}: {e}")
        return None



def send_email(to_email, subject, plain_body, html_body):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
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

# --- Webhook endpoint (for Dialogflow/etc) ---
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

        available_doctors = []
        for doctor_name, details in DOCTORS.items():
            if specialty and specialty.lower() not in details["specialty"].lower():
                continue

            matching_locations = []
            for loc in details["locations"]:
                hospital = HOSPITALS.get(loc, {})
                if city and city.lower() not in hospital.get("city", "").lower():
                    continue
                if postcode and postcode.lower() != hospital.get("postcode", "").lower():
                    continue
                matching_locations.append(loc)

            if matching_locations:
                doctor_details = details.copy()
                doctor_details["name"] = doctor_name
                doctor_details["locations"] = matching_locations
                doctor_details["available_dates"] = {loc: dates for loc, dates in details.get("available_dates", {}).items() if loc in matching_locations}
                available_doctors.append(doctor_details)

        if available_doctors:
            doctor_text_lines = ["Here are some of our doctors who match your search. Which one would you like to know more about?"]
            chips_options = []
            
            for i, doctor in enumerate(available_doctors, 1):
                text_line = (
                    f"\n{i}. {doctor['name']}\n"
                    f"    Specialty: {doctor['specialty']}\n"
                    f"    Locations: {', '.join(doctor['locations'])}"
                )
                doctor_text_lines.append(text_line)

                chips_options.append({
                    "text": f"View {doctor['name']}",
                    "value": f"View {doctor['name']}"
                })

            card_text_message = {"text": {"text": doctor_text_lines}}
            chips_payload = {"richContent": [[{"type": "chips", "options": chips_options}]]}
            
            return jsonify({
                "fulfillment_response": {
                    "messages": [card_text_message, {"payload": chips_payload}]
                }
            })
        else:
            response_text = f"Sorry, no {specialty} doctors found in {city or postcode}."
            return jsonify({
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": [response_text]}}
                    ]
                }
            })

    # --- Tag: Get Doctor Details (Updated to include times as chips) ---
    elif tag == "get_doctor_details":
        doctor_name = params.get("doctor_name")
        doctor_details = DOCTORS.get(doctor_name)

        if doctor_details:
            # Build the rich card response with more details
            locations_text = ", ".join(doctor_details.get("locations", []))
            services_text = ", ".join(doctor_details.get("services", []))

            # Build schedule text and chips
            schedule_text = []
            chips_options = []

            for loc, slots in doctor_details.get("available_dates", {}).items():
                schedule_text.append(f"🏥 {loc}")
                for slot in slots:
                    date_obj = datetime.strptime(slot["date"], "%Y-%m-%d")
                    date_str = date_obj.strftime("%a, %d %b")
                    times = ", ".join(slot["times"]) if slot["times"] else "No appointments"
                    schedule_text.append(f"    📅 {date_str}: {times}")

                    for t in slot["times"]:
                        chips_options.append({
                            "text": f"{date_str} {t}",
                            "value": f"Book appointment with {doctor_name} on {date_obj.date()} at {t}"
                        })

            detail_text = (
                f"Here are the details for {doctor_name}:\n\n"
                f"Specialty: {doctor_details.get('specialty')}\n"
                f"Qualifications: {doctor_details.get('qualifications')}\n"
                f"Practising Since: {doctor_details.get('practisingSince')}\n"
                f"Locations: {locations_text}\n"
                f"Services: {services_text}\n"
                f"Initial Consultation Fee: £{doctor_details['fees'].get('Initial consultation')}\n\n"
                f"📅 Available Dates & Times:\n" + "\n".join(schedule_text)
            )

            # The full rich response payload with chips
            chips_payload = {
                "richContent": [
                    [
                        {"type": "chips", "options": chips_options[:8]},  # Limit chips to 8 per row
                        {"type": "chips", "options": [
                            {"text": "Go Back", "value": "Go back to doctor list"}
                        ]}
                    ]
                ]
            }

            return jsonify({
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": [detail_text]}},
                        {"payload": chips_payload}
                    ]
                }
            })
        else:
            return jsonify({
                "fulfillment_response": {
                    "messages": [{"text": {"text": ["Sorry, I couldn't find details for that doctor."]}}]
                }
            })

    # --- Tag: Confirm Booking ---
    elif tag == "confirm_booking":
        name = params.get("person_name", {})
        first_name = name.get("first") if isinstance(name, dict) else name
        mobile = params.get("phone_number")
        email = params.get("email")
        appointment_datetime = params.get("appointment_datetime")
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
        if appointment_datetime:
            try:
                dt_obj = datetime.fromisoformat(appointment_datetime)
                formatted_date_time = dt_obj.strftime("%A, %d %B %Y at %I:%M %p")
            except Exception as e:
                logging.warning(f"Failed to parse appointment_datetime: {appointment_datetime}, error: {e}")

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
