# import traceback
# import mysql.connector
# import streamlit as st
# import hashlib
# import smtplib
# import random
# import string
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from datetime import datetime, timedelta
# from database import *
# from mysql.connector import Error
# import os
# import json

# # Email Configuration - REPLACE WITH YOUR ACTUAL EMAIL SERVICE DETAILS
# EMAIL_HOST = "smtp.gmail.com"  # Replace with your SMTP server
# EMAIL_PORT = 587  # Standard port for TLS
# EMAIL_USER = "muhammadashiqalam@gmail.com"  # Replace with your email
# EMAIL_PASSWORD = "ynng odsx ztsq veme"  # Replace with your app password (if using Gmail)

# # Trial Period Configuration
# TRIAL_PERIOD_DAYS = 3

# # Directory for OTP storage 
# OTP_DIR = "otp_storage"
# os.makedirs(OTP_DIR, exist_ok=True)

# def create_trial_tables():
#     """Create necessary tables for trial management"""
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor()
#         try:
#             # Create trials table to track trial users
#             cursor.execute("""
#                 CREATE TABLE IF NOT EXISTS trials (
#                     trial_id INT AUTO_INCREMENT PRIMARY KEY,
#                     user_id INT NOT NULL,
#                     start_date DATETIME NOT NULL,
#                     end_date DATETIME NOT NULL,
#                     is_active BOOLEAN DEFAULT TRUE,
#                     FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
#                 )
#             """)
            
#             # Create email_verification table
#             cursor.execute("""
#                 CREATE TABLE IF NOT EXISTS email_verification (
#                     email VARCHAR(100) PRIMARY KEY,
#                     otp VARCHAR(6) NOT NULL,
#                     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                     expires_at TIMESTAMP NOT NULL
#                 )
#             """)
            
#             # Create user_databases table to track user databases
#             cursor.execute("""
#                 CREATE TABLE IF NOT EXISTS user_databases (
#                     user_id INT PRIMARY KEY,
#                     db_name VARCHAR(255) NOT NULL,
#                     expiration_date DATETIME NOT NULL
#                 )
#             """)
            
#             conn.commit()
#             return True
#         except Error as e:
#             print(f"Error creating trial tables: {e}")
#             return False
#         finally:
#             cursor.close()
#             conn.close()
#     return False


# def is_email_registered(email):
#     """Check if an email is already registered"""
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor()
#         try:
#             cursor.execute("SELECT COUNT(*) FROM users WHERE email = %s", (email,))
#             count = cursor.fetchone()[0]
#             return count > 0
#         except Error as e:
#             print(f"Error checking email: {e}")
#             return False
#         finally:
#             cursor.close()
#             conn.close()
#     return False

# def is_username_registered(username):
#     """Check if a username is already registered"""
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor()
#         try:
#             cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s", (username,))
#             count = cursor.fetchone()[0]
#             return count > 0
#         except Error as e:
#             print(f"Error checking username: {e}")
#             return False
#         finally:
#             cursor.close()
#             conn.close()
#     return False



# def generate_otp():
#     """Generate a 6-digit OTP"""
#     return ''.join(random.choices(string.digits, k=6))

# def save_otp(email, otp):
#     """Save OTP to database with 10-minute expiration"""
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor()
#         try:
#             # Calculate expiration time (10 minutes from now)
#             expires_at = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
            
#             # Delete any existing OTP for this email
#             cursor.execute("DELETE FROM email_verification WHERE email = %s", (email,))
            
#             # Insert new OTP
#             cursor.execute("""
#                 INSERT INTO email_verification (email, otp, expires_at)
#                 VALUES (%s, %s, %s)
#             """, (email, otp, expires_at))
            
#             conn.commit()
#             return True
#         except Error as e:
#             print(f"Error saving OTP: {e}")
#             return False
#         finally:
#             cursor.close()
#             conn.close()
#     return False

# def verify_otp(email, otp):
#     """Verify if OTP is valid and not expired"""
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor(dictionary=True)
#         try:
#             # Check if OTP exists and is not expired
#             cursor.execute("""
#                 SELECT * FROM email_verification 
#                 WHERE email = %s AND otp = %s AND expires_at > NOW()
#             """, (email, otp))
            
