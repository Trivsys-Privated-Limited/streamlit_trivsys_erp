import calendar
from datetime import datetime
import decimal
import tempfile
import streamlit as st
import pandas as pd
from credit_sales import fetch_credit_sales_history, fetch_customers, fetch_payments_for_sale, get_customer_balance
from database import get_db_connection
import warnings
from purchase import fetch_grouped_purchase_orders
warnings.filterwarnings("ignore", category=UserWarning, message="pandas only supports SQLAlchemy connectable")
from database import *
import time
import plotly.express as px
from io import BytesIO
import xlsxwriter

def open_account_ui():
    st.title("Open New Account")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('#### Select Account')
        account_title = st.text_input("Account Title",label_visibility = 'collapsed')
        st.markdown('#### Account Number')
        account_number = st.text_input("Account Number",label_visibility = 'collapsed')

    with col2:
        st.markdown('#### Account Holder Name')
        holder_name = st.text_input("Account Holder Name",label_visibility = 'collapsed')
        st.markdown('#### Initial Amount')
        amount = st.number_input("Initial Amount", min_value=0.0, step=0.01,label_visibility = 'collapsed')

    if st.button("Create Account"):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO accounts (account_title, account_number, account_holder_name, opening_balance, amount)
                VALUES (%s, %s, %s, %s, %s)
            """, (account_title, account_number, holder_name, amount, amount))
            account_id = cur.lastrowid
            
            # Create opening balance transaction
            if amount > 0:
                cur.execute("""
                    INSERT INTO transactions (account_id, txn_date, txn_type, amount, description, reference, balance_after, category)
                    VALUES (%s, NOW(), 'credit', %s, 'Opening Balance', 'OPENING', %s, 'Opening Balance')
                """, (account_id, amount, amount))
            
            conn.commit()
            st.success("✅ Account created successfully!")
            time.sleep(1)
            st.rerun()
        except mysql.connector.Error as e:
            st.error(f"Error: {e}")
        finally:
            cur.close()
            conn.close()


def update_account_ui():
    st.subheader("Update Account Balance")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, account_number, account_holder_name, amount FROM accounts")
    accounts = cur.fetchall()
    cur.close()
    conn.close()

    if accounts:
        st.markdown('#### Select Account')
        selected = st.selectbox("Select Account", [f"{a['account_number']} - {a['account_holder_name']}" for a in accounts], label_visibility='collapsed')
        selected_account = next(a for a in accounts if f"{a['account_number']} - {a['account_holder_name']}" == selected)

        st.markdown('#### New Amount')
        new_amount = st.number_input("New Amount", min_value=0.0, step=0.01, value=float(selected_account['amount']), label_visibility='collapsed')

        st.markdown('#### Add Amount')
        add_amount = st.number_input("Add Amount", min_value=0.0, step=0.01, value=0.0, label_visibility='collapsed')

        st.markdown('#### Decrease Amount')
        decrease_amount = st.number_input("Decrease Amount", min_value=0.0, step=0.01, value=0.0, label_visibility='collapsed')

        if st.button("Update Amount"):
            updated_balance = new_amount + add_amount - decrease_amount
            conn = get_db_connection()
            cur = conn.cursor()
            
            try:
                # Record adjustment transaction
                if add_amount > 0:
                    cur.execute("""
                        INSERT INTO transactions (account_id, txn_date, txn_type, amount, description, reference, balance_after, category)
                        VALUES (%s, NOW(), 'credit', %s, 'Manual Balance Adjustment - Addition', 'ADJ', %s, 'Adjustment')
                    """, (selected_account['id'], add_amount, updated_balance))
                
                if decrease_amount > 0:
                    cur.execute("""
                        INSERT INTO transactions (account_id, txn_date, txn_type, amount, description, reference, balance_after, category)
                        VALUES (%s, NOW(), 'debit', %s, 'Manual Balance Adjustment - Deduction', 'ADJ', %s, 'Adjustment')
                    """, (selected_account['id'], decrease_amount, updated_balance))
                
                cur.execute("UPDATE accounts SET amount = %s WHERE id = %s", (updated_balance, selected_account['id']))
                conn.commit()
                st.success("✅ Account updated successfully!")
                time.sleep(1)
                st.rerun()
            except mysql.connector.Error as e:
                st.error(f"Error: {e}")
                conn.rollback()
            finally:
                cur.close()
                conn.close()
    else:
        st.info("No accounts available to update.")


def view_accounts_ui():
    st.subheader("All Accounts")
    conn = get_db_connection()
    df = pd.read_sql("SELECT account_title, account_number, account_holder_name, amount, created_at FROM accounts", conn)
    conn.close()

    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['Opening Month'] = df['created_at'].dt.strftime('%B %Y')

        st.markdown("### Account Summary")
        for _, row in df.iterrows():
            st.markdown(f"**Account Holder:** {row['account_holder_name']}")
            st.markdown(f"**Account Number:** {row['account_number']}")
            st.markdown(f"**Opened In:** {row['Opening Month']}")
            st.markdown(f"**Current Balance:** Rs. {row['amount']:.2f}")
            st.markdown("---")
    else:
        st.info("No accounts available.")


def record_transaction(account_identifier, txn_type, amount, description, reference="", category=""):
    """
    Helper function to record a transaction
    Can accept either account_id (int), account_title, account_number, or account_holder_name (str)
    
    Returns: (success: bool, message: str, new_balance: float or None)
    """
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    
    try:
        # If account_identifier is a string, try to get the actual account
        if isinstance(account_identifier, str):
            cur.execute("""
                SELECT id, amount, account_title FROM accounts 
                WHERE account_holder_name = %s OR account_number = %s OR account_title = %s
                OR CONCAT(account_number, ' - ', account_holder_name) = %s
                LIMIT 1
            """, (account_identifier, account_identifier, account_identifier, account_identifier))
            account = cur.fetchone()
        else:
            # Get current balance using ID
            cur.execute("SELECT id, amount, account_title FROM accounts WHERE id = %s", (account_identifier,))
            account = cur.fetchone()
        
        if not account:
            return False, "Account not found", None
        
        # Use the actual account ID from now on
        actual_account_id = account['id']
        current_balance = float(account['amount'])
        
        # Calculate new balance (NEGATIVE BALANCES NOW ALLOWED)
        if txn_type == 'credit':
            new_balance = current_balance + float(amount)
        else:  # debit
            new_balance = current_balance - float(amount)
            # Insufficient balance check REMOVED - negative balances are now permitted
        
        # Insert transaction
        cur.execute("""
            INSERT INTO transactions (account_id, txn_date, txn_type, amount, description, reference, balance_after, category)
            VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s)
        """, (actual_account_id, txn_type, amount, description, reference, new_balance, category))
        
        # Update account balance
        cur.execute("UPDATE accounts SET amount = %s WHERE id = %s", (new_balance, actual_account_id))
        
        conn.commit()
        return True, f"Transaction recorded successfully. New balance: Rs. {new_balance:.2f}", new_balance
    
    except mysql.connector.Error as e:
        conn.rollback()
        return False, f"Database error: {str(e)}", None
    finally:
        cur.close()
        conn.close()
        
def fetch_customer_transactions(customer_name):
    """
    Fetch all manual transactions for a specific customer.
    Returns list of dicts with transaction details.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        query = """
            SELECT id, customer_name, txn_date, txn_type, amount, 
                   description, reference, category, source
            FROM customer_transactions
            WHERE customer_name = %s
            ORDER BY txn_date ASC
        """
        cur.execute(query, (customer_name,))
        transactions = cur.fetchall()
        cur.close()
        conn.close()
        return transactions
    except Exception as e:
        print(f"Error fetching customer transactions: {e}")
        return []


