import os
import sys
import logging
from flask import Flask, render_template, jsonify

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("web.log"),
              logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key")
NOTIFICATION_BOT_TOKEN = os.environ.get("BOT_TOKEN")

try:
    # Import directly from admin_panel.py
    import admin_panel
    
    # Get the Flask app instance
    app = admin_panel.app
    
    logger.info("Successfully imported Flask app from admin_panel")
except Exception as e:
    logger.error(f"Error initializing web app: {e}")
    # For local development, re-raise
    if 'gunicorn' not in sys.modules:
        raise
    
    # For Gunicorn, create a simple fallback app
    logger.info("Creating fallback Flask app")
    app = Flask(__name__)
    app.secret_key = FLASK_SECRET_KEY
    
    @app.route('/')
    def error_page():
        return jsonify({"error": "Application failed to initialize. Please check logs."}), 500

if __name__ == "__main__":
    # For local development only
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)