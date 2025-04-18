from database_setup import setup_database

# Initialize the database before running the application
if __name__ == "__main__":
    print("Initializing database...")
    if setup_database():
        print("Database initialization successful.")
    else:
        print("Database initialization failed!")