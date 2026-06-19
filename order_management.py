
# import streamlit as st
# import pandas as pd

# from credit_sales import fetch_customers
# from database import get_db_connection, update_customer
# from datetime import datetime
# from order_management_db import *
# from fpdf import FPDF
# import json as json_lib
# import os
# from sales import get_filtered_sales
# from datetime import datetime, timedelta

# from user_auth import has_module_access

# # This is the Measurement  PDF Class
# class MeasurementsPDF(FPDF):
#     def __init__(self, customer_name, measurement_type):
#         super().__init__('P', 'mm', 'A4')
#         self.page_width = 210
#         self.left_margin = 10
#         self.right_margin = 10
#         self.customer_name = customer_name
#         self.measurement_type = measurement_type
#         self.set_auto_page_break(auto=True, margin=15)
#         self.theme_color = (23, 24, 22)  # Black theme
#         self.header_text_color = (166, 124, 33)  # Golden text
#         self.logo_path = "static/order_management.jpg"
#         self.logo_width = 30
#         self.logo_height = 20

#     def header(self):
#         # Theme background
#         self.set_fill_color(*self.theme_color)
#         self.rect(0, 0, self.page_width, 25, style='F')

#         # Add logo if exists
#         if os.path.exists(self.logo_path):
#             try:
#                 self.image(self.logo_path, x=self.left_margin, y=5, w=self.logo_width, h=self.logo_height)
#             except RuntimeError as e:
#                 print(f"Logo error: {e}")

#         # Title (centered next to logo)
#         self.set_text_color(*self.header_text_color)
#         self.set_font('Arial', 'B', 16)
#         self.set_xy(self.left_margin + self.logo_width + 5, 8)
#         self.cell(0, 8, "HF DESIGN", ln=True)

#         # Subtitle
#         self.set_font('Arial', '', 11)
#         self.set_x(self.left_margin + self.logo_width + 5)
#         self.cell(0, 8, f"{self.measurement_type} Measurements - {self.customer_name}", ln=True)

#         self.set_text_color(0, 0, 0)  # Reset for body
#         self.ln(10)



#     def footer(self):
#         self.set_y(-15)
#         self.set_font('Arial', 'I', 8)
#         self.set_text_color(100, 100, 100)
#         self.cell(0, 10, f'Page {self.page_no()} - Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')

#     def _format_value(self, value):
#         """Format measurement values for display"""
#         if value is None or value == 'N/A':
#             return "N/A"
#         if hasattr(value, '__float__'):
#             return str(float(value))
#         return str(value).strip() if str(value).strip() else "0"

#     def add_sherwani_measurements(self, data):
#         self.set_font('Arial', 'B', 14)
#         self.cell(0, 10, f"{self.measurement_type} Measurements for {self.customer_name}", ln=True)
#         self.ln(5)

#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 8, "Basic Information:", ln=True)
#         self.set_font('Arial', '', 11)
#         for label, key in [("Head Size", 'head_size'), ("Shoe Size", 'shoe_size')]:
#             self.cell(0, 6, f"{label}: {self._format_value(data.get(key))}", ln=True)

#         self.ln(5)
#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 8, "Sherwani Upper Measurements:", ln=True)

#         self.set_fill_color(166, 124, 33)  # Golden background
#         self.set_text_color(255, 255, 255)
#         self.set_font('Arial', 'B', 10)

#         col1_width, col2_width = 60, 30
#         self.cell(col1_width, 8, "Measurement", 1, 0, 'C', fill=True)
#         self.cell(col2_width, 8, "Value", 1, 0, 'C', fill=True)
#         self.cell(col1_width, 8, "Measurement", 1, 0, 'C', fill=True)
#         self.cell(col2_width, 8, "Value", 1, 1, 'C', fill=True)

#         self.set_text_color(0, 0, 0)
#         self.set_font('Arial', '', 10)

#         pairs = [
#             ("Length (L.)", 'sherwani_length', "Shalwar Length", 'shalwar_length'),
#             ("Chest (CH.)", 'chest', "Width (WT.)", 'sherwani_width'),
#             ("Waist (W.)", 'waist', "Shoulder (SHL.)", 'shoulder'),
#             ("Thigh (TH.)", 'sherwani_thigh', "Sleeve (SLV.)", 'sleeve_length'),
#             ("Knee (KN.)", 'sherwani_knee', "Neck (N.)", 'neck'),
#             ("Bottom (BT.)", 'sherwani_bottom', "", "")
#         ]

#         for label1, key1, label2, key2 in pairs:
#             self.cell(col1_width, 6, label1, 1)
#             self.cell(col2_width, 6, self._format_value(data.get(key1)), 1)
#             self.cell(col1_width, 6, label2, 1)
#             self.cell(col2_width, 6, self._format_value(data.get(key2)) if key2 else "", 1, ln=True)

#         self.ln(5)
#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 8, "Accessories:", ln=True)
#         self.set_font('Arial', '', 11)

#         # Basic accessories
#         for acc in ['waistcoat', 'shoes', 'turban']:
#             status = "Yes" if data.get(acc) else "No"
#             self.cell(0, 6, f"{acc.capitalize()}: {status}", ln=True)

#         # Additional JSON accessories
#         accessories = data.get('accessories', {})
#         if isinstance(accessories, str):
#             try:
#                 accessories = json.loads(accessories)
#             except:
#                 accessories = {}

#         for key, value in accessories.items():
#             if value:
#                 acc_name = key.replace('_', ' ').title()
#                 self.cell(0, 6, f"{acc_name}: Yes", ln=True)

#         # Notes
#         notes = data.get('notes', '')
#         if notes.strip():
#             self.ln(5)
#             self.set_font('Arial', 'B', 12)
#             self.cell(0, 8, "Special Notes:", ln=True)
#             self.set_font('Arial', '', 11)
#             self.multi_cell(0, 6, notes)

#     def add_suit_measurements(self, data):
#         self.set_font('Arial', 'B', 14)
#         self.cell(0, 10, f"{self.measurement_type} Measurements for {self.customer_name}", ln=True)
#         self.ln(5)

#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 8, "Basic Information:", ln=True)
#         self.set_font('Arial', '', 11)
        
#         # Display basic measurements
#         for label, key in [("Head Size", 'head_size'), ("Shoe Size", 'shoe_size')]:
#             self.cell(0, 6, f"{label}: {self._format_value(data.get(key))}", ln=True)

#         # ✅ COAT TYPE DISPLAY (uses pre-injected name, not DB call)
#         coat_type_name = data.get('coat_type_name')
#         self.set_font('Arial', 'B', 12)
#         self.set_fill_color(240, 240, 240)  # Light gray background

#         if coat_type_name:
#             self.cell(0, 8, f"Coat Type: {coat_type_name}", ln=True, fill=True)
#         else:
#             self.cell(0, 8, "Coat Type: Not specified", ln=True, fill=True)

#         self.set_font('Arial', '', 11)  # Reset font


#         self.ln(5)
#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 8, "Suit Measurements:", ln=True)

#         self.set_fill_color(166, 124, 33)
#         self.set_text_color(255, 255, 255)
#         self.set_font('Arial', 'B', 10)

#         col1_width, col2_width = 60, 30
#         self.cell(col1_width, 8, "Measurement", 1, 0, 'C', fill=True)
#         self.cell(col2_width, 8, "Value", 1, 0, 'C', fill=True)
#         self.cell(col1_width, 8, "Measurement", 1, 0, 'C', fill=True)
#         self.cell(col2_width, 8, "Value", 1, 1, 'C', fill=True)

#         self.set_text_color(0, 0, 0)
#         self.set_font('Arial', '', 10)

#         pairs = [
#             ("Length (Coat)", 'suit_length', "Pant Length", 'suit_pant_length'),
#             ("Chest", 'suit_chest', "Pant Width", 'suit_pant_width'),
#             ("Waist", 'suit_waist', "Pant Height", 'suit_pant_height'),
#             ("Shoulder", 'suit_shoulder', "Thigh", 'suit_thigh'),
#             ("Sleeve", 'suit_sleeve', "Bottom", 'suit_bottom'),
#             ("Neck", 'suit_neck', "", "")
#         ]

#         for label1, key1, label2, key2 in pairs:
#             self.cell(col1_width, 6, label1, 1)
#             self.cell(col2_width, 6, self._format_value(data.get(key1)), 1)
#             self.cell(col1_width, 6, label2, 1)
#             self.cell(col2_width, 6, self._format_value(data.get(key2)) if key2 else "", 1, ln=True)

#         self.ln(5)
#         self.set_font('Arial', 'B', 12)
#         self.cell(0, 8, "Accessories:", ln=True)
#         self.set_font('Arial', '', 11)

