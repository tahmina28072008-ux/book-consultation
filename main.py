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
            # --- Start of new logic to create the rich card response ---
            doctor_text_lines = ["Here are some of our doctors who match your search. Which one would you like to know more about?"]
            chips_options = []
            
            for i, doctor in enumerate(available_doctors, 1):
                # Build the text part for the message
                text_line = (
                    f"\n{i}. {doctor['name']}\n"
                    f"   Specialty: {doctor['specialty']}\n"
                    f"   Qualifications: {doctor['qualifications']}\n"
                    f"   Locations: {', '.join(doctor['locations'])}"
                )
                doctor_text_lines.append(text_line)

                # Build the chips for the rich content
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
            # --- End of new logic ---
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

# --- New endpoint for the simple UI to fetch doctor data ---
@app.route('/get_doctors_for_ui', methods=['GET'])
def get_doctors_for_ui():
    """
    Returns all doctor data formatted for the frontend UI.
    """
    available_doctors = []
    for doctor_name, details in DOCTORS.items():
        doctor_details = details.copy()
        doctor_details["name"] = doctor_name
        available_doctors.append(doctor_details)
    
    return jsonify({"doctor_list": available_doctors})

# --- Root endpoint to serve the HTML page ---
@app.route('/', methods=['GET'])
def serve_doctors_html():
    """
    Serves the main HTML page for the doctor directory.
    """
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Doctor Directory</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Google Fonts - Inter -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
        }
        .modal-fade-enter {
            opacity: 0;
            transform: scale(0.95);
        }
        .modal-fade-enter-active {
            opacity: 1;
            transform: scale(1);
            transition: opacity 0.3s ease, transform 0.3s ease;
        }
        .modal-fade-exit {
            opacity: 1;
            transform: scale(1);
        }
        .modal-fade-exit-active {
            opacity: 0;
            transform: scale(0.95);
            transition: opacity 0.3s ease, transform 0.3s ease;
        }
    </style>
