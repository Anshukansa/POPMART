import os
import psycopg2
import sqlite3
import time

# Get database URL from environment (Heroku provides DATABASE_URL)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///popmart.db")

# Fix for Heroku PostgreSQL URL format change
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_connection():
    """Get a database connection based on the environment"""
    if DATABASE_URL.startswith("sqlite"):
        conn = sqlite3.connect(DATABASE_URL.replace("sqlite:///", ""), check_same_thread=False)
    else:
        # For PostgreSQL, retry connection a few times
        retries = 5
        while retries > 0:
            try:
                conn = psycopg2.connect(DATABASE_URL)
                break
            except Exception as e:
                print(f"Error connecting to database: {e}")
                retries -= 1
                if retries == 0:
                    raise
                time.sleep(1)
    
    return conn

def setup_database():
    """Set up the database schema"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check database type
    is_postgres = not DATABASE_URL.startswith("sqlite")
    
    try:
        # For PostgreSQL, first check if tables exist
        if is_postgres:
            # Check if users table exists
            cursor.execute("SELECT to_regclass('public.users')")
            users_exists = cursor.fetchone()[0] is not None
            
            # Check if products table exists
            cursor.execute("SELECT to_regclass('public.products')")
            products_exists = cursor.fetchone()[0] is not None
            
            # Check if user_monitoring table exists
            cursor.execute("SELECT to_regclass('public.user_monitoring')")
            monitoring_exists = cursor.fetchone()[0] is not None
            
            # Only create tables if they don't exist
            if not users_exists:
                print("Creating users table...")
                cursor.execute('''
                CREATE TABLE users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    balance REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
            
            if not products_exists:
                print("Creating products table...")
                cursor.execute('''
                CREATE TABLE products (
                    product_id TEXT PRIMARY KEY,
                    product_name TEXT,
                    global_link TEXT,
                    au_link TEXT,
                    price REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
            
            if not monitoring_exists:
                print("Creating user_monitoring table...")
                cursor.execute('''
                CREATE TABLE user_monitoring (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    product_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expiry_date TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (product_id) REFERENCES products (product_id)
                )
                ''')
        else:
            # SQLite schema
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
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
        
        conn.commit()
        print("Database setup complete.")
        return True
    
    except Exception as e:
        print(f"Error setting up database: {e}")
        conn.rollback()
        return False
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Run database setup directly
    setup_database()