#         # Basic accessories
#         for acc in ['waistcoat', 'shoes', 'turban']:
#             status = "Yes" if data.get(acc) else "No"
#             self.cell(0, 6, f"{acc.capitalize()}: {status}", ln=True)

#         # Additional JSON accessories
#         accessories = data.get('accessories', {})
#         if isinstance(accessories, str):
#             try:
#                 accessories = json.loads(accessories)
#             except:
#                 accessories = {}

#         for key, value in accessories.items():
#             if value:
#                 acc_name = key.replace('_', ' ').title()
#                 self.cell(0, 6, f"{acc_name}: Yes", ln=True)

#         # Notes
#         notes = data.get('notes', '')
#         if notes.strip():
#             self.ln(5)
#             self.set_font('Arial', 'B', 12)
#             self.cell(0, 8, "Special Notes:", ln=True)
#             self.set_font('Arial', '', 11)
#             self.multi_cell(0, 6, notes)

# def generate_measurements_pdf(customer_name, measurements_data, measurement_type):
#     """Generate PDF for customer measurements"""
#     try:
#         if not customer_name:
#             raise ValueError("Customer name is required")
#         if not measurements_data:
#             raise ValueError("Measurements data is required")
        
#         pdf = MeasurementsPDF(customer_name, measurement_type)
#         pdf.add_page()
        
#         if measurement_type == "Sherwani":
#             pdf.add_sherwani_measurements(measurements_data)
#         elif measurement_type == "Suit":
#             pdf.add_suit_measurements(measurements_data)
#         else:
#             pdf.set_font('Arial', 'B', 16)
#             pdf.cell(0, 10, f"Measurements for {customer_name}", ln=True)
#             pdf.set_font('Arial', '', 12)
#             pdf.cell(0, 10, f"Type: {measurement_type}", ln=True)
        
#         return pdf.output(dest='S').encode('latin-1')
    
#     except Exception as e:
#         error_pdf = FPDF()
#         error_pdf.add_page()
#         error_pdf.set_font('Arial', 'B', 16)
#         error_pdf.cell(0, 10, "Error generating PDF", ln=True)
#         error_pdf.set_font('Arial', '', 12)
#         error_pdf.cell(0, 10, f"Error: {str(e)}", ln=True)
#         error_pdf.cell(0, 10, f"Customer: {customer_name}", ln=True)
#         error_pdf.cell(0, 10, f"Type: {measurement_type}", ln=True)
#         return error_pdf.output(dest='S').encode('latin-1')
    

# # This is the Tailor Ledger PDF Class
# # Tailor Ledger PDF Class
# class TailorLedgerPDF(FPDF):
#     def __init__(self, tailor_name=""):
#         super().__init__(orientation='L', unit='mm', format='A4')
#         self.page_width = 297
#         self.left_margin = 10
#         self.right_margin = 10
#         self.tailor_name = tailor_name  # 🆕 Save tailor name
#         self.set_auto_page_break(auto=True, margin=15)
#         self.theme_color = (23, 24, 22)  # 🟡 Updated color
#         self.alt_row_color = (240, 240, 240)

#     def header(self):
#         logo_path = "static/order_management.jpg"
#         logo_width = 30
#         logo_height = 20  # 🟡 Updated height

#         self.set_fill_color(*self.theme_color)
#         self.rect(0, 0, self.page_width, 25, style='F')

#         if os.path.exists(logo_path):
#             try:
#                 self.image(logo_path, x=self.left_margin, y=5, w=logo_width, h=logo_height)
#             except RuntimeError as e:
#                 print(f"Logo error: {e}")

#         self.set_text_color(166, 124, 33)
#         self.set_font('Arial', 'B', 16)
#         self.set_xy(self.left_margin + logo_width + 5, 8)
#         self.cell(0, 8, "HF DESIGN", ln=True)

#         self.set_font('Arial', '', 11)
#         self.set_x(self.left_margin + logo_width + 5)
#         self.cell(0, 8, f"Tailor Payment Ledger - {self.tailor_name}", ln=True)

#         self.set_text_color(0, 0, 0)
#         self.ln(10)


#     def footer(self):
#         self.set_y(-15)
#         self.set_font("Arial", "I", 8)
#         self.set_text_color(100, 100, 100)
#         self.cell(0, 10, f"Page {self.page_no()} - Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 0, "C")

#     def set_tailor_info(self, name, phone):
#         self.tailor_name = name
#         self.tailor_phone = phone
#         self.set_font("Arial", "I", 11)
#         self.set_text_color(*self.theme_color)
#         self.cell(0, 10, f"Tailor: {name} | Phone: {phone}", ln=True)
#         self.ln(3)

#     def add_payment_table(self, payments):
#         if not payments:
#             self.set_font("Arial", "I", 9)
#             self.cell(0, 8, "No payment records available.", ln=True)
#             return

#         self.set_font("Arial", "B", 9)
#         self.set_fill_color(166, 124, 33)
#         self.set_text_color(255, 255, 255)

#         headers = ["Date", "Amount Paid (Rs.)", "Remarks"]
#         col_widths = [90, 80, 105]

#         for i, header in enumerate(headers):
#             self.cell(col_widths[i], 8, header, border=1, align="C", fill=True)
#         self.ln()

#         self.set_font("Arial", "", 9)
#         self.set_text_color(0, 0, 0)

#         for i, payment in enumerate(payments):
#             is_even = i % 2 == 0
#             bg_color = self.alt_row_color if is_even else (255, 255, 255)
#             self.set_fill_color(*bg_color)

#             date = payment[0].strftime('%Y-%m-%d %I:%M %p')
#             amount = f"Rs. {float(payment[1]):,.2f}"
#             remarks = payment[2] if payment[2] else "-"

#             row = [date, amount, remarks]
#             for j, val in enumerate(row):
#                 self.cell(col_widths[j], 8, val, border=1, fill=True)
#             self.ln()

#         # Totals Row
#         self.set_font("Arial", "B", 9)
#         self.set_fill_color(255, 255, 255)  # Golden background
#         self.set_text_color(0, 0, 0)
#         self.cell(90, 8, "Total", border=1, align="C", fill=True)
#         self.cell(80, 8, f"Rs. {sum(p[1] for p in payments):,.2f}", border=1, align="C", fill=True)
#         self.cell(105, 8, "", border=1, fill=True)
#         self.ln(5)

# # This is the pdf code of Total Purchases by All Customers


# class CustomerLedgerPDF(FPDF):
#     def __init__(self, customer_name=None, display_month_name="Customer Purchase Summary"):
#         super().__init__(orientation='L', unit='mm', format='A4')
#         self.customer_name = customer_name
#         self.display_month_name = display_month_name
#         self.page_width = 297
#         self.set_auto_page_break(auto=True, margin=15)
#         self.theme_color = (37, 38, 35)
#         self.alt_row_color = (240, 240, 240)

#     # ---------------------- HEADER ----------------------  
#     def header(self):
#         logo_path = "static/order_management.jpg"
#         logo_width = 30
#         logo_height = 20

#         self.set_fill_color(*self.theme_color)
#         self.rect(0, 0, self.page_width, 25, style='F')

#         if os.path.exists(logo_path):
#             try:
#                 self.image(logo_path, x=10, y=5, w=logo_width, h=logo_height)
#             except RuntimeError as e:
#                 print(f"Logo error: {e}")

#         self.set_text_color(166, 124, 33)
#         self.set_font('Arial', 'B', 16)
#         self.set_xy(10 + logo_width + 5, 8)
#         self.cell(0, 8, "HF DESIGN", ln=True)

#         self.set_font('Arial', '', 11)
#         self.set_x(10 + logo_width + 5)
#         label = f"Customer Ledger - {self.customer_name} - {self.display_month_name}" if self.customer_name else self.display_month_name
#         self.cell(0, 8, label, ln=True)

#         self.set_text_color(0, 0, 0)
#         self.ln(10)

#     # ---------------------- FOOTER ----------------------
#     def footer(self):
#         self.set_y(-15)
#         self.set_font("Arial", "I", 8)
#         self.set_text_color(100, 100, 100)
#         now = datetime.now().strftime('%Y-%m-%d %I:%M %p')
#         self.cell(0, 10, f"Page {self.page_no()} - Generated on {now}", 0, 0, "C")

#     # ---------------------- OVERALL TOTAL ----------------------
#     def add_overall_total(self, grand_total):
#         self.set_font("Arial", "B", 12)
#         self.set_text_color(*self.theme_color)
#         self.cell(0, 10, f"Total Purchases by All Customers: Rs. {grand_total:,.2f}", ln=True)
#         self.set_text_color(0, 0, 0)
#         self.ln(3)

