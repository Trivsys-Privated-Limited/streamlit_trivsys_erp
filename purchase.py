import io
from shutil import Error
import streamlit as st
import pandas as pd
from database import *
from decimal import Decimal


if "tenant" in st.session_state and hasattr(st.session_state.tenant, "business_name"):
    business_name = st.session_state.tenant.business_name.upper()
else:
    business_name = 'default_name'
# Function to handle payment addition
def add_payment(order_id, amount):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Check if the order_id exists in purchase_orders and get the total amount
            cursor.execute("""
                SELECT po.id, po.total_amount
                FROM purchase_orders po
                WHERE po.id = %s
            """, (order_id,))
            result = cursor.fetchone()
            cursor.fetchall()  # Fetch all remaining results

            if result:
                purchase_order_id = result[0]  # purchase_order_id from purchase_orders
                total_amount = Decimal(result[1])  # Ensure this is a Decimal value
                # print(f"Found Purchase Order ID: {purchase_order_id}, Total Amount: {total_amount:.2f}")
            else:
                st.error(f"❌ Purchase Order ID #{order_id} not found in purchase_orders.")
                return False

            # Fetch the corresponding purchase_id from purchases table using order_id
            cursor.execute("""
                SELECT p.id
                FROM purchases p
                WHERE p.order_id = %s
            """, (purchase_order_id,))
            purchase_result = cursor.fetchone()
            cursor.fetchall()  # Fetch all remaining results

            if purchase_result:
                purchase_id = purchase_result[0]
                # print(f"Found Purchase ID: {purchase_id}")
            else:
                st.error(f"❌ Purchase ID not found for Order ID #{order_id}.")
                return False

            # Calculate the total payments made for this purchase
            cursor.execute("""
                SELECT SUM(vp.amount)
                FROM vendor_payments vp
                WHERE vp.purchase_id = %s
            """, (purchase_id,))
            payment_result = cursor.fetchone()
            cursor.fetchall()  # Fetch all remaining results

            total_paid = Decimal(payment_result[0]) if payment_result[0] else Decimal(0)
            due_amount = total_amount - total_paid
            # print(f"Total Paid: Rs.{total_paid:.2f}, Due Amount: Rs.{due_amount:.2f}")

            # Ensure the amount is passed as a Decimal to avoid float issues
            amount = Decimal(amount)

            if amount > due_amount:
                st.error("❌ Payment exceeds the due amount.")
                return False

            # Insert the payment record into vendor_payments
            cursor.execute("""
                INSERT INTO vendor_payments (purchase_id, amount, due_amount)
                VALUES (%s, %s, %s)
                """, (purchase_id, amount, due_amount - amount))

            conn.commit()
            # print(f"Payment of Rs.{amount} recorded for Order ID #{order_id}.")

            # Recalculate the outstanding balance after payment
            new_due_amount = due_amount - amount
            # print(f"Updated Due Amount for Order ID #{order_id}: Rs.{new_due_amount:.2f}")
            
            return new_due_amount  # Return the updated due amount
        except Exception as e:
            print(f"Error adding payment: {e}")
            conn.rollback()
            st.error("❌ An error occurred while processing the payment.")
            return False
        finally:
            conn.close()
    return False