#             result = cursor.fetchone()
            
#             # If valid OTP found, delete it from database (one-time use)
#             if result:
#                 cursor.execute("DELETE FROM email_verification WHERE email = %s", (email,))
#                 conn.commit()
#                 return True
#             return False
#         except Error as e:
#             print(f"Error verifying OTP: {e}")
#             return False
#         finally:
#             cursor.close()
#             conn.close()
#     return False

# def send_otp_email(email, otp):
#     """Send OTP via email"""
#     try:
#         # Create message
#         msg = MIMEMultipart()
#         msg['From'] = EMAIL_USER
#         msg['To'] = email
#         msg['Subject'] = "Your ALIF ERP Trial Verification Code"
        
#         # Email body
#         body = f"""
#         <html>
#         <body style="font-family: Arial, sans-serif; line-height: 1.6;">
#             <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
#                 <h2 style="color: #4a6fa5; text-align: center;">ALIF ERP Trial Access</h2>
#                 <p>Thank you for your interest in trying ALIF ERP!</p>
#                 <p>Your verification code is:</p>
#                 <div style="text-align: center; margin: 20px 0;">
#                     <span style="font-size: 24px; background-color: #f0f0f0; padding: 10px 20px; border-radius: 4px; letter-spacing: 5px; font-weight: bold;">{otp}</span>
#                 </div>
#                 <p>This code will expire in 10 minutes.</p>
#                 <p>If you didn't request this code, please ignore this email.</p>
#                 <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">
#                 <p style="font-size: 12px; color: #777; text-align: center;">© 2025 ALIF ERP. All rights reserved.</p>
#             </div>
#         </body>
#         </html>
#         """
        
#         # Attach HTML content
#         msg.attach(MIMEText(body, 'html'))
        
#         # Connect to server and send email
#         server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
#         server.starttls()  # Secure the connection
#         server.login(EMAIL_USER, EMAIL_PASSWORD)
#         server.send_message(msg)
#         server.quit()
        
#         return True
#     except Exception as e:
#         print(f"Error sending email: {e}")
#         return False

# import mysql.connector
# from mysql.connector import Error

# def initialize_user_database(user_db_name):
#     """Initialize the schema for a new user database"""
#     try:
#         # Connect to the MySQL server
#         conn = mysql.connector.connect(
#             host=DB_HOST,
#             user=DB_USERNAME,
#             password=DB_PASSWORD
#         )
#         cursor = conn.cursor()
        
#         # Create the new database
#         cursor.execute(f"CREATE DATABASE IF NOT EXISTS {user_db_name}")
        
#         # Use the new database
#         cursor.execute(f"USE {user_db_name}")
        
#         # Read the schema from the SQL file
#         with open("my_database_schema.sql", "r") as sql_file:
#             sql_script = sql_file.read()
        
#         # Split the SQL script into individual statements
#         sql_statements = sql_script.split(';')
        
#         # Execute each statement
#         for statement in sql_statements:
#             statement = statement.strip()
#             if statement:
#                 cursor.execute(statement)
        
#         conn.commit()
#         cursor.close()
#         conn.close()
#         return True
#     except Error as e:
#         st.error(f"❌ Error initializing database schema: {e}")
#         traceback.print_exc()  # This shows the full traceback in the console
#         return False
    

# def register_trial_user(username, password, full_name, email):
#     """Register a new trial user"""
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor()
#         try:
#             # Hash the password
#             password_hash = hashlib.sha256(password.encode()).hexdigest()
            
#             # Insert new user with admin role
#             cursor.execute("""
#                 INSERT INTO users (username, password_hash, full_name, email, role)
#                 VALUES (%s, %s, %s, %s, %s)
#             """, (username, password_hash, full_name, email, 'admin'))
            
#             user_id = cursor.lastrowid
            
#             # Create a new database for the user
#             user_db_name = f"user_{user_id}_db"
#             if not initialize_user_database(user_db_name):
#                 raise Exception("Failed to initialize user database")
            
#             # Set up trial period
#             start_date = datetime.now()
#             end_date = start_date + timedelta(days=TRIAL_PERIOD_DAYS)
            
