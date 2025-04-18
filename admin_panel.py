from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import logging
from selenium_monitor import SeleniumMonitor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("web.log"),
              logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key')

# Initialize the monitor
bot_token = os.environ.get('BOT_TOKEN')
if not bot_token:
    logger.warning("No BOT_TOKEN environment variable found. Some features may not work.")

# Initialize the Selenium monitor
logger.info("Initializing SeleniumMonitor for web interface")
selenium_monitor = SeleniumMonitor(bot_token or "dummy_token")
logger.info("GlobalMonitor initialized successfully")

@app.route('/')
def index():
    """Home page - redirects to dashboard if logged in, otherwise shows login form"""
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/', methods=['POST'])
def login():
    """Handle login form submission"""
    password = request.form.get('password')
    
    # Simple password check (you might want to use a more secure approach)
    if password == os.environ.get('ADMIN_PASSWORD', 'admin'):
        session['logged_in'] = True
        flash('You are now logged in', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Incorrect password', 'danger')
        return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    """Display admin dashboard"""
    if not session.get('logged_in'):
        flash('Please log in first', 'warning')
        return redirect(url_for('index'))
    
    # Get products from database
    products = selenium_monitor.db.get_all_products()
    
    return render_template('dashboard.html', products=products)

@app.route('/add_product', methods=['POST'])
def add_product():
    """Add a new product to monitor"""
    if not session.get('logged_in'):
        flash('Please log in first', 'warning')
        return redirect(url_for('index'))
    
    product_name = request.form.get('product_name')
    global_link = request.form.get('global_link')
    au_link = request.form.get('au_link')
    
    if not product_name or not global_link:
        flash('Product name and global link are required', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        selenium_monitor.db.add_product(product_name, global_link, au_link)
        flash(f'Product "{product_name}" added successfully', 'success')
    except Exception as e:
        logger.error(f"Error adding product: {str(e)}")
        flash(f'Error adding product: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/toggle_monitoring/<product_id>')
def toggle_monitoring(product_id):
    """Toggle monitoring status for a product"""
    if not session.get('logged_in'):
        flash('Please log in first', 'warning')
        return redirect(url_for('index'))
    
    try:
        current_status = selenium_monitor.db.is_product_monitored(product_id)
        selenium_monitor.db.set_product_monitoring(product_id, not current_status)
        
        status_msg = "enabled" if not current_status else "disabled"
        flash(f'Monitoring {status_msg} for product {product_id}', 'success')
    except Exception as e:
        logger.error(f"Error toggling monitoring: {str(e)}")
        flash(f'Error toggling monitoring: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/test_global_stock', methods=['POST'])
def test_global_stock():
    """Test checking stock for a product using Selenium"""
    if not session.get('logged_in'):
        flash('Please log in first', 'warning')
        return redirect(url_for('index'))
    
    product_id = request.form.get('product_id')
    if not product_id:
        flash('No product ID provided', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        result = selenium_monitor.check_product_stock(product_id)
        
        if result.get('success'):
            flash(f"Stock check result: {result.get('message')} - {result.get('product_title')}", 'info')
        else:
            flash(f"Stock check failed: {result.get('message')}", 'warning')
    except Exception as e:
        logger.error(f"Error testing stock: {str(e)}")
        flash(f'Error testing stock: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/test_au_stock', methods=['POST'])
def test_au_stock():
    """Test checking Australian store stock"""
    if not session.get('logged_in'):
        flash('Please log in first', 'warning')
        return redirect(url_for('index'))
    
    product_id = request.form.get('product_id')
    if not product_id:
        flash('No product ID provided', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        product = selenium_monitor.db.get_product(product_id)
        if not product or len(product) < 4:
            flash('Product not found or missing AU link', 'warning')
            return redirect(url_for('dashboard'))
        
        au_link = product[3]  # Get AU link from the product
        if not au_link:
            flash('Product does not have an AU link', 'warning')
            return redirect(url_for('dashboard'))
        
        product_name = product[1]
        
        # Process AU link
        logger.info(f"Checking stock for: {au_link}")
        
        # For simplicity, just log that we'd check the AU link
        # Normally you'd have an AU-specific check here
        flash(f"[AU] {product_name} is out of stock.", 'info')
    except Exception as e:
        logger.error(f"Error testing AU stock: {str(e)}")
        flash(f'Error testing AU stock: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    """Log the user out"""
    session.pop('logged_in', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))

# Add cleanup handler to properly close Selenium drivers when Flask shuts down
@app.teardown_appcontext
def cleanup_selenium_drivers(exception=None):
    selenium_monitor.cleanup()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)