# Get payment history for a purchase
def get_payment_history(order_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # First, find all purchase_ids associated with the order_id
            cursor.execute("""
                SELECT p.id
               FROM purchases p
               WHERE p.order_id = %s
            """, (order_id,))
            purchase_ids = [row[0] for row in cursor.fetchall()]

            if not purchase_ids:
                print(f"❌ No Purchase IDs found for Order ID #{order_id}.")
                return []

            # Now, fetch the payment history for all purchase_ids
            # Create a string of placeholders for the SQL query
            placeholders = ', '.join(['%s'] * len(purchase_ids))
            cursor.execute(f"""
                SELECT vp.id, vp.amount, vp.due_amount, vp.payment_date 
                FROM vendor_payments vp
                WHERE vp.purchase_id IN ({placeholders})
                ORDER BY vp.payment_date DESC
            """, purchase_ids)
            payments = cursor.fetchall()
            return payments
        except Exception as e:
            print(f"Error fetching payment history: {e}")
            return []
        finally:
            conn.close()
    return []
import io
from datetime import datetime
import streamlit as st
import pandas as pd
from decimal import Decimal
from fpdf import FPDF
import tempfile
import os

# ============================================================================
# REFACTORED VENDOR LEDGER - MATCHING CUSTOMER LEDGER ARCHITECTURE
# ============================================================================
# This implementation mirrors the Customer Ledger structure exactly:
# 1. Builds unified all_transactions list
# 2. Sorts by date
# 3. Computes opening balance
# 4. Maintains running balance
# 5. Displays single ledger table
# 6. Supports PDF export with same layout
# ============================================================================

import io
from datetime import datetime
import streamlit as st
import pandas as pd
from decimal import Decimal
from fpdf import FPDF
import tempfile
import os

# ============================================================================
# REFACTORED VENDOR LEDGER - MATCHING CUSTOMER LEDGER ARCHITECTURE
# ============================================================================
# This implementation mirrors the Customer Ledger structure exactly:
# 1. Builds unified all_transactions list
# 2. Sorts by date
# 3. Computes opening balance
# 4. Maintains running balance
# 5. Displays single ledger table
# 6. Supports PDF export with same layout
# ============================================================================

def vendor_ledger_page():
    """
    Vendor Ledger implementation with Money In / Money Out terminology.
    
    ACCOUNTING RULES (from COMPANY's perspective):
    - Backend: CREDIT = Company owes vendor (purchase created)
    - Backend: DEBIT = Company paid vendor (payment made)
     
    UI MAPPING (from COMPANY's perspective):
    - Credit (backend) → Money Out (company owes vendor, money will go out)
    - Debit (backend) → Money In (company paid vendor, reduces what company owes)
    
    - Positive balance: Company owes vendor
    - Negative balance: Vendor owes company (rare, overpayment)
    """
    
    st.header("Vendor Ledger")

    # --- Fetch active vendors ---
    vendors = fetch_vendors()
    ledger_vendors = []

    for vendor in vendors:
        vendor_id = vendor[0]
        vendor_name = vendor[1]
        ledger_vendors.append((vendor_id, vendor_name))

    if not ledger_vendors:
        st.warning("No vendors with purchase records found.")
        return

    vendor_names = [name for _, name in ledger_vendors]

    col1, col2, col3 = st.columns(3)
    
    # --- Select Vendor ---
    with col1:
        st.markdown('##### Select Vendor')
        selected_vendor_name = st.selectbox(
            "Select Vendor", 
            vendor_names, 
            label_visibility='collapsed'
        )
    
    # Get vendor_id for selected vendor
    selected_vendor_id = next(
        vid for vid, vname in ledger_vendors if vname == selected_vendor_name
    )

    # --- Date Filter ---
    today = datetime.now()
    current_year = today.year
    current_month = today.month

    years = list(range(current_year - 4, current_year + 1))
    months = ["Whole Year", "January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]

    with col2:
        st.markdown('##### Select Year')
        selected_year = st.selectbox(
            "Select Year", 
            years, 
            index=len(years) - 1, 
            label_visibility='collapsed'
        )
    
    with col3:
        st.markdown('##### Select Month')
        selected_month = st.selectbox(
            "Select Month", 
            months, 
            index=current_month, 
            label_visibility='collapsed'
        )

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

    # ========================================================================
    # BUILD UNIFIED TRANSACTION LIST
    # ========================================================================
    all_transactions = []

    # --- Fetch all purchase orders for this vendor ---
    vendor_purchases = fetch_purchase_orders_by_vendor(selected_vendor_id)

    for po in vendor_purchases:
        order_id = po['order_id']
        products = po['products']
        quantities = po['quantities']
        total_amount = float(po['total_amount'])
        purchase_date = pd.to_datetime(po['purchase_date']) if po['purchase_date'] else pd.to_datetime(today)

        # Build products list with quantities
        products_list = ""
        try:
            if products and quantities:
                names = [n.strip() for n in str(products).split(',')]
                qtys = [q.strip() for q in str(quantities).split(',')]
                combined = []
                for i, name in enumerate(names):
                    qty = qtys[i] if i < len(qtys) else ''
                    if qty:
                        combined.append(f"{name} ({qty})")
                    else:
                        combined.append(name)
                products_list = ', '.join(combined)
            else:
                products_list = products or ''
        except Exception:
            products_list = products or ''

        # Purchase Order transaction
        # Backend: CREDIT - company owes vendor (unchanged)
        all_transactions.append({
            'date': purchase_date,
            'type': 'purchase',
            'order_id': order_id,
            'products': products_list,
            'debit': 0.0,  # Backend unchanged
            'credit': total_amount  # Backend unchanged
        })

        # --- Fetch payments for this purchase order ---
        payments = get_payment_history(order_id)
        
        for payment in payments:
            payment_id, amount, due_amount, payment_date = payment
            pay_date = pd.to_datetime(payment_date) if payment_date else purchase_date
            
            # Payment transaction
            # Backend: DEBIT - company paid vendor (unchanged)
            all_transactions.append({
                'date': pay_date,
                'type': 'payment',
                'order_id': order_id,
                'products': "",
                'debit': float(amount),  # Backend unchanged
                'credit': 0.0  # Backend unchanged
            })

    # --- Fetch manual vendor transactions ---
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        query = """
            SELECT txn_date, txn_type, amount, description, reference, category
            FROM vendor_manual_transactions
            WHERE vendor_name = %s
            ORDER BY txn_date
        """
        cur.execute(query, (selected_vendor_name,))
        manual_transactions = cur.fetchall()
        cur.close()
        conn.close()
        
        # Add manual transactions - backend values unchanged
        for mt in manual_transactions:
            txn_date = pd.to_datetime(mt['txn_date']) if mt['txn_date'] else pd.to_datetime(today)
            txn_type = mt['txn_type']  # 'debit' or 'credit'
            amount = float(mt['amount'])
            
            all_transactions.append({
                'date': txn_date,
                'type': 'manual_transaction',
                'order_id': None,
                'products': "",
                'debit': amount if txn_type == 'debit' else 0.0,  # Backend unchanged
                'credit': amount if txn_type == 'credit' else 0.0,  # Backend unchanged
                'manual_description': mt['description'] or 'Manual Transaction',
                'manual_reference': mt.get('reference', ''),
                'manual_category': mt.get('category', '')
            })
    except Exception as e:
        print(f"Error fetching manual vendor transactions: {e}")

    # --- Sort by date ---
    all_transactions.sort(key=lambda x: x['date'])

    # --- Opening balance (Backend calculation unchanged) ---
    # Positive = company owes vendor, Negative = vendor owes company
    opening_balance = sum(t['credit'] - t['debit'] for t in all_transactions if t['date'] < start_date)

    # --- Filter transactions for selected range ---
    monthly_transactions = [t for t in all_transactions if start_date <= t['date'] < end_date]

    # ========================================================================
    # BUILD LEDGER DATA WITH MONEY IN/OUT
    # ========================================================================
    ledger_data = []
    running_balance = opening_balance
    serial = 1

    # Opening balance row
    if opening_balance != 0:
        # UI MAPPING: 
        # Positive balance (company owes vendor) → Money Out from company's perspective
        # Negative balance (vendor owes company) → Money In from company's perspective
        ledger_data.append({
            'S.No': serial,
            'Date': start_date.strftime("%d-%b-%Y"),
            'TYPE': f"Opening Balance for {display_month_name}",
            'Products': "",
            'Method': "",
            # If company owes vendor (+ve), show as Money Out
            # If vendor owes company (-ve), show as Money In
            'Money Out': abs(opening_balance) if opening_balance > 0 else 0.0,
            'Money In': abs(opening_balance) if opening_balance < 0 else 0.0,
            'Balance': opening_balance
        })
        serial += 1

    # Transaction rows
    for t in monthly_transactions:
        running_balance += t['credit'] - t['debit']  # Backend calculation unchanged
        
        if t['type'] == 'purchase':
            type_desc = f"Purchase Order ID: {t['order_id']}"
            products = t['products']
            method = ""
        elif t['type'] == 'payment':
            type_desc = f"Payment for Purchase Order ID: {t['order_id']}"
            products = ""
            method = "Cash"
        elif t['type'] == 'manual_transaction':
            ref_text = f" [Ref: {t.get('manual_reference', '')}]" if t.get('manual_reference') else ""
            cat_text = f" ({t.get('manual_category', '')})" if t.get('manual_category') else ""
            type_desc = f"Manual Transaction - {t.get('manual_description', '')}{cat_text}{ref_text}"
            products = ""
            method = "Manual"
        else:
            type_desc = "Transaction"
            products = ""
            method = ""

        # UI MAPPING for transactions:
        # Backend credit (company owes more) → Money Out (from company perspective)
        # Backend debit (company paid) → Money In (reduces what company owes)
        ledger_data.append({
            'S.No': serial,
            'Date': t['date'].strftime("%d-%b-%Y"),
            'TYPE': type_desc,
            'Products': products,
            'Method': method,
            'Money Out': t['credit'],  # credit → Money Out (company owes vendor)
            'Money In': t['debit'],  # debit → Money In (company paid vendor)
            'Balance': running_balance
        })
        serial += 1

    # ========================================================================
    # DISPLAY LEDGER TABLE
    # ========================================================================
    if ledger_data:
        ledger_df = pd.DataFrame(ledger_data)
        display_df = ledger_df.copy()
        display_df['Money Out'] = display_df['Money Out'].map(lambda x: f"{x:.0f}")
        display_df['Money In'] = display_df['Money In'].map(lambda x: f"{x:.0f}")
        display_df['Balance'] = display_df['Balance'].map(lambda x: f"{x:.0f}")

        st.markdown(f"### Vendor Ledger - {selected_vendor_name} - {display_month_name}")
        st.table(display_df)

        # --- Calculate Summary Metrics (Backend calculations unchanged) ---
        monthly_credits = sum(t['credit'] for t in monthly_transactions)
        monthly_debits = sum(t['debit'] for t in monthly_transactions)
        
        total_purchases = sum(t['credit'] for t in all_transactions if t['type'] == 'purchase')
        total_payments = sum(t['debit'] for t in all_transactions if t['type'] == 'payment')
        
        final_balance = running_balance

        # --- Display Summary Metrics ---
        st.markdown("### Summary")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📦 Total Purchases", f"PKR {total_purchases:,.2f}")
        col2.metric("💰 Total Paid", f"PKR {total_payments:,.2f}")
        col3.metric("💼 Net Balance", f"PKR {final_balance:,.2f}",
                    delta=f"{final_balance - opening_balance:,.2f}",
                    delta_color="inverse" if final_balance >= 0 else "normal")
        col4.metric("📅 Period Purchases", f"PKR {monthly_credits:,.2f}")

        # --- Opening Balance Display ---
        if opening_balance != 0:
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**Opening Balance:**")
            with col2:
                balance_color = "red" if opening_balance >= 0 else "green"
                balance_text = "Payable" if opening_balance >= 0 else "Receivable"
                st.markdown(
                    f"<h4 style='color: {balance_color};'>PKR {abs(opening_balance):,.2f} ({balance_text})</h4>", 
                    unsafe_allow_html=True
                )

        # ====================================================================
        # PDF GENERATION - Updated column headers only
        # ====================================================================
        class VendorLedgerPDF(FPDF):
            def __init__(self, vendor_name):
                super().__init__()
                self.page_width = 210
                self.left_margin = 10
                self.right_margin = 10
                self.vendor_name = vendor_name
                self.set_auto_page_break(auto=True, margin=15)
            
            def header(self):
                logo_path = "static/trivsys.png"
                logo_width = 30
                logo_height = 20

                header_bg_color = (255, 255, 255)
                self.set_fill_color(*header_bg_color)
                self.rect(0, 0, self.page_width, 25, style='F')

                if os.path.exists(logo_path):
                    try:
                        self.image(logo_path, x=self.left_margin, y=5, w=logo_width, h=logo_height)
                    except RuntimeError as e:
                        print(f"Error loading image: {e}")

                self.set_text_color(0, 0, 0)
                self.set_font('Arial', 'B', 16)
                self.set_xy(self.left_margin + logo_width + 5, 8)
                self.cell(0, 8, business_name, ln=True)

                self.set_font('Arial', '', 11)
                self.set_x(self.left_margin + logo_width + 5)
                self.cell(0, 8, f"Vendor Ledger - {self.vendor_name}", ln=True)

                self.set_text_color(0, 0, 0)
                self.ln(5)

            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                footer_color = (100, 100, 100)
                self.set_text_color(*footer_color)
                self.cell(
                    0, 10, 
                    f'Page {self.page_no()} - Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 
                    0, 0, 'C'
                )

            def section_title(self, title):
                self.set_font('Arial', 'B', 12)
                self.set_text_color(54, 95, 145)
                self.cell(0, 8, title, 0, 1)
                self.set_draw_color(54, 95, 145)
                self.line(self.left_margin, self.get_y(), self.page_width - self.right_margin, self.get_y())
                self.ln(3)
                self.set_text_color(0, 0, 0)

            def table_header(self, headers, col_widths):
                header_bg_color = (166, 124, 33)
                header_text_color = (255, 255, 255)

                self.set_font("Arial", "B", 10)
                self.set_fill_color(*header_bg_color)
                self.set_text_color(*header_text_color)
                self.set_draw_color(23, 24, 22)

                for i, header in enumerate(headers):
                    self.cell(col_widths[i], 8, header, border=1, align="C", fill=True)
                self.ln()

                self.set_text_color(0, 0, 0)

            def table_row(self, row, col_widths, headers, is_even_row):
                row_bg_color = (240, 240, 240) if is_even_row else (255, 255, 255)
                self.set_fill_color(*row_bg_color)
                self.set_font("Arial", "", 9)
                self.set_draw_color(23, 24, 22)

                current_y = self.get_y()
                max_cell_height = 7

                type_height = 0
                products_height = 0

                if "TYPE" in headers:
                    type_idx = headers.index("TYPE")
                    type_width = col_widths[type_idx]
                    type_lines = self.multi_cell(
                        type_width, 5, str(row["TYPE"]), 
                        border=0, align="L", fill=False, split_only=True
                    )
                    type_height = len(type_lines) * 5

                if "Products" in headers and str(row["Products"]):
                    prod_idx = headers.index("Products")
                    prod_width = col_widths[prod_idx]
                    prod_lines = self.multi_cell(
                        prod_width, 5, str(row["Products"]), 
                        border=0, align="L", fill=False, split_only=True
                    )
                    products_height = len(prod_lines) * 5

                max_cell_height = max(max_cell_height, type_height, products_height)
                self.set_y(current_y)

                # Update column names in PDF rendering
                for i, (col, width) in enumerate(zip(headers, col_widths)):
                    if col in ["Money Out", "Money In"]:  # Updated from "Debit", "Credit"
                        value = f"{float(row[col]):,.2f}" if float(row[col]) != 0 else "-"
                        align = "R"
                        self.cell(width, max_cell_height, value, border=1, align=align, fill=True)
                    elif col == "Balance":
                        value = f"{float(row[col]):,.2f}"
                        align = "R"
                        if float(row[col]) > 0:
                            self.set_text_color(255, 0, 0)
                        elif float(row[col]) < 0:
                            self.set_text_color(0, 128, 0)
                        self.cell(width, max_cell_height, value, border=1, align=align, fill=True)
                        self.set_text_color(0, 0, 0)
                    elif col == "TYPE":
                        current_x = self.get_x()
                        current_y = self.get_y()
                        self.multi_cell(width, 5, str(row[col]), border=0, align="L", fill=True)
                        self.rect(current_x, current_y, width, max_cell_height)
                        self.set_xy(current_x + width, current_y)
                    elif col == "Products":
                        current_x = self.get_x()
                        current_y = self.get_y()
                        self.multi_cell(width, 5, str(row[col]), border=0, align="L", fill=True)
                        self.rect(current_x, current_y, width, max_cell_height)
                        self.set_xy(current_x + width, current_y)
                    else:
                        self.cell(width, max_cell_height, str(row[col]), border=1, align="C", fill=True)

                self.ln(max_cell_height)

        def generate_vendor_ledger_pdf(vendor_name, ledger_df, total_purchases, total_payments, final_balance):
            pdf = VendorLedgerPDF(vendor_name)
            pdf.add_page()
            
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, "Vendor Ledger Report", 0, 1, 'C')
            pdf.ln(5)
            
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 6, f"Vendor: {vendor_name}", 0, 1, 'C')
            pdf.cell(0, 6, f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1, 'C')
            pdf.ln(10)
            
            pdf.section_title("Transaction Details")
            
            # Updated PDF headers: Money Out, Money In instead of Debit, Credit
            headers = ["S.No", "Date", "TYPE", "Products", "Method", "Money Out", "Money In", "Balance"]
            col_widths = [8, 18, 32, 42, 15, 20, 20, 20]
            
            pdf.table_header(headers, col_widths)
            
            for idx, row in ledger_df.iterrows():
                is_even_row = idx % 2 == 0
                pdf.table_row(row, col_widths, headers, is_even_row)
            
            pdf.ln(10)
            pdf.section_title("Notes")
            pdf.set_font('Arial', '', 9)
            # Updated notes to reflect Money In/Out terminology
            notes = "* All amounts are in Pakistani Rupees (PKR)\n"
            notes += "* Positive balance indicates you owe vendor\n"
            notes += "* Negative balance indicates vendor owes you\n"
            notes += "* Money Out = Purchase (amount owed to vendor)\n"
            notes += "* Money In = Payment (amount paid to vendor)"
            pdf.multi_cell(0, 5, notes)
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf.output(temp_file.name)
            return temp_file.name

        # PDF Generation Button
        if st.button("⬇️ Generate & Download PDF Report", key="generate_vendor_pdf_button"):
            with st.spinner("Creating vendor ledger report..."):
                try:
                    pdf_path = generate_vendor_ledger_pdf(
                        selected_vendor_name,
                        ledger_df,
                        total_purchases,
                        total_payments,
                        final_balance
                    )

                    st.success("✅ Vendor ledger report generated successfully!")
                    
                    with open(pdf_path, "rb") as f:
                        file_name = f"Vendor_Ledger_{selected_vendor_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                        st.download_button(
                            label="⬇️ Download PDF Report",
                            data=f,
                            file_name=file_name,
                            mime="application/pdf",
                            help="Click to download the vendor ledger report",
                            key="download_vendor_pdf"
                        )

                    os.remove(pdf_path)

                except Exception as e:
                    st.error(f"Error generating PDF: {str(e)}")
                    import traceback
                    st.error(f"Debug info: {traceback.format_exc()}")
    else:
        st.warning("No transactions found for the selected vendor and period.")