#     # ---------------------- CUSTOMER SECTION ----------------------
#     def add_customer_section(self, customer_name, sales, total):
#         self.set_font("Arial", "B", 11)
#         self.set_text_color(*self.theme_color)
#         self.cell(0, 8, f"Customer: {customer_name}", ln=True)
#         self.set_text_color(0, 0, 0)

#         if not sales:
#             self.set_font("Arial", "I", 10)
#             self.cell(0, 8, "No orders found.", ln=True)
#             return

#         # Table header
#         self.set_font("Arial", "B", 10)
#         self.set_fill_color(*self.theme_color)
#         self.set_text_color(166, 124, 33)
#         self.cell(40, 8, "Order ID", border=1, fill=True)
#         self.cell(70, 8, "Date & Time", border=1, fill=True)
#         self.cell(60, 8, "Order Amount (Rs.)", border=1, fill=True)
#         self.ln()

#         # Table rows
#         self.set_font("Arial", "", 10)
#         self.set_text_color(0, 0, 0)
#         for i, (sale_id, total_price, sale_date) in enumerate(sales):
#             bg_color = self.alt_row_color if i % 2 == 0 else (255, 255, 255)
#             self.set_fill_color(*bg_color)
#             formatted_date = sale_date.strftime('%Y-%m-%d %I:%M %p') if isinstance(sale_date, datetime) else str(sale_date)

#             self.cell(40, 8, f"Order #{sale_id}", border=1, fill=True)
#             self.cell(70, 8, formatted_date, border=1, fill=True)
#             self.cell(60, 8, f"Rs. {total_price:,.2f}", border=1, fill=True)
#             self.ln()

#         # Totals
#         self.set_font("Arial", "B", 10)
#         self.set_fill_color(245, 245, 245)
#         self.cell(110, 8, "Total", border=1, fill=True)
#         self.cell(60, 8, f"Rs. {total:,.2f}", border=1, fill=True)
#         self.ln(10)

#     # ---------------------- LEDGER TABLE (Optional) ----------------------
#     def add_ledger_table(self, ledger_data):
#         if not ledger_data:
#             self.set_font("Arial", "I", 10)
#             self.cell(0, 10, "No transactions available.", ln=True)
#             return

#         headers = ["S.No", "Date", "TYPE", "Products", "Method", "Debit", "Credit", "Balance"]
#         col_widths = [12, 25, 70, 45, 30, 25, 25, 30]

#         self.set_font("Arial", "B", 9)
#         self.set_fill_color(*self.theme_color)
#         self.set_text_color(255, 255, 255)
#         for i, header in enumerate(headers):
#             self.cell(col_widths[i], 8, header, border=1, align="C", fill=True)
#         self.ln()

#         self.set_font("Arial", "", 8)
#         self.set_text_color(0, 0, 0)
#         for i, row in enumerate(ledger_data):
#             bg_color = self.alt_row_color if i % 2 == 0 else (255, 255, 255)
#             self.set_fill_color(*bg_color)

#             values = [
#                 str(row['S.No']),
#                 row['Date'],
#                 row['TYPE'][:40],
#                 row['Products'][:30],
#                 row['Method'],
#                 f"{row['Debit']:.0f}",
#                 f"{row['Credit']:.0f}",
#                 f"{row['Balance']:.0f}"
#             ]
#             for j, val in enumerate(values):
#                 align = "L" if j in [2, 3] else "C"
#                 self.cell(col_widths[j], 8, val, border=1, align=align, fill=True)
#             self.ln()

#     # ------------------------ ADD CUSTOMER TAB ------------------------
# # ------------------------ ADD / UPDATE CUSTOMER TAB ------------------------
# def show_add_update_customer_section():
#     st.header("👤 Customer Management")

#     action = st.radio("Select Action", ["Add Customer", "Update Customer"], horizontal=True)
#     st.markdown("---")

#     if action == "Add Customer":
#         with st.form('add_customer_form'):
#             col1, col2 = st.columns(2)

#             with col1:
#                 customer_name = st.text_input('Customer Name *', placeholder="Enter full name")
#                 phone_number = st.text_input('Phone Number *', placeholder="03XXXXXXXXX")

#             with col2:
#                 email = st.text_input('Email (Optional)', placeholder="customer@email.com")
#                 address = st.text_area('Address (Optional)', placeholder="Complete address")

#             submit_customer = st.form_submit_button('🔥 Add Customer')

#             if submit_customer:
#                 if customer_name and phone_number:
#                     try:
#                         add_customer_to_db(customer_name, phone_number, email, address)
#                         st.success(f'✅ {customer_name} added successfully!')
#                         st.balloons()
#                         st.rerun()
#                     except Exception as e:
#                         st.error(f"❌ Error adding customer: {str(e)}")
#                 else:
#                     st.warning("⚠️ Please fill in required fields (Name & Phone)")

#     elif action == "Update Customer":
#         st.subheader("✏️ Update Customer Information")
        
#         conn = get_db_connection()
#         cursor = conn.cursor()
#         cursor.execute("SELECT id, customer_name, customer_number FROM customers")
#         customers = cursor.fetchall()
#         conn.close()

#         if customers:
#             customer_dict = {f"{c[1]} - {c[2]}": c[0] for c in customers}
#             selected_customer = st.selectbox("Select a customer to update:", list(customer_dict.keys()))

#             if selected_customer:
#                 customer_id = customer_dict[selected_customer]
#                 selected_name, selected_number = selected_customer.rsplit(" - ", 1)

#                 col1, col2 = st.columns(2)
#                 with col1:
#                     updated_name = st.text_input("Update Customer Name", selected_name)
#                 with col2:
#                     updated_number = st.text_input("Update Customer Number", selected_number)

#                 if st.button("Update Customer"):
#                     update_customer(customer_id, updated_name, updated_number)
#                     st.success(f"✅ Customer '{updated_name}' updated successfully!")
#                     st.rerun()
#         else:
#             st.info("No customers available to update.")

#     # Show all customers at bottom
#     st.markdown("---")
#     st.subheader("📋 Existing Customers")

#     customers = get_all_customers()
#     if customers:
#         customer_data = [{"Name": c[1], "Phone": c[2]} for c in customers]
#         st.table(customer_data)
#     else:
#         st.info("No customers found in the database.")




# # ------------------------ COAT MANAGEMENT TAB ------------------------
# def show_coat_management_section():
#     st.header("🧥 Coat Type Management")
    
#     # Initialize editing state if not exists
#     if 'editing_coat_id' not in st.session_state:
#         st.session_state.editing_coat_id = None
    
#     # Add new coat type section
#     with st.expander("➕ Add New Coat Type", expanded=True):
#         with st.form('add_coat_form'):
#             col1, col2 = st.columns([2, 3])
            
#             with col1:
#                 coat_name = st.text_input('Coat Type Name *', placeholder="e.g., Waistcoat, American Collar")
            
#             with col2:
#                 description = st.text_input('Description (Optional)', placeholder="e.g., Regular fit, Double breasted style")
            
#             submit_coat = st.form_submit_button('🔥 Add Coat Type')
            
#             if submit_coat:
#                 if coat_name:
#                     try:
#                         add_coat_type_to_db(coat_name, description)
#                         st.success(f'✅ {coat_name} added successfully!')
#                         st.rerun()
#                     except Exception as e:
#                         st.error(f"❌ Error adding coat type: {str(e)}")
#                 else:
#                     st.warning("⚠️ Please enter coat type name")
    
#     # Display existing coat types
#     st.subheader("📋 Existing Coat Types")
    
#     coat_types = get_all_coat_types()
    
#     if not coat_types:
#         st.info("🧥 No coat types found. Add some coat types above.")
#     else:
#         # Create a table to display coat types
#         for coat in coat_types:
#             coat_id, coat_name, coat_description = coat
            
#             # Check if this coat is being edited
#             is_editing = st.session_state.editing_coat_id == coat_id
            
#             if is_editing:
#                 # Show edit form
#                 with st.form(f'edit_coat_form_{coat_id}'):
#                     st.write(f"**Editing: {coat_name}**")
#                     edit_col1, edit_col2, edit_col3, edit_col4 = st.columns([2, 3, 1, 1])
                    
#                     with edit_col1:
#                         new_name = st.text_input('Name', value=coat_name, key=f'edit_name_{coat_id}')
                    
#                     with edit_col2:
#                         new_desc = st.text_input('Description', value=coat_description if coat_description else '', key=f'edit_desc_{coat_id}')
                    
#                     with edit_col3:
#                         if st.form_submit_button('💾 Save'):
#                             if new_name.strip():
#                                 try:
#                                     update_coat_type(coat_id, new_name, new_desc)
#                                     st.success(f"✅ {new_name} updated successfully!")
#                                     st.session_state.editing_coat_id = None
#                                     st.rerun()
#                                 except Exception as e:
#                                     st.error(f"❌ Error updating coat type: {str(e)}")
#                             else:
#                                 st.error("❌ Name cannot be empty")
                    