def record_customer_transaction(customer_name, txn_type, amount, description, reference, category):
    """
    Record a manual transaction linked to a customer.
    txn_type: 'debit' (customer owes more) or 'credit' (customer owes less)
    Returns: (success: bool, message: str)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = """
            INSERT INTO customer_transactions 
            (customer_name, txn_date, txn_type, amount, description, reference, category, source)
            VALUES (%s, NOW(), %s, %s, %s, %s, %s, 'Manual Transaction')
        """
        cur.execute(query, (customer_name, txn_type, amount, description, reference, category))
        conn.commit()
        cur.close()
        conn.close()
        return True, "Customer transaction recorded successfully"
    except Exception as e:
        print(f"Error recording customer transaction: {e}")
        return False, f"Error: {str(e)}"
    
def fetch_vendor_transactions(vendor_name):
    """
    Fetch all manual transactions for a specific vendor.
    Returns list of dicts with transaction details.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        query = """
            SELECT id, vendor_name, txn_date, txn_type, amount, 
                   description, reference, category, source
            FROM vendor_manual_transactions
            WHERE vendor_name = %s
            ORDER BY txn_date ASC
        """
        cur.execute(query, (vendor_name,))
        transactions = cur.fetchall()
        cur.close()
        conn.close()
        return transactions
    except Exception as e:
        print(f"Error fetching vendor transactions: {e}")
        return []


