from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import mysql.connector
import requests
from datetime import datetime

load_dotenv()  # Load .env file

app = Flask(__name__)

# === Config ===
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
META_API_URL = f'https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages'

# === MySQL Connection ===
db = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)
cursor = db.cursor()


# === Initialize DB and Table ===
def init_db():
    try:
        temp_conn = mysql.connector.connect(
            host=MYSQL_CONFIG['host'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password']
        )
        temp_cursor = temp_conn.cursor()
        temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']}")
        temp_cursor.close()
        temp_conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")

    # Connect to the created database
    db = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            wa_id VARCHAR(50),
            name VARCHAR(100),
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    return db, cursor

# === Initialize DB Connection ===
db, cursor = init_db()

# === Webhook ===
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Verification token mismatch', 403

    elif request.method == 'POST':
        data = request.get_json()
        try:
            entry = data['entry'][0]['changes'][0]['value']
            messages = entry.get('messages', [])
            contacts = entry.get('contacts', [])

            if messages and contacts:
                wa_id = contacts[0]['wa_id']
                name = contacts[0]['profile']['name']
                message_text = messages[0]['text']['body'].strip().lower()

                cursor.execute(
                    "INSERT INTO client_data (wa_id, name, message) VALUES (%s, %s, %s)",
                    (wa_id, name, message_text)
                )
                db.commit()

                if message_text == "my data":
                    cursor.execute(
                        "SELECT message, timestamp FROM client_data WHERE wa_id = %s ORDER BY timestamp DESC LIMIT 5",
                        (wa_id,)
                    )
                    results = cursor.fetchall()
                    insights = "\n".join([f"- {msg} ({time})" for msg, time in results])
                    response = insights or "No data found."
                    send_whatsapp_message(wa_id, f"📦 Here's your recent data:\n{response}")

                elif message_text == "delete my data":
                    cursor.execute("DELETE FROM client_data WHERE wa_id = %s", (wa_id,))
                    db.commit()
                    send_whatsapp_message(wa_id, "✅ Your data has been deleted.")

                elif message_text == "help":
                    send_whatsapp_message(wa_id,
                        "🤖 Available Commands:\n- 'My data': View what we've saved\n- 'Delete my data': Remove your info\n- 'Help': Show this menu")

        except Exception as e:
            print(f"Error: {e}")
        return jsonify({"status": "received"}), 200

# === WhatsApp Message Sender ===
def send_whatsapp_message(recipient_id, message_text):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "text",
        "text": {"body": message_text}
    }
    requests.post(META_API_URL, json=payload, headers=headers)

# === Legal Pages ===
@app.route('/privacy-policy')
def privacy_policy():
    return """
    <h1>Privacy Policy</h1>
    <p>We collect your WhatsApp name and message content to support you better.</p>
    <p>Your data is stored securely and not shared with third parties without your consent.</p>
    <p>To access or delete your data, message "My data" or "Delete my data".</p>
    <p>Contact: support@example.com</p>
    """

@app.route('/terms-of-service')
def terms_of_service():
    return """
    <h1>Terms of Service</h1>
    <p>By using this WhatsApp service, you agree to allow us to store and use your data to provide insights and support.</p>
    <p>You must not misuse or attempt to breach this service.</p>
    <p>We may update these terms anytime. Continued use implies acceptance.</p>
    """

@app.route('/')
def home():
    return """
    <h1>Welcome to Our WhatsApp Service</h1>
    <p><a href='/privacy-policy'>Privacy Policy</a></p>
    <p><a href='/terms-of-service'>Terms of Service</a></p>
    """

# === Run Server ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