#                     with edit_col4:
#                         if st.form_submit_button('❌ Cancel'):
#                             st.session_state.editing_coat_id = None
#                             st.rerun()
            
#             else:
#                 # Show display mode
#                 col1, col2, col3, col4 = st.columns([2, 3, 1, 1])
                
#                 with col1:
#                     st.write(f"**{coat_name}**")
                
#                 with col2:
#                     st.write(coat_description if coat_description else "No description")
                
#                 with col3:
#                     if st.button("✏️", key=f"edit_coat_{coat_id}", help="Edit coat type"):
#                         st.session_state.editing_coat_id = coat_id
#                         st.rerun()
                
#                 with col4:
#                     if st.button("🗑️", key=f"delete_coat_{coat_id}", help="Delete coat type"):
#                         try:
#                             delete_coat_type(coat_id)
#                             st.success(f"✅ {coat_name} deleted successfully!")
#                             st.rerun()
#                         except Exception as e:
#                             st.error(f"❌ Error deleting coat type: {str(e)}")
            
#             st.markdown("---")

# # ------------------------ MEASUREMENTS TAB ------------------------

# def create_measurement_form(measurement_type, existing_measurements, customer_id, customer_name):
#     """Create a unified measurement form for both Sherwani and Suit"""
    
#     # Define measurement fields for each type
#     if measurement_type == "sherwani":
#         fields = {
#             "main_measurements": [
#                 ("Length", "sherwani_length", "L."),
#                 ("Shalwar Length", "shalwar_length", "L."),
#                 ("Chest", "chest", "CH."),
#                 ("Width", "sherwani_width", "WT."),
#                 ("Waist", "waist", "W."),
#                 ("Shoulder", "shoulder", "SHL."),
#                 ("Thigh", "sherwani_thigh", "TH."),
#                 ("Sleeve", "sleeve_length", "SLV."),
#                 ("Knee", "sherwani_knee", "KN."),
#                 ("Neck", "neck", "N."),
#                 ("Bottom", "sherwani_bottom", "BT.")
#             ],
#             "accessories": [
#                 ("Kurta Pajama", "kurta_pajama"),
#                 ("Churidar", "churidar"),
#                 ("Dupatta", "dupatta"),
#                 ("Sehra", "sehra"),
#                 ("Khussa", "khussa"),
#                 ("Mojari", "mojari")
#             ]
#         }
#     else:  # suit
#         fields = {
#             "main_measurements": [
#                 ("Coat Length", "suit_length", "L."),
#                 ("Pant Length", "suit_pant_length", "L."),
#                 ("Chest", "suit_chest", "CH."),
#                 ("Pant Width", "suit_pant_width", "WT."),
#                 ("Waist", "suit_waist", "W."),
#                 ("Pant Height", "suit_pant_height", "H."),
#                 ("Shoulder", "suit_shoulder", "SHL."),
#                 ("Thigh", "suit_thigh", "TH."),
#                 ("Sleeve", "suit_sleeve", "SLV."),
#                 ("Knee", "suit_knee", "KN."),
#                 ("Neck", "suit_neck", "N."),
#                 ("Bottom", "suit_bottom", "BT.")
#             ],
#             "accessories": [
#                 ("Blazer", "blazer"),
#                 ("Vest", "vest"),
#                 ("Tie", "tie"),
#                 ("Bow Tie", "bow_tie"),
#                 ("Cufflinks", "cufflinks"),
#                 ("Pocket Square", "pocket_square")
#             ]
#         }
    
#     # PDF Generation Button
#     # Replace the existing PDF generation button logic with this:
#     if existing_measurements:
#         if st.button(f"📄 Generate {measurement_type.title()} PDF", key=f"{measurement_type}_pdf_btn"):
#             try:
#                 # Prepare measurements data for PDF
#                 pdf_data = existing_measurements.copy()

#                 # ✅ Inject coat_type_name into data before generating PDF
#                 if measurement_type == "suit":
#                     coat_type_id = pdf_data.get("coat_type_id")
#                     if coat_type_id:
#                         coat_name = get_coat_name_by_id(coat_type_id)
#                         pdf_data["coat_type_name"] = coat_name

#                 # Generate PDF
#                 pdf_bytes = generate_measurements_pdf(customer_name, pdf_data, measurement_type.title())

#                 st.download_button(
#                     label=f"⬇️ Download {measurement_type.title()} PDF",
#                     data=pdf_bytes,
#                     file_name=f"{customer_name}_{measurement_type.title()}_Measurements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
#                     mime="application/pdf",
#                     key=f"download_{measurement_type}_pdf"
#                 )
#                 st.success(f"✅ {measurement_type.title()} PDF generated successfully!")

#             except Exception as e:
#                 st.error(f"❌ Error generating PDF: {str(e)}")
#                 if 'pdf_data' in locals():
#                     st.error(f"Debug coat_type_id: {pdf_data.get('coat_type_id')}")


#     # Measurement Form
#     # Measurement Form
#     with st.form(f'{measurement_type}_measurements_form'):
#         st.markdown(f"### {measurement_type.upper()} MEASUREMENTS")
        
#         measurements = {}
#         selected_coat_id = None  # ✅ Ensure it's defined

#         # Coat Type Selection (only for suits)
#         if measurement_type == "suit":
#             coat_types = get_all_coat_types()
#             if coat_types:
#                 st.markdown("### 🧥 **Select Coat Type**")
#                 coat_options = ["None"] + [
#                     f"{coat[1]} - {coat[2] if coat[2] else 'No description'}" for coat in coat_types
#                 ]
                
#                 # Get current coat type
#                 current_coat_id = existing_measurements.get('coat_type_id')
#                 current_index = 0
#                 if current_coat_id:
#                     for i, coat in enumerate(coat_types):
#                         if coat[0] == current_coat_id:
#                             current_index = i + 1  # +1 because of "None" option
#                             break
                
#                 selected_coat = st.selectbox(
#                     "Coat Style",
#                     coat_options,
#                     index=current_index,
#                     key=f"{measurement_type}_coat_selection",
#                     help="Choose the coat style for this suit"
#                 )
                
#                 if selected_coat != "None":
#                     coat_index = coat_options.index(selected_coat) - 1  # -1 due to "None"
#                     selected_coat_id = coat_types[coat_index][0]
#             else:
#                 st.info("🧥 No coat types available. Add coat types in the Coat Management tab first.")
        
#         col1, col2, col3 = st.columns([2, 2, 1.5])
        
#         # Main Measurements (Left Column)
#         with col1:
#             st.markdown(f"**{measurement_type.title()} Measurements**")
#             for i in range(0, len(fields["main_measurements"]), 2):
#                 row_col1, row_col2 = st.columns(2)
                
#                 with row_col1:
#                     field = fields["main_measurements"][i]
#                     st.markdown(f"**{field[2]}**")
#                     measurements[field[1]] = st.number_input(
#                         field[0],
#                         value=float(existing_measurements.get(field[1], 0.0)),
#                         min_value=0.0, step=0.5,
#                         key=f"{measurement_type}_{field[1]}",
#                         label_visibility="collapsed"
#                     )
                
#                 if i + 1 < len(fields["main_measurements"]):
#                     with row_col2:
#                         field = fields["main_measurements"][i + 1]
#                         st.markdown(f"**{field[2]}**")
#                         measurements[field[1]] = st.number_input(
#                             field[0],
#                             value=float(existing_measurements.get(field[1], 0.0)),
#                             min_value=0.0, step=0.5,
#                             key=f"{measurement_type}_{field[1]}",
#                             label_visibility="collapsed"
#                         )
        
#         # Additional Measurements (Middle Column)
#         with col2:
#             st.markdown("**Additional Measurements**")
#             additional_fields = ["head_size", "shoe_size"]
#             for field in additional_fields:
#                 measurements[field] = st.number_input(
#                     field.replace('_', ' ').title(),
#                     value=float(existing_measurements.get(field, 0.0)),
#                     min_value=0.0, step=0.5,
#                     key=f"{measurement_type}_{field}"
#                 )
            
#             st.markdown("**📝 Notes**")
#             measurements["notes"] = st.text_area(
#                 'Special Instructions',
#                 value=existing_measurements.get('notes', ''),
#                 placeholder="Any special requirements...",
#                 key=f"{measurement_type}_notes"
#             )
        
