"""
Simple admin panel for managing users, products, and monitoring
"""
import os
import time
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import database as db
import monitor_global
import monitor_au
from functools import wraps
import logging
from io import StringIO
import threading
from config import ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_PORT

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Setup logging
log_stream = StringIO()
file_handler = logging.StreamHandler(log_stream)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Add handlers to all loggers we want to capture
loggers = [
    logging.getLogger('monitor_global'),
    logging.getLogger('monitor_au'),
    logging.getLogger('telegram_bot')
]

for logger in loggers:
    logger.addHandler(file_handler)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@login_required
def index():
    user_count = len(db.get_all_users())
    product_count = len(db.get_all_products())
    monitors = db.get_all_active_monitors()
    monitor_count = len(monitors)
    
    return render_template('admin.html', 
                           user_count=user_count,
                           product_count=product_count,
                           monitor_count=monitor_count,
                           section='dashboard')

# Monitoring logs
@app.route('/logs')
@login_required
def view_logs():
    logs = log_stream.getvalue()
    return render_template('admin.html', logs=logs, section='logs')

# Test stock checking
@app.route('/test_stock/<int:product_id>')
@login_required
def test_stock(product_id):
    product = db.get_product(product_id)
    results = {}
    
    if product['global_link']:
        # Test Global stock
        product_id_global = monitor_global.extract_product_id_from_url(product['global_link'])
        logger.info(f"Testing global stock for product: {product['product_name']} (ID: {product_id})")
        if product_id_global:
            in_stock_global = monitor_global.check_product_stock(product_id_global, "AU")  # Use AU country code
            results['global'] = {
                'status': 'In Stock' if in_stock_global else 'Out of Stock',
                'link': product['global_link']
            }
            logger.info(f"Global stock result: {results['global']['status']}")
        else:
            logger.warning(f"Could not extract global product ID from URL: {product['global_link']}")
    
    if product['au_link']:
        # Test AU stock
        logger.info(f"Testing AU stock for product: {product['product_name']} (ID: {product_id})")
        in_stock_au = monitor_au.check_stock(product['au_link'])
        results['au'] = {
            'status': 'In Stock' if in_stock_au else 'Out of Stock',
            'link': product['au_link']
        }
        logger.info(f"AU stock result: {results['au']['status']}")
    
    flash(f'Stock check complete for {product["product_name"]}', 'success')
    return render_template('admin.html', 
                          product=product, 
                          stock_results=results, 
                          section='test_stock')

@app.route('/api/test_stock/<int:product_id>')
@login_required
def api_test_stock(product_id):
    product = db.get_product(product_id)
    results = {
        'product_name': product['product_name'],
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    if product['global_link']:
        # Test Global stock
        product_id_global = monitor_global.extract_product_id_from_url(product['global_link'])
        if product_id_global:
            in_stock_global = monitor_global.check_product_stock(product_id_global)
            results['global'] = {
                'status': 'In Stock' if in_stock_global else 'Out of Stock',
                'link': product['global_link']
            }
    
    if product['au_link']:
        # Test AU stock
        in_stock_au = monitor_au.check_stock(product['au_link'])
        results['au'] = {
            'status': 'In Stock' if in_stock_au else 'Out of Stock',
            'link': product['au_link']
        }
    
    return jsonify(results)

# Authentication
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('admin.html', section='login')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# Users management
@app.route('/users')
@login_required
def users():
    all_users = db.get_all_users()
    return render_template('admin.html', users=all_users, section='users')

@app.route('/users/add_balance', methods=['POST'])
@login_required
def add_balance():
    user_id = request.form.get('user_id')
    amount = float(request.form.get('amount', 0))
    
    if amount <= 0:
        flash('Amount must be positive', 'danger')
    else:
        db.update_user_balance(user_id, amount)
        flash(f'Added ${amount:.2f} to user {user_id}', 'success')
    
    return redirect(url_for('users'))

@app.route('/users/update_balance', methods=['POST'])
@login_required
def update_balance():
    user_id = request.form.get('user_id')
    new_balance = float(request.form.get('new_balance', 0))
    
    if new_balance < 0:
        flash('Balance cannot be negative', 'danger')
        return redirect(url_for('view_user', user_id=user_id))
    
    # Get current balance
    user = db.get_user(user_id)
    current_balance = user['balance']
    
    # Calculate adjustment needed
    adjustment = new_balance - current_balance
    
    # Update balance
    db.update_user_balance(user_id, adjustment)
    flash(f'Updated balance to ${new_balance:.2f} for user {user_id}', 'success')
    
    return redirect(url_for('view_user', user_id=user_id))

@app.route('/users/view/<int:user_id>')
@login_required
def view_user(user_id):
    user = db.get_user(user_id)
    monitoring = db.get_user_monitoring(user_id)
    return render_template('admin.html', user=user, monitoring=monitoring, section='user_detail')

# Products management
@app.route('/products')
@login_required
def products():
    all_products = db.get_all_products()
    return render_template('admin.html', products=all_products, section='products')

@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        product_name = request.form.get('product_name')
        global_link = request.form.get('global_link')
        au_link = request.form.get('au_link')
        price = float(request.form.get('price', 0))
        
        if not product_name:
            flash('Product name is required', 'danger')
        elif price <= 0:
            flash('Price must be positive', 'danger')
        elif not (global_link or au_link):
            flash('At least one link is required', 'danger')
        else:
            db.add_product(product_name, global_link, au_link, price)
            flash(f'Product {product_name} added successfully', 'success')
            return redirect(url_for('products'))
    
    return render_template('admin.html', section='add_product')

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = db.get_product(product_id)
    
    if request.method == 'POST':
        product_name = request.form.get('product_name')
        global_link = request.form.get('global_link')
        au_link = request.form.get('au_link')
        price = float(request.form.get('price', 0))
        
        if not product_name:
            flash('Product name is required', 'danger')
        elif price <= 0:
            flash('Price must be positive', 'danger')
        elif not (global_link or au_link):
            flash('At least one link is required', 'danger')
        else:
            db.update_product(product_id, product_name, global_link, au_link, price)
            flash(f'Product {product_name} updated successfully', 'success')
            return redirect(url_for('products'))
    
    return render_template('admin.html', product=product, section='edit_product')

@app.route('/monitoring')
@login_required
def monitoring():
    all_monitors = db.get_all_active_monitors()
    return render_template('admin.html', monitors=all_monitors, section='monitoring')

@app.route('/monitoring/cancel/<int:monitor_id>')
@login_required
def cancel_monitoring(monitor_id):
    db.cancel_monitoring(monitor_id)
    flash('Monitoring cancelled successfully', 'success')
    return redirect(url_for('monitoring'))

def run_admin_panel():
    """Start the admin panel Flask server"""
    app.run(host='0.0.0.0', port=ADMIN_PORT, debug=False)

if __name__ == '__main__':
    run_admin_panel()