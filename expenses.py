import calendar
from datetime import datetime, timedelta
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
import os


if "sub_menu" not in st.session_state:
    st.session_state.sub_menu = 'Add Expense'


def record_expense_transaction(account_title, amount, description, reference="", person_name=""):
    """
    Record expense transaction in the transactions table and update account balance
    Returns: (success: bool, message: str, new_balance: float or None)
    """
    from accounts import record_transaction
    
    # Build full description
    full_description = description
    if person_name:
        full_description = f"{description} - Paid to: {person_name}"
    
    return record_transaction(account_title, 'debit', amount, full_description, reference, 'Expense')


def insert_expense(amount, person_name, description, expense_from_account=None, invoice_file=None, expense_date=None):
    """
    Insert an expense and update the account balance atomically with transaction logging.
    """
    conn = get_db_connection()
    if not conn:
        st.error("Database connection unavailable.")
        return None

    cursor = conn.cursor()
    try:
        # Check if account exists
        if expense_from_account and expense_from_account != 'Cash':
            cursor.execute("SELECT id, amount FROM accounts WHERE account_title = %s", (expense_from_account,))
            acc = cursor.fetchone()
            if not acc:
                st.error(f"Account '{expense_from_account}' does not exist.")
                return None
            
            account_id = acc[0]
            current_balance = float(acc[1]) if acc[1] is not None else 0.0
            
            # Check sufficient balance
            if current_balance < float(amount):
                st.error(f"Insufficient balance in '{expense_from_account}'. Available: Rs. {current_balance:.2f}, Required: Rs. {amount:.2f}")
                return None

        # Insert expense record
        query = """
            INSERT INTO expenses (amount, person_name, expense_from_account, description, invoice_file, expense_date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (amount, person_name, expense_from_account, description, invoice_file, expense_date)
        cursor.execute(query, values)
        expense_id = cursor.lastrowid

        # If account provided and not Cash, record transaction
        if expense_from_account and expense_from_account != 'Cash':
            # Calculate new balance
            new_balance = current_balance - float(amount)
            
            # Insert transaction record
            full_description = f"{description} - Paid to: {person_name}"
            cursor.execute("""
                INSERT INTO transactions (account_id, txn_date, txn_type, amount, description, reference, balance_after, category)
                VALUES (%s, %s, 'debit', %s, %s, %s, %s, 'Expense')
            """, (account_id, expense_date or datetime.now(), amount, full_description, f'EXP-{expense_id}', new_balance))
            
            # Update account balance
            cursor.execute("UPDATE accounts SET amount = %s WHERE id = %s", (new_balance, account_id))

        conn.commit()
        
        if expense_from_account and expense_from_account != 'Cash':
            st.success(f"✅ Expense of Rs. {amount:.2f} recorded. New balance: Rs. {new_balance:.2f}")
        else:
            st.success(f"✅ Cash expense of Rs. {amount:.2f} recorded for {person_name}.")

        return expense_id

    except Exception as e:
        st.error(f"Error occurred while inserting expense: {str(e)}")
        conn.rollback()
        return None
    finally:
        try:
            cursor.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass


def fetch_accounts():
    """Return a list of account dicts: [{'id':..., 'account_title':..., 'account_number':..., 'amount':...}, ...]"""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, account_title, account_number, amount FROM accounts ORDER BY account_title")
        accounts = cursor.fetchall()
        conn.close()
        return accounts
    except Exception as e:
        st.error(f"Error fetching accounts: {e}")
        try:
            conn.close()
        except:
            pass
        return []


def get_account_by_title(title):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM accounts WHERE account_title = %s", (title,))
        acc = cursor.fetchone()
        conn.close()
        return acc
    except Exception as e:
        st.error(f"Error fetching account: {e}")
        try:
            conn.close()
        except:
            pass
        return None


def fetch_expenses():
    query = "SELECT expense_date, amount, person_name, expense_from_account, description FROM expenses"
    conn = get_db_connection()
    if conn:
        try:
            expenses_df = pd.read_sql(query, conn)
            return expenses_df
        except Exception as e:
            st.error(f"Error occurred while fetching expenses: {str(e)}")
        finally:
            conn.close()
    return pd.DataFrame()


def fetch_filtered_expenses(filter_option, selected_month=None):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            today = datetime.today()

            if filter_option == "Daily":
                start_date = today.date()
                query = f"SELECT expense_date, amount, person_name, expense_from_account, description, invoice_file FROM expenses WHERE DATE(expense_date) = '{start_date}'"
                
            elif filter_option == "Weekly":
                start_date = today - timedelta(days=7)
                query = f"SELECT expense_date, amount, person_name, expense_from_account, description, invoice_file FROM expenses WHERE expense_date >= '{start_date}'"
                
            elif filter_option == "Monthly":
                if selected_month:
                    query = f"SELECT expense_date, amount, person_name, expense_from_account, description, invoice_file FROM expenses WHERE MONTH(expense_date) = {selected_month} AND YEAR(expense_date) = {today.year}"
                else:
                    st.warning("Please select a month to filter by.")
                    return pd.DataFrame()
                
            elif filter_option == "Last 30 Days":
                start_date = today - timedelta(days=30)
                query = f"SELECT expense_date, amount, person_name, expense_from_account, description, invoice_file FROM expenses WHERE expense_date >= '{start_date}'"
            
            cursor.execute(query)
            expenses = cursor.fetchall()
            if not expenses:
                return pd.DataFrame()

            columns = ['expense_date', 'amount', 'person_name', 'expense_from_account', 'description', 'invoice_file']
            expenses_df = pd.DataFrame(expenses, columns=columns)

            return expenses_df
        except Exception as e:
            st.error(f"Error occurred while fetching expenses: {str(e)}")
        finally:
            conn.close()
    return pd.DataFrame()


def fetch_total_expenses(filter_option, selected_month=None):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            today = datetime.today()

            if filter_option == "Daily":
                start_date = today.date()
                query = f"SELECT SUM(amount) FROM expenses WHERE DATE(expense_date) = '{start_date}'"
                
            elif filter_option == "Weekly":
                start_date = today - timedelta(days=7)
                query = f"SELECT SUM(amount) FROM expenses WHERE expense_date >= '{start_date}'"
                
            elif filter_option == "Monthly":
                if selected_month:
                    query = f"SELECT SUM(amount) FROM expenses WHERE MONTH(expense_date) = {selected_month} AND YEAR(expense_date) = {today.year}"
                else:
                    st.warning("Please select a month to filter by.")
                    return None
                
            elif filter_option == "Last 30 Days":
                start_date = today - timedelta(days=30)
                query = f"SELECT SUM(amount) FROM expenses WHERE expense_date >= '{start_date}'"
            
            cursor.execute(query)
            total_expense = cursor.fetchone()[0]
            
            return total_expense if total_expense else 0
        except Exception as e:
            st.error(f"Error occurred while fetching expenses: {str(e)}")
        finally:
            conn.close()
    return 0


def save_uploaded_file(uploaded_file, expense_id):
    """
    Save the uploaded file to the expenses_bills folder with expense_id as the prefix.
    Returns the file path if successful, None otherwise.
    """
    try:
        bills_folder = "expenses_bills"
        if not os.path.exists(bills_folder):
            os.makedirs(bills_folder)

        file_extension = uploaded_file.name.split(".")[-1]
        file_name = f"{expense_id}.{file_extension}"
        file_path = os.path.join(bills_folder, file_name)

        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        return file_path
    except Exception as e:
        st.error(f"Error saving uploaded file: {e}")
        return None


def expense_page():
    
    st.title("Expense Tracking")
    
    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.rerun()

    menu_items = [
            "Add Expense",
            "Expense History",
        ]
    with st.sidebar:
        st.markdown("### EXPENSES")
        for item in menu_items:
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.sub_menu = item
                st.rerun()
    sub_menu = st.session_state.sub_menu

    if sub_menu == "Add Expense":
        st.header("Miscellaneous Expenses")
        st.markdown("**Track all your business-related expenses like payments for services or supplies.**")

        with st.form(key='expense_form'):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown('##### Expense Amount')
                amount = st.number_input("Expense Amount (Rs.)", min_value=0.00, step=100.00, format="%.2f", label_visibility='collapsed')
            
            with col2:
                st.markdown('##### Person/Service Name')
                person_name = st.text_input("Person/Service Name", label_visibility='collapsed')

            # Account selection with balance display
            accounts = fetch_accounts()
            account_titles = [a['account_title'] for a in accounts] if accounts else []
            st.markdown('##### From Account')
            
            account_options = ['-- Select --', 'Cash'] + account_titles
            expense_account = st.selectbox('Select account', account_options, index=0, key='expense_account_select')

            # Show account balance if account is selected
            if expense_account not in ['-- Select --', 'Cash', None]:
                selected_acc = next((a for a in accounts if a['account_title'] == expense_account), None)
                if selected_acc:
                    current_balance = float(selected_acc['amount'])
                    st.info(f"💰 Available Balance: Rs. {current_balance:,.2f}")
                    
                    # Warning if expense exceeds balance
                    if amount > 0 and amount > current_balance:
                        st.warning(f"⚠️ Expense amount (Rs. {amount:,.2f}) exceeds available balance!")

            st.markdown('##### Description of the Expense')
            description = st.text_area("Description of the Expense", height=100, label_visibility='collapsed')

            st.markdown('##### Select Expense Date')
            expense_date = st.date_input("Select Expense Date", value=datetime.today(), label_visibility='collapsed')
            expense_date = datetime.combine(expense_date, datetime.now().time())
            st.markdown('##### Upload Invoice/Bill (Optional)')
            uploaded_file = st.file_uploader("Upload Invoice/Bill", type=["png", "jpg", "jpeg"], label_visibility='collapsed')

            submit_button = st.form_submit_button(label="Add Expense")

            if submit_button:
                if amount <= 0:
                    st.warning("Amount should be greater than 0.")
                elif not person_name.strip():
                    st.warning("Please provide the name of the person/service.")
                elif not description.strip():
                    st.warning("Please provide a description of the expense.")
                elif expense_account == '-- Select --':
                    st.warning("Please select an account or Cash.")
                else:
                    try:
                        # Insert expense into database
                        expense_id = insert_expense(
                            amount,
                            person_name,
                            description,
                            expense_from_account=expense_account.strip() if expense_account and expense_account.strip() else None,
                            invoice_file=None,
                            expense_date=expense_date
                        )

                        # Save the uploaded file if provided
                        if uploaded_file and expense_id:
                            file_path = save_uploaded_file(uploaded_file, expense_id)
                            if file_path:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE expenses SET invoice_file = %s WHERE id = %s", (file_path, expense_id))
                                conn.commit()
                                cursor.close()
                                conn.close()

                        if expense_id:
                            # Clear form fields
                            if "expense_form" in st.session_state:
                                del st.session_state["expense_form"]
                            st.session_state["Person/Service Name"] = ""
                            st.session_state["Description of the Expense"] = ""
                            st.session_state["Expense Amount (Rs.)"] = 0.00

                            time.sleep(1.5)
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error occurred while adding expense: {str(e)}")

    elif sub_menu == 'Expense History':
        st.header("Expenses History")
        
        col1, col2 = st.columns([2, 2])
        with col1:
            st.markdown('#### Filter Period')
            filter_option = st.selectbox(
                "Filter Period",
                ["Daily", "Weekly", "Monthly", "Last 30 Days"],
                label_visibility='collapsed'
            )
        
        with col2:
            if filter_option == "Monthly":
                st.markdown('#### Select Month')
                selected_month = st.selectbox(
                    "Select Month",
                    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                    format_func=lambda x: datetime(2022, x, 1).strftime('%B'),
                    key="month_filter_selectbox",
                    label_visibility='collapsed'
                )
            else:
                selected_month = None

        st.markdown("---")

        expenses_df = fetch_filtered_expenses(filter_option, selected_month)
        
        if not expenses_df.empty:
            expenses_df['expense_date'] = pd.to_datetime(expenses_df['expense_date'])
            expenses_df = expenses_df.sort_values(by='expense_date', ascending=False)
            expenses_df['expense_date'] = expenses_df['expense_date'].dt.strftime('%d-%m-%Y')

            total_expenses = expenses_df['amount'].sum()
            st.markdown(f"### 💰 Total Expenses: Rs. {total_expenses:,.2f}")
            st.markdown("---")

            col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 1.5, 2, 2.5, 1.2])
            with col1:
                st.markdown('##### Date')
            with col2:
                st.markdown('##### Amount')
            with col3:
                st.markdown('##### Person')
            with col4:
                st.markdown('##### From Account')
            with col5:
                st.markdown('##### Description')
            with col6:
                st.markdown('##### Action')

            st.markdown('---')

            for idx, row in expenses_df.iterrows():
                col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 1.5, 2, 2.5, 1.2])
                
                with col1:
                    st.write(f"📅 {row['expense_date']}")
                with col2:
                    st.write(f"**Rs. {row['amount']:,.2f}**")
                with col3:
                    st.write(row['person_name'])
                with col4:
                    account_display = row['expense_from_account'] if row['expense_from_account'] else 'N/A'
                    st.write(account_display)
                with col5:
                    desc = row['description']
                    if len(desc) > 50:
                        desc = desc[:50] + "..."
                    st.write(desc)
                with col6:
                    if row['invoice_file'] and os.path.exists(row['invoice_file']):
                        if st.button("🖼️ View", key=f"view_invoice_{idx}", use_container_width=True):
                            st.session_state[f"show_image_{idx}"] = not st.session_state.get(f"show_image_{idx}", False)
                    else:
                        st.write("—")
                
                st.markdown("---")
                
                if st.session_state.get(f"show_image_{idx}", False) and row['invoice_file']:
                    try:
                        from PIL import Image
                        img = Image.open(row['invoice_file'])
                        
                        st.markdown(f"""
                        <div style="background-color: #f8fafc; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                            <h4 style="color: #1e293b; margin-bottom: 0.5rem;">📄 Invoice for {row['person_name']}</h4>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.image(img, use_container_width=False)
                        
                        with open(row['invoice_file'], "rb") as file:
                            st.download_button(
                                label="📥 Download Invoice",
                                data=file,
                                file_name=os.path.basename(row['invoice_file']),
                                mime="image/jpeg",
                                key=f"download_{idx}"
                            )
                        
                        st.markdown("---")
                    except Exception as e:
                        st.error(f"Error loading image: {e}")
                        st.markdown("---")
        else:
            st.warning("No expenses found for the selected filter.")
        
        if st.button("Generate and Download PDF"):
            if selected_month:
                selected_month_name = datetime(2022, selected_month, 1).strftime('%B')
                filter_option = selected_month_name
            generate_expenses_pdf(expenses_df, filter_option)