#         # Accessories (Right Column)
#         with col3:
#             st.markdown("**Accessories**")
#             measurements["waistcoat"] = st.checkbox(
#                 "Waistcoat", 
#                 value=bool(existing_measurements.get('waistcoat', False)),
#                 key=f"{measurement_type}_waistcoat"
#             )
#             measurements["shoes"] = st.checkbox(
#                 "Shoes", 
#                 value=bool(existing_measurements.get('shoes', False)),
#                 key=f"{measurement_type}_shoes"
#             )
#             measurements["turban"] = st.checkbox(
#                 "Turban", 
#                 value=bool(existing_measurements.get('turban', False)),
#                 key=f"{measurement_type}_turban"
#             )
            
#             # Parse existing accessories
#             existing_accessories = existing_measurements.get('accessories', '{}')
#             if isinstance(existing_accessories, str):
#                 try:
#                     accessories_dict = json_lib.loads(existing_accessories)
#                     if not isinstance(accessories_dict, dict):
#                         accessories_dict = {}
#                 except:
#                     accessories_dict = {}
#             elif isinstance(existing_accessories, dict):
#                 accessories_dict = existing_accessories
#             else:
#                 accessories_dict = {}
            
#             accessories_data = {}
#             for acc_name, acc_key in fields["accessories"]:
#                 accessories_data[acc_key] = st.checkbox(
#                     acc_name,
#                     value=accessories_dict.get(acc_key, False),
#                     key=f"{measurement_type}_{acc_key}"
#                 )
#             measurements["accessories"] = json_lib.dumps(accessories_data)
#         st.divider()
#         # Submit Button
#         submit_btn = st.form_submit_button(
#             f'Save {measurement_type.title()} Measurements',
#         )

#         if submit_btn:
#             if measurement_type == "suit":
#                 measurements["coat_type_id"] = selected_coat_id

#             measurements['customer_id'] = customer_id

#             try:
#                 save_customer_measurements(measurements, measurement_type)
#                 st.success(f'✅ {measurement_type.title()} measurements saved for {customer_name}!')
#                 st.rerun()
#             except Exception as e:
#                 st.error(f"❌ Error saving measurements: {str(e)}")


# # ------------------------ MEASUREMENTS TAB ------------------------
# def show_measurements_section():
#     st.header("📏 Customer Measurements")
    
#     customers = get_all_customers()
    
#     if not customers:
#         st.info("👥 No customers found. Please add customers first.")
#     else:
#         # Customer selection
#         customer_options = [f"{c[1]} - {c[2]}" for c in customers]
#         selected_customer = st.selectbox(
#             "Select Customer", 
#             customer_options,
#             help="Choose customer to add/update measurements"
#         )
        
#         if selected_customer:
#             customer_id = customers[customer_options.index(selected_customer)][0]
#             customer_name = selected_customer.split(' - ')[0]
            
#             # Get existing measurements
#             existing_measurements = get_customer_measurements(customer_id)
            
#             st.subheader(f"📐 Measurements for {customer_name}")
            
#             # Create tabs for different measurement types
#             sherwani_tab, suit_tab = st.tabs(["👘 Sherwani", "🤵 Suit"])
            
#             with sherwani_tab:
#                 create_measurement_form("sherwani", existing_measurements, customer_id, customer_name)
            
#             with suit_tab:
#                 create_measurement_form("suit", existing_measurements, customer_id, customer_name)
            
#             # Display measurements summary
#             if existing_measurements:
#                 st.markdown("---")
#                 st.header("Measurements Summary")
                
#                 col1, col2, col3 = st.columns(3)
                
#                 with col1:
#                     st.markdown("**Sherwani:**")
#                     sherwani_fields = ["sherwani_length", "chest", "waist", "shoulder"]
#                     for field in sherwani_fields:
#                         value = existing_measurements.get(field, 0)
#                         if value > 0:
#                             st.write(f"{field.replace('_', ' ').title()}: {value}")
                
#                 with col2:
#                     st.markdown("**Suit:**")
#                     suit_fields = ["suit_length", "suit_chest", "suit_waist", "suit_shoulder"]
#                     for field in suit_fields:
#                         value = existing_measurements.get(field, 0)
#                         if value > 0:
#                             st.write(f"{field.replace('suit_', '').replace('_', ' ').title()}: {value}")
                    
#                     # Display selected coat type
#                     coat_type_id = existing_measurements.get('coat_type_id')
#                     if coat_type_id is not None:

#                         coat_name = get_coat_name_by_id(coat_type_id)
#                         st.write(f"**Coat Style:** {coat_name}")
                
#                 with col3:
#                     st.markdown("**General:**")
#                     st.write(f"Head Size: {existing_measurements.get('head_size', 0)}")
#                     st.write(f"Shoe Size: {existing_measurements.get('shoe_size', 0)}")                    
                
#                 if existing_measurements.get('notes'):
#                     st.markdown("**Notes:**")
#                     st.write(existing_measurements.get('notes'))

# # ------------------------ TAILOR MANAGEMENT TAB ------------------------
# def show_tailor_mgmt_section():
#         st.header("👨‍🔧 Tailor Management")
        
#         col1, col2 = st.columns([1, 1])
        
#         with col1:
#             st.subheader("➕ Add New Tailor")
#             with st.form('add_tailor_form'):
#                 tailor_name = st.text_input('Tailor Name *')
#                 tailor_phone = st.text_input('Phone Number *')
#                 tailor_address = st.text_area('Address')
#                 specialization = st.selectbox('Specialization', 
#                                             ['Cutting', 'Stitching', 'Embroidery', 'Finishing', 'All Types'])
#                 daily_capacity = st.number_input('Daily Capacity (pieces)', min_value=1, value=5)
                
#                 submit_tailor = st.form_submit_button('🔥 Add Tailor')
                
#                 if submit_tailor:
#                     if tailor_name and tailor_phone:
#                         try:
#                             add_tailor_to_db(tailor_name, tailor_phone, tailor_address, 
#                                         specialization, daily_capacity)
#                             st.success(f'✅ {tailor_name} added successfully!')
#                         except Exception as e:
#                             st.error(f"❌ Error adding tailor: {str(e)}")
#                     else:
#                         st.warning("⚠️ Please fill in required fields")
        
#         with col2:
#             st.subheader("👥 Current Tailors")
#             tailors = get_all_tailors()
            
#             if tailors:
#                 for tailor in tailors:
#                     with st.container():
#                         st.markdown(f"""
#                         <div style='
#                             border:1px solid #ddd;
#                             padding:10px;
#                             border-radius:8px;
#                             margin-bottom:8px;
#                             background-color:#bed5ed;
#                         '>
#                         <b>👨‍🔧 {tailor[1]}</b><br>
#                         📞 {tailor[2]}<br>
#                         🎯 {tailor[4]} | 📊 {tailor[5]} pieces/day
#                         </div>
#                         """, unsafe_allow_html=True)
#             else:
#                 st.info("No tailors found. Add some tailors first.")


# # ------------------------ ORDER MANAGEMENT TAB ------------------------
# # ------------------------ ORDER MANAGEMENT TAB ------------------------
# # ------------------------ ORDER MANAGEMENT TAB ------------------------
# def show_order_mgmt_section():
#         st.header("📋 Order Management")
        
#         # Get all orders with item details
#         orders = get_orders_with_item_details()
        
#         if not orders:
#             st.info("📦 No orders found.")
#         else:
#             # Convert to DataFrame for better handling
#             df = pd.DataFrame(orders, columns=[
#                 "Sale_id", "Customer", "Sale_date", "Source", "Paid_amount", "Due_amount", "Total_price",
#                 "Item_id", "Product", "Quantity", "Sale_Price", "Item_total", "Item_Status", "Current_Tailor", "Tailor_assigned_date"
#             ])
            
#             # Group by order ID to get unique orders
#             orders_df = df.groupby("Sale_id").agg({
#                 "Customer": "first",
#                 "Sale_date": "first", 
#                 "Source": "first",
#                 "Paid_amount": "first",
#                 "Due_amount": "first",
#                 "Total_price": "first"
#             }).reset_index()
            
#             # Sort by Sale_date in descending order (newest first)
#             orders_df = orders_df.sort_values("Sale_date", ascending=False)
            
#             # ------------------------ FILTERS & CONTROLS ------------------------
#             col1, col2, col3 = st.columns([2, 1, 1])
            
#             with col1:
#                 # Status filtering
#                 status_filter = st.selectbox(
#                     "🔍 Filter by Status",
#                     ["All", "Pending", "In Progress", "Ready for Delivery", "Delivered", "Mixed Status"],
#                     help="Filter orders by their overall completion status"
#                 )
            
#             with col2:
#                 # Orders per page
#                 orders_per_page = st.selectbox(
#                     "📄 Orders per page",
#                     [10, 20, 50, 100],
#                     index=0
#                 )
            
#             with col3:
#                 # Search by customer or order ID
#                 search_query = st.text_input("🔍 Search", placeholder="Customer name or Order ID")
            