# ============================================================================
# INTEGRATION NOTE:
# Replace the "Vendor Ledger" section in your purchase_page() function with:
# 

# ============================================================================

# Get outstanding balance for a purchase
def get_outstanding_balance(order_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Get the total amount from purchase_orders
            cursor.execute("""
                SELECT total_amount
                FROM purchase_orders
                WHERE id = %s
            """, (order_id,))
            result = cursor.fetchone()
            if result:
                total_amount = result[0]
            else:
                total_amount = 0  # Default to 0 if no result found

            # Get the total payments made
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) 
                FROM vendor_payments 
                WHERE purchase_id IN (
                    SELECT id
                    FROM purchases
                    WHERE order_id = %s
                )
            """, (order_id,))
            payment_result = cursor.fetchone()
            total_paid = payment_result[0] if payment_result else 0

            # Calculate the outstanding balance
            outstanding_balance = total_amount - total_paid

            
            return outstanding_balance
        except Exception as e:
            print(f"Error calculating outstanding balance: {e}")
            return 0
        finally:
            conn.close()
    return 0



# Fetch all products including cost price
def fetch_products():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, stock, cost_price FROM products")  # Fetch cost_price
        products = cursor.fetchall()
        conn.close()
        return products
    return []

# Fetch purchase history
def fetch_grouped_purchase_orders():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT 
            po.id AS order_id,
            GROUP_CONCAT(pr.name ORDER BY pr.name SEPARATOR ', ') AS products,
            GROUP_CONCAT(p.quantity ORDER BY pr.name SEPARATOR ', ') AS quantities,
            ROUND(SUM(p.quantity * pr.cost_price), 2) AS total_amount,
            v.name AS vendor,
            MAX(po.order_date) AS date
        FROM purchase_orders po
        JOIN purchases p ON po.id = p.order_id
        JOIN products pr ON p.product_id = pr.id
        JOIN vendors v ON po.vendor_id = v.id
        GROUP BY po.id
        ORDER BY po.order_date DESC
        """
        cursor.execute(query)
        result = cursor.fetchall()
        conn.close()
        return result
    return []


