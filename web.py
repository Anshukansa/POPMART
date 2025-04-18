import os
import sys
from admin_panel import AdminPanel

# Load environment variables
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")
NOTIFICATION_BOT_TOKEN = os.environ.get("NOTIFICATION_BOT_TOKEN")

try:
    # Create the admin panel with notification token for testing functionality
    panel = AdminPanel(ADMIN_USERNAME, ADMIN_PASSWORD, NOTIFICATION_BOT_TOKEN)
    
    # Expose the Flask app for Gunicorn
    app = panel.app
except Exception as e:
    print(f"Error initializing web app: {e}")
    # For local development, re-raise
    if 'gunicorn' not in sys.modules:
        raise
    
    # For Gunicorn, create a simple fallback app
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/')
    def error_page():
        return jsonify({"error": "Application failed to initialize. Please check logs."}), 500

if __name__ == "__main__":
    # For local development only
    port = int(os.environ.get("PORT", 5000))
    panel.run(host="0.0.0.0", port=port)