def generate_expenses_pdf(expenses, filter_type):
    from fpdf import FPDF
    import tempfile

    if isinstance(expenses, pd.DataFrame):
        expenses = expenses.to_dict('records')
    
    if not expenses:
        st.warning("No expenses to generate report.")
        return

    class PDF(FPDF):
        def header(self):
            import os
            logo_path = "static/trivsys.png"
            logo_width = 30
            logo_height = 20
            if os.path.exists(logo_path):
                try:
                    self.image(logo_path, y=5, w=logo_width, h=logo_height)
                except RuntimeError as e:
                    print(f"Error loading image: {e}")
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'Expense Report', 0, 1, 'C')
            self.set_font('Arial', 'B', 14)
            self.cell(0, 10, f'{filter_type.upper()} EXPENSE REPORT', 0, 1, 'C')
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)

    pdf.cell(25, 10, 'Date', 0, 0, 'C')
    pdf.cell(55, 10, 'From Account', 0, 0, 'L')
    pdf.cell(25, 10, 'Amount', 0, 0, 'C')
    pdf.cell(90, 10, 'Description', 0, 0, 'L')
    pdf.ln()

    pdf.set_font('Arial', '', 11)
    total_expense = 0
    for expense in expenses:
        formatted_date = str(expense.get('expense_date', 'N/A'))
        from_account = str(expense.get('expense_from_account', 'N/A'))
        amount = float(expense.get('amount', 0))
        description = str(expense.get('description', 'N/A'))
        
        pdf.cell(25, 10, formatted_date, 0, 0, 'L')
        pdf.cell(55, 10, from_account, 0, 0, 'L')
        pdf.cell(25, 10, f"{amount:.2f}", 0, 0, 'C')
        pdf.cell(90, 10, description, 0, 0, 'L')
        pdf.ln()
        total_expense += amount

    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f'Total Expense: {total_expense:.2f}', 0, 1, 'R')

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        pdf.output(tmpfile.name)
        with open(tmpfile.name, 'rb') as f:
            pdf_data = f.read()
        
        st.download_button(
            label="Download Expense Report",
            data=pdf_data,
            file_name="expense_report.pdf",
            mime="application/pdf"
        )