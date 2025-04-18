from flask import Flask, render_template, request, redirect, url_for, flash
from database import Database
import os

class AdminPanel:
    def __init__(self, admin_username, admin_password):
        self.app = Flask(__name__)
        self.app.secret_key = os.environ.get("SECRET_KEY", "popmart_admin_secret")
        self.db = Database()
        self.admin_username = admin_username
        self.admin_password = admin_password
        
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
                self.db.update_balance(user_id, amount)
                flash(f'Added ${amount:.2f} to user {user_id}')
            
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
    
    def get_all_users(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()
    
    def run(self, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))):
        self.app.run(host=host, port=port)