def create_purchase_order(vendor_id, items):
    """Create a purchase order with multiple items"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # Calculate total amount
            total_amount = sum(item['quantity'] * item['cost_price'] for item in items)
            print(f"Total amount: {total_amount}")
            
            # Create the purchase order
            cursor.execute("""
                INSERT INTO purchase_orders (vendor_id, total_amount, order_date)
                VALUES (%s, %s, NOW())
            """, (vendor_id, total_amount))
            order_id = cursor.lastrowid
            print(f"Order ID: {order_id}")
            
            # Add all items to purchases table
            for item in items:
                print(f"Adding item: {item}")
                cursor.execute("""
                    INSERT INTO purchases (product_id, vendor_id, quantity, order_id)
                    VALUES (%s, %s, %s, %s)
                """, (item['product_id'], vendor_id, item['quantity'], order_id))
                
                # Update product stock
                cursor.execute("""
                    UPDATE products 
                    SET stock = stock + %s
                    WHERE id = %s
                """, (item['quantity'], item['product_id']))
            
            conn.commit()
            return order_id
        except Exception as e:
            conn.rollback()
            print(f"Error creating purchase order: {e}")
            return None
        finally:
            conn.close()
    return None


def fetch_purchase_orders_by_vendor(vendor_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT 
            p.order_id,
            p.purchase_date,
            GROUP_CONCAT(pr.name SEPARATOR ', ') AS products,
            GROUP_CONCAT(p.quantity SEPARATOR ', ') AS quantities,
            SUM(pr.cost_price * p.quantity) AS total_amount
        FROM purchases p
        JOIN products pr ON p.product_id = pr.id
        WHERE p.vendor_id = %s
        GROUP BY p.order_id, p.purchase_date
        ORDER BY p.purchase_date DESC
    """
    
    cursor.execute(query, (vendor_id,))
    results = cursor.fetchall()
    conn.close()
    return results



