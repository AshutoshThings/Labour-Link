from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, Response, session
import json
import os
from werkzeug.security import generate_password_hash, check_password_hash
import traceback
from datetime import datetime
from twilio.rest import Client
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = ''

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = ''
TWILIO_PHONE_NUMBER = '' 

try:
    if TWILIO_ACCOUNT_SID == '' or TWILIO_AUTH_TOKEN == '' or TWILIO_PHONE_NUMBER == '':
        print("Twilio credentials are not set. Please replace the placeholder values.")
        twilio_client = None
    else:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
except Exception as e:
    print(f"Error initializing Twilio Client: {e}")
    twilio_client = None

CONTRACTOR_CREDENTIALS_FILE = 'contractors.json'
WORKER_DATA_FILE = 'workers.json'
AVAILABLE_WORKERS_CALLS_FILE = 'available_workers_calls.json'

def load_contractor_credentials():
    if not os.path.exists(CONTRACTOR_CREDENTIALS_FILE):
        with open(CONTRACTOR_CREDENTIALS_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    try:
        with open(CONTRACTOR_CREDENTIALS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {CONTRACTOR_CREDENTIALS_FILE}. File might be empty or corrupted.")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred loading {CONTRACTOR_CREDENTIALS_FILE}: {e}")
        traceback.print_exc()
        return {}

def save_contractor_credentials(credentials):
    try:
        with open(CONTRACTOR_CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials, f, indent=4)
    except Exception as e:
        print(f"An unexpected error occurred saving to {CONTRACTOR_CREDENTIALS_FILE}: {e}")
        traceback.print_exc()

def load_worker_data():
    if not os.path.exists(WORKER_DATA_FILE):
        with open(WORKER_DATA_FILE, 'w') as f:
            json.dump([], f)
        return []
    try:
        with open(WORKER_DATA_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {WORKER_DATA_FILE}. File might be empty or corrupted.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred loading {WORKER_DATA_FILE}: {e}")
        traceback.print_exc()
        return []

def save_worker_data(workers):
    try:
        with open(WORKER_DATA_FILE, 'w') as f:
            json.dump(workers, f, indent=4)
    except Exception as e:
        print(f"An unexpected error occurred saving to {WORKER_DATA_FILE}: {e}")
        traceback.print_exc()

def load_available_workers_calls():
    if not os.path.exists(AVAILABLE_WORKERS_CALLS_FILE):
        with open(AVAILABLE_WORKERS_CALLS_FILE, 'w') as f:
            json.dump([], f)
        return []
    try:
        with open(AVAILABLE_WORKERS_CALLS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {AVAILABLE_WORKERS_CALLS_FILE}. File might be empty or corrupted.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred loading {AVAILABLE_WORKERS_CALLS_FILE}: {e}")
        traceback.print_exc()
        return {}

def save_available_workers_calls(calls):
    try:
        with open(AVAILABLE_WORKERS_CALLS_FILE, 'w') as f:
            json.dump(calls, f, indent=4)
    except Exception as e:
        print(f"An unexpected error occurred saving to {AVAILABLE_WORKERS_CALLS_FILE}: {e}")
        traceback.print_exc()


@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(app.static_folder, 'favicon.ico')
    except FileNotFoundError:
        return Response(status=404)

@app.route('/')
def index():
    try:
        return render_template('index.html', title='JobJunction - Connects Laborers and Contractors')
    except Exception as e:
        print(f"Error rendering index page: {e}")
        traceback.print_exc()
        return "An error occurred loading the homepage.", 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        skills = request.form.get('skills')
        experience = request.form.get('experience')
        phone_number = request.form.get('phone_number')

        if not name or not location or not skills or not phone_number:
            flash('Please fill in all required fields.', 'danger')
            try:
                return render_template('register.html', title='Worker Registration')
            except Exception as e:
                print(f"Error rendering worker registration page after validation error: {e}")
                traceback.print_exc()
                return "An error occurred.", 500

        worker_data = load_worker_data()

        if any(worker.get('phone_number') == phone_number for worker in worker_data):
            flash('A worker with this phone number is already registered.', 'danger')
            try:
                return render_template('register.html', title='Worker Registration')
            except Exception as e:
                print(f"Error rendering worker registration page after duplicate phone error: {e}")
                traceback.print_exc()
                return "An error occurred.", 500

        worker_id = 1
        if worker_data:
             worker_id = max(worker.get('id', 0) for worker in worker_data) + 1

        new_worker = {
            'id': worker_id,
            'name': name,
            'location': location,
            'skills': skills,
            'experience': experience,
            'phone_number': phone_number,
        }

        worker_data.append(new_worker)
        save_worker_data(worker_data)

        flash('Registration successful! You can now give a missed call to mark yourself available.', 'success')
        return redirect(url_for('index'))

    try:
        return render_template('register.html', title='Worker Registration')
    except Exception as e:
        print(f"Error rendering worker registration page (GET): {e}")
        traceback.print_exc()
        return "An error occurred loading the registration page.", 500

@app.route('/contractor-register', methods=['GET', 'POST'])
def contractor_register():
    """Contractor Registration Page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        phone_number = request.form.get('phone_number')
        age = request.form.get('age')
        job_type = request.form.get('job_type')

        contractor_credentials = load_contractor_credentials()

        if username in contractor_credentials:
            flash('Username already exists. Please choose a different one.', 'danger')
            try:
                return render_template('contractor_register.html', title='Contractor Registration')
            except Exception as e:
                print(f"Error rendering contractor registration page after duplicate username error: {e}")
                traceback.print_exc()
                return "An error occurred.", 500

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        contractor_details = {
            'password': hashed_password,
            'name': name,
            'phone_number': phone_number,
            'age': age,
            'job_type': job_type
        }

        contractor_credentials[username] = contractor_details
        save_contractor_credentials(contractor_credentials)

        flash('Contractor registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    try:
        return render_template('contractor_register.html', title='Contractor Registration')
    except Exception as e:
        print(f"Error rendering contractor registration page (GET): {e}")
        traceback.print_exc()
        return "An error occurred loading the contractor registration page.", 500

@app.route('/missed-call', methods=['GET', 'POST'])
def missed_call():
    """Handles missed call API endpoint from Exotel or similar."""
    phone_number = request.form.get('CallerId') or request.args.get('CallerId')
    if not phone_number:
        phone_number = request.form.get('phone_number') or request.args.get('phone_number')
    if not phone_number:
        phone_number = request.form.get('CallFrom') or request.args.get('CallFrom')
    if not phone_number:
        phone_number = request.form.get('From') or request.args.get('From')

    timestamp_str = request.args.get('CurrentTime')

    if phone_number:
        available_calls_data = load_available_workers_calls()
        worker_data = load_worker_data()

        is_registered_worker = any(worker.get('phone_number') == phone_number for worker in worker_data)

        if is_registered_worker:
            today_str = datetime.now().strftime('%Y-%m-%d')
            is_already_available_today = any(
                call.get('phone_number') == phone_number and call.get('timestamp', '').startswith(today_str)
                for call in available_calls_data
            )

            if not is_already_available_today:
                new_call_entry = {
                    'phone_number': phone_number,
                    'timestamp': timestamp_str if timestamp_str else datetime.now().isoformat(),
                    'is_hired': False 
                }
                available_calls_data.append(new_call_entry)
                save_available_workers_calls(available_calls_data)
                print(f"Received missed call from registered worker: {phone_number}. Recorded as available.")
                return 'Missed call recorded', 200
            else:
                print(f"Received missed call from registered worker: {phone_number}. Already marked as available today.")
                return 'Already available today', 200

        else:
            print(f"Received missed call from unregistered number: {phone_number}.")
            return 'Phone number not registered as a worker', 404
    else:
        print("No phone number found in request parameters.")
        return 'No phone number provided', 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Contractor Login Page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        contractor_credentials = load_contractor_credentials()

        if username in contractor_credentials and check_password_hash(contractor_credentials[username].get('password'), password):
            session['contractor_username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check your username and password.', 'danger')

    try:
        return render_template('login.html', title='Contractor Login')
    except Exception as e:
        print(f"Error rendering login page: {e}")
        traceback.print_exc()
        return "An error occurred loading the login page.", 500

@app.route('/logout')
def logout():
    """Contractor Logout"""
    session.pop('contractor_username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    """Contractor Dashboard"""
    if 'contractor_username' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

    available_calls_data = load_available_workers_calls()
    worker_data = load_worker_data()

    today_str = datetime.now().strftime('%Y-%m-%d')
    available_worker_phone_numbers_today = {
        call.get('phone_number'): call.get('is_hired', False) 
        for call in available_calls_data
        if call.get('phone_number') and call.get('timestamp', '').startswith(today_str)
    }

    available_workers_with_status = []
    for worker in worker_data:
        phone_number = worker.get('phone_number')
        if phone_number in available_worker_phone_numbers_today:
            is_hired = available_worker_phone_numbers_today[phone_number]
            worker_with_status = worker.copy()
            worker_with_status['is_hired'] = is_hired
            available_workers_with_status.append(worker_with_status)


    try:
        return render_template('dashboard.html', title='Contractor Dashboard', workers=available_workers_with_status)
    except Exception as e:
        print(f"Error rendering dashboard page: {e}")
        traceback.print_exc()
        return "An error occurred loading the dashboard.", 500

@app.route('/hire/<int:worker_id>', methods=['POST'])
def hire_worker(worker_id):
    """Handles hiring a worker and sending SMS notification."""
    if 'contractor_username' not in session:
        flash('Please log in to hire a worker.', 'warning')
        return redirect(url_for('login'))

    contractor_username = session['contractor_username']
    contractor_credentials = load_contractor_credentials()
    contractor_details = contractor_credentials.get(contractor_username)

    if not contractor_details:
        flash('Contractor details not found.', 'danger')
        return redirect(url_for('dashboard'))

    worker_data = load_worker_data()
    worker_to_hire = None
    for worker in worker_data:
        if worker.get('id') == worker_id:
            worker_to_hire = worker
            break

    if worker_to_hire:
        if twilio_client:
            try:
                contractor_name = contractor_details.get('name', 'A Contractor')
                contractor_job = contractor_details.get('job_type', 'the job')
                contractor_location = contractor_details.get('location', 'their location')

                worker_phone = worker_to_hire.get('phone_number')

                cleaned_phone_number = re.sub(r'\D', '', worker_phone)
                if cleaned_phone_number.startswith('0'):
                    cleaned_phone_number = cleaned_phone_number[1:]

                formatted_worker_phone = '+91' + cleaned_phone_number 

                message_body = f"Congratulations, you have been hired for today by {contractor_name} for the job: {contractor_job} at {contractor_location}."

                message = twilio_client.messages.create(
                    body=message_body,
                    from_=TWILIO_PHONE_NUMBER,
                    to=formatted_worker_phone
                )
                print(f"SMS sent to {formatted_worker_phone}. SID: {message.sid}")
                flash(f'Notification sent to {worker_to_hire.get("name", "N/A")}.', 'success')

                available_calls_data = load_available_workers_calls()
                today_str = datetime.now().strftime('%Y-%m-%d')
                for call in available_calls_data:
                    if call.get('phone_number') == worker_to_hire.get('phone_number') and call.get('timestamp', '').startswith(today_str):
                        call['is_hired'] = True
                        break 

                save_available_workers_calls(available_calls_data)
                print(f"Marked worker {worker_to_hire.get('phone_number')} as hired in available calls.")


            except Exception as e:
                print(f"Failed to send SMS to {worker_to_hire.get('phone_number')}: {e}")
                flash(f'Failed to send notification to {worker_to_hire.get("name", "N/A")}. Error: {e}', 'danger')
        else:
            print("Twilio client not initialized. Cannot send SMS.")
            flash('SMS service is not available. Cannot send notification.', 'danger')

    else:
        flash('Worker not found.', 'danger')

    return redirect(url_for('dashboard'))

@app.route('/how-it-works')
def how_it_works():
    """How It Works Page"""
    try:
        return render_template('how_it_works.html', title='How JobJunction Works')
    except Exception as e:
        print(f"Error rendering how it works page: {e}")
        traceback.print_exc()
        return "An error occurred loading the 'How It Works' page.", 500

@app.errorhandler(404)
def page_not_found(e):
    try:
        return render_template('404.html'), 404
    except Exception as render_error:
        print(f"Error rendering 404.html template: {render_error}")
        traceback.print_exc()
        return "Page not found and the error page could not be rendered.", 404

@app.errorhandler(500)
def internal_server_error(e):
    print(f"An internal server error occurred: {e}")
    traceback.print_exc()
    try:
        return render_template('500.html'), 500
    except Exception as render_error:
        print(f"Error rendering 500.html template: {render_error}")
        traceback.print_exc()
        return "An internal server error occurred and the error page could not be rendered.", 500

if __name__ == '__main__':
    load_contractor_credentials()
    load_worker_data()
    load_available_workers_calls()
    app.run(debug=True)