#             cursor.execute("""
#                 INSERT INTO trials (user_id, start_date, end_date)
#                 VALUES (%s, %s, %s)
#             """, (user_id, start_date, end_date))
            
#             # Store the user's database name and expiration date
#             cursor.execute("""
#                 INSERT INTO user_databases (user_id, db_name, expiration_date)
#                 VALUES (%s, %s, %s)
#             """, (user_id, user_db_name, end_date))
            
#             conn.commit()
            
#             # Store the user's database name in the session state
#             st.session_state.user_db_name = user_db_name
            
#             return True, user_id
#         except Error as e:
#             print(f"Error registering trial user: {e}")
#             return False, None
#         finally:
#             cursor.close()
#             conn.close()
#     return False, None

# def check_trial_status(user_id):
#     """Check if user's trial is still active"""
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor(dictionary=True)
#         try:
#             cursor.execute("""
#                 SELECT * FROM trials
#                 WHERE user_id = %s AND is_active = TRUE AND end_date > NOW()
#             """, (user_id,))
            
#             trial = cursor.fetchone()
            
#             if trial:
#                 # Calculate days left
#                 now = datetime.now()
#                 end_date = trial['end_date']
#                 days_left = (end_date - now).days + 1  # +1 to include today
                
#                 return True, {
#                     'active': True,
#                     'days_left': days_left,
#                     'end_date': end_date.strftime('%Y-%m-%d')
#                 }
#             else:
#                 # Check if trial expired
#                 cursor.execute("""
#                     SELECT * FROM trials
#                     WHERE user_id = %s
#                 """, (user_id,))
                
#                 expired_trial = cursor.fetchone()
#                 if expired_trial:
#                     return False, {
#                         'active': False,
#                         'message': "Your trial period has expired"
#                     }
                
#                 return False, {
#                     'active': False,
#                     'message': "No trial found for this user"
#                 }
#         except Error as e:
#             print(f"Error checking trial status: {e}")
#             return False, {'active': False, 'message': f"Database error: {str(e)}"}
#         finally:
#             cursor.close()
#             conn.close()
#     return False, {'active': False, 'message': "Database connection error"}

# def deactivate_expired_trials():
#     """Deactivate all expired trials"""
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor()
#         try:
#             cursor.execute("""
#                 UPDATE trials
#                 SET is_active = FALSE
#                 WHERE end_date < NOW() AND is_active = TRUE
#             """)
            
#             conn.commit()
#             return cursor.rowcount  # Number of deactivated trials
#         except Error as e:
#             print(f"Error deactivating expired trials: {e}")
#             return 0
#         finally:
#             cursor.close()
#             conn.close()
#     return 0

# def cleanup_expired_databases():
#     """Clean up expired user databases"""
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor()
#         try:
#             cursor.execute("""
#                 SELECT user_id, db_name FROM user_databases
#                 WHERE expiration_date < NOW()
#             """)
#             expired_dbs = cursor.fetchall()
            
#             for user_id, db_name in expired_dbs:
#                 cursor.execute(f"DROP DATABASE {db_name}")
#                 cursor.execute("DELETE FROM user_databases WHERE user_id = %s", (user_id,))
            
#             conn.commit()
#         except Error as e:
#             print(f"Error cleaning up expired databases: {e}")
#         finally:
#             cursor.close()
#             conn.close()

# def show_signup_page():
#     """Display the signup form for trial users"""
#     st.title("Start Your 3-Day Free Trial")
    
#     # Custom CSS for signup page
#     st.markdown("""
#         <style>
#         /* Signup container styling */
#         .signup-container {
#             max-width: 500px;
#             margin: 40px auto;
#             padding: 30px;
#             border-radius: 16px;
#             box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
#             background: white;
#         }
        
#         /* Header styling */
#         .signup-header h2 {
#             color: #2c3e50;
#             margin-bottom: 5px;
#             font-size: 24px;
#             font-weight: 700;
#         }
        
#         .signup-header p {
#             color: #7f8c8d;
#             font-size: 14px;
#             margin-bottom: 20px;
#         }
        
#         /* Form styling */
#         .stForm > div > div > div > div > div:nth-child(1) {
#             font-weight: 600;
#             font-size: 14px;
#             color: #2c3e50;
#         }
        
