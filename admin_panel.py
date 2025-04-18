from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import Database
from monitors.global_monitor import GlobalMonitor
from monitors.au_monitor import AUMonitor
import os

class AdminPanel:
    def __init__(self, admin_username, admin_password, notification_bot_token=None):
        self.app = Flask(__name__)
        self.app.secret_key = os.environ.get("SECRET_KEY", "popmart_admin_secret")
        self.db = Database()
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.notification_bot_token = notification_bot_token
        
        # Initialize monitors if token is provided
        if notification_bot_token:
            self.global_monitor = GlobalMonitor(notification_bot_token)
            self.au_monitor = AUMonitor(notification_bot_token)
        else:
            self.global_monitor = None
            self.au_monitor = None
        
        self.setup_routes()
    
    def setup_routes(self):
        @self.app.route('/', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                
                if username == self.admin_username and password == self.admin_password:
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid credentials')
            
            return render_template('admin.html', page='login')
        
        @self.app.route('/dashboard')
        def dashboard():
            users = self.get_all_users()
            products = self.db.get_all_products()
            monitoring = self.db.get_all_active_monitoring()
            
            return render_template(
                'admin.html', 
                page='dashboard',
                users=users,
                products=products,
                monitoring=monitoring
            )
        
        @self.app.route('/add_balance', methods=['POST'])
        def add_balance():
            user_id = request.form.get('user_id')
            amount = float(request.form.get('amount', 0))
            
            if user_id and amount > 0:
                self.db.update_balance(int(user_id), amount)
                flash(f'Added ${amount:.2f} to user {user_id}')
            
            return redirect(url_for('dashboard'))
        
        @self.app.route('/set_balance', methods=['POST'])
        def set_balance():
            user_id = request.form.get('user_id')
            amount = float(request.form.get('balance', 0))
            
            if user_id and amount >= 0:
                self.db.set_balance(int(user_id), amount)
                flash(f'Set balance to ${amount:.2f} for user {user_id}')
            
            return redirect(url_for('dashboard'))
        
        @self.app.route('/add_product', methods=['POST'])
        def add_product():
            product_id = request.form.get('product_id')
            product_name = request.form.get('product_name')
            global_link = request.form.get('global_link')
            au_link = request.form.get('au_link')
            price = float(request.form.get('price', 0))
            
            if product_id and product_name and (global_link or au_link) and price > 0:
                self.db.add_product(product_id, product_name, global_link, au_link, price)
                flash(f'Added product {product_name}')
            
            return redirect(url_for('dashboard'))
        
        @self.app.route('/test_global_stock', methods=['POST'])
        def test_global_stock():
            if not self.global_monitor:
                flash('Notification bot token not set. Cannot test stock.')
                return redirect(url_for('dashboard'))
                
            product_id = request.form.get('product_id')
            
            if not product_id:
                flash('Product ID is required')
                return redirect(url_for('dashboard'))
                
            result = self.global_monitor.check_product(product_id)
            
            if result['success']:
                flash(f"Global Stock Check: {result['message']}")
            else:
                flash(f"Error checking global stock: {result['message']}")
                
            return redirect(url_for('dashboard'))
            
        @self.app.route('/test_au_stock', methods=['POST'])
        def test_au_stock():
            if not self.au_monitor:
                flash('Notification bot token not set. Cannot test stock.')
                return redirect(url_for('dashboard'))
                
            product_id = request.form.get('product_id')
            
            if not product_id:
                flash('Product ID is required')
                return redirect(url_for('dashboard'))
                
            # Get the product to find the AU link
            product = self.db.get_product(product_id)
            if not product or not product[3]:  # product[3] is the AU link
                flash('Product not found or no AU link available')
                return redirect(url_for('dashboard'))
                
            result = self.au_monitor.check_product(product[3])
            
            if result['success']:
                flash(f"AU Stock Check: {result['message']}")
            else:
                flash(f"Error checking AU stock: {result['message']}")
                
            return redirect(url_for('dashboard'))
        
        # Health check endpoint for Heroku
        @self.app.route('/health')
        def health():
            return jsonify({"status": "ok"}), 200
    
    def get_all_users(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()
    
    def run(self, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))):
        self.app.run(host=host, port=port)