import os
from admin_panel import AdminPanel

# Load environment variables
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")

# Create the admin panel
panel = AdminPanel(ADMIN_USERNAME, ADMIN_PASSWORD)

# Expose the Flask app for Gunicorn
app = panel.app

if __name__ == "__main__":
    # For local development only
    port = int(os.environ.get("PORT", 5000))
    panel.run(host="0.0.0.0", port=port)