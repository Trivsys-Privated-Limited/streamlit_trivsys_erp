import calendar
from datetime import datetime
import decimal
import tempfile
import streamlit as st
import pandas as pd
from credit_sales import fetch_credit_sales_history, fetch_customers, fetch_payments_for_sale, get_customer_balance
from database import get_db_connection, fetch_sessions
import warnings
from purchase import fetch_grouped_purchase_orders
warnings.filterwarnings("ignore", category=UserWarning, message="pandas only supports SQLAlchemy connectable")
from database import *
import time
import plotly.express as px
from sales import get_filtered_sales, fetch_payments_to_customer, fetch_payments_for_sales, record_payment_to_customer, fetch_filtered_expenses
from fpdf import FPDF

# Define business_name based on tenant session state
if "tenant" in st.session_state and hasattr(st.session_state.tenant, "business_name"):
    business_name = st.session_state.tenant.business_name.upper()
else:
    business_name = "DEFAULT_NAME"

# Calculate total_sales using the imported function
def ledgers_page():
    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.rerun()

    st.markdown("### Ledgers & Reports")
    
    if 'sub_menu' not in st.session_state:
        st.session_state.sub_menu = "Customer Ledgers"
    with st.sidebar:
    # Navigation buttons
        menu_items = [
            "Customer Ledgers",
            "Main Ledger",
            "POS Sessions History"
        ]
                
        for item in menu_items:
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.sub_menu = item
                st.rerun()

    
    
    # =====CUSTOMER LEDGER======
    if st.session_state.sub_menu == "Customer Ledgers":
        st.header("Customer Ledger")

        # --- Fetch active customers (those with at least one sale) ---
        customers = fetch_customers()
        active_customers = []
        for customer_id, customer_name in customers:
            if get_filtered_sales(None, customer_name, "All"):
                active_customers.append((customer_id, customer_name))
        customer_names = [name for _, name in active_customers]

        col1,col2,col3 = st.columns(3)
        # --- Select Customer ---
        
        with col1:
            st.markdown('##### Select Customer')
            selected_customer_name = st.selectbox("Select Customer", customer_names,label_visibility='collapsed')

        # --- Date Filter ---
        today = datetime.now()
        current_year = today.year
        current_month = today.month

        years = list(range(current_year - 4, current_year + 1))
        months = ["Whole Year", "January", "February", "March", "April", "May", "June", 
                "July", "August", "September", "October", "November", "December"]

        with col2:
            st.markdown('##### Select Year')
            selected_year = st.selectbox("Select Year", years, index=len(years) - 1,label_visibility='collapsed')
        with col3:
            st.markdown('##### Select Month')
            selected_month = st.selectbox("Select Month", months, index=current_month,label_visibility='collapsed')

        # --- Determine Date Range ---
        if selected_month == "Whole Year":
            start_date = pd.to_datetime(f"{selected_year}-01-01")
            end_date = pd.to_datetime(f"{selected_year + 1}-01-01")
            display_month_name = str(selected_year)
        else:
            month_num = months.index(selected_month)
            start_date = pd.to_datetime(f"{selected_year}-{month_num:02d}-01")
            end_date = (pd.to_datetime(f"{selected_year + 1}-01-01") if month_num == 12 
                        else pd.to_datetime(f"{selected_year}-{month_num + 1:02d}-01"))
            display_month_name = f"{selected_month} {selected_year}"

        # --- Fetch all sales for the customer ---
        all_sales = get_filtered_sales(None, selected_customer_name, "All")

        # --- Process transactions ---
        all_transactions = []
        for sale in all_sales:
            sale_id, product_names, p_qty, total_price, paid_amount, due_amount, _, sale_date_str, source = sale
            sale_date = pd.to_datetime(sale_date_str)

            # Build products list with quantities in parentheses, e.g. "Product A (2), Product B (1)"
            products_list = ""
            try:
                if product_names:
                    # product_names and p_qty are comma-separated strings from GROUP_CONCAT
                    names = [n.strip() for n in str(product_names).split(',')]
                    qtys = [q.strip() for q in str(p_qty).split(',')] if p_qty else []
                    combined = []
                    for i, name in enumerate(names):
                        qty = qtys[i] if i < len(qtys) else ''
                        if qty != '':
                            combined.append(f"{name} ({qty})")
                        else:
                            combined.append(name)
                    products_list = ', '.join(combined)
                else:
                    products_list = ''
            except Exception:
                # Fallback to raw product_names if any parsing error occurs
                products_list = product_names or ''

            # Sale transaction
            all_transactions.append({
                'date': sale_date,
                'type': 'sale',
                'sale_id': sale_id,
                'source': source,
                'products': products_list,
                'debit': float(total_price),
                'credit': 0.0 if source not in ['POS', 'Sales Module'] else float(total_price)
            })

            # Payments
            additional_payments = fetch_payments_for_sales(sale_id)
            if source not in ['POS', 'Sales Module']:  # Credit sale
                total_followup = sum([float(p[0]) for p in additional_payments])
                initial_payment = float(paid_amount) - total_followup
                if initial_payment > 0:
                    all_transactions.append({
                        'date': sale_date,
                        'type': 'initial_payment',
                        'sale_id': sale_id,
                        'products': "",  # No products for payment transactions
                        'debit': 0.0,
                        'credit': initial_payment,
                        'payment_method': 'Cash',  # Default for initial payments
                        'payment_note': 'Initial payment at time of sale'
                    })

            # Process additional payments with payment method and note
            for payment_data in additional_payments:
                # Handle different payment data formats
                if len(payment_data) >= 4:  # New format with payment_method and note
                    amount, pay_date, payment_method, payment_note = payment_data[:4]
                    # Skip automatic return payments
                    is_automatic_return = (
                        payment_method == 'Return Credit' or
                        'Auto payment from return' in (payment_note or '')
                    )
                    if is_automatic_return:
                        continue  # Skip this payment as it's automatic from return
                else:
                    # Fallback for old format
                    amount, pay_date = payment_data[:2]
                    payment_method = 'Cash'  # Default for old records
                    payment_note = None
                
                all_transactions.append({
                    'date': pd.to_datetime(pay_date),
                    'type': 'payment',
                    'sale_id': sale_id,
                    'products': "",  # No products for payment transactions
                    'debit': 0.0,
                    'credit': float(amount),
                    'payment_method': payment_method,
                    'payment_note': payment_note
                })

        # --- Fetch returns for the customer ---
        try:
            # Fetch all returns from the returns table
            all_returns = fetch_returns_from_returns_table()
            
            # Filter returns for the selected customer
            customer_returns = [r for r in all_returns if r.get('customer_name') == selected_customer_name]
            
            # Add return transactions
            for return_item in customer_returns:
                return_date = pd.to_datetime(return_item['return_date'])
                return_amount = float(return_item['return_amount'])
                product_name = return_item['product_name']
                quantity = return_item['quantity']
                sale_id = return_item['sale_id']
                reason = return_item.get('reason', '')
                
                # Add return transaction (Credit reduces customer's debt)
                all_transactions.append({
                    'date': return_date,
                    'type': 'return',
                    'sale_id': sale_id,
                    'source': 'Return',
                    'products': f"{product_name} (Qty: {quantity})",
                    'debit': 0.0,
                    'credit': return_amount,
                    'return_reason': reason
                })
                
        except Exception as e:
            st.warning(f"Could not fetch returns data: {e}")

        # --- Fetch payments made to customer (EXCLUDE automatic return payments) ---
        try:
            customer_payments_to = fetch_payments_to_customer(selected_customer_name)
            
            # Add payment-to-customer transactions (FILTER OUT AUTOMATIC RETURN PAYMENTS)
            for payment in customer_payments_to:
                payment_date = pd.to_datetime(payment['payment_date'])
                payment_amount = float(payment['amount'])
                payment_note = payment.get('note', '')
                
                # SKIP automatic payments created during return process
                is_automatic_return_payment = (
                    'return' in payment_note.lower() or 
                    'refund' in payment_note.lower() or 
                    'sale id' in payment_note.lower() or
                    payment_note.startswith('Excess refund from return')
                )
                
                # Only add manual payments to customer, not automatic ones from returns
                if not is_automatic_return_payment:
                    all_transactions.append({
                        'date': payment_date,
                        'type': 'payment_to_customer',
                        'sale_id': None,
                        'source': 'Company Payment',
                        'products': "",
                        'debit': payment_amount,  # Debit because company is paying customer
                        'credit': 0.0,
                        'payment_note': payment_note
                    })
                
        except Exception as e:
            st.warning(f"Could not fetch payment-to-customer data: {e}")

        # --- Sort by date ---
        all_transactions.sort(key=lambda x: x['date'])

        # --- Opening balance before start_date ---
        opening_balance = sum(t['debit'] - t['credit'] for t in all_transactions if t['date'] < start_date)

        # --- Filter transactions for selected range ---
        monthly_transactions = [t for t in all_transactions if start_date <= t['date'] < end_date]

        # --- Build Ledger Data ---
        ledger_data = []
        running_balance = opening_balance
        serial = 1

        if opening_balance != 0:
            ledger_data.append({
                'S.No': serial,
                'Date': start_date.strftime("%d-%b-%Y"),
                'TYPE': f"Opening Balance for {display_month_name}",
                'Products': "",  # No products for opening balance
                'Method': "",  # No method for opening balance
                'Debit': 0.0 if opening_balance >= 0 else abs(opening_balance),
                'Credit': abs(opening_balance) if opening_balance < 0 else 0.0,
                'Balance': opening_balance
            })
            serial += 1

        for t in monthly_transactions:
            running_balance += t['debit'] - t['credit']
            
            # Enhanced transaction descriptions with payment method
            if t['type'] == 'sale':
                type_desc = f"Sale ID: {t['sale_id']} ({t['source']})"
                products = t['products']
                method = ""  # No method for sales
            elif t['type'] == 'initial_payment':
                type_desc = f"Initial payment for Sale ID {t['sale_id']}"
                products = ""  # No products for payment rows
                method = t.get('payment_method', 'Cash')
            elif t['type'] == 'payment':
                # Show payment method in the transaction description
                payment_method = t.get('payment_method', 'Cash')
                payment_note = t.get('payment_note', '')
                note_text = f" - {payment_note}" if payment_note else ""
                type_desc = f"Payment for Sale ID {t['sale_id']} ({payment_method}){note_text}"
                products = ""  # No products for payment rows
                method = payment_method
            elif t['type'] == 'return':
                # Handle return transactions
                reason_text = f" - {t.get('return_reason', '')}" if t.get('return_reason') else ""
                type_desc = f"Return for Sale ID {t['sale_id']}{reason_text}"
                products = t['products']  # This will show the returned product and quantity
                method = ""  # No method for returns
            elif t['type'] == 'payment_to_customer':
                # Handle payment to customer (only manual ones now)
                note_text = f" - {t.get('payment_note', '')}" if t.get('payment_note') else ""
                type_desc = f"Payment to Customer{note_text}"
                products = ""
                method = ""
            else:
                type_desc = f"Received for Sale ID {t['sale_id']}"
                products = ""  # No products for payment rows
                method = t.get('payment_method', '')

            ledger_data.append({
                'S.No': serial,
                'Date': t['date'].strftime("%d-%b-%Y"),
                'TYPE': type_desc,
                'Products': products,
                'Method': method,
                'Debit': t['debit'],
                'Credit': t['credit'],
                'Balance': running_balance
            })
            serial += 1
        # --- Create and display ledger ---
        if ledger_data:
            ledger_df = pd.DataFrame(ledger_data)
            display_df = ledger_df.copy()
            display_df['Debit'] = display_df['Debit'].map(lambda x: f"{x:.0f}")
            display_df['Credit'] = display_df['Credit'].map(lambda x: f"{x:.0f}")
            display_df['Balance'] = display_df['Balance'].map(lambda x: f"{x:.0f}")

            st.markdown(f"### Customer ledger - {selected_customer_name} - {display_month_name}")
            st.table(display_df)
            # --- Calculate Summary Metrics (excluding automatic return payments) ---
            monthly_debits = sum(t['debit'] for t in monthly_transactions)
            monthly_credits = sum(t['credit'] for t in monthly_transactions)
            total_returns = sum(t['credit'] for t in all_transactions if t['type'] == 'return')
            
            # Only count actual customer payments, not automatic return credit applications
            total_actual_payments_from_customer = sum(t['credit'] for t in all_transactions if t['type'] in ['payment', 'initial_payment'])
            total_payments_to_customer = sum(t['debit'] for t in all_transactions if t['type'] == 'payment_to_customer')
            
            # FIXED: Calculate cash sales correctly
            total_cash_sales = sum(t['credit'] for t in all_transactions if t['type'] == 'sale' and t.get('source') in ['POS', 'Sales Module'])
            
            # FIXED: Total Received = Actual customer payments + Cash sales (not including automatic return applications)
            total_received = total_actual_payments_from_customer + total_cash_sales
                
            final_balance = running_balance
            
            # --- Display Enhanced Summary Metrics ---
            st.markdown("### Summary")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("💰 Total Received", f"PKR {total_received:,.2f}")
            col2.metric("📤 Total Sales", f"PKR {total_sales:,.2f}")
            col3.metric("🔄 Total Returns", f"PKR {total_returns:,.2f}")
            col4.metric("💼 Net Balance", f"PKR {final_balance:,.2f}",
                        delta=f"{final_balance - opening_balance:,.2f}",
                        delta_color="normal" if final_balance >= 0 else "inverse")
            col5.metric("💸 Paid to Customer", f"PKR {total_payments_to_customer:,.2f}")

            # --- Opening Balance Display ---
            if opening_balance != 0:
                st.markdown("---")
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown("**Opening Balance:**")
                with col2:
                    balance_color = "green" if opening_balance >= 0 else "red"
                    st.markdown(f"<h4 style='color: {balance_color};'>PKR {opening_balance:,.2f}</h4>", unsafe_allow_html=True)

            # --- NEW: Pay to Customer Section ---
            if final_balance < 0:  # Company owes money to customer
                st.markdown("---")
                st.markdown("### 💸 Pay to Customer")
                st.warning(f"Company owes PKR {abs(final_balance):,.2f} to {selected_customer_name}")
                
                with st.form("pay_to_customer_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        pay_amount = st.number_input("Amount to Pay", 
                                                min_value=0.0, 
                                                max_value=float(abs(final_balance)),
                                                value=float(abs(final_balance)),
                                                step=0.01)
                    with col2:
                        payment_note = st.text_input("Note (optional)", 
                                                placeholder="Payment reason or note...")
                    
                    pay_button = st.form_submit_button("💰 Pay to Customer")
                    
                    if pay_button and pay_amount > 0:
                        try:
                            # Record payment to customer
                            success = record_payment_to_customer(selected_customer_name, pay_amount, payment_note)
                            if success:
                                st.success(f"✅ Payment of PKR {pay_amount:,.2f} recorded for {selected_customer_name}")
                                st.rerun()  # Refresh the page to show updated ledger
                            else:
                                st.error("❌ Failed to record payment. Please try again.")
                        except Exception as e:
                            st.error(f"❌ Error recording payment: {e}")

            # --- Show Returns Summary if any ---
            if total_returns > 0:
                st.markdown("---")
                st.markdown("### Returns Summary")
                return_transactions = [t for t in monthly_transactions if t['type'] == 'return']
                if return_transactions:
                    returns_data = []
                    for rt in return_transactions:
                        returns_data.append({
                            'Date': rt['date'].strftime("%d-%b-%Y"),
                            'Sale ID': rt['sale_id'],
                            'Product': rt['products'],
                            'Amount': f"PKR {rt['credit']:,.2f}",
                            'Reason': rt.get('return_reason', 'N/A')
                        })
                    returns_df = pd.DataFrame(returns_data)
                    st.table(returns_df)

            # --- Show Payments to Customer Summary if any (only manual payments) ---
            if total_payments_to_customer > 0:
                st.markdown("---")
                st.markdown("### Manual Payments to Customer Summary")
                payment_to_customer_transactions = [t for t in monthly_transactions if t['type'] == 'payment_to_customer']
                if payment_to_customer_transactions:
                    payments_data = []
                    for pt in payment_to_customer_transactions:
                        payments_data.append({
                            'Date': pt['date'].strftime("%d-%b-%Y"),
                            'Amount': f"PKR {pt['debit']:,.2f}",
                            'Note': pt.get('payment_note', 'N/A')
                        })
                    # FIXED: Use payments_data instead of returns_data
                    payments_df = pd.DataFrame(payments_data)
                    st.table(payments_df)

                # --- PDF Generation and Download Button ---
                # --- PDF Generation and Download Button ---
                # --- Enhanced PDF Generation with Returns ---
            class CustomerLedgerPDF(FPDF):
                def __init__(self, customer_name):
                    super().__init__()
                    self.page_width = 210  # A4 width in mm
                    self.left_margin = 10
                    self.right_margin = 10
                    self.customer_name = customer_name
                    self.set_auto_page_break(auto=True, margin=15)
                
                def header(self):
                    import os
                    logo_path = "static/trivsys.png"
                    logo_width = 30  # reasonable width
                    logo_height = 20 # avoid stretching

                    # Background bar first
                    header_bg_color = (255, 255, 255)
                    self.set_fill_color(*header_bg_color)
                    self.rect(0, 0, self.page_width, 25, style='F')  # full-width colored bar

                    # Add logo (draw on top of the background)
                    if os.path.exists(logo_path):
                        try:
                            self.image(logo_path, x=self.left_margin, y=5, w=logo_width, h=logo_height)
                        except RuntimeError as e:
                            print(f"Error loading image: {e}")

                    # Text: Company name and report title
                    self.set_text_color(0, 0, 0)
                    self.set_font('Arial', 'B', 16)
                    self.set_xy(self.left_margin + logo_width + 5, 8)
                    self.cell(0, 8, business_name, ln=True)

                    self.set_font('Arial', '', 11)
                    self.set_x(self.left_margin + logo_width + 5)
                    self.cell(0, 8, f"Customer Ledger - {self.customer_name}", ln=True)

                    # Restore defaults
                    self.set_text_color(0, 0, 0)
                    self.ln(5)

                def footer(self):
                    self.set_y(-15)
                    self.set_font('Arial', 'I', 8)
                    self.set_text_color(100, 100, 100)
                    self.cell(0, 10, f'Page {self.page_no()} - Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')

                def section_title(self, title):
                    """Styled section title with underline"""
                    self.set_font('Arial', 'B', 12)
                    self.set_text_color(54, 95, 145)  # Dark blue
                    self.cell(0, 8, title, 0, 1)
                    self.set_draw_color(54, 95, 145)
                    self.line(self.left_margin, self.get_y(), self.page_width - self.right_margin, self.get_y())
                    self.ln(3)
                    self.set_text_color(0, 0, 0)  # Reset to black

                def table_header(self, headers, col_widths):
                    """Styled table header"""
                    header_bg_color = (166, 124, 33)  # Dark blue
                    header_text_color = (255, 255, 255)  # White

                    self.set_font("Arial", "B", 10)
                    self.set_fill_color(*header_bg_color)
                    self.set_text_color(*header_text_color)
                    self.set_draw_color(23, 24, 22)  # Light gray border

                    for i, header in enumerate(headers):
                        self.cell(col_widths[i], 8, header, border=1, align="C", fill=True)
                    self.ln()

                    # Reset text color to black for the rows
                    self.set_text_color(0, 0, 0)  # Reset to black for body rows

                def table_row(self, row, col_widths, headers, is_even_row):
                    row_bg_color = (240, 240, 240) if is_even_row else (255, 255, 255)
                    
                    # Special highlighting for return transactions
                    is_return = "Return for Sale ID" in str(row.get("TYPE", ""))
                    if is_return:
                        row_bg_color = (255, 248, 220)  # Light orange for returns
                        
                    self.set_fill_color(*row_bg_color)
                    self.set_font("Arial", "", 9)
                    self.set_draw_color(23, 24, 22)

                    current_y = self.get_y()
                    max_cell_height = 7

                    # Handle Product and Reason columns that might need wrapping
                    product_height = 0
                    reason_height = 0

                    prod_width = col_widths[2]  # Product column
                    prod_lines = self.multi_cell(prod_width, 5, str(row["Product"]), border=0, align="L", fill=False, split_only=True)
                    product_height = len(prod_lines) * 5

                    reason_width = col_widths[4]  # Reason column  
                    reason_lines = self.multi_cell(reason_width, 5, str(row["Reason"]), border=0, align="L", fill=False, split_only=True)
                    reason_height = len(reason_lines) * 5

                    max_cell_height = max(max_cell_height, product_height, reason_height)
                    self.set_y(current_y)

                    # Render each cell
                    for i, (col, width) in enumerate(zip(headers, col_widths)):
                        if col in ["Debit", "Credit"]:
                            value = f"{float(row[col]):,.2f}" if float(row[col]) != 0 else "-"
                            align = "R"
                            
                            # Special color for return credits
                            if col == "Credit" and is_return and float(row[col]) > 0:
                                self.set_text_color(255, 140, 0)  # Orange for return credits
                                
                            self.cell(width, max_cell_height, value, border=1, align=align, fill=True)
                            self.set_text_color(0, 0, 0)  # Reset color
                            
                        elif col == "Balance":
                            value = f"{float(row[col]):,.2f}"
                            align = "R"
                            if float(row[col]) > 0:
                                self.set_text_color(0, 128, 0)
                            elif float(row[col]) < 0:
                                self.set_text_color(255, 0, 0)
                            self.cell(width, max_cell_height, value, border=1, align=align, fill=True)
                            self.set_text_color(0, 0, 0)
                            
                        elif col == "TYPE":
                            current_x = self.get_x()
                            current_y = self.get_y()
                            value = str(row[col])
                            
                            # Special font for returns
                            if is_return:
                                self.set_font("Arial", "B", 9)
                                
                            self.multi_cell(width, 5, value, border=0, align="L", fill=True)
                            self.rect(current_x, current_y, width, max_cell_height)
                            self.set_xy(current_x + width, current_y)
                            self.set_font("Arial", "", 9)  # Reset font
                            
                        elif col == "Products":
                            current_x = self.get_x()
                            current_y = self.get_y()
                            value = str(row[col])
                            
                            # Special font for return products
                            if is_return:
                                self.set_font("Arial", "I", 9)  # Italic for returned products
                                
                            self.multi_cell(width, 5, value, border=0, align="L", fill=True)
                            self.rect(current_x, current_y, width, max_cell_height)
                            self.set_xy(current_x + width, current_y)
                            self.set_font("Arial", "", 9)  # Reset font
                            
                        else:
                            self.cell(width, max_cell_height, str(row[col]), border=1, align="C", fill=True)

                    self.ln(max_cell_height)

                def summary_item(self, label, value, is_important=False, is_return=False):
                    """Styled summary items with special handling for returns"""
                    self.set_font("Arial", "B" if is_important else "", 10)
                    
                    if is_important:
                        self.set_text_color(54, 95, 145)  # Dark blue for label
                    elif is_return:
                        self.set_text_color(255, 140, 0)  # Orange for returns
                        
                    self.cell(50, 8, label, border=0)
                    
                    if is_important:
                        # Color the value based on positive/negative
                        if value >= 0:
                            self.set_text_color(0, 128, 0)  # Green
                        else:
                            self.set_text_color(255, 0, 0)  # Red
                    elif is_return:
                        self.set_text_color(255, 140, 0)  # Orange for return values
                    
                    self.cell(0, 8, f"PKR {value:,.2f}", ln=True)
                    self.set_text_color(0, 0, 0)  # Reset to black

                def returns_summary_table(self, returns_data):
                    """Create a detailed returns summary table"""
                    if not returns_data:
                        return
                        
                    self.section_title("Returns Summary")
                    
                    # Returns table headers
                    headers = ["Date", "Sale ID", "Product", "Amount", "Reason"]
                    col_widths = [25, 20, 60, 25, 50]
                    
                    self.table_header(headers, col_widths)
                    
                    # Returns table rows
                    for idx, return_item in enumerate(returns_data):
                        is_even_row = idx % 2 == 0
                        return_row = {
                            "Date": return_item['Date'],
                            "Sale ID": str(return_item['Sale ID']),
                            "Product": return_item['Product'],
                            "Amount": return_item['Amount'].replace('PKR ', ''),
                            "Reason": return_item['Reason'] if return_item['Reason'] != 'N/A' else '-'
                        }
                        
                        # Custom row rendering for returns
                        row_bg_color = (255, 248, 220) if is_even_row else (255, 240, 200)  # Light orange variants
                        self.set_fill_color(*row_bg_color)
                        self.set_font("Arial", "", 9)
                        self.set_draw_color(200, 200, 200)

                        current_y = self.get_y()
                        max_cell_height = 7

                        # Handle Product and Reason columns that might need wrapping
                        product_height = 0
                        reason_height = 0

                        prod_width = col_widths[2]  # Product column
                        prod_lines = self.multi_cell(prod_width, 5, str(return_row["Product"]), border=0, align="L", fill=False, split_only=True)
                        product_height = len(prod_lines) * 5

                        reason_width = col_widths[4]  # Reason column  
                        reason_lines = self.multi_cell(reason_width, 5, str(return_row["Reason"]), border=0, align="L", fill=False, split_only=True)
                        reason_height = len(reason_lines) * 5

                        max_cell_height = max(max_cell_height, product_height, reason_height)
                        self.set_y(current_y)

                        # Render each cell
                        for i, (col, width) in enumerate(zip(headers, col_widths)):
                            if col == "Amount":
                                self.set_text_color(255, 140, 0)  # Orange for amounts
                                self.cell(width, max_cell_height, return_row[col], border=1, align="R", fill=True)
                                self.set_text_color(0, 0, 0)
                            elif col in ["Product", "Reason"]:
                                current_x = self.get_x()
                                current_y = self.get_y()
                                self.multi_cell(width, 5, str(return_row[col]), border=0, align="L", fill=True)
                                self.rect(current_x, current_y, width, max_cell_height)
                                self.set_xy(current_x + width, current_y)
                            else:
                                self.cell(width, max_cell_height, str(return_row[col]), border=1, align="C", fill=True)

                        self.ln(max_cell_height)

                def summary_section(self, total_received, total_sales, final_balance, total_returns=0):
                    """Summary section with enhanced styling"""
                    self.set_font('Arial', 'B', 12)
                    self.set_text_color(54, 95, 145)  # Dark blue
                    self.cell(0, 10, "Financial Summary", 0, 1, 'C')
                    self.ln(5)
                    
                    # Summary items
                    self.set_font('Arial', '', 10)
                    self.cell(0, 8, f"Total Received: PKR {total_received:,.2f}", 0, 1)
                    self.cell(0, 8, f"Total Sales: PKR {total_sales:,.2f}", 0, 1)
                    if total_returns > 0:
                        self.cell(0, 8, f"Total Returns: PKR {total_returns:,.2f}", 0, 1)
                    self.cell(0, 8, f"Net Balance: PKR {final_balance:,.2f}", 0, 1)
                    self.ln(10)

                def notes_section(self):
                    """Notes section at the end of the document"""
                    self.set_font('Arial', '', 9)
                    self.cell(0, 6, "* All amounts are in Pakistani Rupees (PKR)", 0, 1)
                    self.cell(0, 6, "* Positive balance indicates customer owes you", 0, 1)
                    self.cell(0, 6, "* Negative balance indicates you owe customer", 0, 1)
                    self.cell(0, 6, "* Returns are highlighted in orange and reduce customer balance", 0, 1)
                    self.cell(0, 6, "* Return transactions show returned products and quantities", 0, 1)

            def generate_customer_ledger_pdf(customer_name, ledger_df, total_received, total_sales, final_balance, total_returns=0, returns_data=None):
                
                """Enhanced PDF generation with returns support"""
                pdf = CustomerLedgerPDF(customer_name)
                pdf.add_page()
                
                # Add document title and customer info
                pdf.set_font('Arial', 'B', 14)
                pdf.cell(0, 10, "Customer Ledger Report", 0, 1, 'C')
                pdf.ln(5)
                
                # Add customer information
                pdf.set_font('Arial', '', 10)
                pdf.cell(0, 6, f"Customer: {customer_name}", 0, 1, 'C')
                pdf.cell(0, 6, f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1, 'C')
                pdf.ln(10)
                
                # Ledger Table
                pdf.section_title("Transaction Details")
                
                # Column widths
                headers = ["S.No", "Date", "TYPE", "Products", "Debit", "Credit", "Balance"]
                col_widths = [8, 20, 35, 50, 22, 22, 22]
                
                pdf.table_header(headers, col_widths)
                
                # Ledger Table Rows
                for idx, row in ledger_df.iterrows():
                    is_even_row = idx % 2 == 0
                    pdf.table_row(row, col_widths, headers, is_even_row)
                
                # Add Enhanced Summary Section
                pdf.ln(12)
                pdf.section_title("Financial Summary")
                
                pdf.summary_item("Total Received:", total_received)
                pdf.summary_item("Total Sales:", total_sales)
                if total_returns > 0:
                    pdf.summary_item("Total Returns:", total_returns, is_return=True)
                pdf.summary_item("Net Balance:", final_balance, is_important=True)
                
                # Add Returns Summary Table if there are returns
                if returns_data and len(returns_data) > 0:
                    pdf.ln(10)
                    pdf.returns_summary_table(returns_data)
                
                # Add notes section
                pdf.ln(10)
                pdf.section_title("Notes")
                pdf.set_font('Arial', '', 9)
                notes_text = "* All amounts are in Pakistani Rupees (PKR)\n"
                notes_text += "* Positive balance indicates customer owes you\n"
                notes_text += "* Negative balance indicates you owe customer\n"
                if total_returns > 0:
                    notes_text += "* Returns are highlighted in orange and reduce customer balance\n"
                    notes_text += "* Return transactions show returned products and quantities"
                
                pdf.multi_cell(0, 5, notes_text)
                
                # Save to temporary file
                import tempfile  # Ensure tempfile is explicitly imported
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                pdf.output(temp_file.name)
                return temp_file.name

            # --- Updated PDF Generation Button Code ---
            if st.button("⬇️ Generate & Download PDF Report", key="generate_pdf_button"):
                with st.spinner("Creating customer ledger report..."):
                    try:
                        # Prepare returns data for PDF if any returns exist
                        pdf_returns_data = []
                        if total_returns > 0:
                            return_transactions = [t for t in monthly_transactions if t['type'] == 'return']
                            for rt in return_transactions:
                                pdf_returns_data.append({
                                    'Date': rt['date'].strftime("%d-%b-%Y"),
                                    'Sale ID': rt['sale_id'],
                                    'Product': rt['products'],
                                    'Amount': f"PKR {rt['credit']:,.2f}",
                                    'Reason': rt.get('return_reason', 'N/A')
                                })
                        
                        # Generate PDF with returns data
                        pdf_path = generate_customer_ledger_pdf(
                            selected_customer_name,
                            ledger_df,
                            total_received,
                            total_sales,
                            final_balance,
                            total_returns,
                            pdf_returns_data
                        )

                        st.success("✅ Customer ledger report generated successfully!")
                        
                        with open(pdf_path, "rb") as f:
                            file_name = f"Customer_Ledger_{selected_customer_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                            st.download_button(
                                label="⬇️ Download PDF Report",
                                data=f,
                                file_name=file_name,
                                mime="application/pdf",
                                help="Click to download the customer ledger report with returns",
                                key="download_customer_pdf"
                            )

                        os.remove(pdf_path)

                    except Exception as e:
                        st.error(f"Error generating PDF: {str(e)}")
                        import traceback
                        st.error(f"Debug info: {traceback.format_exc()}")
    # --- Main Ledger ---
    # --- Main Ledger ---
    elif st.session_state.sub_menu == "Main Ledger":
                st.header("Main Ledger")

                # --- Create a row for filters (Month and Day) ---
                col1, col2 = st.columns([1, 1])

                # --- Month selector in the first column ---
                with col1:
                    month_names = list(calendar.month_name)[1:]
                    st.markdown('##### Select Month')
                    selected_month_name = st.selectbox("Select Month", month_names, key="month_selector",label_visibility='collapsed')
                    selected_month_number = month_names.index(selected_month_name) + 1
                    current_year = datetime.now().year

                # --- Day selector in the second column ---
                with col2:
                    day_filter_options = ['All Days'] + [str(i) for i in range(1, calendar.monthrange(current_year, selected_month_number)[1] + 1)]
                    st.markdown('##### Select Day (Optional)')
                    selected_day = st.selectbox("Select Day (Optional)", day_filter_options, key="day_selector", index=0,label_visibility='collapsed')

                # --- Fetch Sales ---
                sales = get_filtered_sales(None, None, "Monthly", selected_month_name)
                sales_df = pd.DataFrame(sales, columns=[
                    'sale_id', 'product_names', 'quantities', 'total_price',
                    'paid_amount', 'due_amount', 'customer_name', 'sale_date', 'source'
                ])
                if not sales_df.empty:
                    sales_df['sale_date'] = pd.to_datetime(sales_df['sale_date'])
                    sales_df = sales_df[sales_df['sale_date'].dt.month == selected_month_number]
                    if selected_day != "All Days":
                        sales_df = sales_df[sales_df['sale_date'].dt.day == int(selected_day)]
                    daily_sales = sales_df.groupby(sales_df['sale_date'].dt.date)['total_price'].sum().reset_index()
                    daily_sales.columns = ['Date', 'Amount']
                    daily_sales['Type'] = 'Sale'
                else:
                    daily_sales = pd.DataFrame(columns=['Date', 'Amount', 'Type'])

                # --- Fetch Purchases ---
                purchases = fetch_grouped_purchase_orders()
                purchase_df = pd.DataFrame(purchases)
                if not purchase_df.empty:
                    purchase_df['date'] = pd.to_datetime(purchase_df['date'])
                    purchase_df = purchase_df[purchase_df['date'].dt.month == selected_month_number]
                    if selected_day != "All Days":
                        purchase_df = purchase_df[purchase_df['date'].dt.day == int(selected_day)]
                    daily_purchases = purchase_df.groupby(purchase_df['date'].dt.date)['total_amount'].sum().reset_index()
                    daily_purchases.columns = ['Date', 'Amount']
                    daily_purchases['Type'] = 'Purchase'
                else:
                    daily_purchases = pd.DataFrame(columns=['Date', 'Amount', 'Type'])

                # --- Fetch Expenses ---
                expense_df = fetch_filtered_expenses("Monthly", selected_month_number)
                if not expense_df.empty:
                    expense_df['expense_date'] = pd.to_datetime(expense_df['expense_date'])
                    expense_df = expense_df[expense_df['expense_date'].dt.month == selected_month_number]
                    if selected_day != "All Days":
                        expense_df = expense_df[expense_df['expense_date'].dt.day == int(selected_day)]
                    daily_expenses = expense_df.groupby(expense_df['expense_date'].dt.date)['amount'].sum().reset_index()
                    daily_expenses.columns = ['Date', 'Amount']
                    daily_expenses['Type'] = 'Expense'
                else:
                    daily_expenses = pd.DataFrame(columns=['Date', 'Amount', 'Type'])

                # --- Fetch Returns ---
                returns = fetch_returns_from_returns_table()
                returns_df = pd.DataFrame(returns) if returns else pd.DataFrame(columns=['return_date', 'return_amount'])
                
                if not returns_df.empty:
                    returns_df['return_date'] = pd.to_datetime(returns_df['return_date'])
                    returns_df = returns_df[returns_df['return_date'].dt.month == selected_month_number]
                    if selected_day != "All Days":
                        returns_df = returns_df[returns_df['return_date'].dt.day == int(selected_day)]
                    
                    daily_returns = returns_df.groupby(returns_df['return_date'].dt.date)['return_amount'].sum().reset_index()
                    daily_returns.columns = ['Date', 'Amount']
                    daily_returns['Type'] = 'Return'
                else:
                    daily_returns = pd.DataFrame(columns=['Date', 'Amount', 'Type'])

                # --- Combine all transactions ---
                all_transactions = pd.concat([daily_sales, daily_purchases, daily_expenses, daily_returns], ignore_index=True)

                if not all_transactions.empty:
                    all_transactions = all_transactions.sort_values(['Date', 'Type']).reset_index(drop=True)
                    
                    ledger_data = []
                    running_balance = 0
                    
                    for _, row in all_transactions.iterrows():
                        incoming = row['Amount'] if row['Type'] == 'Sale' else 0
                        outgoing = row['Amount'] if row['Type'] in ['Purchase', 'Expense', 'Return'] else 0
                        
                        running_balance += float(incoming - outgoing)
                        
                        ledger_data.append({
                            'Date': row['Date'],
                            'Type': row['Type'],
                            'Incoming Amount': incoming,
                            'Outgoing Amount': outgoing,
                            'Balance': running_balance
                        })
                    
                    ledger_df = pd.DataFrame(ledger_data)
                else:
                    ledger_df = pd.DataFrame(columns=['Date', 'Type', 'Incoming Amount', 'Outgoing Amount', 'Balance'])

                # --- Display Ledger ---
                if selected_day != "All Days":
                    st.subheader(f"Ledger for {selected_day} {selected_month_name} {current_year}")
                else:
                    st.subheader(f"Ledger for {selected_month_name} {current_year}")

                if not ledger_df.empty:
                    st.table(ledger_df)
                else:
                    st.info("No transactions found for the selected month.")
                ledger_df['Outgoing Amount'] = ledger_df['Outgoing Amount'].apply(lambda x: float(x) if isinstance(x, decimal.Decimal) else x)
                # --- Summary Section ---
                if not ledger_df.empty:
                    st.markdown("---")
                    total_incoming = ledger_df['Incoming Amount'].sum()
                    total_outgoing = ledger_df['Outgoing Amount'].sum()
                    final_balance = ledger_df['Balance'].iloc[-1]
                    
                    # Summary columns
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown("**Total Balance:**")
                    with col2:
                        balance_color = "green" if final_balance >= 0 else "red"
                        st.markdown(f"<h4 style='color: {balance_color};'>PKR {final_balance:,.2f}</h4>", unsafe_allow_html=True)

                    # Metrics
                    st.markdown("### Summary")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("💰 Total Incoming", f"PKR {total_incoming:,.2f}")
                    col2.metric("📤 Total Outgoing", f"PKR {total_outgoing:,.2f}")
                    col3.metric("💼 Net Balance", f"PKR {final_balance:,.2f}", 
                                delta=f"{final_balance:,.2f}", 
                                delta_color="normal" if final_balance >= 0 else "inverse")

                    # --- PDF Generation and Download Button ---
                    class PDF(FPDF):
                        def __init__(self):
                            super().__init__()
                            self.page_width = 210  # A4 width in mm
                            self.left_margin = 10
                            self.right_margin = 10
                            self.set_auto_page_break(auto=True, margin=15)
                        
                        def header(self):
                            import os
                            logo_path = "static/trivsys.png"
                            logo_width = 30
                            logo_height = 20

                            # Background bar
                            header_bg_color = (255, 255, 255)
                            self.set_fill_color(*header_bg_color)
                            self.rect(0, 0, self.page_width, 25, style='F')  # full-width header bar

                            # Add logo
                            if os.path.exists(logo_path):
                                try:
                                    self.image(logo_path, x=self.left_margin, y=5, w=logo_width, h=logo_height)
                                except RuntimeError as e:
                                    print(f"Error loading image: {e}")

                            # Company name and report title
                            self.set_text_color(0, 0,0)  # White text
                            self.set_font('Arial', 'B', 16)
                            self.set_xy(self.left_margin + logo_width + 5, 8)
                            self.cell(0, 8, business_name, ln=True)

                            self.set_font('Arial', '', 11)
                            self.set_x(self.left_margin + logo_width + 5)

                            title = f"Main Ledger - {selected_month_name} {current_year}"
                            if selected_day != "All Days":
                                title += f" (Day {selected_day})"

                            self.cell(0, 8, title, ln=True)

                            # Reset text color and add some spacing
                            self.set_text_color(0, 0, 0)
                            self.ln(5)


                        def footer(self):
                            self.set_y(-15)
                            self.set_font('Arial', 'I', 8)
                            self.set_text_color(100, 100, 100)
                            self.cell(0, 10, f'Page {self.page_no()} - Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')

                        def section_title(self, title):
                            """Styled section title with underline"""
                            self.set_font('Arial', 'B', 12)
                            self.set_text_color(54, 95, 145)  # Dark blue
                            self.cell(0, 8, title, 0, 1)
                            self.set_draw_color(54, 95, 145)
                            self.line(self.left_margin, self.get_y(), self.page_width - self.right_margin, self.get_y())
                            self.ln(3)
                            self.set_text_color(0, 0, 0)  # Reset to black

                        def table_header(self, headers, col_widths):
                            """Styled table header"""
                            header_bg_color = (166, 124, 33)  # Dark blue
                            header_text_color = (255, 255, 255)  # White
                            
                            self.set_font("Arial", "B", 10)
                            self.set_fill_color(*header_bg_color)
                            self.set_text_color(*header_text_color)
                            self.set_draw_color(59, 54, 54)  # Light gray border
                            
                            for i, header in enumerate(headers):
                                self.cell(col_widths[i], 8, header, border=1, align="C", fill=True)
                            self.ln()
                            self.set_text_color(0, 0, 0)  # Reset to black

                        def table_row(self, row, col_widths, is_even_row):
                            """Styled table rows with alternating colors"""
                            row_bg_color = (240, 240, 240) if is_even_row else (255, 255, 255)
                            self.set_fill_color(*row_bg_color)
                            self.set_font("Arial", "", 9)
                            self.set_draw_color(59, 54, 54)  # Light gray border
                            
                            for i, (col, width) in enumerate(zip(["Date", "Type", "Incoming Amount", "Outgoing Amount", "Balance"], col_widths)):
                                if col in ["Incoming Amount", "Outgoing Amount", "Balance"]:
                                    value = f"PKR {row[col]:,.2f}" if row[col] != 0 else "-"
                                    align = "R"
                                    # Color positive amounts green, negative red
                                    if col == "Balance":
                                        if row[col] > 0:
                                            self.set_text_color(0, 128, 0)  # Green
                                        elif row[col] < 0:
                                            self.set_text_color(255, 0, 0)  # Red
                                else:
                                    value = str(row[col])
                                    align = "L" if i == 1 else "C"  # Left-align for Type, center for others
                                
                                self.cell(width, 7, value, border=1, align=align, fill=True)
                                self.set_text_color(0, 0, 0)  # Reset color after each cell
                            
                            self.ln()

                        def summary_item(self, label, value, is_important=False):
                            """Styled summary items"""
                            self.set_font("Arial", "B" if is_important else "", 10)
                            
                            if is_important:
                                self.set_text_color(54, 95, 145)  # Dark blue for label
                            
                            self.cell(50, 8, label, border=0)
                            
                            if is_important:
                                # Color the value based on positive/negative
                                if value >= 0:
                                    self.set_text_color(0, 128, 0)  # Green
                                else:
                                    self.set_text_color(255, 0, 0)  # Red
                            
                            self.cell(0, 8, f"PKR {value:,.2f}", ln=True)
                            self.set_text_color(0, 0, 0)  # Reset to black

                    def generate_ledger_pdf():
                        pdf = PDF()
                        pdf.add_page()
                        
                        # Add document title and period info
                        pdf.set_font('Arial', 'B', 14)
                        pdf.cell(0, 10, "Financial Ledger Report", 0, 1, 'C')
                        pdf.ln(5)
                        

                        # Ledger Table
                        pdf.section_title("Transaction Details")
                        col_widths = [25, 30, 35, 35, 40]  # Slightly adjusted widths
                        headers = ["Date", "Type", "Incoming", "Outgoing", "Balance"]
                        pdf.table_header(headers, col_widths)
                        
                        # Ledger Table Rows
                        for idx, row in ledger_df.iterrows():
                            is_even_row = idx % 2 == 0
                            pdf.table_row(row, col_widths, headers, is_even_row)
                        
                        # Add Summary Section
                        pdf.ln(12)
                        pdf.section_title("Financial Summary")
                        
                        pdf.summary_item("Total Incoming:", total_incoming)
                        pdf.summary_item("Total Outgoing:", total_outgoing)
                        pdf.summary_item("Net Balance:", final_balance, is_important=True)
                        
                        # Add notes section
                        pdf.ln(10)
                        pdf.section_title("Notes")
                        pdf.set_font('Arial', '', 9)
                        # In your notes section, replace the bullet with an asterisk
                        pdf.multi_cell(0, 5, "* All amounts are in Pakistani Rupees (PKR)\n* " \
                        "Positive balance indicates net profit\n* Negative balance indicates net loss\n* " \
                        "Returns are included in outgoing amounts")
                        
                        # Save to temporary file                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                        pdf.output(temp_file.name)
                        return temp_file.name

                    # Generate and offer download with improved UI
                    if st.button("Generate PDF Ledger Report"):
                        with st.spinner("Creating professional report..."):
                            try:
                                pdf_path = generate_ledger_pdf()
                                
                                # Show success message
                                st.success("✅ Report generated successfully!")
                                
                                # Display download button with nice styling
                                with open(pdf_path, "rb") as f:
                                    file_name = f"Ledger_Report_{selected_month_name}_{current_year}"
                                    if selected_day != "All Days":
                                        file_name += f"_Day_{selected_day}"
                                    file_name += ".pdf"
                                    
                                    col1, col2, col3 = st.columns([1,2,1])
                                    with col1:
                                        st.download_button(
                                            label="⬇️ Download PDF Report",
                                            data=f,
                                            file_name=file_name,
                                            mime="application/pdf",
                                            help="Click to download the ledger report",
                                            key="download_pdf"
                                        )
                                
                                # Clean up after the download
                                os.remove(pdf_path)
                                
                            except Exception as e:
                                st.error(f"Error generating PDF: {str(e)}")
                    st.divider()

            # --- Daily Balance Chart ---
            # --- Daily Balance Chart ---
    if 'ledger_df' in locals() and not ledger_df.empty and len(ledger_df) > 1:
        st.header("Balance Trend")
        
        # Group by date and get the final balance for each day
        daily_balance = ledger_df.groupby('Date')['Balance'].last().reset_index()
        
        # Create chart
        balance_chart = px.line(
            daily_balance,
            x='Date',
            y='Balance',
            markers=True,
            labels={'Balance': 'Balance (PKR)', 'Date': 'Date'},
            height=400
        )
        
        balance_chart.update_traces(
            line=dict(width=3, color='#945034'),
            marker=dict(size=8, color='#945034')
        )
        
        balance_chart.update_layout(
            yaxis_title="Balance (PKR)",
            xaxis_title="Date",
            margin=dict(t=40, b=40, l=20, r=20)
        )
        
        st.plotly_chart(balance_chart, use_container_width=True)
    
    # POS SESSIONS HSTORY
    elif st.session_state.sub_menu == "POS Sessions History":
            st.header("Session History")

            # Fetch session data from the database
            sessions = fetch_sessions()

            if not sessions:
                st.warning("No session records found.")
            else:
                # Create a DataFrame for session data
                sessions_df = pd.DataFrame(sessions, columns=[
                    "Session ID", "Opening Time", "Closing Time", "Opening Amount", "Closing Amount"
                ])

                # Format the opening and closing times for better readability
                sessions_df["Opening Time"] = pd.to_datetime(sessions_df["Opening Time"]).dt.strftime('%Y-%m-%d %I:%M %p')
                sessions_df["Closing Time"] = sessions_df["Closing Time"].apply(
                    lambda x: pd.to_datetime(x).strftime('%Y-%m-%d %I:%M %p') if pd.notnull(x) else "Open"
                )

                # Display the session history table
                st.table(sessions_df)