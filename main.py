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
                {"date": "2025-09-29", "times": ["15:45"]},
                {"date": "2025-09-30", "times": ["10:15", "10:45", "11:00"]},
                {"date": "2025-10-01", "times": ["14:45", "15:15", "15:30"]},
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
                {"date": "2025-09-29", "times": ["16:30", "16:45"]},
                {"date": "2025-09-30", "times": ["16:30", "16:45"]},
            ],
            "The Holly Hospital": [
                {"date": "2025-09-29", "times": ["17:00", "18:30"]},
                {"date": "2025-09-30", "times": ["17:00", "18:30"]},
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
                {"date": "2025-09-29", "times": ["10:00", "10:30", "11:00"]},
                {"date": "2025-10-02", "times": ["10:00", "10:30", "11:00"]},
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
                {"date": "2025-09-30", "times": ["14:00", "14:30"]},
                {"date": "2025-10-03", "times": ["14:00", "14:30"]},
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
                {"date": "2025-09-29", "times": ["09:00", "09:30", "10:00"]},
                {"date": "2025-09-30", "times": ["09:00", "09:30", "10:00"]},
                {"date": "2025-10-01", "times": ["09:00", "09:30"]},
            ],
            "The Holly Hospital": [
                {"date": "2025-10-02", "times": ["13:00", "13:30", "14:00"]},
                {"date": "2025-10-03", "times": ["13:00", "13:30", "14:00"]},
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
                {"date": "2025-09-29", "times": ["11:00", "11:30", "12:00"]},
                {"date": "2025-09-30", "times": ["11:00", "11:30", "12:00"]},
                {"date": "2025-10-02", "times": ["11:00", "11:30"]},
            ]
        },
        "services": ['Knee Arthroscopy', 'Hip Replacement', 'Sports Injuries']
    },
    "Dr Iffat Azim": {
        "specialty": "General Practice",
        "qualifications": "MBBS, MPH",
        "gmcNumber": "5166467",
        "practisingSince": 1991,
        "locations": ["The Holly Hospital", "Nuffield Health Brentwood Hospital"],
        "fees": {"Initial consultation": 250},
        "available_dates": {
            "The Holly Hospital": [
                {"date": "2025-09-29", "times": ["09:00", "09:30"]},
                {"date": "2025-09-30", "times": ["10:00", "10:30"]},
            ],
            "Nuffield Health Brentwood Hospital": [
                {"date": "2025-09-29", "times": ["14:00", "14:30"]},
                {"date": "2025-09-30", "times": ["15:00", "15:30"]},
            ]
        },
        "services": ['General Health Check-up', 'Preventative Medicine', 'Chronic Disease Management']
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
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False
    finally:
        server.quit()
    return True

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
                    f"     Specialty: {doctor['specialty']}\n"
                    f"     Locations: {', '.join(doctor['locations'])}"
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

    # --- Tag: Get Doctor Details (Updated to include times as chips and full hospital details) ---
    elif tag == "get_doctor_details":
        doctor_name = params.get("doctor_name")
        doctor_details = DOCTORS.get(doctor_name)

        if doctor_details:
            # Build the rich card response with more details
            locations_and_details_text = []
            for loc_name in doctor_details.get("locations", []):
                hospital_info = HOSPITALS.get(loc_name, {})
                location_text = (
                    f"🏥 {loc_name}\n"
                    f"     📍 Address: {hospital_info.get('address', 'N/A')}, {hospital_info.get('postcode', 'N/A')}\n"
                    f"     📞 Phone: {hospital_info.get('phone', 'N/A')}"
                )
                locations_and_details_text.append(location_text)
            
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
                    schedule_text.append(f"     📅 {date_str}: {times}")

                    for t in slot["times"]:
                        chips_options.append({
                            "text": f"{date_str} {t}",
                            "value": f"Book appointment with {doctor_name} on {date_obj.date()} at {t}"
                        })

            detail_text = (
                f"Here are the details for {doctor_name}:\n\n"
                f"🩺 Specialty: {doctor_details.get('specialty')}\n"
                f"🎓 Qualifications: {doctor_details.get('qualifications')}\n"
                f"Practising Since: {doctor_details.get('practisingSince')}\n"
                f"Initial Consultation Fee: £{doctor_details['fees'].get('Initial consultation')}\n\n"
                f"🏥 Locations:\n" + "\n".join(locations_and_details_text) + "\n\n"
                f"Services: {services_text}\n"
                f"📅 Available Dates & Times:\n" + "\n".join(schedule_text)
            )

            # The full rich response payload with chips
            chips_payload = {
                "richContent": [
                    [
                        {"type": "chips", "options": chips_options[:8]}, 
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

    # --- Tag: Ask for Payment Method ---
    elif tag == "confirm_booking":
        response_text = "Thank you. How would you like to pay for the consultation?"
        chips_payload = {
            "richContent": [
                [
                    {
                        "type": "chips",
                        "options": [
                            {
                                "text": "Pay for myself",
                                "event": {
                                    "name": "set_payment_method",
                                    "parameters": {"payment_method": "self"}
                                }
                            },
                            {
                                "text": "I have medical insurance",
                                "event": {
                                    "name": "set_payment_method",
                                    "parameters": {"payment_method": "insurance"}
                                }
                            }
                        ]
                    }
                ]
            ]
        }
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [response_text]}},
                    {"payload": chips_payload}
                ]
            }
        })
    
    # --- New Tag: Ask for Insurance Details ---
    elif tag == "ask_for_insurance_details":
        response_text = "Please provide your Insurer, Policy number, and Authorisation code."
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [response_text]}}
                ]
            }
        })

    # --- New Tag: Final Confirmation and Billing ---
    elif tag == "final_confirm_and_send":
        name = params.get("person_name", {})
        first_name = name.get("name") if isinstance(name, dict) else name
        mobile = params.get("phone_number")
        email = params.get("email")
        appointment_datetime = params.get("appointment_datetime")
        doctor_name = params.get("doctor_name")
        payment_method = params.get("payment_method")
        
        # New parameters for insurance
        insurer = params.get("insurer")
        policy_number = params.get("policy_number")
        authorisation_code = params.get("authorisation_code")

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
                if isinstance(appointment_datetime, dict):
                    # Extract values and cast to int
                    year = int(appointment_datetime.get("year", 0))
                    month = int(appointment_datetime.get("month", 1))
                    day = int(appointment_datetime.get("day", 1))
                    hours = int(appointment_datetime.get("hours", 0))
                    minutes = int(appointment_datetime.get("minutes", 0))
                    seconds = int(appointment_datetime.get("seconds", 0))
                    
                    dt_obj = datetime(year, month, day, hours, minutes, seconds)
                else:
                    # Handle ISO 8601 string
                    dt_obj = datetime.fromisoformat(appointment_datetime)

                formatted_date_time = dt_obj.strftime("%A, %d %B %Y at %I:%M %p")

            except Exception as e:
                logging.warning(
                    f"Failed to parse appointment_datetime: {appointment_datetime}, error: {e}"
                )

        # Calculate the total bill based on the payment method
        base_fee = DOCTORS[doctor_name]['fees'].get('Initial consultation', 0)
        total_bill = 0
        if payment_method == "self":
            total_bill = base_fee
        elif payment_method == "insurance":
            total_bill = base_fee * 0.50  # Example: 50% co-pay

        # Build the confirmation message
        confirmation_message_plain = (
            f"Booking Confirmed!\n\n"
            f"Doctor: {doctor_name}\n"
            f"Specialty: {DOCTORS[doctor_name]['specialty']}\n"
            f"Location: {location_name}\n"
            f"Address: {hospital_info.get('address', 'N/A')}\n"
            f"Phone: {hospital_info.get('phone', 'N/A')}\n"
            f"Date & Time: {formatted_date_time}\n"
            f"Payment Method: {payment_method}\n"
        )
        if payment_method == "I have medical insurance":
            confirmation_message_plain += (
                f"Insurer: {insurer}\n"
                f"Policy Number: {policy_number}\n"
                f"Authorisation Code: {authorisation_code}\n"
            )
        confirmation_message_plain += (
            f"Total Bill: £{total_bill:.2f}\n\n"
            f"A confirmation has been sent to your email ✉️ ({email}) and WhatsApp 📞 ({mobile})."
        )

        confirmation_message_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Appointment Confirmed</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7f6;">
            <div style="max-width: 600px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e0e0e0;">
                
                <!-- Header -->
                <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #f0f0f0;">
                    <img src="https://placehold.co/150x50/2a7ae2/FFFFFF?text=Logo" alt="Nuffield Health Logo" style="max-width: 150px; height: auto;">
                    <h1 style="font-size: 24px; color: #333; margin-top: 10px;">Appointment Confirmed</h1>
                </div>

                <!-- Body -->
                <div style="padding-top: 20px;">
                    <p style="font-size: 16px; color: #555; line-height: 1.6;">Dear {first_name},</p>
                    <p style="font-size: 16px; color: #555; line-height: 1.6;">We're pleased to confirm your upcoming consultation. Please find the details below. We look forward to seeing you!</p>
                    
                    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #888; width: 30%;"><strong>Patient:</strong></td>
                                <td style="padding: 8px 0; color: #333;">{first_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #888;"><strong>Doctor:</strong></td>
                                <td style="padding: 8px 0; color: #333;">{doctor_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #888;"><strong>Specialty:</strong></td>
                                <td style="padding: 8px 0; color: #333;">{DOCTORS[doctor_name]['specialty']}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #888;"><strong>Hospital:</strong></td>
                                <td style="padding: 8px 0; color: #333;">{location_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #888;"><strong>Address:</strong></td>
                                <td style="padding: 8px 0; color: #333;">{hospital_info.get('address', 'N/A')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #888;"><strong>Date & Time:</strong></td>
                                <td style="padding: 8px 0; color: #333;">{formatted_date_time}</td>
                            </tr>
                            <tr style="border-top: 1px solid #e0e0e0;">
                                <td style="padding: 8px 0; color: #888;"><strong>Payment Method:</strong></td>
                                <td style="padding: 8px 0; color: #333;">{payment_method}</td>
                            </tr>
                            {'<tr style="border-top: 1px solid #e0e0e0;">' if payment_method == 'I have medical insurance' else ''}
                            {'<td style="padding: 8px 0; color: #888;"><strong>Insurer:</strong></td>' if payment_method == 'I have medical insurance' else ''}
                            {'<td style="padding: 8px 0; color: #333;">' + str(insurer) + '</td>' if payment_method == 'I have medical insurance' else ''}
                            {'</tr>' if payment_method == 'I have medical insurance' else ''}
                            {'<tr>' if payment_method == 'I have medical insurance' else ''}
                            {'<td style="padding: 8px 0; color: #888;"><strong>Policy Number:</strong></td>' if payment_method == 'I have medical insurance' else ''}
                            {'<td style="padding: 8px 0; color: #333;">' + str(policy_number) + '</td>' if payment_method == 'I have medical insurance' else ''}
                            {'</tr>' if payment_method == 'I have medical insurance' else ''}
                            {'<tr>' if payment_method == 'I have medical insurance' else ''}
                            {'<td style="padding: 8px 0; color: #888;"><strong>Authorisation Code:</strong></td>' if payment_method == 'I have medical insurance' else ''}
                            {'<td style="padding: 8px 0; color: #333;">' + str(authorisation_code) + '</td>' if payment_method == 'I have medical insurance' else ''}
                            {'</tr>' if payment_method == 'I have medical insurance' else ''}
                            <tr>
                                <td style="padding: 8px 0; color: #888;"><strong>Total Bill:</strong></td>
                                <td style="padding: 8px 0; color: #333;"><strong>£{total_bill:.2f}</strong></td>
                            </tr>
                        </table>
                    </div>
                    
                    <p style="font-size: 16px; color: #555; line-height: 1.6;">
                        A confirmation has also been sent to your <strong style="color: #2a7ae2;">📞 WhatsApp ({mobile})</strong>.
                    </p>
                    
                    <!-- Call to Action Button -->
                    <div style="text-align: center; margin-top: 30px;">
                        <a href="#" style="background-color: #2a7ae2; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 25px; font-weight: bold; display: inline-block;">View My Account</a>
                    </div>
                </div>

                <!-- Footer -->
                <div style="text-align: center; padding-top: 20px; border-top: 1px solid #f0f0f0; margin-top: 30px;">
                    <p style="font-size: 14px; color: #aaa; margin: 0;">
                        If you have any questions, please do not hesitate to contact us.
                    </p>
                    <p style="font-size: 14px; color: #aaa; margin: 5px 0 0;">
                        Warm regards,<br>The Nuffield Health Team
                    </p>
                </div>

            </div>
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
    else:
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