#             # Calculate overall status for each order
#             order_statuses = {}
#             for sale_id in orders_df["Sale_id"]:
#                 status_summary = get_order_completion_status(sale_id)
#                 total_items, delivered_items, pending_items, with_tailor_items, received_items = status_summary
                
#                 if delivered_items == total_items:
#                     overall_status = "Delivered"
#                 elif pending_items == total_items:
#                     overall_status = "Pending"
#                 elif with_tailor_items > 0:
#                     overall_status = "In Progress"
#                 elif received_items > 0:
#                     overall_status = "Ready for Delivery"
#                 else:
#                     overall_status = "Mixed Status"
                
#                 order_statuses[sale_id] = overall_status
            
#             # Apply filters
#             filtered_orders_df = orders_df.copy()
            
#             # Status filter
#             if status_filter != "All":
#                 filtered_orders = [sale_id for sale_id, status in order_statuses.items() if status == status_filter]
#                 filtered_orders_df = filtered_orders_df[filtered_orders_df["Sale_id"].isin(filtered_orders)]
            
#             # Search filter
#             if search_query:
#                 search_mask = (
#                     filtered_orders_df["Customer"].str.contains(search_query, case=False, na=False) |
#                     filtered_orders_df["Sale_id"].astype(str).str.contains(search_query, case=False, na=False)
#                 )
#                 filtered_orders_df = filtered_orders_df[search_mask]
            
#             # ------------------------ PAGINATION LOGIC ------------------------
#             total_orders = len(filtered_orders_df)
#             total_pages = (total_orders - 1) // orders_per_page + 1 if total_orders > 0 else 1
            
#             # Initialize page number in session state
#             if "order_page" not in st.session_state:
#                 st.session_state.order_page = 1
            
#             # Pagination controls
#             if total_orders > 0:
#                 col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
                
#                 with col1:
#                     if st.button("⏮️ First", disabled=st.session_state.order_page == 1):
#                         st.session_state.order_page = 1
#                         st.rerun()
                
#                 with col2:
#                     if st.button("⬅️ Previous", disabled=st.session_state.order_page == 1):
#                         st.session_state.order_page -= 1
#                         st.rerun()
                
#                 with col3:
#                     st.markdown(f"**📄 Page {st.session_state.order_page} of {total_pages}** | **📊 Total Orders: {total_orders}**")
                
#                 with col4:
#                     if st.button("➡️ Next", disabled=st.session_state.order_page == total_pages):
#                         st.session_state.order_page += 1
#                         st.rerun()
                
#                 with col5:
#                     if st.button("⏭️ Last", disabled=st.session_state.order_page == total_pages):
#                         st.session_state.order_page = total_pages
#                         st.rerun()
                
#                 # Reset page if it exceeds total pages
#                 if st.session_state.order_page > total_pages:
#                     st.session_state.order_page = 1
                
#                 # Calculate start and end indices
#                 start_idx = (st.session_state.order_page - 1) * orders_per_page
#                 end_idx = start_idx + orders_per_page
                
#                 # Get orders for current page
#                 current_page_orders = filtered_orders_df.iloc[start_idx:end_idx]
                
#                 st.markdown("---")
                
#                 # ------------------------ DISPLAY ORDERS ------------------------
#                 for idx, row in current_page_orders.iterrows():
#                     sale_id = row["Sale_id"]
#                     customer = row["Customer"]
#                     date = row["Sale_date"]
#                     source = row["Source"]
#                     paid = row["Paid_amount"]
#                     due = row["Due_amount"]
#                     total = row["Total_price"]
#                     overall_status = order_statuses.get(sale_id, "Unknown")
                    
#                     # Get items for this order
#                     items_df = df[df["Sale_id"] == sale_id]
                    
#                     # Status color mapping
#                     status_colors = {
#                         "Pending": "#e74c3c",
#                         "In Progress": "#f39c12", 
#                         "Ready for Delivery": "#2ecc71",
#                         "Delivered": "#3498db",
#                         "Mixed Status": "#9b59b6"
#                     }
#                     badge_color = status_colors.get(overall_status, "#7f8c8d")
                    
#                     # Order container with collapsible design
#                     with st.expander(f"🧾 Order #{sale_id} - {customer} - {overall_status}", expanded=False):
#                         # Order header
#                         st.markdown(f"""
#                         <div style='
#                             border:1px solid #ddd;
#                             padding:15px;
#                             border-radius:10px;
#                             margin-bottom:15px;
#                             background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#                             color: white;
#                         '>
#                         <h4 style='margin:0; color:white;'>📋 Order Details</h4>
#                         <b>👤 Customer:</b> {customer} &nbsp;&nbsp;
#                         <b>🗓 Date:</b> {date} &nbsp;&nbsp;
#                         <b>📱 Source:</b> {source}<br>
#                         <b>💰 Total:</b> Rs. {total:,.2f} &nbsp;&nbsp;
#                         <b>✅ Paid:</b> Rs. {paid:,.2f} &nbsp;&nbsp;
#                         <b>⏳ Due:</b> Rs. {due:,.2f}<br><br>
#                         <b>📦 Overall Status:</b> 
#                         <span style='
#                             background-color:{badge_color};
#                             color:white;
#                             padding:6px 12px;
#                             border-radius:15px;
#                             font-size:14px;
#                             font-weight:bold;
#                         '>{overall_status}</span>
#                         </div>
#                         """, unsafe_allow_html=True)
                        
#                         # Items management
#                         st.markdown("### 📦 Items in this Order")
                        
#                         # Display each item with individual controls
#                         for _, item in items_df.iterrows():
#                             item_id = item["Item_id"]
#                             product_name = item["Product"]
#                             quantity = item["Quantity"]
#                             sale_price = item["Sale_Price"]
#                             item_total = item["Item_total"]
#                             item_status = item["Item_Status"]
#                             current_tailor = item["Current_Tailor"] if pd.notna(item["Current_Tailor"]) else None
                            
#                             # Item status colors
#                             item_status_colors = {
#                                 "Pending": "#e74c3c",
#                                 "Received from Tailor": "#2ecc71",
#                                 "Delivered": "#3498db"
#                             }
                            
#                             if "With" in str(item_status):
#                                 item_badge_color = "#f39c12"
#                             else:
#                                 item_badge_color = item_status_colors.get(item_status, "#7f8c8d")
                            
#                             with st.container():
#                                 st.markdown(f"""
#                                 <div style='
#                                     border:1px solid #e0e0e0;
#                                     padding:10px;
#                                     border-radius:8px;
#                                     margin:5px 0;
#                                     background:#f8f9fa;
#                                 '>
#                                 <b>📋 {product_name}</b> (Qty: {quantity})<br>
#                                 <b>💰 Price:</b> Rs. {sale_price:,.2f} each | <b>🔢 Total:</b> Rs. {item_total:,.2f}<br>
#                                 <b>📊 Status:</b> <span style='background-color:{item_badge_color}; color:white; padding:3px 8px; border-radius:10px; font-size:12px;'>{item_status}</span>
#                                 {f"<br><b>👨‍🔧 Current Tailor:</b> {current_tailor}" if current_tailor else ""}
#                                 </div>
#                                 """, unsafe_allow_html=True)
                                
#                                 # Action buttons in columns
#                                 col1, col2, col3 = st.columns([1, 1, 1])
                                
#                                 # Get available tailors
#                                 tailors = get_all_tailors()
                                
#                                 if item_status == "Pending":
#                                     with col1:
#                                         if tailors:
#                                             tailor_options = [f"{t[1]} - {t[4]}" for t in tailors]
#                                             selected_tailor = st.selectbox(
#                                                 "Select Tailor", 
#                                                 tailor_options, 
#                                                 key=f"tailor_select_{item_id}"
#                                             )
                                    
#                                     with col2:
#                                         if st.button("📤 Send to Tailor", key=f"send_{item_id}"):
#                                             if tailors:
#                                                 tailor_id = tailors[tailor_options.index(selected_tailor)][0]
#                                                 tailor_name = tailors[tailor_options.index(selected_tailor)][1]
                                                
#                                                 update_item_status_with_tailor(
#                                                     item_id, 
#                                                     f"With {tailor_name}",
#                                                     tailor_id
#                                                 )
#                                                 update_overall_order_status(sale_id)
#                                                 st.success(f"✅ {product_name} sent to {tailor_name}!")
#                                                 st.rerun()
                                
#                                 elif "With" in str(item_status) and current_tailor:
#                                     with col1:
#                                         if st.button("📥 Receive", key=f"recv_{item_id}"):
#                                             update_item_status_clear_tailor(
#                                                 item_id, 
#                                                 "Received from Tailor"
#                                             )
#                                             update_overall_order_status(sale_id)
#                                             st.success(f"✅ {product_name} received!")
#                                             st.rerun()
                                    
