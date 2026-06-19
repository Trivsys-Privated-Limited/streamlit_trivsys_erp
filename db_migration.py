import mysql.connector
from mysql.connector import Error
import hashlib

from database import DB_HOST, DB_NAME, DB_PASSWORD, DB_USERNAME

# Database connection details - match what's in database.py
# DB_HOST = "localhost"
# DB_USERNAME = "my_user"
# DB_PASSWORD = "ashiq"
# DB_NAME = "my_database"

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USERNAME,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"Error: {e}")
        return None

# Get all available modules in the system
def get_available_modules():
    # List of all modules in the system
    return [
        "POS System",
        "Inventory Management",
        "Attendance Management",
        "Shopify",
        "WhatsApp",
        "Dashboard",
        "Purchase",
        "Payroll",
        "Sales",
        "Credit Sales",
        "Order Management"
    ]

def create_users_table():
    """Create the users table if it doesn't exist"""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    full_name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    role VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL
                )
            """)
            conn.commit()
            print("Users table created or already exists")
            
            # Check if admin user exists
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Create default admin user with password "admin123"
                admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
                cursor.execute("""
                    INSERT INTO users (username, password_hash, full_name, email, role)
                    VALUES (%s, %s, %s, %s, %s)
                """, ('admin', admin_hash, 'Administrator', 'admin@example.com', 'admin'))
                
                # Get the admin user ID
                admin_id = cursor.lastrowid
                
                # Create default employee user with password "employee123"
                employee_hash = hashlib.sha256("employee123".encode()).hexdigest()
                cursor.execute("""
                    INSERT INTO users (username, password_hash, full_name, email, role)
                    VALUES (%s, %s, %s, %s, %s)
                """, ('employee', employee_hash, 'Sample Employee', 'employee@example.com', 'employee'))
                
                # Get the employee user ID
                employee_id = cursor.lastrowid
                
                conn.commit()
                print("Default admin and employee users created")
                
                # Now create permissions table and add permissions
                create_user_permissions_table(conn, admin_id, employee_id)
                
            return True
        except Error as e:
            print(f"Error creating users table: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def create_user_permissions_table(conn=None, admin_id=None, employee_id=None):
    """Create the user_permissions table if it doesn't exist"""
    # If no connection is provided, create one
    connection_provided = conn is not None
    if not connection_provided:
        conn = get_db_connection()
    
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_permissions (
                    permission_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    module_name VARCHAR(50) NOT NULL,
                    has_access BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    UNIQUE KEY unique_user_module (user_id, module_name)
                )
            """)
            conn.commit()
            print("User permissions table created or already exists")
            
            # Add permissions for admin and employee if IDs are provided
            if admin_id and employee_id:
                # Get all modules
                modules = get_available_modules()
                
                # Add admin permissions (all modules)
                for module in modules:
                    cursor.execute("""
                        INSERT INTO user_permissions (user_id, module_name, has_access)
                        VALUES (%s, %s, %s)
                    """, (admin_id, module, True))
                
                # Add employee permissions (limited modules)
                for module in modules:
                    # Employee gets access to basic modules but not admin functions
                    has_access = module not in ["Dashboard", "Purchase", "Sales", "Credit Sales"]
                    cursor.execute("""
                        INSERT INTO user_permissions (user_id, module_name, has_access)
                        VALUES (%s, %s, %s)
                    """, (employee_id, module, has_access))
                
                conn.commit()
                print("Default permissions added for admin and employee users")
            
            return True
        except Error as e:
            print(f"Error creating user_permissions table: {e}")
            return False
        finally:
            cursor.close()
            if not connection_provided:
                conn.close()
    return False

def create_activity_logs_table():
    """Create the activity_logs table if it doesn't exist"""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    log_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    activity_description TEXT NOT NULL,
                    ip_address VARCHAR(45),
                    activity_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
                )
            """)
            conn.commit()
            print("Activity logs table created or already exists")
            return True
        except Error as e:
            print(f"Error creating activity_logs table: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def run_migrations():
    """Run all database migrations"""
    print("Running database migrations...")
    
    # Create users table and default users
    if create_users_table():
        print("Users table migration successful")
    else:
        print("Users table migration failed")
    
    # Create permissions table separately if needed
    # Note: This is already called within create_users_table if users are created
    # But we'll check if it needs to be created separately
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Check if permissions table exists
            cursor.execute("SHOW TABLES LIKE 'user_permissions'")
            exists = cursor.fetchone()
            if not exists:
                create_user_permissions_table()
                print("User permissions table migration successful")
        except Error as e:
            print(f"Error checking permissions table: {e}")
        finally:
            cursor.close()
            conn.close()
        
    # Create activity logs table
    if create_activity_logs_table():
        print("Activity logs table migration successful")
    else:
        print("Activity logs table migration failed")
        
    print("Database migrations completed")

if __name__ == "__main__":
    run_migrations()