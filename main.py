from flask import Flask, request, jsonify
import logging
import os
from datetime import datetime, timedelta
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
    "The Holly Hospital": {"address": "High Road, Buckhurst Hill, Essex, IG9 5HX", "phone": "020 8505 3311"},
    "Nuffield Health Brentwood Hospital": {"address": "Shenfield Road, Brentwood, CM15 8EH", "phone": "01277 695695"}
}

# --- Helper Functions ---
def send_whatsapp_message(to_number, message_body):
    """Sends a WhatsApp message via Twilio."""
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
    """Sends a confirmation email."""
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASSWORD")
    if not sender_email or not sender_password:
        logging.error("Email credentials not found.")
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject

    part1 = MIMEText(plain_body, 'plain')
    part2 = MIMEText(html_body, 'html')
    msg.attach(part1)
    msg.attach(part2)

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

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    fulfillment_response = {
        "fulfillmentResponse": {
            "messages": [
                {"text": {"text": ["I'm sorry, I didn't understand that. Could you please rephrase?"]}}
            ]
        }
    }

    try:
        intent_display_name = req.get("intentInfo", {}).get("displayName")
        parameters = req.get("sessionInfo", {}).get("parameters", {})

        logging.info(f"Intent: {intent_display_name}")
        logging.info(f"Parameters: {parameters}")

        # --- BookConsultationIntent ---
        if intent_display_name == 'BookConsultationIntent':
            fulfillment_response = {
                "fulfillmentResponse": {
                    "messages": [
                        {"text": {"text": ["Hello, I can help you book a consultation. What specialty are you looking for?"]}}
                    ]
                }
            }

        # --- SpecialtySelection ---
        elif intent_display_name == 'SpecialtySelection':
            specialty = parameters.get("specialty")
            # This is a simplified example. In a real app, you'd filter doctors by specialty
            fulfillment_response = {
                "fulfillmentResponse": {
                    "messages": [
                        {"text": {"text": [f"Great! Please provide your location (e.g., London E3, UK) to find a hospital near you."]}}
                    ]
                }
            }

        # --- LocationProvided ---
        elif intent_display_name == 'LocationProvided':
            # In a real app, this would use the location to filter doctors
            doctor_cards = []
            for doctor_name, details in DOCTORS.items():
                doctor_cards.append([
                    {
                        "type": "info",
                        "title": doctor_name,
                        "subtitle": f"Specialty: {details['specialty']}",
                        "image": {
                            "src": {
                                "rawUrl": f"https://placehold.co/100x100/A020F0/white?text={doctor_name[0]}{doctor_name.split()[-1][0]}"
                            }
                        }
                    },
                    {
                        "type": "chips",
                        "options": [
                            {"text": "Book now", "value": f"Book a consultation with {doctor_name}"}
                        ]
                    }
                ])
            
            doctor_list_payload = {
                "richContent": doctor_cards
            }
            
            fulfillment_response = {
                "fulfillmentResponse": {
                    "messages": [
                        {"text": {"text": ["Here are the consultants in your area:"]}},
                        {"payload": doctor_list_payload}
                    ]
                }
            }

        # --- SelectDoctor ---
        elif intent_display_name == 'SelectDoctorFromList':
            doctor_name = parameters.get("doctor_name")
            if doctor_name in DOCTORS:
                # Get first available location
                locations = DOCTORS[doctor_name]["locations"]
                location = locations[0]
                
                # Fetch available dates from dummy data
                available_dates = DOCTORS[doctor_name]["available_dates"][location]
                
                # Create chips for dates and times
                date_time_chips = []
                for entry in available_dates:
                    date_obj = datetime.strptime(entry["date"], "%Y-%m-%d")
                    for time_slot in entry["times"]:
                        combined_dt_str = f"{date_obj.strftime('%Y-%m-%d')}T{time_slot}:00"
                        date_time_chips.append({
                            "text": f"{date_obj.strftime('%a %d %b')}, {time_slot}",
                            "value": combined_dt_str
                        })
                
                combined_payload = {
                    "richContent": [
                        [
                            {
                                "type": "chips",
                                "options": date_time_chips
                            }
                        ]
                    ]
                }
                
                fulfillment_response = {
                    "fulfillmentResponse": {
                        "messages": [
                            {"text": {"text": [f"Great! Here are the available consultation times with {doctor_name} at {location}. Please select one to continue."]}},
                            {"payload": combined_payload}
                        ]
                    }
                }
            else:
                fulfillment_response = {
                    "fulfillmentResponse": {
                        "messages": [
                            {"text": {"text": ["Sorry, I couldn't find available times for that doctor."]}}
                        ]
                    }
                }

        # --- ConfirmBooking ---
        elif intent_display_name == 'ConfirmBooking':
            name = parameters.get("person_name", {})
            mobile = parameters.get("phone_number")
            email = parameters.get("email")
            tour_datetime = parameters.get("tour_datetime")

            doctor_name = parameters.get("doctor_name")
            location_name = DOCTORS[doctor_name]["locations"][0]

            # In a real app, you would parse the date/time string from the webhook
            # For this example, we'll use a placeholder
            formatted_date_time = "your selected date and time"
            
            # Create a simple confirmation message
            confirmation_message_plain = (
                f"Booking Confirmed!\n\n"
                f"Doctor: {doctor_name}\n"
                f"Location: {location_name}\n"
                f"Date & Time: {formatted_date_time}\n\n"
                "A confirmation has been sent to your email and WhatsApp."
            )
            
            # Save booking to Firestore (not implemented, but this is where it would go)
            # if db:
            #     db.collection("consultations").add(...)
            
            # Send confirmation emails and WhatsApp messages
            # send_email(email, "Consultation Confirmed", confirmation_message_plain, "<html>...</html>")
            # send_whatsapp_message(mobile, confirmation_message_plain)
            
            fulfillment_response = {
                "fulfillmentResponse": {
                    "messages": [
                        {"text": {"text": [confirmation_message_plain]}}
                    ]
                }
            }

    except Exception as e:
        logging.error(f"Webhook error: {e}")
        fulfillment_response = {
            "fulfillmentResponse": {
                "messages": [{"text": {"text": [f"Unexpected error: {e}"]}}]
            }
        }

    return jsonify(fulfillment_response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
