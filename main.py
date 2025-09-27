from flask import Flask, request, jsonify
import logging
import os
from datetime import datetime
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import difflib

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# --- Dummy Doctor and Hospital Data ---
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

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

def format_phone_number(phone_number):
    phone_number = phone_number.replace(' ', '').replace('-', '')
    if not phone_number.startswith('+'):
        if phone_number.startswith('0'):
            return f'+44{phone_number[1:]}'
        elif phone_number.startswith('44'):
            return f'+{phone_number}'
        else:
            logging.warning(f"Could not reliably format phone number: {phone_number}")
            return f'+{phone_number}'
    return phone_number

def send_whatsapp_message(to_number, body):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        formatted_to_number = format_phone_number(to_number)
        logging.info(f"Attempting to send message from {TWILIO_PHONE_NUMBER} to {formatted_to_number}")
        message = client.messages.create(
            from_=f'whatsapp:{TWILIO_PHONE_NUMBER}',
            body=body,
            to=f'whatsapp:{formatted_to_number}'
        )
        logging.info(f"WhatsApp message sent to {formatted_to_number}: {message.sid}")
        return message.sid
    except Exception as e:
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

def find_doctor_key(user_input):
    for key in DOCTORS.keys():
        if key.strip().lower() == user_input.strip().lower():
            return key
    options = [k.lower() for k in DOCTORS.keys()]
    input_clean = user_input.lower().replace('dr. ', '').replace('mr ', '').replace('ms ', '').replace('miss ', '').strip()
    match = difflib.get_close_matches(input_clean, options, n=1, cutoff=0.7)
    if match:
        for key in DOCTORS.keys():
            if key.lower() == match[0]:
                return key
    return None

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    tag = req.get("fulfillmentInfo", {}).get("tag")
    params = req.get("sessionInfo", {}).get("parameters", {})
    logging.info(f"Webhook called. Tag: {tag}, Params: {params}, Raw Body: {req}")

    # --- Doctor List ---
    if tag == "get_doctor_list":
        city = params.get("city")
        postcode = params.get("postcode")
        location = params.get("location")
        specialty = params.get("specialty")
        available_doctors = []
        for doctor_name, details in DOCTORS.items():
            if specialty and specialty.lower() not in details["specialty"].lower():
                continue
            matching_locations = []
            for loc in details["locations"]:
                hospital = HOSPITALS.get(loc, {})
                if location:
                    if location.lower() not in hospital.get("city", "").lower() and location.lower() != hospital.get("postcode", "").lower():
                        continue
                elif city and city.lower() not in hospital.get("city", "").lower():
                    continue
                elif postcode and postcode.lower() != hospital.get("postcode", "").lower():
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
                    f"      Specialty: {doctor['specialty']}\n"
                    f"      Locations: {', '.join(doctor['locations'])}"
                )
                doctor_text_lines.append(text_line)
                chips_options.append({
                    "text": f"View {doctor['name']}",
                    "value": doctor['name']
                })
            card_text_message = {"text": {"text": doctor_text_lines}}
            chips_payload = {"richContent": [[{"type": "chips", "options": chips_options}]]}
            return jsonify({
                "fulfillment_response": {
                    "messages": [card_text_message, {"payload": chips_payload}]
                }
            })
        else:
            response_text = f"Sorry, no {specialty} doctors found in {location or city or postcode}."
            return jsonify({
                "fulfillment_response": {
                    "messages": [
                        {"text": {"text": [response_text]}}
                    ]
                }
            })

    # --- Doctor Details ---
    elif tag == "get_doctor_details":
        doctor_name = params.get("doctor_name")
        if not doctor_name:
            doctor_name = req.get("text", "") or req.get("query_result", {}).get("query_text", "")
            if doctor_name.lower().startswith("view "):
                doctor_name = doctor_name[5:]
            doctor_name = doctor_name.strip()
        logging.info(f"Doctor name received: '{doctor_name}'")
        match = find_doctor_key(doctor_name)
        if not match:
            logging.error(f"Doctor not found for input: '{doctor_name}'")
            return jsonify({
                "fulfillment_response": {
                    "messages": [{"text": {"text": ["Sorry, I couldn't find details for that doctor."]}}]
                }
            })
        doctor_details = DOCTORS[match]
        locations_and_details_text = []
        for loc_name in doctor_details.get("locations", []):
            hospital_info = HOSPITALS.get(loc_name, {})
            location_text = (
                f"🏥 {loc_name}\n"
                f"      📍 Address: {hospital_info.get('address', 'N/A')}, {hospital_info.get('postcode', 'N/A')}\n"
                f"      📞 Phone: {hospital_info.get('phone', 'N/A')}"
            )
            locations_and_details_text.append(location_text)
        services_text = ", ".join(doctor_details.get("services", []))
        schedule_text = []
        chips_options = []
        for loc, slots in doctor_details.get("available_dates", {}).items():
            schedule_text.append(f"🏥 {loc}")
            for slot in slots:
                date_obj = datetime.strptime(slot["date"], "%Y-%m-%d")
                date_str = date_obj.strftime("%a, %d %b")
                times = ", ".join(slot["times"]) if slot["times"] else "No appointments"
                schedule_text.append(f"      📅 {date_str}: {times}")
                for t in slot["times"]:
                    chips_options.append({
                        "text": f"{date_str} {t}",
                        "value": f"Book appointment with {match} on {date_obj.date()} at {t}"
                    })
        detail_text = (
            f"Here are the details for {match}:\n\n"
            f"🩺 Specialty: {doctor_details.get('specialty')}\n"
            f"🎓 Qualifications: {doctor_details.get('qualifications')}\n"
            f"Practising Since: {doctor_details.get('practisingSince')}\n"
            f"Initial Consultation Fee: £{doctor_details['fees'].get('Initial consultation')}\n\n"
            f"🏥 Locations:\n" + "\n".join(locations_and_details_text) + "\n\n"
            f"Services: {services_text}\n"
            f"📅 Available Dates & Times:\n" + "\n".join(schedule_text)
        )
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

    # --- Ask if user wants to upload medical document ---
    elif tag == "ask_upload_document":
        prompt = "Would you like to upload a medical test document before confirming your booking?"
        chips_payload = {
            "richContent": [
                [
                    {"type": "chips", "options": [
                        {"text": "Yes, upload document", "value": "yes"},
                        {"text": "No, confirm booking", "value": "no"}
                    ]}
                ]
            ]
        }
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [prompt]}},
                    {"payload": chips_payload}
                ]
            }
        })

    # --- Handle document upload flow ---
    elif tag == "handle_upload_document":
        # You would implement your upload logic here or just acknowledge for mock/demo
        response_text = "Thank you. Your document has been received. Now confirming your booking..."
        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [response_text]}}
                ]
            }
        })
        # After this, Dialogflow transitions to final_confirm_and_send

    # --- Final Confirmation and Billing ---
    elif tag == "final_confirm_and_send":
        name = params.get("person_name", {})
        first_name = name.get("name") if isinstance(name, dict) else name
        mobile = params.get("phone_number")
        email = params.get("email")
        appointment_datetime = params.get("appointment_datetime")
        doctor_name = params.get("doctor_name")
        insurer = params.get("insurance_provider")
        policy_number = params.get("policy_number")
        authorisation_code = params.get("authorisation_code")

        match = find_doctor_key(doctor_name or "")
        if not match:
            return jsonify({
                "fulfillment_response": {
                    "messages": [{"text": {"text": ["Doctor not found."]}}]
                }
            })

        location_name = DOCTORS[match]["locations"][0]
        hospital_info = HOSPITALS.get(location_name, {})
        formatted_date_time = "your selected date and time"
        if appointment_datetime:
            try:
                if isinstance(appointment_datetime, dict):
                    year = int(appointment_datetime.get("year", 0))
                    month = int(appointment_datetime.get("month", 1))
                    day = int(appointment_datetime.get("day", 1))
                    hours = int(appointment_datetime.get("hours", 0))
                    minutes = int(appointment_datetime.get("minutes", 0))
                    seconds = int(appointment_datetime.get("seconds", 0))
                    dt_obj = datetime(year, month, day, hours, minutes, seconds)
                else:
                    dt_obj = datetime.fromisoformat(appointment_datetime)
                formatted_date_time = dt_obj.strftime("%A, %d %B %Y at %I:%M %p")
            except Exception as e:
                logging.warning(f"Failed to parse appointment_datetime: {appointment_datetime}, error: {e}")

        base_fee = DOCTORS[match]['fees'].get('Initial consultation', 0)
        insurance_discount = 1.0
        if insurer and isinstance(insurer, str) and insurer.strip().lower() == "axa health":
            insurance_discount = 0.5
        total_bill = base_fee * insurance_discount

        confirmation_message_plain = (
            f"Booking Confirmed!\n\n"
            f"Doctor: {match}\n"
            f"Specialty: {DOCTORS[match]['specialty']}\n"
            f"Location: {location_name}\n"
            f"Address: {hospital_info.get('address', 'N/A')}\n"
            f"Phone: {hospital_info.get('phone', 'N/A')}\n"
            f"Date & Time: {formatted_date_time}\n"
        )
        if insurer:
            confirmation_message_plain += (
                f"Insurer: {insurer}\n"
                f"Policy Number: {policy_number}\n"
                f"Authorisation Code: {authorisation_code}\n"
            )
        confirmation_message_plain += (
            f"Total Bill: £{total_bill:.2f}\n"
            f"\nA confirmation has been sent to your email ✉️ ({email}) and WhatsApp 📞 ({mobile})."
        )

        whatsapp_message = confirmation_message_plain

        # --- BEGIN: HTML Template for Confirmation Email ---
        confirmation_message_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    color: #222;
                    background-color: #f7f7f7;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    background: #fff;
                    margin: 30px auto;
                    padding: 24px;
                    border-radius: 10px;
                    max-width: 600px;
                    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
                }}
                .header {{
                    background-color: #1d7cab;
                    color: #fff;
                    padding: 16px;
                    border-radius: 10px 10px 0 0;
                    text-align: center;
                }}
                .section-title {{
                    margin-top: 24px;
                    font-size: 18px;
                    color: #1d7cab;
                    border-bottom: 1px solid #eee;
                }}
                .info-list {{
                    list-style: none;
                    padding: 0;
                    margin: 0;
                }}
                .info-list li {{
                    margin-bottom: 10px;
                    font-size: 16px;
                }}
                .footer {{
                    margin-top: 32px;
                    font-size: 15px;
                    color: #666;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>✅ Your Consultation is Confirmed!</h2>
                </div>
                <p>Dear {first_name},</p>
                <p>
                    Thank you for booking your consultation. Here are your appointment details:
                </p>
                <div class="section-title">Doctor Details</div>
                <ul class="info-list">
                    <li><strong>Name:</strong> {match}</li>
                    <li><strong>Specialty:</strong> {DOCTORS[match]['specialty']}</li>
                    <li><strong>Qualifications:</strong> {DOCTORS[match]['qualifications']}</li>
                    <li><strong>GMC Number:</strong> {DOCTORS[match]['gmcNumber']}</li>
                    <li><strong>Practising Since:</strong> {DOCTORS[match]['practisingSince']}</li>
                </ul>
                <div class="section-title">Hospital Details</div>
                <ul class="info-list">
                    <li><strong>Hospital:</strong> {location_name}</li>
                    <li><strong>Address:</strong> {hospital_info.get('address', 'N/A')}</li>
                    <li><strong>City:</strong> {hospital_info.get('city', 'N/A')}</li>
                    <li><strong>Postcode:</strong> {hospital_info.get('postcode', 'N/A')}</li>
                    <li><strong>Phone:</strong> {hospital_info.get('phone', 'N/A')}</li>
                </ul>
                <div class="section-title">Appointment Details</div>
                <ul class="info-list">
                    <li><strong>Date & Time:</strong> {formatted_date_time}</li>
                    <li><strong>Consultation Fee:</strong> £{base_fee:.2f}</li>
                </ul>
        """

        if insurer:
            confirmation_message_html += f"""
                <div class="section-title">Insurance Details</div>
                <ul class="info-list">
                    <li><strong>Provider:</strong> {insurer}</li>
                    <li><strong>Policy Number:</strong> {policy_number}</li>
                    <li><strong>Authorisation Code:</strong> {authorisation_code or "N/A"}</li>
                    <li><strong>Discount Applied:</strong> {'50% insurance discount' if insurance_discount == 0.5 else 'No discount'}</li>
                </ul>
            """

        confirmation_message_html += f"""
                <div class="section-title">Total Bill</div>
                <ul class="info-list">
                    <li><strong>Total Amount Due:</strong> £{total_bill:.2f}</li>
                </ul>
                <div class="section-title">Contact Details</div>
                <ul class="info-list">
                    <li><strong>Email:</strong> {email}</li>
                    <li><strong>Phone:</strong> {mobile}</li>
                </ul>
                <div class="footer">
                    <p>If you have any questions, please contact us at <a href="mailto:info@yourclinic.com">info@yourclinic.com</a> or call {hospital_info.get('phone', 'N/A')}.</p>
                    <p>We look forward to seeing you!</p>
                </div>
            </div>
        </body>
        </html>
        """
        # --- END: HTML Template for Confirmation Email ---

        if email:
            send_email(email, "✅ Consultation Confirmed", confirmation_message_plain, confirmation_message_html)
        if mobile:
            send_whatsapp_message(mobile, whatsapp_message)

        return jsonify({
            "fulfillment_response": {
                "messages": [
                    {"text": {"text": [confirmation_message_plain]}}
                ]
            }
        })

    else:
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