#                                     with col2:
#                                         if tailors:
#                                             available_tailors = [t for t in tailors if t[1] != current_tailor]
#                                             if available_tailors:
#                                                 tailor_options = [f"{t[1]} - {t[4]}" for t in available_tailors]
#                                                 selected_tailor = st.selectbox(
#                                                     "Transfer to", 
#                                                     tailor_options, 
#                                                     key=f"transfer_{item_id}"
#                                                 )
                                                
#                                                 if st.button("🔄 Transfer", key=f"transfer_btn_{item_id}"):
#                                                     tailor_id = available_tailors[tailor_options.index(selected_tailor)][0]
#                                                     tailor_name = available_tailors[tailor_options.index(selected_tailor)][1]
                                                    
#                                                     update_item_status_with_tailor(
#                                                         item_id, 
#                                                         f"With {tailor_name}",
#                                                         tailor_id
#                                                     )
#                                                     add_item_tailor_transfer_history(item_id, current_tailor, tailor_name)
#                                                     update_overall_order_status(sale_id)
#                                                     st.success(f"✅ {product_name} transferred to {tailor_name}!")
#                                                     st.rerun()
                                
#                                 elif item_status == "Received from Tailor":
#                                     with col1:
#                                         if tailors:
#                                             tailor_options = [f"{t[1]} - {t[4]}" for t in tailors]
#                                             selected_tailor = st.selectbox(
#                                                 "Next Tailor", 
#                                                 tailor_options, 
#                                                 key=f"next_tailor_{item_id}"
#                                             )
                                            
#                                             if st.button("📤 Send Next", key=f"send_next_{item_id}"):
#                                                 tailor_id = tailors[tailor_options.index(selected_tailor)][0]
#                                                 tailor_name = tailors[tailor_options.index(selected_tailor)][1]
                                                
#                                                 update_item_status_with_tailor(
#                                                     item_id, 
#                                                     f"With {tailor_name}",
#                                                     tailor_id
#                                                 )
#                                                 update_overall_order_status(sale_id)
#                                                 st.success(f"✅ {product_name} sent to {tailor_name}!")
#                                                 st.rerun()
                                    
#                                     with col2:
#                                         if st.button("🚚 Deliver", key=f"deliver_{item_id}"):
#                                             update_item_status_clear_tailor(
#                                                 item_id, 
#                                                 "Delivered"
#                                             )
#                                             update_overall_order_status(sale_id)
#                                             st.success(f"✅ {product_name} delivered!")
#                                             st.rerun()
                                
#                                 elif item_status == "Delivered":
#                                     with col1:
#                                         st.success("✅ Item Delivered")
                                
#                                 # Timeline and history with toggle buttons
#                                 with col3:
#                                     if st.button("📈 Timeline", key=f"timeline_btn_{item_id}"):
#                                         st.session_state[f"show_timeline_{item_id}"] = not st.session_state.get(f"show_timeline_{item_id}", False)
                                    
#                                     if st.button("🔄 History", key=f"history_btn_{item_id}"):
#                                         st.session_state[f"show_history_{item_id}"] = not st.session_state.get(f"show_history_{item_id}", False)
                                
#                                 # Show timeline if toggled
#                                 if st.session_state.get(f"show_timeline_{item_id}", False):
#                                     with st.container():
#                                         st.markdown("**📈 Timeline:**")
#                                         timeline = get_item_timeline(item_id)
#                                         if timeline:
#                                             for entry in timeline:
#                                                 status, tailor_name, notes, created_at = entry
#                                                 tailor_info = f" - {tailor_name}" if tailor_name else ""
#                                                 st.text(f"🕐 {created_at}: {status}{tailor_info}")
#                                         else:
#                                             st.info("No timeline data")
                                
#                                 # Show transfer history if toggled
#                                 if st.session_state.get(f"show_history_{item_id}", False):
#                                     transfer_history = get_item_tailor_transfer_history(item_id)
#                                     if transfer_history:
#                                         with st.container():
#                                             st.markdown("**🔄 Transfer History:**")
#                                             for transfer in transfer_history:
#                                                 st.text(f"📋 {transfer[2]} → {transfer[3]} on {transfer[4]}")
#                                     else:
#                                         st.info("No transfer history")
                                
#                                 st.markdown("---")
                
#                 # Bottom pagination controls
#                 if total_pages > 1:
#                     st.markdown("---")
#                     col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
                    
#                     with col1:
#                         if st.button("⏮️ First ", disabled=st.session_state.order_page == 1):
#                             st.session_state.order_page = 1
#                             st.rerun()
                    
#                     with col2:
#                         if st.button("⬅️ Previous ", disabled=st.session_state.order_page == 1):
#                             st.session_state.order_page -= 1
#                             st.rerun()
                    
#                     with col3:
#                         st.markdown(f"**📄 Page {st.session_state.order_page} of {total_pages}**")
                    
#                     with col4:
#                         if st.button("➡️ Next ", disabled=st.session_state.order_page == total_pages):
#                             st.session_state.order_page += 1
#                             st.rerun()
                    
#                     with col5:
#                         if st.button("⏭️ Last ", disabled=st.session_state.order_page == total_pages):
#                             st.session_state.order_page = total_pages
#                             st.rerun()
            
#             else:
#                 st.info("📭 No orders found matching your criteria.")
                
#                 # Reset filters button
#                 if st.button("🔄 Reset Filters"):
#                     st.session_state.order_page = 1
#                     st.rerun()

#     # ------------------------ ASSIGNED TAILORS TAB ------------------------
# def show_assigned_tailors_section():
#         st.header("🧵 Assigned Tailors & Their Items")

#         try:
#             assigned_data = get_items_assigned_to_tailors()
#             if not assigned_data:
#                 st.info("No items currently assigned to tailors.")
#             else:
#                 # Convert to DataFrame
#                 df = pd.DataFrame(assigned_data, columns=[
#                     "Tailor", "Order ID", "Customer", "Product", "Quantity", "Status", "Assigned Date", "Item Total"
#                 ])

#                 grouped = df.groupby("Tailor")

#                 for tailor, items in grouped:
#                     # Count items with this tailor
#                     item_count = len(items)
#                     total_value = items["Item Total"].sum()
                    
#                     st.markdown(f"### 👨‍🔧 {tailor} ({item_count} items - Rs. {total_value:,.2f})")
                    
#                     # Style the table
#                     styled_items = items[["Order ID", "Customer", "Product", "Quantity", "Status", "Assigned Date", "Item Total"]].rename(columns={
#                         "Order ID": "Order #",
#                         "Customer": "Customer",
#                         "Product": "Product Name",
#                         "Quantity": "Qty",
#                         "Status": "Status",
#                         "Assigned Date": "Assigned On",
#                         "Item Total": "Value (Rs.)"
#                     })
                    
#                     st.table(styled_items)
#                     st.markdown("---")
                    
#         except Exception as e:
#             st.error(f"Error fetching assigned tailor data: {e}")

#         # ------------------------ TAILORS PAYMENT / LEDGER TAB ------------------------

# def show_tailor_payment_section():
#     st.header("Weekly Tailor Payments")

#     tailors = get_all_tailors_as_dict()
#     tailor_options = {tailor['name']: tailor['id'] for tailor in tailors}

#     selected_tailor_name = st.selectbox("Select Tailor", list(tailor_options.keys()))
#     amount = st.number_input("Amount Paid", min_value=0.0, format="%.2f")
#     remarks = st.text_area("Remarks (optional)")

#     if st.button("Pay Now"):
#         tailor_id = tailor_options[selected_tailor_name]
#         record_tailor_payment(tailor_id, amount, remarks)
#         st.success(f"Payment of Rs. {amount} made to {selected_tailor_name}")

#     st.subheader("Tailor Payment Ledger")
#     selected_tailor_ledger = tailor_options[selected_tailor_name]
#     ledger = get_tailor_payments(selected_tailor_ledger)

#     if ledger:
#         df = pd.DataFrame(ledger, columns=['Date', 'Amount', 'Remarks'])
#         df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%d-%b-%Y')
#         total_amount = df['Amount'].sum()

#         # Show table
#         st.table(df)

#         # Show total
#         st.markdown(f"""
#         **Total Amount Paid:** Rs. {total_amount:,.2f}
#         """)

#         # PDF Generation Section
#         if st.button("📄 Generate Tailor Ledger PDF"):
#             import io

#             pdf = TailorLedgerPDF()
#             pdf.tailor_name = selected_tailor_name
#             pdf.add_page()
#             pdf.set_tailor_info(selected_tailor_name, "")  # Optional: add phone

