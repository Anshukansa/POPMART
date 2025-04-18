import os
import psycopg2
import sqlite3
from datetime import datetime, timedelta

# Parse DB URL for Heroku PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///popmart.db")

# Fix for Heroku PostgreSQL URL format change
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

class Database:
    def __init__(self):
        self.conn = self._get_connection()
        self._create_tables()
    
    def _get_connection(self):
        """Create a database connection based on the URL"""
        if DATABASE_URL.startswith("sqlite"):
            # SQLite connection
            db_path = DATABASE_URL.replace("sqlite:///", "")
            return sqlite3.connect(db_path, check_same_thread=False)
        else:
            # PostgreSQL connection
            return psycopg2.connect(DATABASE_URL)
    
    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        cursor = self.conn.cursor()
        
        if DATABASE_URL.startswith("sqlite"):
            # SQLite schema
            # Users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Products table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT,
                global_link TEXT,
                au_link TEXT,
                price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # User Monitoring table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_monitoring (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expiry_date TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
            ''')
        else:
            # PostgreSQL schema
            # Use PostgreSQL's IF NOT EXISTS functionality
            cursor.execute('''
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'users') THEN
                    CREATE TABLE users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        balance REAL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                END IF;

                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'products') THEN
                    CREATE TABLE products (
                        product_id TEXT PRIMARY KEY,
                        product_name TEXT,
                        global_link TEXT,
                        au_link TEXT,
                        price REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                END IF;

                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_monitoring') THEN
                    CREATE TABLE user_monitoring (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER,
                        product_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expiry_date TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        FOREIGN KEY (product_id) REFERENCES products (product_id)
                    );
                END IF;
            END
            $$;
            ''')
        
        self.conn.commit()
    
    # User methods
    def add_user(self, user_id, username):
        cursor = self.conn.cursor()
        
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
        else:
            cursor.execute("""
                INSERT INTO users (user_id, username) 
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, username))
            
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            
        return cursor.fetchone()
    
    def update_balance(self, user_id, amount):
        cursor = self.conn.cursor()
        
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET balance = balance + %s WHERE user_id = %s",
                (amount, user_id)
            )
            
        self.conn.commit()
        return cursor.rowcount > 0
    
    # Product methods
    def add_product(self, product_id, product_name, global_link, au_link, price):
        cursor = self.conn.cursor()
        
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute(
                "INSERT OR REPLACE INTO products (product_id, product_name, global_link, au_link, price) VALUES (?, ?, ?, ?, ?)",
                (product_id, product_name, global_link, au_link, price)
            )
        else:
            cursor.execute("""
                INSERT INTO products (product_id, product_name, global_link, au_link, price) 
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (product_id) DO UPDATE 
                SET product_name = EXCLUDED.product_name,
                    global_link = EXCLUDED.global_link,
                    au_link = EXCLUDED.au_link,
                    price = EXCLUDED.price
            """, (product_id, product_name, global_link, au_link, price))
            
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_product(self, product_id):
        cursor = self.conn.cursor()
        
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
        else:
            cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            
        return cursor.fetchone()
    
    def get_all_products(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM products")
        return cursor.fetchall()
    
    # Monitoring methods
    def add_monitoring(self, user_id, product_id):
        cursor = self.conn.cursor()
        
        # Check balance
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            
            cursor.execute("SELECT price FROM products WHERE product_id = ?", (product_id,))
            product = cursor.fetchone()
        else:
            cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            
            cursor.execute("SELECT price FROM products WHERE product_id = %s", (product_id,))
            product = cursor.fetchone()
        
        if not user or not product:
            return False, "User or product not found"
        
        if user[0] < product[0]:
            return False, "Insufficient balance"
        
        # Deduct balance
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (product[0], user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET balance = balance - %s WHERE user_id = %s",
                (product[0], user_id)
            )
        
        # Add monitoring
        expiry_date = datetime.now() + timedelta(days=30)
        
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute(
                "INSERT INTO user_monitoring (user_id, product_id, expiry_date) VALUES (?, ?, ?)",
                (user_id, product_id, expiry_date)
            )
        else:
            cursor.execute(
                "INSERT INTO user_monitoring (user_id, product_id, expiry_date) VALUES (%s, %s, %s)",
                (user_id, product_id, expiry_date)
            )
        
        self.conn.commit()
        return True, "Monitoring subscription added successfully"
    
    def get_user_monitoring(self, user_id):
        cursor = self.conn.cursor()
        
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute("""
                SELECT um.id, p.product_name, p.global_link, p.au_link, um.expiry_date 
                FROM user_monitoring um
                JOIN products p ON um.product_id = p.product_id
                WHERE um.user_id = ? AND um.expiry_date > CURRENT_TIMESTAMP
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT um.id, p.product_name, p.global_link, p.au_link, um.expiry_date 
                FROM user_monitoring um
                JOIN products p ON um.product_id = p.product_id
                WHERE um.user_id = %s AND um.expiry_date > CURRENT_TIMESTAMP
            """, (user_id,))
            
        return cursor.fetchall()
    
    def get_product_subscribers(self, product_id):
        cursor = self.conn.cursor()
        
        if DATABASE_URL.startswith("sqlite"):
            cursor.execute("""
                SELECT u.user_id, u.username
                FROM user_monitoring um
                JOIN users u ON um.user_id = u.user_id
                WHERE um.product_id = ? AND um.expiry_date > CURRENT_TIMESTAMP
            """, (product_id,))
        else:
            cursor.execute("""
                SELECT u.user_id, u.username
                FROM user_monitoring um
                JOIN users u ON um.user_id = u.user_id
                WHERE um.product_id = %s AND um.expiry_date > CURRENT_TIMESTAMP
            """, (product_id,))
            
        return cursor.fetchall()
    
    def get_all_active_monitoring(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.product_id, p.product_name, p.global_link, p.au_link, COUNT(DISTINCT um.user_id) as subscriber_count
            FROM products p
            JOIN user_monitoring um ON p.product_id = um.product_id
            WHERE um.expiry_date > CURRENT_TIMESTAMP
            GROUP BY p.product_id, p.product_name, p.global_link, p.au_link
        """)
        return cursor.fetchall()