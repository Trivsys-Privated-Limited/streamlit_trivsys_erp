# # Page configuration - MUST BE FIRST
# import streamlit as st

# st.set_page_config(
#     page_title="ALIF ERP",
#     page_icon="💻",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# # Now import everything else
# import base64
# from io import BytesIO
# import math
# from openpyxl.styles import Font
# import dashboard
# import os
# import re
# import pandas as pd
# from PIL import Image as PILImage
# from openpyxl.drawing.image import Image
# from openpyxl import Workbook
# import shutil

# # Import all modules
# from database import *
# import attendance
# from sales import sales_page
# from report import *
# from shopify_integration import *
# import whatsapp_integration
# import purchase
# import credit_sales
# from user_auth import *
# from trial_management import *
# import order_management
# import payroll

# # Constants
# STATIC_FOLDER = "static"
# os.makedirs(STATIC_FOLDER, exist_ok=True)

# # Initialize application immediately
# create_users_table()

# # Initialize session state variables
# if "page" not in st.session_state:
#     st.session_state.page = "Login"

# # Check and restore session
# if check_session():
#     if st.session_state.page == "Login":
#         st.session_state.page = "Home"

# # Initialize cart and products
# if "cart" not in st.session_state or not isinstance(st.session_state.cart, dict):
#     st.session_state.cart = {}
# if "total" not in st.session_state:
#     st.session_state.total = 0.0
# if "products" not in st.session_state:
#     st.session_state.products = fetch_products()
# if "filtered_products" not in st.session_state:
#     st.session_state.filtered_products = st.session_state.products
# if "trigger_rerun" not in st.session_state:
#     st.session_state.trigger_rerun = False

# # Load CSS for traditional ERP styling
# def load_css():
#     with open("static/style.css") as f:
#         css = f.read()
#     st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# # Utility functions
# def clean_product_name_for_filename(product_name):
#     """Convert product name to a safe filename"""
#     return re.sub(r'[^a-zA-Z0-9_]', '_', product_name.strip().lower())

# def save_product_image(img_data, product_name):
#     """Save an RGBA image as RGB with a white background"""
#     image = PILImage.open(BytesIO(img_data))
    
#     if image.mode == "RGBA":
#         white_bg = PILImage.new("RGB", image.size, (255, 255, 255))
#         white_bg.paste(image, mask=image.split()[3])
#         image = white_bg
    
#     safe_name = clean_product_name_for_filename(product_name)
#     image_filename = f"{safe_name}.jpg"
#     image_path = os.path.join(STATIC_FOLDER, image_filename)
    
#     os.makedirs(STATIC_FOLDER, exist_ok=True)
#     image.save(image_path, "JPEG", quality=95)
    
#     return f"static/{image_filename}"

# def generate_excel_template():
#     """Generate an Excel file template for product uploads with bold header."""
#     wb = Workbook()
#     ws = wb.active
#     ws.title = "Product Upload"
    
#     headers = ["Product Name", "Product Category", "Selling Price", "Cost Price", "Quantity", "Image"]
#     ws.append(headers)
    
#     bold_font = Font(bold=True)
#     for cell in ws[1]:
#         cell.font = bold_font
    
#     ws.append(["Sample Product1", "Fruits", 150.0, 100.0, 20, "sample_product1.jpg"])
#     ws.append(["Sample Product2", "Fruits", 150.0, 100.0, 20, "sample_product2.jpg"])
    
#     virtual_workbook = BytesIO()
#     wb.save(virtual_workbook)
#     virtual_workbook.seek(0)
#     return virtual_workbook

# def process_excel(uploaded_file):
#     """Process uploaded Excel file and add products to database"""
#     df = pd.read_excel(uploaded_file, engine="openpyxl")
    
#     for idx, row in df.iterrows():
#         name = str(row["Product Name"]).strip()
#         category = str(row["Product Category"]).strip()
#         price = float(row["Selling Price"])
#         cost_price = float(row["Cost Price"])
#         stock = max(0, int(row["Quantity"]))
        
#         image_path = None
#         if "Image" in row and pd.notna(row["Image"]):
#             original_image_filename = str(row["Image"]).strip()
#             original_image_path = os.path.join(STATIC_FOLDER, original_image_filename)
            
#             if os.path.exists(original_image_path):
#                 safe_name = clean_product_name_for_filename(name)
#                 new_image_filename = f"{safe_name}.jpg"
#                 new_image_path = os.path.join(STATIC_FOLDER, new_image_filename)
                
