import streamlit as st
from database import (
    db_manager, 
    initialize_master_db, 
    signup_tenant, 
    login_tenant,
    get_db_connection
)
import hashlib
import mysql.connector
from mysql.connector import Error
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import uuid
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Create a directory for storing session data if it doesn't exist
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# ============================================================================
# EMAIL CONFIGURATION - UPDATE WITH YOUR CREDENTIALS
# ============================================================================
EMAIL_HOST = "smtp.gmail.com"  # For Gmail
EMAIL_PORT = 587
EMAIL_ADDRESS = "abdulwahab96540@gmail.com"  # Replace with your email
EMAIL_PASSWORD = "trra zppt mcsc grly"  # Replace with your app password

# ============================================================================
# OTP FUNCTIONS
# ============================================================================

def generate_otp():
    """Generate a 4-digit OTP"""
    return str(random.randint(1000, 9999))

def send_otp_email(email, otp):
    """Send OTP to user's email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = "Your Verification Code"
        
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #f5f5f5; padding: 30px; border-radius: 10px;">
                    <h2 style="color: #7c3aed;">Email Verification</h2>
                    <p style="font-size: 16px; color: #333;">Your verification code is:</p>
                    <div style="background-color: white; padding: 20px; text-align: center; border-radius: 5px; margin: 20px 0;">
                        <h1 style="color: #7c3aed; font-size: 36px; letter-spacing: 8px; margin: 0;">{otp}</h1>
                    </div>
                    <p style="font-size: 14px; color: #666;">This code will expire in 10 minutes.</p>
                    <p style="font-size: 14px; color: #666;">If you didn't request this code, please ignore this email.</p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True, "OTP sent successfully"
    except Exception as e:
        print(f"Error sending email: {e}")
        return False, f"Failed to send OTP: {str(e)}"

def store_otp(email, otp):
    """Store OTP in database with expiration"""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Create OTP table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otp_verification (
                    email VARCHAR(255) PRIMARY KEY,
                    otp VARCHAR(4) NOT NULL,
                    expires TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Delete old OTP for this email
            cursor.execute("DELETE FROM otp_verification WHERE email = %s", (email,))
            
            # Insert new OTP with 10 minute expiration
            expires = datetime.now() + timedelta(minutes=10)
            cursor.execute("""
                INSERT INTO otp_verification (email, otp, expires)
                VALUES (%s, %s, %s)
            """, (email, otp, expires))
            
            conn.commit()
            return True
        except Error as e:
            print(f"Error storing OTP: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def verify_otp(email, entered_otp):
    """Verify OTP from database"""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT otp, expires FROM otp_verification 
                WHERE email = %s
            """, (email,))
            
            result = cursor.fetchone()
            
            if not result:
                return False, "No OTP found for this email"
            
            if datetime.now() > result['expires']:
                cursor.execute("DELETE FROM otp_verification WHERE email = %s", (email,))
                conn.commit()
                return False, "OTP has expired"
            
            if result['otp'] == entered_otp:
                cursor.execute("DELETE FROM otp_verification WHERE email = %s", (email,))
                conn.commit()
                return True, "OTP verified successfully"
            else:
                return False, "Invalid OTP"
                
        except Error as e:
            print(f"Error verifying OTP: {e}")
            return False, "Error verifying OTP"
        finally:
            cursor.close()
            conn.close()
    return False, "Database connection error"

# ============================================================================
# INITIALIZATION - Ensure master database is created
# ============================================================================

def ensure_master_db_initialized():
    """Initialize master database on first run"""
    if 'db_initialized' not in st.session_state:
        if initialize_master_db():
            st.session_state.db_initialized = True
            return True
        else:
            st.error("Failed to initialize master database")
            return False
    return True

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def get_browser_id():
    """Generate a stable browser ID based on IP and user agent or retrieve from cookie"""
    browser_id_param = st.query_params.get('browser_id')
    if browser_id_param:
        st.session_state.browser_id = browser_id_param
        return browser_id_param
        
    if "browser_id" in st.session_state:
        return st.session_state.browser_id
        
    browser_id = str(uuid.uuid4())
    st.session_state.browser_id = browser_id
    
    current_params = st.query_params.to_dict()
    params = dict(current_params)
    params['browser_id'] = browser_id
    st.query_params.update(params)
    
    return browser_id