def get_total_paid(purchase_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM vendor_payments WHERE purchase_id = %s", (purchase_id,))
    result = cursor.fetchone()
    conn.close()
    # Handle None result and return Decimal(0) if no payments found
    return Decimal(result[0] if result[0] is not None else 0.0) 



def get_vendor_id_by_name(vendor_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM vendors WHERE name = %s", (vendor_name,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


# Purchase Module UI
def purchase_page():
    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.rerun()
        
    if 'sub_menu' not in st.session_state:
        st.session_state.sub_menu = "Purchase History"
    with st.sidebar:
    # Module Title

        st.markdown("### PURCHASE")
        
        # Navigation buttons
        menu_items = [
            "Purchase History",
            "Purchase Products",
            "Manage Vendors",
            "Update Payments",
            "Vendor Ledger",
        ]
        
        for item in menu_items:
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.sub_menu = item
                st.rerun()

    sub_menu = st.session_state.sub_menu

    # sub_menu = st.sidebar.selectbox("Select Submenu", ["Purchase History", "Purchase Products",  "Manage Vendors","Update Payments", "Vendor Ledger"])

    # Inside your purchase_page function, modify the "Purchase Products" block to behave like a cart

    if sub_menu == "Purchase Products":
        st.header("Purchase Products")

        # Fetch products and vendors
        products = fetch_products()
        vendors = fetch_vendors()

        if not products:
            st.warning("No products found in inventory.")
            return

        if not vendors:
            st.warning("No vendors found.")
            return

        # Session state to hold cart
        if "purchase_cart" not in st.session_state:
            st.session_state.purchase_cart = []

        st.markdown('---')
        col1, col2,col3 = st.columns(3)
        with col1:
        # --- Vendor Selection (applies to whole cart) ---
            st.markdown('#### Select Vendor : ')
            vendor_options = {v[1]: v[0] for v in vendors}
            selected_vendor_name = st.selectbox("Select Vendor", list(vendor_options.keys()),label_visibility='collapsed')
            selected_vendor_id = vendor_options[selected_vendor_name]

        # --- Product Selection ---
        
        with col2:
            st.markdown('#### Select Product : ')
            product_options = {f"{p[1]} (Stock: {p[2]}, Cost: Rs.{p[3]:,.2f})": (p[0], p[3]) for p in products}
            selected_product = st.selectbox("Select Product", list(product_options.keys()),label_visibility='collapsed')
        with col3:
            st.markdown('#### Quantity : ')
            quantity = st.number_input("Quantity", min_value=1, step=1, key="purchase_qty",label_visibility='collapsed')

        # Add to Cart
        if st.button("Add to Cart"):
            product_id, cost_price = product_options[selected_product]
            product_name = selected_product.split("(")[0].strip()
            st.session_state.purchase_cart.append({
                "product_id": product_id,
                "product_name": product_name,
                "quantity": quantity,
                "cost_price": cost_price
            })
            st.success(f"Added {quantity} x {product_name} to cart")

        # --- Show Cart Items ---
        if st.session_state.purchase_cart:
            st.subheader("Purchase Cart")
            cart_df = pd.DataFrame(st.session_state.purchase_cart)
            cart_df["Total"] = cart_df["quantity"] * cart_df["cost_price"]
            st.table(cart_df)

            total_amount = cart_df["Total"].sum()
            st.markdown(f"### Total Purchase Amount: Rs. {total_amount:,.2f}")


            # Replace this section in your "Purchase Products" block:
            # Finalize Purchase Button - Modified version
            if st.button("Create Purchase Order"):
                if not st.session_state.purchase_cart:
                    st.warning("Your cart is empty!")
                    return
                    
                # Use the new purchase order method
                order_id = create_purchase_order(
                    vendor_id=selected_vendor_id,
                    items=st.session_state.purchase_cart
                )
                
                if order_id:
                    st.success(f"✅ Purchase Order #{order_id} created successfully!")
                    
                    # Show order summary
                    st.subheader("Purchase Order Summary")
                    order_df = pd.DataFrame(st.session_state.purchase_cart)
                    order_df['Total'] = order_df['quantity'] * order_df['cost_price']
                    st.table(order_df)
                    
                    total_amount = order_df['Total'].sum()
                    st.markdown(f"### Purchase Order Amount: Rs. {total_amount:,.2f}")
                    
                    # Clear the cart
                    st.session_state.purchase_cart.clear()
                else:
                    st.error("❌ Failed to create purchase order. Please try again.")


    elif sub_menu == "Purchase History":
        st.header("Purchase History")

        # ✅ Fetch grouped purchase history
        purchases = fetch_grouped_purchase_orders()

        if not purchases:
            st.warning("No purchase records found.")
        else:
            # Convert to DataFrame
            purchases_df = pd.DataFrame(purchases)

            # Rename columns for display
            purchases_df.rename(columns={
                "order_id": "PURCHASE ID",
                "products": "PRODUCTS",
                "quantities": "QUANTITIES",
                "total_amount": "TOTAL AMOUNT",
                "vendor": "VENDOR",
                "date": "DATE"
            }, inplace=True)

            # Convert 'DATE' column to datetime
            purchases_df["DATE"] = pd.to_datetime(purchases_df["DATE"])

            # 🌙 Format date in 12-hour format
            purchases_df["DATE_STR"] = purchases_df["DATE"].apply(
                lambda x: x.strftime("%Y-%m-%d %I:%M %p") if pd.notna(x) else 'N/A')

            # 👉 Show filter options
            st.markdown('##### Select Filter: ')
            filter_option = st.selectbox("Select Filter", ["All Time", "Last 30 Days", "Month Wise", "Week Wise", "Day Wise"],label_visibility='collapsed')

            filtered_df = purchases_df.copy()  # Work on a copy

            if filter_option == "Last 30 Days":
                date_30_days_ago = pd.Timestamp.today() - pd.Timedelta(days=30)
                filtered_df = filtered_df[filtered_df["DATE"] >= date_30_days_ago]
                st.write(f"Showing purchases from the last 30 days: {date_30_days_ago.date()} to {pd.Timestamp.today().date()}")

            elif filter_option == "Month Wise":
                month = st.selectbox("Select Month", [
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"
                ])
                month_number = pd.to_datetime(month, format='%B').month
                filtered_df = filtered_df[filtered_df["DATE"].dt.month == month_number]
                st.write(f"Showing purchases for {month}")

            elif filter_option == "Week Wise":
                start_of_week = pd.Timestamp.today() - pd.Timedelta(days=pd.Timestamp.today().weekday())
                end_of_week = start_of_week + pd.Timedelta(days=6)
                filtered_df = filtered_df[(filtered_df["DATE"] >= start_of_week) & (filtered_df["DATE"] <= end_of_week)]
                st.write(f"Showing purchases for the week: {start_of_week.date()} to {end_of_week.date()}")

            elif filter_option == "Day Wise":
                today = pd.Timestamp.today().normalize()
                filtered_df = filtered_df[filtered_df["DATE"].dt.date == today.date()]
                st.write(f"Showing purchases for today: {today.date()}")

            # 🔍 Search bar for product names
            st.markdown('##### Search for Product:')
            search_query = st.text_input("Search for a product", "",label_visibility='collapsed').strip().lower()
            if search_query:
                filtered_df = filtered_df[filtered_df["PRODUCTS"].str.lower().str.contains(search_query, na=False)]

            # ➕ Calculate totals
            total_quantity = 0
            for qlist in filtered_df["QUANTITIES"]:
                qty = [int(q.strip()) for q in qlist.split(",") if q.strip().isdigit()]
                total_quantity += sum(qty)

            total_cost = filtered_df["TOTAL AMOUNT"].sum()

            # Display the filtered table with formatted date
            display_df = filtered_df.drop(columns=["DATE"]).copy()
            display_df.rename(columns={"DATE_STR": "DATE"}, inplace=True)
            st.table(display_df)

            # Show totals
            st.subheader(f"Total Purchases: Rs. {total_cost:,.2f}")

    elif sub_menu == "Manage Vendors":
        st.header("Manage Vendors")

        # Fetch and display vendors
        vendors = fetch_vendors()
        if vendors:
            for vendor in vendors:
                with st.expander(f"{vendor[1]} ({vendor[2]})"):
                    st.write(f"**Services/Products:** {vendor[3]}")
                    if st.button(f"Delete {vendor[1]}", key=f"delete_{vendor[0]}"):
                        delete_vendor(vendor[0])
                        st.rerun()
        else:
            st.write("No vendors found.")

        # Add a new vendor
        c1,c2,c3 = st.columns(3)
        st.subheader("Add New Vendor")
        with c1:
            st.markdown('##### Vendor Name')
            name = st.text_input("Vendor Name",label_visibility='collapsed')
        with c2:
            st.markdown('##### Phone Numeber')
            phone = st.text_input("Phone Number",label_visibility='collapsed')
        with c3:
            st.markdown('##### Service/ Product')
            service_products = st.text_area("Service/Products",label_visibility='collapsed')

        if st.button("Add Vendor"):
            if name and phone and service_products:
                add_vendor(name, phone, service_products)
                st.success(f"Vendor '{name}' added successfully! ✅")
                st.rerun()
            else:
                st.error("Please fill in all fields.")

                
    # UI Code for Updating Payment and Showing the Outstanding Balance
    if sub_menu == "Update Payments":
        st.header(" Update Vendor Payments")

        purchase_orders = fetch_grouped_purchase_orders()

        if not purchase_orders:
            st.warning("No purchase records found.")
            return

        # ✅ Define purchase_options before using it
        purchase_options = {}

        # ✅ Only include purchase orders with due amount > 1
        for po in purchase_orders:
            order_id = po['order_id']
            vendor = po['vendor']
            products = po['products']
            date = po['date'].strftime("%Y-%m-%d") if po['date'] else 'N/A'
            total = po['total_amount']
            due = get_outstanding_balance(order_id)

            if due > 1:
                label = f"[#{order_id}] {vendor} - {products} | {date} | Rs.{due:,.0f} due"
                purchase_options[label] = order_id

        # ✅ Check if anything was added
        if not purchase_options:
            st.success("🎉 All purchase orders are fully paid! No outstanding payments.")
            return

        # ✅ Display dropdown
        st.subheader("Select a Purchase Order")
        selected_label = st.selectbox("Search or select purchase", list(purchase_options.keys()))
        order_id = purchase_options[selected_label]

        # --- Summary Display ---
        total_amount = next((po['total_amount'] for po in purchase_orders if po['order_id'] == order_id), 0.0)
        outstanding_balance = get_outstanding_balance(order_id)

        st.markdown("### Purchase Summary")
        st.markdown(f"""
            <div style='
                background-color: #f4f4f8;
                padding: 20px;
                border-radius: 12px;
                border: 1px solid #ddd;
                font-size: 16px;
                line-height: 1.7;
            '>
                <b>Purchase ID:</b> #{order_id}<br>
                <b>Total Amount:</b> Rs.{total_amount:,.2f}<br>
                <b>Outstanding Balance:</b> <span style='color: #d11a2a;'>Rs.{outstanding_balance:,.2f}</span>
            </div>
        """, unsafe_allow_html=True)

        # --- Payment History ---
        payment_history = get_payment_history(order_id)
        if payment_history:
            st.subheader("Payment History")
            payment_df = pd.DataFrame(payment_history, columns=["Payment ID", "Amount Paid", "Due Amount", "Date"])
            payment_df['Date'] = pd.to_datetime(payment_df['Date']).dt.strftime("%Y-%m-%d") if not payment_df.empty else 'N/A'
            st.table(payment_df)
        else:
            st.info("No payments recorded yet.")

        # --- Add Payment Form ---
        st.header("Add New Payment")
        with st.form("payment_form"):
            amount = st.number_input(
                "Enter Amount to Pay",
                min_value=0.0,
                max_value=float(outstanding_balance),
                step=100.00,
                format="%.2f"
            )
            submit_button = st.form_submit_button("Record Payment")

            if submit_button and amount > 0:
                new_outstanding_balance = add_payment(order_id, amount)

                if new_outstanding_balance is not False:
                    st.success("✅ Payment recorded successfully!")

                    st.markdown(f"""
                        <div style='
                            background-color: #f4f4f8;
                            padding: 20px;
                            border-radius: 12px;
                            border: 1px solid #ddd;
                            font-size: 16px;
                            line-height: 1.7;
                        '>
                            <b>Purchase ID:</b> #{order_id}<br>
                            <b>Total Amount:</b> Rs.{total_amount:,.2f}<br>
                            <b>Outstanding Balance:</b> <span style='color: #28a745;'>Rs.{new_outstanding_balance:,.2f}</span>
                        </div>
                    """, unsafe_allow_html=True)

                    st.rerun()
                else:
                    st.error("❌ Failed to record payment.")



    # 5th Submenu Vendor ledger
    elif sub_menu == "Vendor Ledger":
        vendor_ledger_page()

# Run the page function
if __name__ == "__main__":
    purchase_page()