</head>
<body class="p-4 md:p-8">
    <div class="max-w-4xl mx-auto">
        <header class="text-center mb-10">
            <h1 class="text-3xl sm:text-4xl font-bold text-gray-900 mb-2">Find a Doctor</h1>
            <p class="text-gray-600 text-lg">Browse our directory of medical professionals.</p>
        </header>

        <!-- Search Bar -->
        <div class="mb-8">
            <input type="text" id="searchInput" placeholder="Search by name, specialty, or location..." class="w-full p-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-shadow">
        </div>

        <!-- Doctor List Container -->
        <div id="doctorList" class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="col-span-1 md:col-span-2 text-center text-gray-500">Loading doctors...</div>
        </div>

        <!-- Appointment Modal -->
        <div id="appointmentModal" class="fixed inset-0 z-50 hidden items-center justify-center p-4 modal-fade-exit">
            <div class="absolute inset-0 bg-gray-900 bg-opacity-75 transition-opacity"></div>
            <div class="relative bg-white rounded-xl shadow-2xl max-w-sm w-full p-6 transform modal-fade-exit">
                <div class="text-center">
                    <h3 class="text-2xl font-semibold text-gray-900 mb-2">Appointment Scheduled!</h3>
                    <p class="text-gray-600 mb-4">You have booked an appointment with:</p>
                    <p id="modalDoctorName" class="text-lg font-bold text-blue-600 mb-2"></p>
                    <p class="text-sm text-gray-500">A confirmation email has been sent.</p>
                </div>
                <button id="closeModal" class="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
        </div>
    </div>

    <script>
        const doctorListContainer = document.getElementById('doctorList');
        const searchInput = document.getElementById('searchInput');
        const appointmentModal = document.getElementById('appointmentModal');
        const modalDoctorName = document.getElementById('modalDoctorName');
        const closeModalButton = document.getElementById('closeModal');
        let allDoctors = [];

        async function fetchDoctors() {
            try {
                const response = await fetch('/get_doctors_for_ui');
                const data = await response.json();
                allDoctors = data.doctor_list;
                renderDoctors(allDoctors);
            } catch (error) {
                console.error("Failed to fetch doctors:", error);
                doctorListContainer.innerHTML = '<p class="col-span-1 md:col-span-2 text-center text-red-500">Error loading doctor data. Please try again later.</p>';
            }
        }

        function renderDoctors(filteredDoctors) {
            doctorListContainer.innerHTML = '';
            if (filteredDoctors.length === 0) {
                doctorListContainer.innerHTML = '<p class="col-span-1 md:col-span-2 text-center text-gray-500">No doctors found matching your search.</p>';
            }

            filteredDoctors.forEach(doctor => {
                const qualificationsHtml = doctor.qualifications;
                const specialtiesHtml = doctor.specialty;
                const servicesHtml = doctor.services.map(service => `<li class="text-sm text-gray-600">• ${service}</li>`).join('');

                const doctorCard = `
                    <div class="bg-white rounded-xl shadow-lg p-6 flex flex-col justify-between hover:shadow-xl transition-shadow duration-300">
                        <div>
                            <h2 class="text-xl font-bold text-gray-900 mb-2">${doctor.name}</h2>
                            <div class="mb-3">
                                <p class="text-sm text-gray-700">
                                    <span class="font-semibold">Qualifications:</span> ${qualificationsHtml}
                                </p>
                                <p class="text-sm text-gray-700">
                                    <span class="font-semibold">GMC number:</span> ${doctor.gmcNumber}
                                </p>
                                <p class="text-sm text-gray-700">
                                    <span class="font-semibold">Practising since:</span> ${doctor.practisingSince}
                                </p>
                            </div>
                            <p class="text-lg font-medium text-blue-600 mb-3">
                                <span class="font-semibold text-gray-700">Specialties:</span> ${specialtiesHtml}
                            </p>
                            <p class="text-gray-700 mb-1">
                                <span class="font-semibold">Locations:</span> ${doctor.locations.join(', ')}
                            </p>
                            <div class="mb-4">
                                <span class="font-semibold text-gray-700 block mb-1">Services:</span>
                                <ul class="list-none pl-0">
                                    ${servicesHtml}
                                </ul>
                            </div>
                        </div>
                        <button data-doctor-name="${doctor.name}" class="mt-4 w-full bg-blue-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
                            Book an Appointment
                        </button>
                    </div>
                `;
                doctorListContainer.innerHTML += doctorCard;
            });

            // Re-attach event listeners after rendering new cards
            document.querySelectorAll('button[data-doctor-name]').forEach(button => {
                button.addEventListener('click', (event) => {
                    const doctorName = event.target.getAttribute('data-doctor-name');
                    modalDoctorName.textContent = doctorName;
                    appointmentModal.classList.remove('hidden', 'modal-fade-exit-active');
                    appointmentModal.classList.add('flex', 'modal-fade-enter-active');
                });
            });
        }

        // Close modal functionality
        closeModalButton.addEventListener('click', () => {
            appointmentModal.classList.remove('modal-fade-enter-active');
            appointmentModal.classList.add('modal-fade-exit-active');
            setTimeout(() => {
                appointmentModal.classList.add('hidden');
                appointmentModal.classList.remove('flex', 'modal-fade-exit-active');
            }, 300); // Wait for transition to finish
        });

        // Search functionality
        searchInput.addEventListener('keyup', (event) => {
            const searchTerm = event.target.value.toLowerCase();
            const filteredDoctors = allDoctors.filter(doctor =>
                doctor.name.toLowerCase().includes(searchTerm) ||
                (doctor.qualifications && doctor.qualifications.toLowerCase().includes(searchTerm)) ||
                (doctor.specialty && doctor.specialty.toLowerCase().includes(searchTerm)) ||
                (doctor.locations && doctor.locations.some(loc => loc.toLowerCase().includes(searchTerm)))
            );
            renderDoctors(filteredDoctors);
        });

        // Initial fetch and render
        window.onload = () => {
            fetchDoctors();
        };
    </script>
</body>
</html>
    """
    return html_content

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