def generate_session_token(tenant, browser_id):
    """Generate a unique session token for tenant"""
    timestamp = datetime.now().timestamp()
    token = f"{tenant.tenant_id}_{browser_id}_{timestamp}"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    session_data = {
        'tenant_id': tenant.tenant_id,
        'business_name': tenant.business_name,
        'email': tenant.email,
        'database_name': tenant.database_name,
        'db_host': tenant.db_host,
        'db_user': tenant.db_user,
        'is_active': tenant.is_active,
        'expires': (datetime.now() + timedelta(hours=24)).timestamp()
    }
    
    # Store in master database
    conn = get_db_connection()  # Master DB connection
    if conn:
        cursor = conn.cursor()
        try:
            # Delete old sessions for this browser
            cursor.execute("""
                DELETE FROM tenant_sessions
                WHERE browser_id = %s
            """, (browser_id,))
            
            # Create tenant_sessions table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenant_sessions (
                    token VARCHAR(128) PRIMARY KEY,
                    session_data TEXT NOT NULL,
                    browser_id VARCHAR(128) NOT NULL,
                    tenant_id INT NOT NULL,
                    expires FLOAT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                )
            """)
            
            # Insert new session
            cursor.execute("""
                INSERT INTO tenant_sessions (token, session_data, browser_id, tenant_id, expires)
                VALUES (%s, %s, %s, %s, %s)
            """, (token_hash, json.dumps(session_data), browser_id, tenant.tenant_id, session_data['expires']))
            conn.commit()
            
            # Backup to file
            with open(os.path.join(SESSION_DIR, f"{browser_id}.json"), "w") as f:
                json.dump({
                    'token': token_hash,
                    'session_data': session_data,
                    'browser_id': browser_id,
                    'expires': session_data['expires']
                }, f)
                
        except Error as e:
            print(f"Error storing session data: {e}")
        finally:
            cursor.close()
            conn.close()
    
    return token_hash

def validate_session(token):
    """Validate a session token"""
    if not token:
        return None
    
    browser_id = get_browser_id()
    conn = get_db_connection()  # Master DB connection
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT session_data, expires 
                FROM tenant_sessions 
                WHERE token = %s AND browser_id = %s
            """, (token, browser_id))
            session = cursor.fetchone()
            
            if session and float(session['expires']) > datetime.now().timestamp():
                return json.loads(session['session_data'])
            else:
                if session:
                    cursor.execute("DELETE FROM tenant_sessions WHERE token = %s", (token,))
                    conn.commit()
                
                session_file = os.path.join(SESSION_DIR, f"{browser_id}.json")
                if os.path.exists(session_file):
                    os.remove(session_file)
                    
        except Error as e:
            print(f"Error validating session from database: {e}")
        finally:
            cursor.close()
            conn.close()
    
    # Fallback to file
    session_file = os.path.join(SESSION_DIR, f"{browser_id}.json")
    if os.path.exists(session_file):
        try:
            with open(session_file, "r") as f:
                file_data = json.load(f)
                token_from_file = file_data.get('token')
                session_data = file_data.get('session_data')
                expires = file_data.get('expires')
                
            if token_from_file == token and expires > datetime.now().timestamp():
                return session_data
            elif expires <= datetime.now().timestamp():
                os.remove(session_file)
        except Exception as e:
            print(f"Error validating session from file: {e}")
    
    return None

def check_session():
    """Check for existing session and initialize session state"""
    browser_id = get_browser_id()
    token_param = st.query_params.get('token')
    
    if "auth_token" in st.session_state:
        token = st.session_state.auth_token
    elif token_param:
        token = token_param
    else:
        token = None
    
    if token:
        session_data = validate_session(token)
        if session_data:
            if "auth_token" not in st.session_state:
                st.session_state.auth_token = token
                
            st.session_state.logged_in = True
            # Normalize tenant into an object with attributes for safer access
            if isinstance(session_data, dict):
                st.session_state.tenant = type('obj', (object,), session_data)()
            else:
                # If session_data already resembles an object, keep as-is
                st.session_state.tenant = session_data
            
            if not token_param:
                params = st.query_params.to_dict()
                params['token'] = token
                st.query_params.update(params)
                
            if "page" not in st.session_state or st.session_state.page == "Login":
                st.session_state.page = "Home"
                
            return True
    
    # Try to recover from file
    session_file = os.path.join(SESSION_DIR, f"{browser_id}.json")
    if os.path.exists(session_file):
        try:
            with open(session_file, "r") as f:
                file_data = json.load(f)
                token_from_file = file_data.get('token')
                session_data = file_data.get('session_data')
                expires = file_data.get('expires')
                
            if expires > datetime.now().timestamp():
                st.session_state.auth_token = token_from_file
                st.session_state.logged_in = True
                # Normalize tenant like above
                if isinstance(session_data, dict):
                    st.session_state.tenant = type('obj', (object,), session_data)()
                else:
                    st.session_state.tenant = session_data
                
                params = st.query_params.to_dict()
                params['token'] = token_from_file
                st.query_params.update(params)
                
                if "page" not in st.session_state or st.session_state.page == "Login":
                    st.session_state.page = "Home"
                    
                return True
            else:
                os.remove(session_file)
        except Exception as e:
            print(f"Error recovering session from file: {e}")
    
    return False