#         /* Button styling */
#         .stButton > button {
#             width: 100%;
#             background: linear-gradient(to right, #667eea, #764ba2);
#             color: white;
#             padding: 10px 15px;
#             font-size: 16px;
#             font-weight: 600;
#             border: none;
#             border-radius: 8px;
#             cursor: pointer;
#             margin-top: 10px;
#         }
        
#         /* Trial info styling */
#         .trial-info {
#             background-color: #f8f9fa;
#             border-left: 4px solid #4a6fa5;
#             padding: 15px;
#             margin: 20px 0;
#             border-radius: 4px;
#         }
        
#         .trial-info h3 {
#             color: #4a6fa5;
#             margin: 0 0 10px 0;
#             font-size: 18px;
#         }
        
#         .trial-info ul {
#             margin: 0;
#             padding-left: 20px;
#         }
        
#         .trial-info li {
#             margin-bottom: 5px;
#         }
#         </style>
#     """, unsafe_allow_html=True)
    
#     # Initialize session state variables
#     if "signup_step" not in st.session_state:
#         st.session_state.signup_step = 1
#     if "signup_data" not in st.session_state:
#         st.session_state.signup_data = {}
    
#     # Trial information box
#     st.markdown("""
#         <div class="trial-info">
#             <h3>What's included in your trial:</h3>
#             <ul>
#                 <li>Full access to all ERP modules for 3 days</li>
#                 <li>Admin privileges to explore all features</li>
#                 <li>No credit card required</li>
#                 <li>Trial expires automatically after 3 days</li>
#             </ul>
#         </div>
#     """, unsafe_allow_html=True)
    
#     # Step 1: Collect user information
#     if st.session_state.signup_step == 1:
#         with st.form("signup_form"):
#             st.subheader("Create Your Account")
            
#             col1, col2 = st.columns(2)
#             with col1:
#                 username = st.text_input("Username*", key="signup_username")
#                 email = st.text_input("Email Address*", key="signup_email")
            
#             with col2:
#                 full_name = st.text_input("Full Name*", key="signup_full_name")
#                 password = st.text_input("Password*", type="password", key="signup_password")
            
#             agree = st.checkbox("I agree to the Terms of Service and Privacy Policy")
            
#             submitted = st.form_submit_button("Next: Verify Email")
            
#             if submitted:
#                 # Validate inputs
#                 if not (username and email and full_name and password):
#                     st.error("All fields are required")
#                 elif not agree:
#                     st.error("You must agree to the Terms of Service")
#                 elif len(password) < 6:
#                     st.error("Password must be at least 6 characters long")
#                 elif "@" not in email or "." not in email:
#                     st.error("Please enter a valid email address")
#                 elif is_username_registered(username):
#                     st.error("Username already exists. Please choose another one.")
#                 elif is_email_registered(email):
#                     st.error("Email already registered. Please use another email.")
#                 else:
#                     # Store data in session state
#                     st.session_state.signup_data = {
#                         "username": username,
#                         "email": email,
#                         "full_name": full_name,
#                         "password": password
#                     }
                    
#                     # Generate OTP
#                     otp = generate_otp()
#                     if save_otp(email, otp):
#                         # For demonstration purposes, let's show the OTP (in production, don't do this)
#                         # Instead, comment out this line and uncomment the email sending line below
#                         # st.session_state.debug_otp = otp  # Debug only
                        
#                         # Try to send OTP email
#                         # In production, uncomment this:
#                         if send_otp_email(email, otp):
#                             st.session_state.signup_step = 2
#                         else:
#                             st.error("Failed to send verification email. Please try again.")
                        
#                         # For demo purposes without email configuration:
#                         st.session_state.signup_step = 2
#                         st.rerun()
#                     else:
#                         st.error("Error saving verification code. Please try again.")
    
#     # Step 2: Email verification
#     elif st.session_state.signup_step == 2:
#         st.subheader("Email Verification")
#         st.write(f"We've sent a verification code to {st.session_state.signup_data['email']}")
        