#                 if original_image_filename != new_image_filename:
#                     os.rename(original_image_path, new_image_path)
                
#                 image_path = f"static/{new_image_filename}"
#             else:
#                 st.warning(f"⚠️ Image '{original_image_filename}' not found for product '{name}'")
        
#         add_product(name, price, cost_price, stock, category, image_path)
    
#     st.success("✅ Products uploaded successfully!")

# def delete_product_image(product_name):
#     """Delete the product image if it exists"""
#     safe_name = clean_product_name_for_filename(product_name)
#     image_extensions = [".jpg", ".png"]
#     for ext in image_extensions:
#         image_path = os.path.join(STATIC_FOLDER, f"{safe_name}{ext}")
#         if os.path.exists(image_path):
#             os.remove(image_path)
#             return True
#     return False

# def log_activity(activity):
#     """Log an activity with a timestamp"""
#     timestamp = pd.to_datetime("now").strftime("%Y-%m-%d %H:%M:%S")
    
#     if "user" in st.session_state and st.session_state.get("logged_in", False):
#         username = st.session_state.user.get("username", "unknown")
#         log_entry = {"timestamp": timestamp, "user": username, "action": activity}
#     else:
#         log_entry = {"timestamp": timestamp, "user": "system", "action": activity}
    
#     if "activity_log" not in st.session_state:
#         st.session_state.activity_log = []
    
#     st.session_state.activity_log.append(log_entry)
    
#     with open("activity_log.txt", "a") as f:
#         if "user" in st.session_state and st.session_state.get("logged_in", False):
#             f.write(f"{timestamp} - {st.session_state.user['username']} - {activity}\n")
#         else:
#             f.write(f"{timestamp} - system - {activity}\n")

# def create_sidebar_navigation():
#     """Create traditional ERP-style left sidebar navigation"""
    
#     # Define all modules with their access requirements
#     modules = [
#         {"name": "Dashboard", "icon": "📊", "page": "Dashboard"},
#         {"name": "POS System", "icon": "🛒", "page": "POS System"},
#         {"name": "Inventory Management", "icon": "📦", "page": "Inventory Management"},
#         {"name": "Sales Module", "icon": "💰", "page": "Sales Module"},
#         {"name": "Credit Sales", "icon": "💳", "page": "Credit Sales"},
#         {"name": "Purchase Module", "icon": "🛍️", "page": "Purchase Module"},
#         {"name": "Order Management", "icon": "📋", "page": "Order Management"},
#         {"name": "Attendance Management", "icon": "👥", "page": "Attendance Management"},
#         {"name": "Payroll Management", "icon": "💼", "page": "Payroll Management"},
#         {"name": "Shopify Integration", "icon": "🛒", "page": "Shopify"},
#         {"name": "WhatsApp Integration", "icon": "💬", "page": "WhatsApp Integration"},
#     ]
    
#     # Create sidebar
#     with st.sidebar:
#         st.markdown("### 🏢 ALIF ERP")
#         st.markdown("---")
        
#         # User info
#         if st.session_state.get("logged_in", False):
#             st.markdown(f"**👤 {st.session_state.user['full_name']}**")
#             st.markdown(f"*{st.session_state.user['role'].title()}*")
#             st.markdown("---")
        
#         # Navigation menu
#         for module in modules:
#             # Check if user has access to this module
#             if has_module_access(module["name"]):
#                 if st.button(f"{module['icon']} {module['name']}", key=f"nav_{module['page']}", use_container_width=True):
#                     st.session_state.page = module["page"]
#                     log_activity(f"Navigated to {module['name']}")
#                     st.rerun()
        
#         st.markdown("---")
        
#         # Admin-only features
#         if st.session_state.get("logged_in", False) and st.session_state.user['role'] == 'admin':
#             if st.button("👤 User Management", key="nav_user_mgmt", use_container_width=True):
#                 st.session_state.page = "User Management"
#                 st.rerun()
        
#         # Logout button
#         if st.session_state.get("logged_in", False):
#             if st.button("🔓 Logout", key="nav_logout", use_container_width=True):
#                 logout_user()

# def go_to_page(page_name):
#     """Navigate to a specific page with access control"""
#     if page_name == "Home" and st.session_state.get("logged_in", False):
#         st.session_state.page = page_name
#         st.rerun()
#     elif has_module_access(page_name):
#         st.session_state.page = page_name
#         st.rerun()
#     else:
#         st.error(f"Access denied. You don't have permission to access {page_name}.")

# # Initialize application
# def initialize_app():
#     """Additional initialization if needed"""
#     # Most initialization is now done at module level
#     pass