def record_vendor_transaction(vendor_name, txn_type, amount, description, reference, category):
    """
    Record a manual transaction linked to a vendor.
    txn_type: 'credit' (company owes vendor more) or 'debit' (company paid vendor)
    Returns: (success: bool, message: str)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = """
            INSERT INTO vendor_manual_transactions 
            (vendor_name, txn_date, txn_type, amount, description, reference, category, source)
            VALUES (%s, NOW(), %s, %s, %s, %s, %s, 'Manual Transaction')
        """
        cur.execute(query, (vendor_name, txn_type, amount, description, reference, category))
        conn.commit()
        cur.close()
        conn.close()
        return True, "Vendor transaction recorded successfully"
    except Exception as e:
        print(f"Error recording vendor transaction: {e}")
        return False, f"Error: {str(e)}"
    
def add_transaction_ui():
    st.subheader("Record Transaction")
    
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, account_number, account_holder_name, amount FROM accounts")
    accounts = cur.fetchall()
    cur.close()
    conn.close()
    
    if not accounts:
        st.warning("No accounts available. Please create an account first.")
        return
    
    # Fetch customers for optional linking
    customers = fetch_customers()
    customer_options = ["None (Not linked)"] + [name for _, name in customers]
    
    # Fetch vendors for optional linking - FIXED: Handle tuple with more than 2 elements
    vendors = fetch_vendors()
    vendor_options = ["None (Not linked)"] + [v[1] for v in vendors]  # v[1] is vendor name
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('#### Select Account')
        selected = st.selectbox("Select Account", 
                                [f"{a['account_number']} - {a['account_holder_name']}" for a in accounts], 
                                label_visibility='collapsed')
        selected_account = next(a for a in accounts if f"{a['account_number']} - {a['account_holder_name']}" == selected)
        
        st.markdown('#### Link to Customer (Optional)')
        selected_customer = st.selectbox("Link to Customer", customer_options, 
                                        label_visibility='collapsed',
                                        help="Optional: Link this transaction to a customer ledger")
        
        st.markdown('#### Link to Vendor (Optional)')
        selected_vendor = st.selectbox("Link to Vendor", vendor_options, 
                                      label_visibility='collapsed',
                                      help="Optional: Link this transaction to a vendor ledger")
        
        st.markdown('#### Transaction Type')
        # UI CHANGE: Display "Money In" and "Money Out" to user
        # Backend: Credit = Money In to company, Debit = Money Out from company
        txn_type = st.selectbox("Transaction Type", ["Money In", "Money Out"], 
                                label_visibility='collapsed')
        # Map UI selection to backend txn_type
        txn_type_value = 'credit' if txn_type == 'Money In' else 'debit'
        
        st.markdown('#### Amount')
        amount = st.number_input("Amount", min_value=0.01, step=0.01, label_visibility='collapsed')
    
    with col2:
        st.markdown('#### Category')
        categories = ["Expense", "Income", "Transfer", "Adjustment", "Payment", "Refund", "Other"]
        category = st.selectbox("Category", categories, label_visibility='collapsed')
        
        st.markdown('#### Reference')
        reference = st.text_input("Reference (e.g., Invoice #, Receipt #)", label_visibility='collapsed')
        
        st.markdown('#### Description')
        description = st.text_area("Description", label_visibility='collapsed')
    
    st.info(f"**Current Balance:** Rs. {selected_account['amount']:.2f}")
    
    # Show linking info if customer or vendor selected
    # When Money IN to company account → Customer ledger shows Money OUT (credit reduces customer debt)
    # When Money OUT from company account → Customer ledger shows Money IN (debit increases customer debt)
    if selected_customer != "None (Not linked)":
        if txn_type_value == 'credit':  # Money IN to company
            st.info(f"📊 This transaction will appear in **{selected_customer}'s ledger** as **Money Out** (customer payment received)")
        else:  # Money OUT from company
            st.info(f"📊 This transaction will appear in **{selected_customer}'s ledger** as **Money In** (customer receivable)")
    
    # When Money IN to company account → Vendor ledger shows Money OUT (debit = company paid vendor)
    # When Money OUT from company account → Vendor ledger shows Money IN (credit = company owes vendor)
    if selected_vendor != "None (Not linked)":
        if txn_type_value == 'debit':  # Money OUT from company
            st.info(f"🏢 This transaction will appear in **{selected_vendor}'s ledger** as **Money In** (company owes vendor)")
        else:  # Money IN to company
            st.info(f"🏢 This transaction will appear in **{selected_vendor}'s ledger** as **Money Out** (company paid vendor)")
    
    # Warning if both customer and vendor selected
    if selected_customer != "None (Not linked)" and selected_vendor != "None (Not linked)":
        st.warning("⚠️ Both customer and vendor selected. Transaction will be recorded in both ledgers.")
    
    if st.button("Record Transaction", type="primary"):
        if not description:
            st.error("Please enter a description")
            return
        
        # Record account transaction (existing logic - untouched)
        success, message, new_balance = record_transaction(
            selected_account['id'], 
            txn_type_value, 
            amount, 
            description, 
            reference, 
            category
        )
        
        if success:
            success_messages = [f"✅ {message}"]
            
            # If customer is selected, also record customer transaction
            if selected_customer != "None (Not linked)":
                cust_success, cust_message = record_customer_transaction(
                    selected_customer,
                    txn_type_value,
                    amount,
                    description,
                    reference,
                    category
                )
                if cust_success:
                    success_messages.append(f"Customer ledger updated for {selected_customer}")
                else:
                    st.warning(f"⚠️ Customer ledger update failed: {cust_message}")
            
            # If vendor is selected, also record vendor transaction
            if selected_vendor != "None (Not linked)":
                vend_success, vend_message = record_vendor_transaction(
                    selected_vendor,
                    txn_type_value,
                    amount,
                    description,
                    reference,
                    category
                )
                if vend_success:
                    success_messages.append(f"Vendor ledger updated for {selected_vendor}")
                else:
                    st.warning(f"⚠️ Vendor ledger update failed: {vend_message}")
            
            # Display all success messages
            st.success(" | ".join(success_messages))
            
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"❌ {message}")

def generate_general_ledger_excel(account_id, month, year):
    """
    Generate Excel report for General Ledger with Opening Balance row
    """
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    
    # Get account details
    cur.execute("""
        SELECT account_number, account_holder_name, account_title 
        FROM accounts WHERE id = %s
    """, (account_id,))
    account = cur.fetchone()
    
    # Get transactions for the month
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    # Get opening balance (balance before start of month)
    cur.execute("""
        SELECT balance_after 
        FROM transactions 
        WHERE account_id = %s AND txn_date < %s 
        ORDER BY txn_date DESC, id DESC 
        LIMIT 1
    """, (account_id, start_date))
    opening = cur.fetchone()
    opening_balance = float(opening['balance_after']) if opening else 0.0
    
    # Get all transactions in the month
    cur.execute("""
        SELECT txn_date, txn_type, amount, description, reference, category, balance_after
        FROM transactions
        WHERE account_id = %s AND txn_date >= %s AND txn_date < %s
        ORDER BY txn_date, id
    """, (account_id, start_date, end_date))
    transactions = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Create Excel file
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('General Ledger')
    
    # Formats
    title_format = workbook.add_format({
        'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter'
    })
    header_format = workbook.add_format({
        'bold': True, 'bg_color': '#4472C4', 'font_color': 'white', 
        'border': 1, 'align': 'center'
    })
    cell_format = workbook.add_format({'border': 1})
    money_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    date_format = workbook.add_format({'border': 1, 'num_format': 'dd-mmm-yyyy'})
    total_format = workbook.add_format({
        'bold': True, 'bg_color': '#D9E1F2', 'border': 1, 'num_format': '#,##0.00'
    })
    opening_balance_format = workbook.add_format({
        'bold': True, 'bg_color': '#FFF2CC', 'border': 1, 'align': 'left'
    })
    opening_balance_money_format = workbook.add_format({
        'bold': True, 'bg_color': '#FFF2CC', 'border': 1, 'num_format': '#,##0.00'
    })
    
    # Set column widths
    worksheet.set_column('A:A', 15)
    worksheet.set_column('B:B', 40)
    worksheet.set_column('C:C', 15)
    worksheet.set_column('D:D', 15)
    worksheet.set_column('E:E', 15)
    worksheet.set_column('F:F', 15)
    worksheet.set_column('G:G', 15)
    
    # Write header
    month_name = calendar.month_name[month]
    worksheet.merge_range('A1:G1', f'GENERAL LEDGER - {month_name} {year}', title_format)
    
    row = 2
    worksheet.write(row, 0, 'Account Number:', workbook.add_format({'bold': True}))
    worksheet.write(row, 1, account['account_number'])
    row += 1
    worksheet.write(row, 0, 'Account Holder:', workbook.add_format({'bold': True}))
    worksheet.write(row, 1, account['account_holder_name'])
    row += 1
    worksheet.write(row, 0, 'Account Title:', workbook.add_format({'bold': True}))
    worksheet.write(row, 1, account['account_title'])
    row += 2
    
    # UI CHANGE: Column headers changed to "Money Out" and "Money In"
    headers = ['Date', 'Description', 'Reference', 'Category', 'Money Out', 'Money In', 'Balance']
    for col, header in enumerate(headers):
        worksheet.write(row, col, header, header_format)
    row += 1
    
    # ADD OPENING BALANCE ROW (if balance exists)
    if opening_balance != 0:
        # Format the date as 01-MMM-YYYY for opening balance
        from datetime import datetime
        opening_date = datetime.strptime(start_date, '%Y-%m-%d')
        
        worksheet.write_datetime(row, 0, opening_date, date_format)
        worksheet.write(row, 1, 'Opening Balance (Carried forward from previous period)', opening_balance_format)
        worksheet.write(row, 2, '', opening_balance_format)
        worksheet.write(row, 3, '', opening_balance_format)
        worksheet.write(row, 4, '', opening_balance_format)  # Money Out - empty
        worksheet.write(row, 5, '', opening_balance_format)  # Money In - empty
        worksheet.write(row, 6, opening_balance, opening_balance_money_format)  # Balance
        row += 1
    
    # Write transaction rows
    total_money_out = 0
    total_money_in = 0
    
    for txn in transactions:
        worksheet.write_datetime(row, 0, txn['txn_date'], date_format)
        worksheet.write(row, 1, txn['description'], cell_format)
        worksheet.write(row, 2, txn['reference'] or '', cell_format)
        worksheet.write(row, 3, txn['category'] or '', cell_format)
        
        # MAPPING: debit (DB) = Money Out (UI), credit (DB) = Money In (UI)
        if txn['txn_type'] == 'debit':  # Money Out
            worksheet.write(row, 4, float(txn['amount']), money_format)
            worksheet.write(row, 5, '', cell_format)
            total_money_out += float(txn['amount'])
        else:  # credit = Money In
            worksheet.write(row, 4, '', cell_format)
            worksheet.write(row, 5, float(txn['amount']), money_format)
            total_money_in += float(txn['amount'])
        
        worksheet.write(row, 6, float(txn['balance_after']), money_format)
        row += 1
    
    # Totals row
    worksheet.write(row, 3, 'TOTAL:', workbook.add_format({'bold': True, 'align': 'right'}))
    worksheet.write(row, 4, total_money_out, total_format)
    worksheet.write(row, 5, total_money_in, total_format)
    row += 1
    
    # Closing balance
    closing_balance = transactions[-1]['balance_after'] if transactions else opening_balance
    worksheet.write(row, 0, 'Closing Balance:', workbook.add_format({'bold': True}))
    worksheet.write(row, 6, float(closing_balance), total_format)
    
    workbook.close()
    output.seek(0)
    
    return output

def general_ledger_ui():
    st.subheader("General Ledger Report")
    
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, account_number, account_holder_name FROM accounts ORDER BY account_number")
    accounts = cur.fetchall()
    cur.close()
    conn.close()
    
    if not accounts:
        st.warning("No accounts available. Please create an account first.")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('#### Select Account')
        selected = st.selectbox("Select Account", 
                                [f"{a['account_number']} - {a['account_holder_name']}" for a in accounts], 
                                label_visibility='collapsed', key='gl_account')
        selected_account = next(a for a in accounts if f"{a['account_number']} - {a['account_holder_name']}" == selected)
    
    with col2:
        st.markdown('#### Select Month')
        current_month = datetime.now().month
        months = [(i, calendar.month_name[i]) for i in range(1, 13)]
        month_display = st.selectbox("Month", months, format_func=lambda x: x[1], 
                                     index=current_month-1, label_visibility='collapsed')
        selected_month = month_display[0]
    
    with col3:
        st.markdown('#### Select Year')
        current_year = datetime.now().year
        years = list(range(current_year - 5, current_year + 2))
        selected_year = st.selectbox("Year", years, index=5, label_visibility='collapsed')
    
    # Show preview
    if st.button("Preview Report", type="secondary"):
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        
        start_date = f"{selected_year}-{selected_month:02d}-01"
        if selected_month == 12:
            end_date = f"{selected_year + 1}-01-01"
        else:
            end_date = f"{selected_year}-{selected_month + 1:02d}-01"
        
        # Get opening balance (balance before start of selected period)
        cur.execute("""
            SELECT balance_after 
            FROM transactions 
            WHERE account_id = %s AND txn_date < %s 
            ORDER BY txn_date DESC, id DESC 
            LIMIT 1
        """, (selected_account['id'], start_date))
        opening = cur.fetchone()
        opening_balance = float(opening['balance_after']) if opening else 0.0
        
        # Get transactions for the selected period
        cur.execute("""
            SELECT txn_date, txn_type, amount, description, reference, category, balance_after
            FROM transactions
            WHERE account_id = %s AND txn_date >= %s AND txn_date < %s
            ORDER BY txn_date, id
        """, (selected_account['id'], start_date, end_date))
        transactions = cur.fetchall()
        cur.close()
        conn.close()
        
        st.markdown("---")
        st.markdown(f"### {calendar.month_name[selected_month]} {selected_year}")
        
        # BUILD DISPLAY DATA WITH OPENING BALANCE ROW
        display_data = []
        
        # ADD OPENING BALANCE ROW (if there's a carried forward balance)
        if opening_balance != 0:
            display_data.append({
                'Date': start_date.split('-')[2] + '-' + calendar.month_abbr[selected_month] + '-' + str(selected_year),
                'Description': f'Opening Balance (Carried forward from previous period)',
                'Reference': '',
                'Category': '',
                'Money Out': '',
                'Money In': '',
                'Balance': f"Rs. {opening_balance:,.2f}"
            })
        
        # ADD TRANSACTION ROWS
        if transactions:
            df = pd.DataFrame(transactions)
            df['txn_date'] = pd.to_datetime(df['txn_date']).dt.strftime('%d-%b-%Y')
            
            # UI CHANGE: Display "Money Out" and "Money In" columns instead of Debit/Credit
            # MAPPING: debit → Money Out, credit → Money In (from company's perspective)
            df['Money Out'] = df.apply(lambda x: f"Rs. {float(x['amount']):,.2f}" if x['txn_type'] == 'debit' else '', axis=1)
            df['Money In'] = df.apply(lambda x: f"Rs. {float(x['amount']):,.2f}" if x['txn_type'] == 'credit' else '', axis=1)
            df['Balance'] = df['balance_after'].apply(lambda x: f"Rs. {float(x):,.2f}")
            
            # Convert transactions to list of dicts
            for _, row in df.iterrows():
                display_data.append({
                    'Date': row['txn_date'],
                    'Description': row['description'],
                    'Reference': row['reference'] if row['reference'] else '',
                    'Category': row['category'] if row['category'] else '',
                    'Money Out': row['Money Out'],
                    'Money In': row['Money In'],
                    'Balance': row['Balance']
                })
        
        # DISPLAY THE COMPLETE LEDGER (Opening Balance + Transactions)
        if display_data:
            display_df = pd.DataFrame(display_data)
            st.table(display_df)
            
            # Calculate totals (excluding opening balance row)
            total_money_out = sum(float(t['amount']) for t in transactions if t['txn_type'] == 'debit') if transactions else 0
            total_money_in = sum(float(t['amount']) for t in transactions if t['txn_type'] == 'credit') if transactions else 0
            closing_balance = float(transactions[-1]['balance_after']) if transactions else opening_balance
            
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total Money Out", f"Rs. {total_money_out:,.2f}")
            col_b.metric("Total Money In", f"Rs. {total_money_in:,.2f}")
            col_c.metric("Closing Balance", f"Rs. {closing_balance:,.2f}")
        else:
            st.info("No transactions found for this period.")
            st.markdown(f"**Opening Balance:** Rs. {opening_balance:,.2f}")
            st.markdown(f"**Closing Balance:** Rs. {opening_balance:,.2f}")
    
    # Download button
    if st.button("📥 Download General Ledger (Excel)", type="primary"):
        excel_file = generate_general_ledger_excel(selected_account['id'], selected_month, selected_year)
        
        filename = f"GL_{selected_account['account_number']}_{calendar.month_name[selected_month]}_{selected_year}.xlsx"
        
        st.download_button(
            label="💾 Click to Download",
            data=excel_file,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def accounts_page():
    st.title("Accounts Management")
    
    if st.button("Back to Home"):
        st.session_state.page = "Home"  
        st.rerun()

    menu_items = [
        "Open Account",
        # "Update Account",
        "View Accounts",
        "Record Transaction",
        "General Ledger"
    ]
    if 'sub_menu' not in st.session_state:
        st.session_state.sub_menu = "Open Account"
    with st.sidebar:
        st.markdown("### ACCOUNTS")
        for item in menu_items:
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.sub_menu = item
                st.rerun()
    
    sub_menu = st.session_state.sub_menu
    
    if sub_menu == "Open Account":
        open_account_ui()
    elif sub_menu == "Update Account":
        update_account_ui()
    elif sub_menu == "View Accounts":
        view_accounts_ui()
    elif sub_menu == "Record Transaction":
        add_transaction_ui()
    elif sub_menu == "General Ledger":
        general_ledger_ui()