#         # For demo purposes only (remove in production)
#         if hasattr(st.session_state, 'debug_otp'):
#             st.info(f"DEBUG: Your OTP is {st.session_state.debug_otp}")
        
#         with st.form("otp_form"):
#             otp_input = st.text_input("Enter verification code", max_chars=6)
            
#             col1, col2 = st.columns([1, 1])
#             with col1:
#                 back_button = st.form_submit_button("Back")
#             with col2:
#                 verify_button = st.form_submit_button("Verify & Create Account")
            
#             if back_button:
#                 st.session_state.signup_step = 1
#                 st.rerun()
            
#             if verify_button:
#                 if not otp_input:
#                     st.error("Please enter the verification code")
#                 else:
#                     # Verify OTP
#                     if verify_otp(st.session_state.signup_data['email'], otp_input):
#                         # Create user account
#                         success, user_id = register_trial_user(
#                             st.session_state.signup_data['username'],
#                             st.session_state.signup_data['password'],
#                             st.session_state.signup_data['full_name'],
#                             st.session_state.signup_data['email']
#                         )
                        
#                         if success:
#                             st.session_state.signup_step = 3
#                             st.rerun()
#                         else:
#                             st.error("Failed to create your account. Please try again.")
#                     else:
#                         st.error("Invalid or expired verification code")
    
#     # Step 3: Success
#     elif st.session_state.signup_step == 3:
#         st.success("🎉 Your trial account has been created successfully!")
#         st.info(f"Your 3-day trial starts now. You can log in with your username: {st.session_state.signup_data['username']}")
        
#         if st.button("Go to Login"):
#             # Clear signup data
#             st.session_state.signup_step = 1
#             st.session_state.signup_data = {}
#             if hasattr(st.session_state, 'debug_otp'):
#                 del st.session_state.debug_otp
                
#             # Redirect to login page
#             st.session_state.page = "Login"
#             st.rerun()

# def show_trial_banner():
#     """Show trial status banner for trial users"""
#     if "user" in st.session_state and st.session_state.get("logged_in", False):
#         user_id = st.session_state.user.get("user_id")
#         is_active, trial_info = check_trial_status(user_id)
        
#         if is_active:
#             days_left = trial_info.get('days_left', 0)
#             end_date = trial_info.get('end_date', 'Unknown')
            
#             # Style based on days left
#             if days_left <= 1:
#                 banner_color = "#ff5252"  # Red for last day
#             else:
#                 banner_color = "#4a6fa5"  # Blue for normal
            
#             st.markdown(f"""
#                 <div style="background-color: {banner_color}; color: white; padding: 10px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
#                     <div>
#                         <strong>Trial Status:</strong> {days_left} day{'s' if days_left != 1 else ''} remaining (Expires on {end_date})
#                     </div>
#                     <div>
#                         <a href="#" style="color: white; text-decoration: underline;">Upgrade Now</a>
#                     </div>
#                 </div>
#             """, unsafe_allow_html=True)
#         elif not is_active and 'message' in trial_info:
#             # Trial expired
#             st.markdown(f"""
#                 <div style="background-color: #ff5252; color: white; padding: 10px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
#                     <div>
#                         <strong>Trial Status:</strong> {trial_info['message']}
#                     </div>
#                     <div>
#                         <a href="#" style="color: white; text-decoration: underline;">Purchase Full Version</a>
#                     </div>
#                 </div>
#             """, unsafe_allow_html=True)

# # Run this function periodically (e.g., on startup and periodically during app usage)
# def cleanup_expired_data():
#     """Clean up expired OTPs and deactivate expired trials"""
#     # Clean up expired OTPs
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor()
#         try:
#             cursor.execute("DELETE FROM email_verification WHERE expires_at < NOW()")
#             conn.commit()
#         except Error as e:
#             print(f"Error cleaning up expired OTPs: {e}")
#         finally:
#             cursor.close()
#             conn.close()
    
#     # Deactivate expired trials
#     deactivated = deactivate_expired_trials()
#     if deactivated > 0:
#         print(f"Deactivated {deactivated} expired trials")
    
#     # Clean up expired databases
#     cleanup_expired_databases()

# # Initialize trial tables when imported
# create_trial_tables()
# cleanup_expired_data()



