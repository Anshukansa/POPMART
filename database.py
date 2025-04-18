import os
from datetime import datetime, timedelta
from database_setup import get_connection, DATABASE_URL

class Database:
    def __init__(self):
        # Get a connection from the setup module
        self.conn = get_connection()
    
    def _execute_query(self, query, params=None, fetch=None):
        """Execute a query with proper error handling"""
        cursor = self.conn.cursor()
        result = None
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch == 'one':
                result = cursor.fetchone()
            elif fetch == 'all':
                result = cursor.fetchall()
            else:
                result = cursor.rowcount > 0
                
            self.conn.commit()
        except Exception as e:
            print(f"Database error executing query: {e}")
            print(f"Query: {query}")
            print(f"Params: {params}")
            self.conn.rollback()
            # Re-establish connection if it was lost
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                try:
                    self.conn = get_connection()
                except Exception as conn_err:
                    print(f"Failed to re-establish connection: {conn_err}")
        finally:
            cursor.close()
        
        return result
    
    # User methods
    def add_user(self, user_id, username):
        """Add a user to the database if they don't exist"""
        if DATABASE_URL.startswith("sqlite"):
            query = "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)"
            params = (user_id, username)
        else:
            query = """
                INSERT INTO users (user_id, username) 
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """
            params = (user_id, username)
        
        return self._execute_query(query, params)
    
    def get_user(self, user_id):
        """Get user information by Telegram ID"""
        if DATABASE_URL.startswith("sqlite"):
            query = "SELECT * FROM users WHERE user_id = ?"
            params = (user_id,)
        else:
            query = "SELECT * FROM users WHERE user_id = %s"
            params = (user_id,)
        
        return self._execute_query(query, params, fetch='one')
    
    def update_balance(self, user_id, amount):
        """Add or subtract from a user's balance"""
        if DATABASE_URL.startswith("sqlite"):
            query = "UPDATE users SET balance = balance + ? WHERE user_id = ?"
            params = (amount, user_id)
        else:
            query = "UPDATE users SET balance = balance + %s WHERE user_id = %s"
            params = (amount, user_id)
        
        return self._execute_query(query, params)
    
    # Product methods
    def add_product(self, product_id, product_name, global_link, au_link, price):
        """Add or update a product"""
        if DATABASE_URL.startswith("sqlite"):
            query = """
                INSERT OR REPLACE INTO products 
                (product_id, product_name, global_link, au_link, price) 
                VALUES (?, ?, ?, ?, ?)
            """
            params = (product_id, product_name, global_link, au_link, price)
        else:
            query = """
                INSERT INTO products 
                (product_id, product_name, global_link, au_link, price) 
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (product_id) DO UPDATE 
                SET product_name = EXCLUDED.product_name,
                    global_link = EXCLUDED.global_link,
                    au_link = EXCLUDED.au_link,
                    price = EXCLUDED.price
            """
            params = (product_id, product_name, global_link, au_link, price)
        
        return self._execute_query(query, params)
    
    def get_product(self, product_id):
        """Get product information by ID"""
        if DATABASE_URL.startswith("sqlite"):
            query = "SELECT * FROM products WHERE product_id = ?"
            params = (product_id,)
        else:
            query = "SELECT * FROM products WHERE product_id = %s"
            params = (product_id,)
        
        return self._execute_query(query, params, fetch='one')
    
    def get_all_products(self):
        """Get all products"""
        query = "SELECT * FROM products"
        return self._execute_query(query, fetch='all')
    
    # Monitoring methods
    def add_monitoring(self, user_id, product_id):
        """Add monitoring subscription for a product"""
        # First check user balance
        if DATABASE_URL.startswith("sqlite"):
            balance_query = "SELECT balance FROM users WHERE user_id = ?"
            balance_params = (user_id,)
            
            price_query = "SELECT price FROM products WHERE product_id = ?"
            price_params = (product_id,)
        else:
            balance_query = "SELECT balance FROM users WHERE user_id = %s"
            balance_params = (user_id,)
            
            price_query = "SELECT price FROM products WHERE product_id = %s"
            price_params = (product_id,)
        
        user = self._execute_query(balance_query, balance_params, fetch='one')
        product = self._execute_query(price_query, price_params, fetch='one')
        
        if not user or not product:
            return False, "User or product not found"
        
        if user[0] < product[0]:
            return False, "Insufficient balance"
        
        # Deduct balance
        self.update_balance(user_id, -product[0])
        
        # Add monitoring with 30-day expiry
        expiry_date = datetime.now() + timedelta(days=30)
        
        if DATABASE_URL.startswith("sqlite"):
            query = """
                INSERT INTO user_monitoring 
                (user_id, product_id, expiry_date) 
                VALUES (?, ?, ?)
            """
            params = (user_id, product_id, expiry_date)
        else:
            query = """
                INSERT INTO user_monitoring 
                (user_id, product_id, expiry_date) 
                VALUES (%s, %s, %s)
            """
            params = (user_id, product_id, expiry_date)
        
        success = self._execute_query(query, params)
        
        if success:
            return True, "Monitoring subscription added successfully"
        else:
            # Refund if monitoring creation failed
            self.update_balance(user_id, product[0])
            return False, "Failed to add monitoring subscription"
    
    def get_user_monitoring(self, user_id):
        """Get all active monitoring subscriptions for a user"""
        if DATABASE_URL.startswith("sqlite"):
            query = """
                SELECT um.id, p.product_name, p.global_link, p.au_link, um.expiry_date 
                FROM user_monitoring um
                JOIN products p ON um.product_id = p.product_id
                WHERE um.user_id = ? AND um.expiry_date > datetime('now')
            """
            params = (user_id,)
        else:
            query = """
                SELECT um.id, p.product_name, p.global_link, p.au_link, um.expiry_date 
                FROM user_monitoring um
                JOIN products p ON um.product_id = p.product_id
                WHERE um.user_id = %s AND um.expiry_date > CURRENT_TIMESTAMP
            """
            params = (user_id,)
        
        return self._execute_query(query, params, fetch='all')
    
    def get_product_subscribers(self, product_id):
        """Get all users monitoring a specific product"""
        if DATABASE_URL.startswith("sqlite"):
            query = """
                SELECT u.user_id, u.username
                FROM user_monitoring um
                JOIN users u ON um.user_id = u.user_id
                WHERE um.product_id = ? AND um.expiry_date > datetime('now')
            """
            params = (product_id,)
        else:
            query = """
                SELECT u.user_id, u.username
                FROM user_monitoring um
                JOIN users u ON um.user_id = u.user_id
                WHERE um.product_id = %s AND um.expiry_date > CURRENT_TIMESTAMP
            """
            params = (product_id,)
        
        return self._execute_query(query, params, fetch='all')
    
    def get_all_active_monitoring(self):
        """Get all products that are being monitored"""
        if DATABASE_URL.startswith("sqlite"):
            query = """
                SELECT p.product_id, p.product_name, p.global_link, p.au_link, 
                       COUNT(DISTINCT um.user_id) as subscriber_count
                FROM products p
                JOIN user_monitoring um ON p.product_id = um.product_id
                WHERE um.expiry_date > datetime('now')
                GROUP BY p.product_id, p.product_name, p.global_link, p.au_link
            """
        else:
            query = """
                SELECT p.product_id, p.product_name, p.global_link, p.au_link, 
                       COUNT(DISTINCT um.user_id) as subscriber_count
                FROM products p
                JOIN user_monitoring um ON p.product_id = um.product_id
                WHERE um.expiry_date > CURRENT_TIMESTAMP
                GROUP BY p.product_id, p.product_name, p.global_link, p.au_link
            """
        
        return self._execute_query(query, fetch='all')
    
    def get_all_users(self):
        """Get all registered users"""
        query = "SELECT * FROM users"
        return self._execute_query(query, fetch='all')
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()