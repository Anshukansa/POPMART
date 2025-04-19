"""
Database models and connection handling
"""
import sqlite3
import datetime
from contextlib import contextmanager
from config import DATABASE_PATH

# Initialize the database
def init_db():
    """Create the database tables if they don't exist"""
    with get_db_connection() as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            global_link TEXT,
            au_link TEXT,
            price REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.execute('''
        CREATE TABLE IF NOT EXISTS monitoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            active BOOLEAN DEFAULT 1,
            expiry_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        )
        ''')
        
        print("Database initialized successfully")

@contextmanager
def get_db_connection():
    """Get a database connection with context management"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# User operations
def add_user(user_id, username):
    """Add a new user to the database"""
    with get_db_connection() as conn:
        # Check if user already exists
        cursor = conn.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if cursor.fetchone() is None:
            conn.execute(
                'INSERT INTO users (user_id, username) VALUES (?, ?)',
                (user_id, username)
            )
            conn.commit()
            return True
        return False

def get_user(user_id):
    """Get user information by user_id"""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()

def update_user_balance(user_id, amount):
    """Update a user's balance"""
    with get_db_connection() as conn:
        conn.execute(
            'UPDATE users SET balance = balance + ? WHERE user_id = ?',
            (amount, user_id)
        )
        conn.commit()
        return True

def get_all_users():
    """Get all users"""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM users ORDER BY created_at DESC')
        return cursor.fetchall()

# Product operations
def add_product(product_name, global_link, au_link, price):
    """Add a new product to the database"""
    with get_db_connection() as conn:
        conn.execute(
            'INSERT INTO products (product_name, global_link, au_link, price) VALUES (?, ?, ?, ?)',
            (product_name, global_link, au_link, price)
        )
        conn.commit()
        return conn.lastrowid

def get_product(product_id):
    """Get product information by product_id"""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM products WHERE product_id = ?', (product_id,))
        return cursor.fetchone()

def get_all_products():
    """Get all products"""
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM products ORDER BY product_name')
        return cursor.fetchall()

def update_product(product_id, product_name=None, global_link=None, au_link=None, price=None):
    """Update product information"""
    with get_db_connection() as conn:
        # Get current values
        cursor = conn.execute('SELECT * FROM products WHERE product_id = ?', (product_id,))
        product = cursor.fetchone()
        
        if not product:
            return False
        
        # Update with new values or keep existing ones
        name = product_name if product_name is not None else product['product_name']
        global_url = global_link if global_link is not None else product['global_link']
        au_url = au_link if au_link is not None else product['au_link']
        new_price = price if price is not None else product['price']
        
        conn.execute(
            'UPDATE products SET product_name = ?, global_link = ?, au_link = ?, price = ? WHERE product_id = ?',
            (name, global_url, au_url, new_price, product_id)
        )
        conn.commit()
        return True

# Monitoring operations
def add_monitoring(user_id, product_id, days=30):
    """Add a new monitoring subscription"""
    with get_db_connection() as conn:
        # Calculate expiry date (30 days from now by default)
        expiry_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if user has enough balance
        cursor = conn.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        cursor = conn.execute('SELECT price FROM products WHERE product_id = ?', (product_id,))
        product = cursor.fetchone()
        
        if not user or not product or user['balance'] < product['price']:
            return False, "Insufficient balance"
        
        # Deduct balance
        conn.execute(
            'UPDATE users SET balance = balance - ? WHERE user_id = ?',
            (product['price'], user_id)
        )
        
        # Add monitoring
        conn.execute(
            'INSERT INTO monitoring (user_id, product_id, expiry_date) VALUES (?, ?, ?)',
            (user_id, product_id, expiry_date)
        )
        conn.commit()
        return True, "Monitoring added successfully"

def get_user_monitoring(user_id):
    """Get all active monitoring subscriptions for a user"""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT m.id, m.product_id, p.product_name, m.expiry_date 
            FROM monitoring m 
            JOIN products p ON m.product_id = p.product_id 
            WHERE m.user_id = ? AND m.active = 1 AND m.expiry_date > datetime('now')
            ORDER BY m.expiry_date
        ''', (user_id,))
        return cursor.fetchall()

def get_product_monitors(product_id):
    """Get all users monitoring a specific product"""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT m.id, m.user_id, u.username, m.expiry_date 
            FROM monitoring m 
            JOIN users u ON m.user_id = u.user_id 
            WHERE m.product_id = ? AND m.active = 1 AND m.expiry_date > datetime('now')
            ORDER BY m.expiry_date
        ''', (product_id,))
        return cursor.fetchall()

def get_all_active_monitors():
    """Get all active monitoring subscriptions with user and product details"""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT m.id, m.user_id, u.username, m.product_id, p.product_name, p.global_link, p.au_link, m.expiry_date 
            FROM monitoring m 
            JOIN users u ON m.user_id = u.user_id 
            JOIN products p ON m.product_id = p.product_id 
            WHERE m.active = 1 AND m.expiry_date > datetime('now')
            ORDER BY m.expiry_date
        ''')
        return cursor.fetchall()

def cancel_monitoring(monitor_id):
    """Cancel a monitoring subscription"""
    with get_db_connection() as conn:
        conn.execute('UPDATE monitoring SET active = 0 WHERE id = ?', (monitor_id,))
        conn.commit()
        return True