# ============================================================================
# LOGIN & SIGNUP FUNCTIONS
# ============================================================================

def login_user(email, password):
    """Authenticate tenant and create session"""
    authenticated, tenant, message = login_tenant(email, password)
    
    if authenticated and tenant:
        browser_id = get_browser_id()
        session_token = generate_session_token(tenant, browser_id)
        
        st.session_state.auth_token = session_token
        st.session_state.logged_in = True
        # Ensure tenant stored in session_state is an object with attributes
        if isinstance(tenant, dict):
            st.session_state.tenant = type('obj', (object,), tenant)()
        else:
            st.session_state.tenant = tenant
        st.session_state.page = "Home"
        
        params = st.query_params.to_dict()
        params['token'] = session_token
        st.query_params.update(params)
        
        return tenant, session_token, message
    else:
        return None, None, message

def signup_user(business_name, email, phone_number, password, confirm_password):
    """Create a new tenant account"""
    if password != confirm_password:
        return False, "Passwords do not match"

    if len(password) < 6:
        return False, "Password must be at least 6 characters long"

    success, message = signup_tenant(business_name, email, phone_number, password)
    return success, message

# ============================================================================
# UI FUNCTIONS
# ============================================================================

def show_login_page():
    """Display the login page with login and signup tabs"""
    # Ensure master DB is initialized
    if not ensure_master_db_initialized():
        st.error("System initialization failed. Please contact support.")
        return
    
    # Check if user is already logged in
    if check_session():
        return
    
    # Initialize OTP verification state
    if 'otp_verification_step' not in st.session_state:
        st.session_state.otp_verification_step = False
    if 'pending_signup_data' not in st.session_state:
        st.session_state.pending_signup_data = None
    
    # Hide default Streamlit elements
    st.markdown("""
        <style>
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Import font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* Main container styling */
        [data-testid="stAppViewContainer"] {
            background: #1a1a2e;
            font-family: 'Inter', sans-serif;
        }
        
        /* Center content */
        .block-container {
            max-width: 550px;
            padding-top: 5rem;
            padding-bottom: 5rem;
        }
        
        /* Login card container */
        .login-card {
            background: #2d2d44;
            border: 2px solid #7c3aed;
            border-radius: 16px;
            padding: 48px 40px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        
        /* Header styling */
        .login-header {
            color: #ffffff;
            font-size: 42px;
            font-weight: 600;
            margin-bottom: 12px;
            letter-spacing: -0.5px;
        }
        
        .login-subheader {
            color: #b4b4c8;
            font-size: 14px;
            margin-bottom: 32px;
        }
        
        .login-subheader a {
            color: #ffffff;
            text-decoration: underline;
            cursor: pointer;
        }
        
        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0px;
            background-color: transparent;
            border-bottom: 1px solid #3d3d54;
            margin-bottom: 32px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 0px 24px;
            background-color: transparent;
            border: 1px solid white;
            color: #8e8ea9;
            font-weight: 500;
            font-size: 25px;
            border-radius: 0;
            margin-left: 10px;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: transparent;
            color: #ffffff;
            border-bottom: 2px solid #7c3aed;
        }
        
        /* Form elements */
        .stTextInput > div > div > input {
            background-color: #3d3d54;
            border: 1px solid #3d3d54;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 20px;
            color: black;
            transition: all 0.2s ease;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #7c3aed;
            background-color: #3d3d54;
            box-shadow: 0 0 0 1px #7c3aed;
            outline: none;
        }
        
        .stTextInput > div > div > input::placeholder {
            color: #8e8ea9;
        }
        
        .stTextInput > label {
            display: none;
        }
        
        /* Checkbox styling */
        .stCheckbox {
            color: #b4b4c8;
            font-size: 13px;
        }
        
        .stCheckbox > label {
            color: white;
            font-size: 13px;
        }
        
        .stCheckbox a {
            color: #ffffff;
            text-decoration: underline;
        }
        
        /* Button styling */
        .stButton > button {
            width: 100%;
            background: #7c3aed;
            color: white;
            padding: 12px 24px;
            font-size: 15px;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            transition: all 0.2s ease;
            margin-top: 8px;
            cursor: pointer;
            letter-spacing: 0.3px;
        }
        
        .stButton > button:hover {
            background: #6d28d9;
        }
        
        .stButton > button:active {
            transform: scale(0.98);
        }
        
        /* Form container */
        [data-testid="stForm"] {
            border: none;
            padding: 0;
        }
        
        /* Alert messages */
        .stAlert {
            border-radius: 8px;
            border: none;
            font-size: 14px;
        }
        
        /* Column spacing */
        [data-testid="column"] {
            padding: 0 4px;
        }
        
        /* Remove extra spacing */
        .element-container {
            margin-bottom: 16px;
        }
        
        /* Success/Error message styling */
        .stSuccess, .stError, .stWarning, .stInfo {
            background-color: #3d3d54;
            border-radius: 8px;
            padding: 12px;
            border-left: 3px solid;
        }
        
        .stSuccess {
            border-left-color: #10b981;
            color: #10b981;
        }
        
        .stError {
            border-left-color: #ef4444;
            color: #ef4444;
        }
        
        .stWarning {
            border-left-color: #f59e0b;
            color: #f59e0b;
        }
        
        .stInfo {
            border-left-color: #3b82f6;
            color: #3b82f6;
        }
        
        /* OTP input styling */
        .otp-input {
            text-align: center;
            font-size: 32px !important;
            letter-spacing: 10px;
            font-weight: 600;
        }
        </style>
    """, unsafe_allow_html=True)

    # Show OTP verification screen if in that step
    if st.session_state.otp_verification_step and st.session_state.pending_signup_data:
        show_otp_verification_screen()
        return
    
    # Create tabs for login and sign-up
    tabs = st.tabs(["Login", "Sign up"])

    # LOGIN TAB
    with tabs[0]:
        st.markdown('<p class="login-header">Login to your account</p>', unsafe_allow_html=True)
        st.markdown('<p class="login-subheader">Don\'t have an account? Switch to Sign up tab</p>', unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "Email",
                placeholder="Email",
                label_visibility="collapsed"
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                label_visibility="collapsed"
            )
                
            submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                if email and password:
                    tenant, session_token, message = login_user(email, password)
                    
                    if tenant:
                        business_name = getattr(tenant, 'business_name', None) if tenant else None
                        if not business_name:
                            business_name = get_tenant_business_name(default="Tenant")
                        st.success(f"Welcome back, {business_name}!")
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please enter both email and password")

    # SIGNUP TAB
    with tabs[1]:
        st.markdown('<p class="login-header">Create an account</p>', unsafe_allow_html=True)
        st.markdown('<p class="login-subheader">Already have an account? Switch to Login tab</p>', unsafe_allow_html=True)
        
        with st.form("signup_form", clear_on_submit=False):
            business_name = st.text_input(
                "Business Name",
                placeholder="Business name",
                label_visibility="collapsed"
            )
            
            email = st.text_input(
                "Email",
                placeholder="Email",
                key="signup_email",
                label_visibility="collapsed"
            )
            
            phone_number = st.text_input(
                "Phone Number",
                placeholder="Enter your phone number",
                label_visibility="collapsed"
            )
            
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="signup_password",
                label_visibility="collapsed"
            )
            
            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Confirm password",
                label_visibility="collapsed"
            )
            
            agree = st.checkbox("I agree to the Terms & Conditions", value=False)
            
            submitted = st.form_submit_button("Create account", use_container_width=True)
            
            if submitted:
                if not agree:
                    st.warning("Please agree to the Terms & Conditions")
                elif business_name and email and phone_number and password and confirm_password:
                    if password != confirm_password:
                        st.error("Passwords do not match")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters long")
                    else:
                        # Generate and send OTP
                        otp = generate_otp()
                        
                        # Store OTP in database
                        if store_otp(email, otp):
                            # Send OTP via email
                            success, message = send_otp_email(email, otp)
                            
                            if success:
                                # Store signup data temporarily
                                st.session_state.pending_signup_data = {
                                    'business_name': business_name,
                                    'email': email,
                                    'phone_number': phone_number,
                                    'password': password
                                }
                                st.session_state.otp_verification_step = True
                                st.success("OTP sent to your email! Check your inbox.")
                                st.rerun()
                            else:
                                st.error(f"Failed to send OTP: {message}")
                        else:
                            st.error("Failed to generate OTP. Please try again.")
                else:
                    st.warning("Please fill in all fields")