# # Main application logic
# def main():
#     """Main application entry point"""
#     # Load CSS
#     load_css()
    
#     # Additional initialization if needed
#     initialize_app()
    
#     # Handle routing
#     if st.session_state.page == "Login":
#         show_login_page()
#         return
    
#     # For all other pages, ensure user is logged in
#     if not st.session_state.get("logged_in", False):
#         st.session_state.page = "Login"
#         st.rerun()
#         return
    
#     # Create sidebar navigation
#     create_sidebar_navigation()
    
#     # Main content area
#     if st.session_state.page == "Home":
#         st.title("ALIF ERP Dashboard")
#         st.markdown("### Welcome to your Enterprise Resource Planning System")
        
#         # Quick stats or overview
#         col1, col2, col3, col4 = st.columns(4)
#         with col1:
#             st.metric("Total Products", len(st.session_state.products))
#         with col2:
#             st.metric("Active Users", "1")  # You can make this dynamic
#         with col3:
#             st.metric("Today's Sales", "Rs 0")  # You can make this dynamic
#         with col4:
#             st.metric("Low Stock Items", "0")  # You can make this dynamic
        
#         st.markdown("---")
#         st.markdown("#### Quick Actions")
#         st.markdown("Use the sidebar navigation to access different modules of the ERP system.")
    
#     elif st.session_state.page == "User Management":
#         st.title("👤 User Management")
#         show_user_management()
    
#     elif st.session_state.page == "Dashboard":
#         # st.title("📊 Dashboard")
#         dashboard.show_dashboard()
    
#     elif st.session_state.page == "POS System":
#         # st.title("🛒 POS System")
#         # Add your POS system logic here
#         st.info("POS System module - Implementation needed")
    
#     elif st.session_state.page == "Inventory Management":
#         # st.title("📦 Inventory Management")
#         # Add your inventory management logic here
#         st.info("Inventory Management module - Implementation needed")
    
#     elif st.session_state.page == "Sales Module":
#         # st.title("💰 Sales Module")
#         sales_page()
    
#     elif st.session_state.page == "Credit Sales":
#         # st.title("💳 Credit Sales")
#         credit_sales.credit_sales_page()
    
#     elif st.session_state.page == "Purchase Module":
#         # st.title("🛍️ Purchase Module")
#         purchase.purchase_page()
    
#     elif st.session_state.page == "Order Management":
#         # st.title("📋 Order Management")
#         order_management.order_management_page()
    
#     elif st.session_state.page == "Attendance Management":
#         # st.title("👥 Attendance Management")
#         attendance.attendance_page()
    
#     elif st.session_state.page == "Payroll Management":
#         # st.title("💼 Payroll Management")
#         payroll.payroll_page()
    
#     elif st.session_state.page == "Shopify":
#         # st.title("🛒 Shopify Integration")
        
#         # Initialize session state for credentials
#         if "shop_url" not in st.session_state:
#             st.session_state.shop_url = ""
#         if "access_token" not in st.session_state:
#             st.session_state.access_token = ""
#         if "shopify_credentials_saved" not in st.session_state:
#             st.session_state.shopify_credentials_saved = False
        
#         # Credentials input
#         if not st.session_state.shopify_credentials_saved:
#             if st.button("Back to Home"):
#                 st.session_state.page = "Home"
#                 st.rerun()            
#             st.subheader("Enter Shopify Credentials")
#             shop_url = st.text_input("Shopify Shop URL", value=st.session_state.shop_url)
#             access_token = st.text_input("Shopify Access Token", type="password", value=st.session_state.access_token)
            
#             if st.button("Save Credentials"):
#                 st.session_state.shop_url = shop_url
#                 st.session_state.access_token = access_token
#                 st.session_state.shopify_credentials_saved = True
#                 st.success("Credentials saved successfully!")
#                 st.rerun()
        
#         # Sync buttons
#         col1, col2 = st.columns(2)
#         with col1:
#             if st.button("Sync from Shopify"):
#                 result = fetch_and_update_products()
#                 st.success(result)
#                 log_activity("Synced products from Shopify")
        
#         with col2:
#             if st.button("Sync to Shopify"):
#                 result = update_shopify_inventory()
#                 st.success(result)
#                 log_activity("Synced inventory to Shopify")
    
#     elif st.session_state.page == "WhatsApp Integration":
#         # st.title("💬 WhatsApp Integration")
#         whatsapp_integration.whatsapp_page()

# # Run the application
# if __name__ == "__main__":
#     main()