#             # Format ledger for PDF
#             formatted_ledger = []
#             for row in ledger:
#                 payment_date = row[0]  # assuming datetime
#                 amount_paid = float(row[1])
#                 note = row[2] if row[2] else "-"
#                 formatted_ledger.append((payment_date, amount_paid, note))

#             pdf.add_payment_table(formatted_ledger)

#             pdf_buffer = io.BytesIO()
#             pdf_output = pdf.output(dest='S').encode('latin-1')
#             pdf_buffer.write(pdf_output)
#             pdf_buffer.seek(0)

#             st.download_button(
#                 label="⬇️ Download Tailor Ledger PDF",
#                 data=pdf_buffer,
#                 file_name=f"{selected_tailor_name}_Tailor_Ledger.pdf",
#                 mime="application/pdf"
#             )

#     else:
#         st.info("No payment records found for this tailor.")

#     # ------------------------ CUSTOMER PURCHASE SUMMARY TAB ------------------------
# # ------------------------ CUSTOMER PURCHASE SUMMARY TAB ------------------------
# def show_customer_summary_section():
#     st.header("📊 Customer Purchase Summary")

#     # Fetch all customers
#     customers = fetch_customers()  # [(id, name), ...]

#     if not customers:
#         st.info("No customers found.")
#     else:
#         # ------------------------ CALENDAR FILTER SECTION ------------------------
#         st.subheader("📅 Filter by Date Range")
        
#         # Create two columns for date inputs
#         col1, col2 = st.columns(2)
        
#         with col1:
#             start_date = st.date_input(
#                 "📅 Start Date",
#                 value=datetime.now().date() - timedelta(days=30),  # Default to last 30 days
#                 key="customer_summary_start_date"
#             )
        
#         with col2:
#             end_date = st.date_input(
#                 "📅 End Date",
#                 value=datetime.now().date(),
#                 key="customer_summary_end_date"
#             )
        
#         # Validate date range
#         if start_date > end_date:
#             st.error("❌ Start date cannot be after end date!")
#             st.stop()
        
#         # Convert dates to datetime for comparison
#         start_datetime = datetime.combine(start_date, datetime.min.time())
#         end_datetime = datetime.combine(end_date, datetime.max.time())
        
#         st.markdown(f"**Showing data from {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}**")
#         st.markdown("---")

#         total_purchases_all_customers = 0.0

#         # Pre-fetch all sales once to avoid repeated DB calls
#         all_sales_data = {}
#         for _, customer_name in customers:
#             all_sales = get_filtered_sales(None, customer_name, "All")
#             # Filter sales by date range
#             filtered_sales = []
#             if all_sales:
#                 for sale in all_sales:
#                     sale_datetime = sale[7]  # Assuming index 7 is the datetime
#                     # Convert sale_datetime to datetime if it's not already
#                     if isinstance(sale_datetime, str):
#                         try:
#                             sale_datetime = datetime.strptime(sale_datetime, '%Y-%m-%d %H:%M:%S')
#                         except ValueError:
#                             try:
#                                 sale_datetime = datetime.strptime(sale_datetime, '%Y-%m-%d')
#                             except ValueError:
#                                 continue  # Skip this sale if date parsing fails
#                     elif not isinstance(sale_datetime, datetime):
#                         continue  # Skip if not a valid datetime
                    
#                     # Check if sale is within date range
#                     if start_datetime <= sale_datetime <= end_datetime:
#                         filtered_sales.append(sale)
            
#             all_sales_data[customer_name] = filtered_sales

#         # --- PDF GENERATION BUTTON (Moved to Top) ---
#         if st.button("📄 Download PDF Ledger"):
#             pdf = CustomerLedgerPDF(f"Customer Purchase Summary ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})")
#             pdf.add_page()

#             # Calculate total purchases across all customers
#             for sales in all_sales_data.values():
#                 if sales:
#                     total_purchases_all_customers += sum(float(s[3]) for s in sales)

#             pdf.add_overall_total(total_purchases_all_customers)

#             # Add customer-wise breakdown
#             for customer_id, customer_name in customers:
#                 sales = all_sales_data.get(customer_name)
#                 if sales:
#                     total = 0.0
#                     summary_lines = []
#                     for sale in sales:
#                         sale_id = sale[0]
#                         total_price = float(sale[3])
#                         sale_date = sale[7]
#                         summary_lines.append((sale_id, total_price, sale_date))
#                         total += total_price
#                     pdf.add_customer_section(customer_name, summary_lines, total)

#             # Save and offer download
#             pdf_output = f"customer_purchase_summary_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}.pdf"
#             pdf_path = os.path.join("/tmp", pdf_output)
#             pdf.output(pdf_path)

#             with open(pdf_path, "rb") as f:
#                 st.download_button(
#                     label="📥 Click to Download PDF",
#                     data=f,
#                     file_name=pdf_output,
#                     mime="application/pdf"
#                 )

#         # Calculate total purchases across all customers (for display)
#         total_purchases_all_customers = 0.0
#         for sales in all_sales_data.values():
#             if sales:
#                 total_purchases_all_customers += sum(float(s[3]) for s in sales)

#         # Display overall total with date range info
#         st.markdown(
# f"""
# <div style="background-color:#b6dde0;padding:1rem;border-left:5px solid #00b894;border-radius:5px;">
#     <h3 style="color:#2d3436;margin:0;">
#         🧮 Total Purchases by All Customers: Rs. {total_purchases_all_customers:,.2f}
#     </h3>
#     <p style="color:#636e72;margin:0.5rem 0 0 0;font-size:0.9rem;">
#         📅 Period: {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}
#     </p>
# </div>
# """,
# unsafe_allow_html=True
# )

#         st.markdown("---")

#         # Show breakdown per customer
#         customers_with_sales = False
#         for customer_id, customer_name in customers:
#             sales = all_sales_data.get(customer_name)
#             if sales:
#                 customers_with_sales = True
#                 st.markdown(f"### 🧍 Customer: **{customer_name}**")
#                 st.markdown("**ORDER # | 🕒 DATE & TIME | 💰 ORDER PRICE**")
#                 total = 0.0

#                 for sale in sales:
#                     sale_id = sale[0]
#                     total_price = float(sale[3])
#                     sale_datetime = sale[7]
#                     formatted_date = sale_datetime.strftime('%Y-%m-%d %I:%M %p') if isinstance(sale_datetime, datetime) else str(sale_datetime)
                    
#                     st.markdown(f"🧾 **Order #{sale_id}** | 🕒 {formatted_date} | 💰 Rs. {total_price:,.2f}")
#                     total += total_price

#                 st.success(f"**🧮 Total Purchases by {customer_name}: Rs. {total:,.2f}**")
#                 st.markdown("---")
        
#         # Show message if no sales found in the selected date range
#         if not customers_with_sales:
#             st.info(f"📅 No sales found for the selected date range ({start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')})")
#             st.markdown("💡 **Tip:** Try selecting a different date range or check if there are any sales recorded in your system.")
    
# def order_management_page():
#     st.title("🧵 HF DESIGNS — Order Management")
#     # Back button to return to the homepage
#     if st.button("Back to Home"):
#         go_to_page("Home")
#     # Sidebar sub-navigation using buttons
#     with st.sidebar:
#         st.markdown("---")
#         st.subheader("📂 Order Management Menu")

#         order_mgmt_tabs = [
#             "Add / Update Customer",
#             "Coat Management",
#             "Customer Measurements",
#             "Tailor Management",
#             "Order Management",
#             "Assigned Tailors",
#             "Tailor Payments / Ledger",
#             "Customer Purchase Summary"
#         ]

#         # Initialize selected tab if not already set
#         if "selected_om_tab" not in st.session_state:
#             st.session_state.selected_om_tab = order_mgmt_tabs[0]

#         # Render buttons for navigation
#         for tab in order_mgmt_tabs:
#             if st.button(tab, key=f"btn_{tab}", use_container_width=True):
#                 st.session_state.selected_om_tab = tab
#                 st.rerun()

#     # Get the currently selected tab from session state
#     selected_om_tab = st.session_state.selected_om_tab

#     # Route to the correct section
#     if selected_om_tab == "Add / Update Customer":
#         show_add_update_customer_section()
#     elif selected_om_tab == "Coat Management":
#         show_coat_management_section()
#     elif selected_om_tab == "Customer Measurements":
#         show_measurements_section()
#     elif selected_om_tab == "Tailor Management":
#         show_tailor_mgmt_section()
#     elif selected_om_tab == "Order Management":
#         show_order_mgmt_section()
#     elif selected_om_tab == "Assigned Tailors":
#         show_assigned_tailors_section()
#     elif selected_om_tab == "Tailor Payments / Ledger":
#         show_tailor_payment_section()
#     elif selected_om_tab == "Customer Purchase Summary":
#         show_customer_summary_section()

        
# # go back to home function 
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