def show_otp_verification_screen():
    """Display OTP verification screen"""
    st.markdown('<p class="login-header">Verify Your Email</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="login-subheader">We sent a 4-digit code to {st.session_state.pending_signup_data["email"]}</p>', unsafe_allow_html=True)
    
    with st.form("otp_form", clear_on_submit=False):
        otp_input = st.text_input(
            "Enter OTP",
            placeholder="Enter 4-digit code",
            max_chars=4,
            label_visibility="collapsed",
            key="otp_input"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            verify_button = st.form_submit_button("Verify", use_container_width=True)
        
        with col2:
            resend_button = st.form_submit_button("Resend OTP", use_container_width=True)
        
        if verify_button:
            if len(otp_input) == 4:
                email = st.session_state.pending_signup_data['email']
                success, message = verify_otp(email, otp_input)
                
                if success:
                    # Create the account
                    signup_data = st.session_state.pending_signup_data
                    account_created, account_message = signup_user(
                        signup_data['business_name'],
                        signup_data['email'],
                        signup_data['phone_number'],
                        signup_data['password'],
                        signup_data['password']
                    )
                    
                    if account_created:
                        st.success("Account created successfully! Redirecting to login...")
                        # Clear OTP verification state
                        st.session_state.otp_verification_step = False
                        st.session_state.pending_signup_data = None
                        st.rerun()
                    else:
                        st.error(f"Account creation failed: {account_message}")
                else:
                    st.error(message)
            else:
                st.warning("Please enter a 4-digit OTP")
        
        if resend_button:
            email = st.session_state.pending_signup_data['email']
            otp = generate_otp()
            
            if store_otp(email, otp):
                success, message = send_otp_email(email, otp)
                if success:
                    st.info("New OTP sent to your email!")
                else:
                    st.error(f"Failed to resend OTP: {message}")
            else:
                st.error("Failed to generate new OTP")
    
    # Cancel button outside form
    if st.button("Cancel", use_container_width=True):
        st.session_state.otp_verification_step = False
        st.session_state.pending_signup_data = None
        st.rerun()

# ============================================================================
# LOGOUT FUNCTION
# ============================================================================

def logout_user():
    """Log out the current tenant"""
    browser_id = get_browser_id()
    
    # Clear session from database
    if "auth_token" in st.session_state:
        token = st.session_state.auth_token
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM tenant_sessions WHERE token = %s", (token,))
                conn.commit()
            except Error as e:
                print(f"Error during logout: {e}")
            finally:
                cursor.close()
                conn.close()
    
    # Remove session file
    session_file = os.path.join(SESSION_DIR, f"{browser_id}.json")
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
        except Exception as e:
            print(f"Error removing session file: {e}")
    
    # Clear query params
    try:
        if 'token' in st.query_params:
            st.query_params.clear()
    except Exception as e:
        print(f"Error clearing query params: {e}")
    
    # Clear session state
    keys_to_delete = ['logged_in', 'tenant', 'auth_token', 'page', 'sub_menu', 'purchase_cart', 
                      'otp_verification_step', 'pending_signup_data']
    for key in list(st.session_state.keys()):
        if key in keys_to_delete or key.startswith('nav_'):
            del st.session_state[key]
    
    # Set page to Login
    st.session_state.page = "Login"
    st.session_state.logged_in = False
    
    st.rerun()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_current_tenant():
    """Get the currently logged-in tenant object"""
    if st.session_state.get("logged_in") and "tenant" in st.session_state:
        return st.session_state.tenant
    return None


def get_tenant_business_name(default="Unknown"):
    """Return the business name for current tenant safely.

    Returns a string (default if missing).
    """
    tenant = get_current_tenant()
    if not tenant:
        return default

    # support dict-like or object-like tenant
    try:
        if isinstance(tenant, dict):
            return tenant.get('business_name') or default
        return getattr(tenant, 'business_name', default) or default
    except Exception:
        return default

def cleanup_expired_sessions():
    """Clean up expired session files"""
    current_time = datetime.now().timestamp()
    for filename in os.listdir(SESSION_DIR):
        if filename.endswith('.json'):
            session_file = os.path.join(SESSION_DIR, filename)
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                if session_data.get('expires', 0) < current_time:
                    os.remove(session_file)
                    print(f"Removed expired session: {filename}")
            except Exception as e:
                print(f"Error processing session file {filename}: {e}")

def cleanup_expired_otps():
    """Clean up expired OTPs from database"""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                DELETE FROM otp_verification 
                WHERE expires < NOW()
            """)
            conn.commit()
            print(f"Cleaned up expired OTPs")
        except Error as e:
            print(f"Error cleaning up OTPs: {e}")
        finally:
            cursor.close()
            conn.close()

# Run cleanup on import
cleanup_expired_sessions()
cleanup_expired_otps()