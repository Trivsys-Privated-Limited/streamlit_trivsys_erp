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
from accounts import fetch_customer_transactions

if "tenant" in st.session_state and hasattr(st.session_state.tenant, "business_name"):
    business_name = st.session_state.tenant.business_name.upper()
else:
    business_name = 'default_name'

def fetch_payments_for_sales(sale_id):
    """
    Fetch payments for a specific sale including payment method and note
    to distinguish between manual and automatic payments
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT amount, payment_date, payment_method, payment_note
            FROM payments 
            WHERE sale_id = %s 
            ORDER BY payment_date ASC
        """, (sale_id,))
        
        payments = cursor.fetchall()
        conn.close()
        
        return payments
        
    except Exception as e:
        print(f"Error fetching payments for sale {sale_id}: {e}")
        return []

def process_return_with_auto_payment(sale_id, return_amount, customer_name, return_date, product_name, quantity, reason):
    """
    Process return and automatically handle payment allocation:
    1. If customer has pending dues, apply return amount to clear dues first
    2. If return amount exceeds dues, record payment to customer for excess
    """
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Start transaction
        conn.autocommit = False
        
        # Get customer_id from the sale
        cursor.execute("SELECT customer_id FROM sales WHERE id = %s", (sale_id,))
        customer_result = cursor.fetchone()
        if not customer_result:
            raise Exception("Sale not found")
        customer_id = customer_result[0]
        
        # Get total pending dues for this customer across ALL sales
        cursor.execute("""
            SELECT SUM(due_amount) 
            FROM sales 
            WHERE customer_id = %s AND credit_sale = TRUE AND due_amount > 0
        """, (customer_id,))
        total_due_result = cursor.fetchone()
        total_pending_dues = Decimal(str(total_due_result[0] or 0))
        
        # Ensure return_amount is Decimal
        return_amount = Decimal(str(return_amount))
        
        # Insert the return record
        cursor.execute("""
            INSERT INTO returns (sale_id, product_name, quantity, return_amount, 
                               return_date, customer_name, reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (sale_id, product_name, quantity, return_amount, return_date, customer_name, reason))
        
        # Process payment allocation
        if total_pending_dues > 0:
            # Customer has pending dues - allocate return amount to clear dues
            payment_to_apply = min(return_amount, total_pending_dues)
            
            if payment_to_apply > 0:
                # Apply payment using FIFO approach (same as record_customer_payment)
                cursor.execute("""
                    SELECT id, due_amount 
                    FROM sales 
                    WHERE customer_id = %s AND credit_sale = TRUE AND due_amount > 0 
                    ORDER BY sale_date ASC
                """, (customer_id,))
                pending_sales = cursor.fetchall()
                
                remaining_payment = payment_to_apply
                
                for pending_sale_id, due_amount in pending_sales:
                    # Convert due_amount to Decimal
                    due_amount = Decimal(str(due_amount))
                    
                    if remaining_payment <= 0:
                        break
                    
                    # Calculate payment for this sale
                    payment_for_this_sale = min(remaining_payment, due_amount)
                    
                    # Update the sale record
                    cursor.execute("""
                        UPDATE sales 
                        SET paid_amount = paid_amount + %s, 
                            due_amount = due_amount - %s 
                        WHERE id = %s
                    """, (payment_for_this_sale, payment_for_this_sale, pending_sale_id))
                    
                    # Record the payment in payments table with note indicating it's from return
                    cursor.execute("""
                        INSERT INTO payments (sale_id, amount, payment_date, payment_method, payment_note)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (pending_sale_id, payment_for_this_sale, return_date, 'Return Credit', 
                          f'Auto payment from return of {product_name} (Qty: {quantity}) from Sale ID {sale_id}'))
                    
                    remaining_payment -= payment_for_this_sale
            
            # Check if there's excess amount after clearing dues
            excess_amount = return_amount - payment_to_apply
            
            if excess_amount > 0:
                # Company owes money to customer - record in customer_payments
                cursor.execute("""
                    INSERT INTO customer_payments (customer_name, amount, payment_date, note)
                    VALUES (%s, %s, %s, %s)
                """, (customer_name, excess_amount, return_date, 
                      f'Excess refund from return of {product_name} (Qty: {quantity}) from Sale ID {sale_id}'))
        
        else:
            # No pending dues - entire return amount goes to customer_payments
            cursor.execute("""
                INSERT INTO customer_payments (customer_name, amount, payment_date, note)
                VALUES (%s, %s, %s, %s)
            """, (customer_name, return_amount, return_date, 
                  f'Refund for return of {product_name} (Qty: {quantity}) from Sale ID {sale_id}'))
        
        # Commit transaction
        conn.commit()
        return True, f"Return processed successfully. Return amount: Rs.{return_amount:,.2f}"
        
    except Exception as e:
        conn.rollback()
        return False, f"Error processing return: {str(e)}"
    
    finally:
        conn.close()

def record_payment_to_customer(customer_name, amount, note=""):
    """
    Record payment made by company to customer (for excess refunds, etc.)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO customer_payments (customer_name, amount, payment_date, note)
            VALUES (%s, %s, NOW(), %s)
        """, (customer_name, amount, note))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Error recording payment to customer: {e}")
        return False


def fetch_payments_to_customer(customer_name):
    """
    Fetch all payments made by company to a specific customer
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT amount, payment_date, note
            FROM customer_payments
            WHERE customer_name = %s
            ORDER BY payment_date DESC
        """, (customer_name,))
        
        payments = cursor.fetchall()
        conn.close()
        
        return [
            {
                'amount': payment[0],
                'payment_date': payment[1],
                'note': payment[2] or ''
            }
            for payment in payments
        ]
        
    except Exception as e:
        st.error(f"Error fetching payments to customer: {e}")
        return []
    

# --- Helper Function for Styling Table ---
def highlight_ledger(row):
    # Row highlighting
    if row['Net Profit'] > 0:
        return ['background-color: #89AC46'] * len(row)  # Green for Profit
    elif row['Net Profit'] < 0:
        return ['background-color: #FF8989'] * len(row)  # Red for Loss
    else:
        return ['background-color: #F8ED8C'] * len(row)  # Yellow for Zero Net Profit

# Fetch all products from the database
def fetch_products():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, stock, price FROM products")
        products = cursor.fetchall()
        conn.close()
        return products
    return []


# Function to add sale items to the database
# Function to add a sale record to the database
def add_sale(sale_id, total_price, customer_id, source="Sales Module", credit_sale=0, due_amount=0, paid_amount=0, payment_due_date=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
            INSERT INTO sales (id, total_price, sale_date, source, customer_id, credit_sale, due_amount, paid_amount, payment_due_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        sale_date = datetime.now()
        cursor.execute(query, (sale_id, total_price, sale_date, source, customer_id, credit_sale, due_amount, paid_amount, payment_due_date))
        conn.commit()
        return True
    except Exception as e:
        print("Error inserting sale:", e)
        conn.rollback()
        return False
    finally:
        conn.close()

# Function to add sale items to the database
def add_sale_items(sale_id, product_id, quantity, sale_price):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
            INSERT INTO sale_items (sale_id, product_id, quantity, sale_price)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (sale_id, product_id, quantity, sale_price))
        conn.commit()
        return True
    except Exception as e:
        print("Error inserting sale item:", e)
        conn.rollback()
        return False
    finally:
        conn.close()

# Function to finalize a sale and update the database
def finalize_sale(sale_items, customer_name):
    if not sale_items:
        st.error("Cart is empty. Add products to the cart before finalizing.")
        return

    customer_id = get_or_create_customer(customer_name)

    # Calculate total price
    total_price = sum(item["quantity"] * item["sale_price"] for item in sale_items)

    # Generate a unique sale_id
    sale_id = generate_unique_sale_id()

    # Add sale record to the sales table
    if not add_sale(sale_id, total_price, customer_id):
        st.error("Failed to log sale.")
        return

    # Add each sale item to the sale_items table
    for item in sale_items:
        if not add_sale_items(sale_id, item["product_id"], item["quantity"], item["sale_price"]):
            st.error(f"Failed to log sale item for {item['product_name']}.")
            return

        # Update stock after sale
        if not update_stock_after_sale(item["product_id"], item["quantity"]):
            st.error(f"Failed to update stock for {item['product_name']}.")
            return

    items_sold = len(sale_items)
    st.session_state.sales_cart = []
    st.success(f"Successfully processed the sale for {items_sold} products.")

# Function to generate a unique sale ID
def generate_unique_sale_id():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT MAX(id) FROM sales")
        max_id = cursor.fetchone()[0]
        new_sale_id = max_id + 1 if max_id else 1
        return new_sale_id
    except Exception as e:
        print("Error generating unique sale ID:", e)
        return None
    finally:
        conn.close()



# Update stock after a sale is made
def update_stock_after_sale(product_id, quantity):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Fetch current stock from products table
            cursor.execute("SELECT stock FROM products WHERE id = %s", (product_id,))
            product_data = cursor.fetchone()
            if not product_data:
                st.error("Product not found in inventory.")
                return False

            current_stock = product_data[0]

            if quantity > current_stock:
                st.error("Not enough stock available!")
                return False

            # Update stock: Subtract the sold quantity from current stock
            new_stock = current_stock - quantity
            cursor.execute("UPDATE products SET stock = %s WHERE id = %s", (new_stock, product_id))
            st.write(f"Stock updated to: {new_stock}")

            conn.commit()
            return True
        except Exception as e:
            st.error(f"Error occurred while updating stock: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()
    return False

def get_filtered_sales(product_search, customer_search, date_filter, selected_month=None):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()

        base_query = """
            SELECT 
                s.id AS sale_id,
                GROUP_CONCAT(p.name ORDER BY p.name ASC) AS product_names,
                GROUP_CONCAT(si.quantity ORDER BY p.name ASC) AS quantities,
                SUM(si.quantity * si.sale_price) AS total_price,
                s.paid_amount,
                s.due_amount,
                c.customer_name,
                s.sale_date,
                s.source
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            JOIN customers c ON s.customer_id = c.id
            WHERE s.credit_sale = {credit_sale}
        """

        # Build filter string and parameters
        filters = ""
        params_regular = []
        params_credit = []

        if product_search:
            filters += " AND p.name LIKE %s"
            params_regular.append(f"%{product_search}%")
            params_credit.append(f"%{product_search}%")

        if customer_search:
            filters += " AND c.customer_name = %s COLLATE utf8mb4_bin"
            params_regular.append(customer_search)
            params_credit.append(customer_search)

        if date_filter == "Daily":
            filters += " AND DATE(s.sale_date) = %s"
            today = datetime.today().date()
            params_regular.append(today)
            params_credit.append(today)
        elif date_filter == "Weekly":
            today = datetime.today().date()
            start_of_week = today - timedelta(days=today.weekday())  # Monday
            end_of_week = start_of_week + timedelta(days=6)         # Sunday
            filters += " AND DATE(s.sale_date) BETWEEN %s AND %s"
            params_regular.extend([start_of_week, end_of_week])
            params_credit.extend([start_of_week, end_of_week])
        elif date_filter == "Last 30 Days":
            start = (datetime.today() - timedelta(days=30)).date()
            filters += " AND s.sale_date >= %s"
            params_regular.append(start)
            params_credit.append(start)
        elif date_filter == "Monthly" and selected_month:
            month_number = list(calendar.month_name).index(selected_month)
            filters += " AND MONTH(s.sale_date) = %s"
            params_regular.append(month_number)
            params_credit.append(month_number)

        # Prepare full queries
        query_regular = base_query.format(credit_sale=0) + filters + " GROUP BY s.id"
        query_credit = base_query.format(credit_sale=1) + filters + " GROUP BY s.id"

        # Final combined query
        final_query = f"""
            ({query_regular})
            UNION ALL
            ({query_credit})
            ORDER BY sale_date DESC
        """

        # Merge parameters
        full_params = params_regular + params_credit

        cursor.execute(final_query, full_params)
        sales = cursor.fetchall()
        conn.close()
        return sales


# Function to insert an expense record into the database
def insert_expense(amount, person_name, description):
    query = """
        INSERT INTO expenses (amount, person_name, description)
        VALUES (%s, %s, %s)
    """
    values = (amount, person_name, description)
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, values)  # Pass the values directly
            conn.commit()  # Commit the transaction
            st.success(f"✅ Expense of Rs. {amount:.2f} added for {person_name}.")
        except Exception as e:
            st.error(f"Error occurred while inserting expense: {str(e)}")
            conn.rollback()
        finally:
            cursor.close()  # Ensure the cursor is closed after the transaction
            conn.close()  # Close the connection


# Fetch the expenses from the database and calculate the total expenses
def fetch_expenses():
    query = "SELECT expense_date, amount, person_name, description FROM expenses"
    conn = get_db_connection()
    if conn:
        try:
            # Using pandas to directly read the query result into a DataFrame
            expenses_df = pd.read_sql(query, conn)
            
            return expenses_df
        except Exception as e:
            st.error(f"Error occurred while fetching expenses: {str(e)}")
        finally:
            conn.close()  # Always close the connection after use
    return pd.DataFrame()  # Return an empty DataFrame if something goes wrong


# Function to fetch expenses based on selected filters
def fetch_filtered_expenses(filter_option, selected_month=None):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            today = datetime.today()

            # SQL queries for different filter options
            if filter_option == "Daily":
                start_date = today.date()
                query = f"SELECT expense_date, amount, person_name, description FROM expenses WHERE DATE(expense_date) = '{start_date}'"
                
            elif filter_option == "Weekly":
                start_date = today - timedelta(days=7)
                query = f"SELECT expense_date, amount, person_name, description FROM expenses WHERE expense_date >= '{start_date}'"
                
            elif filter_option == "Monthly":
                if selected_month:
                    query = f"SELECT expense_date, amount, person_name, description FROM expenses WHERE MONTH(expense_date) = {selected_month} AND YEAR(expense_date) = {today.year}"
                else:
                    st.warning("Please select a month to filter by.")
                    return pd.DataFrame()
                
            elif filter_option == "Last 30 Days":
                start_date = today - timedelta(days=30)
                query = f"SELECT expense_date, amount, person_name, description FROM expenses WHERE expense_date >= '{start_date}'"
            
            # Execute the query
            cursor.execute(query)
            expenses = cursor.fetchall()
            if not expenses:
                return pd.DataFrame()

            # Ensure we only fetch the correct columns
            columns = ['expense_date', 'amount', 'person_name', 'description']
            expenses_df = pd.DataFrame(expenses, columns=columns)

            return expenses_df
        except Exception as e:
            st.error(f"Error occurred while fetching expenses: {str(e)}")
        finally:
            conn.close()
    return pd.DataFrame()  # Return an empty DataFrame if there's an error

# Function to fetch total expenses based on filters
def fetch_total_expenses(filter_option, selected_month=None):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            today = datetime.today()

            # SQL queries for different filter options
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
            
            # Execute the query
            cursor.execute(query)
            total_expense = cursor.fetchone()[0]
            
            # Return total expense or 0 if no records
            return total_expense if total_expense else 0
        except Exception as e:
            st.error(f"Error occurred while fetching expenses: {str(e)}")
        finally:
            conn.close()
    return 0


# --- New Database Functions for Pay-to-Customer Feature ---

def record_payment_to_customer(customer_name, amount, note=""):
    """Record a payment made to a customer."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        insert_query = """
        INSERT INTO customer_payments (customer_name, amount, note)
        VALUES (%s, %s, %s)
        """
        
        cursor.execute(insert_query, (customer_name, amount, note))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error recording payment to customer: {e}")
        return False

def fetch_payments_to_customer(customer_name):
    """Fetch all payments made to a specific customer."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
    SELECT * FROM customer_payments 
    WHERE customer_name = %s 
    ORDER BY payment_date DESC
    """
    
    cursor.execute(query, (customer_name,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_customer_payment_history(customer_name):
    """Get detailed payment history for a customer including total paid to them."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
    SELECT 
        payment_date,
        amount,
        note,
        DATE_FORMAT(payment_date, '%d-%b-%Y %H:%i') as formatted_date
    FROM customer_payments 
    WHERE customer_name = %s 
    ORDER BY payment_date DESC
    """
    
    cursor.execute(query, (customer_name,))
    payments = cursor.fetchall()
    
    # Calculate total
    total_paid = sum(float(payment['amount']) for payment in payments)
    
    conn.close()
    return payments, total_paid

    
# Sales Module UI
def sales_page():
    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.rerun()
        
    st.title("Sales Module")
#  trying new submenu
    if 'sub_menu' not in st.session_state:
        st.session_state.sub_menu = "Record Sale"
    with st.sidebar:
    # Module Title

        st.markdown("### Sales")
        
        # Navigation buttons
        menu_items = [
            "Record Sale",
            "Sales History", 
            "Customer Ledger",
            "Customer Sales History",
            "Main Ledger",
            # "Expense",
            "Manage Customers",
            "Return Product",
        ]
        
        for item in menu_items:
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.sub_menu = item
                st.rerun()

    sub_menu = st.session_state.sub_menu

    if "sales_cart" not in st.session_state or not isinstance(st.session_state.sales_cart, list):
        st.session_state.sales_cart = []

    if sub_menu == "Record Sale":
        st.header("Create a Sale")

        # Fetch products from the database
        products = fetch_products()

        if not products:
            st.warning("No products found in inventory.")
            return
        c1,c2 = st.columns([3,1])
        # Create a dictionary with product options (including stock and price)
        with c1:
            st.markdown('#### Select Product')
            product_options = {f"{p[1]} (Stock: {p[2]}, Price: Rs.{p[3]:,.2f})": (p[0], p[2], p[3]) for p in products}
            selected_product = st.selectbox("Select Product", list(product_options.keys()),label_visibility='collapsed')
            product_id, stock, sale_price = product_options[selected_product]
        with c2:
        # Quantity input
            st.markdown('#### Enter Quantity to Sell')
            quantity = st.number_input("Enter Quantity to Sell", min_value=1, step=1,label_visibility='collapsed')
        c3,c4 = st.columns(2)
        # Customer name input
        with c3:
            st.markdown('#### Customer Name')
            customer_name = st.text_input("Customer Name", max_chars=255,label_visibility='collapsed')

        # Disable "Add to Cart" button if stock is 0 or quantity exceeds stock
        if stock == 0:
            st.warning("This product is out of stock!")
            add_to_cart_disabled = True
        elif quantity > stock:
            st.warning(f"Only {stock} units available! Please enter a valid quantity.")
            add_to_cart_disabled = True
        else:
            add_to_cart_disabled = False

        # Add to cart
        with c4:
            st.markdown('#### ')
            if st.button("Add to Cart", disabled=add_to_cart_disabled):
                if not customer_name.strip():
                    st.error("Customer Name is required!")
                    return
                st.session_state.sales_cart.append({
                    "product_id": product_id,
                    "product_name": selected_product,
                    "quantity": quantity,
                    "sale_price": sale_price,
                    "customer_name": customer_name
                })
                st.success(f"Added {quantity} units of {selected_product} to the cart.")


        # Finalize Sale
        # 🛒 Display cart
        if st.session_state.sales_cart:
            st.subheader("Sales Cart")
            cart_df = pd.DataFrame(st.session_state.sales_cart)
            st.table(cart_df[["product_name", "quantity", "sale_price"]])

            # 💰 Payment section
            st.subheader("Payment Details")
            total_price = sum(item["quantity"] * item["sale_price"] for item in st.session_state.sales_cart)
            total_price_decimal = Decimal(str(total_price))  # Convert to Decimal safely

            st.write(f"**Total Price:** Rs.{total_price_decimal:,.2f}")

            paid_amount = st.number_input(
                "Enter Paid Amount",
                min_value=0.0,
                max_value=float(total_price_decimal),
                value=float(total_price_decimal),
                step=100.0
            )

            due_amount = total_price_decimal - Decimal(str(paid_amount))

            if st.button("Finalize Sale"):
                customer_name = st.session_state.sales_cart[0]["customer_name"]
                customer_id = get_or_create_customer(customer_name)
                sale_id = generate_unique_sale_id()
                credit_sale = 1 if due_amount > 0 else 0

                if not add_sale(
                    sale_id, total_price_decimal, customer_id,
                    source="Sales Module",
                    credit_sale=credit_sale,
                    due_amount=due_amount,
                    paid_amount=Decimal(str(paid_amount))
                ):
                    st.error("Failed to log sale.")
                    return

                for item in st.session_state.sales_cart:
                    if not add_sale_items(sale_id, item["product_id"], item["quantity"], item["sale_price"]):
                        st.error(f"Failed to log sale item for {item['product_name']}.")
                        return

                    if not update_stock_after_sale(item["product_id"], item["quantity"]):
                        st.error(f"Failed to update stock for {item['product_name']}.")
                        return

                st.success(f"✅ Sale complete! {len(st.session_state.sales_cart)} item(s) sold.")
                
                st.subheader("Sale Summary")
                st.write(f"**Sale ID:** {sale_id}")
                st.write(f"**Customer:** {customer_name}")
                st.write(f"**Total Amount:** Rs.{total_price_decimal:,.2f}")
                st.write(f"**Paid:** Rs.{paid_amount:,.2f} | **Due:** Rs.{due_amount:,.2f}")
                st.write("**Products Sold:**")
                st.table(pd.DataFrame(st.session_state.sales_cart)[["product_name", "quantity", "sale_price"]])

                st.session_state.sales_cart = []



    # Sales History Display with Filters
    # Sales History Display with Filters
    elif sub_menu == "Sales History":
        st.header("Sales History")
        st.write("View and filter all past sales records.")

        # --- Filters Row ---
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1.5])

        with col1:
            date_filter = st.selectbox("Date Filter", ["All Time", "Daily", "Weekly", "Last 30 Days", "Monthly"])

        with col2:
            selected_month = None
            if date_filter == "Monthly":
                months = list(calendar.month_name)[1:]
                selected_month = st.selectbox("Select Month", months)

        with col3:
            product_search = st.text_input("Product Search")

        with col4:
            customer_search = st.text_input("Customer Search")

        # --- Fetch Sales with Filters ---
        sales = get_filtered_sales(product_search, customer_search, date_filter, selected_month)

        if not sales:
            st.warning("No sales records found.")
        else:
            # --- Prepare Sales DataFrame ---
            # --- Prepare Sales DataFrame ---
            sales_df = pd.DataFrame(sales, columns=[
                "SALE ID", "PRODUCTS", "QUANTITY", "TOTAL PRICE",
                "PAID AMOUNT", "DUE AMOUNT", "CUSTOMER", "DATE", "SOURCE"
            ])
            sales_df['TOTAL PRICE'] = pd.to_numeric(sales_df['TOTAL PRICE'], errors='coerce').fillna(0)

            # 👇 Round down to nearest whole number
            sales_df['TOTAL PRICE'] = sales_df['TOTAL PRICE'].apply(lambda x: int(x))

            # --- Prepare Sales DataFrame ---
            sales_df = pd.DataFrame(sales, columns=[
                "SALE ID", "PRODUCTS", "QUANTITY", "TOTAL PRICE",
                "PAID AMOUNT", "DUE AMOUNT", "CUSTOMER", "DATE", "SOURCE"
            ])
            sales_df['TOTAL PRICE'] = pd.to_numeric(sales_df['TOTAL PRICE'], errors='coerce').fillna(0)

            # 👇 Round down to nearest whole number
            sales_df['TOTAL PRICE'] = sales_df['TOTAL PRICE'].apply(lambda x: int(x))

            # 👇 Format DATE to 12-hour format
            sales_df['DATE'] = pd.to_datetime(sales_df['DATE']).dt.strftime('%Y-%m-%d %I:%M %p')

            # --- Calculate Totals ---
            total_sales = sales_df['TOTAL PRICE'].sum()

            # --- Handle Returns (if applicable) ---
            try:
                returned_items = fetch_returns_from_returns_table()
                total_returned_amount = pd.DataFrame(returned_items)['return_amount'].sum() if returned_items else 0
            except Exception as e:
                total_returned_amount = 0
                st.error(f"Error fetching returns: {e}")

            adjusted_sales = total_sales - total_returned_amount

            # --- Display Totals ---
            col_total, col_adjusted = st.columns(2)

            with col_total:
                st.markdown(f"#####  Total Sales: **Rs.{total_sales:,.2f}**")

            with col_adjusted:
                st.markdown(f"#####  Adjusted Sales (After Returns): **Rs.{adjusted_sales:,.2f}**")


            # --- Display Sales Table ---
            st.table(sales_df)


    elif sub_menu == "Customer Sales History":
        st.header("Customer Sales History")
        
        # Fetch all unique customer names
        conn = get_db_connection()
        customers = []
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT customer_name FROM customers ORDER BY customer_name")
            customers = [row[0] for row in cursor.fetchall()]
            conn.close()

        if not customers:
            st.warning("No customers found.")
            return

        # Inside your Customer Ledger block

        # Row layout for customer and product search
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('#### Select Customer')
            selected_customer = st.selectbox("Select Customer", customers,label_visibility='collapsed')

        with col2:
            st.markdown('#### Search By Product')
            product_search = st.text_input("Search by Product",label_visibility='collapsed')

        # Date filter options
        date_filter = st.radio("Filter by", ["All Time", "Daily", "Weekly", "Last 30 Days", "Monthly"], index=0)

        # Show Month dropdown only if "Monthly" filter is selected
        selected_month = None
        if date_filter == "Monthly":
            months = list(calendar.month_name)[1:]
            selected_month = st.selectbox("Select a Month", months)

        # Continue with search logic
        customer_search = selected_customer
        sales = get_filtered_sales(product_search, customer_search, date_filter, selected_month)


        if not sales:
            st.warning("No sales records found for this customer.")
        else:
            # Convert sales data to DataFrame (same format as Sales History)
            sales_df = pd.DataFrame(sales, columns=["ID", "PRODUCTS", "QUANTITIES", "TOTAL PRICE", "PAID AMOUNT", "DUE AMOUNT", "CUSTOMER", "DATE", "SOURCE"])                  


            # Display total sales at the top
            total_sales = sales_df['TOTAL PRICE'].sum()
            total_paid = sales_df['PAID AMOUNT'].sum()
            total_due = sales_df['DUE AMOUNT'].sum()

            st.markdown(
                f"""
                <div style='font-size:15px; line-height:1.6;'>
                    <h4>Total Sales:</b> Rs. {total_sales:,.2f} &nbsp;&nbsp;
                    ✅ <b>Total Paid:</b> Rs. {total_paid:,.2f} &nbsp;&nbsp;
                    ❌ <b>Amount Due:</b> Rs. {total_due:,.2f}
                </div>
                """,
                unsafe_allow_html=True
        )
            # Optional: Export options (Excel or PDF)
            export_format = st.selectbox("Export as", ["PDF", "Excel"])

            if export_format == "Excel":
                import io
                with io.BytesIO() as buffer:
                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        sales_df.to_excel(writer, index=False, sheet_name="Customer Sales History")
                    st.download_button(
                        label="Download Excel",
                        data=buffer.getvalue(),
                        file_name=f"{selected_customer}_sales_history.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )


            elif export_format == "PDF":
                import io
                from fpdf import FPDF

                class PDF(FPDF):
                    def __init__(self):
                        super().__init__(orientation='L', unit='mm', format='A4')
                        self.page_width = 297  # A4 Landscape width
                        self.left_margin = 10
                        self.right_margin = 10
                        self.set_auto_page_break(auto=True, margin=15)

                    def header(self):
                        import os
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
                        self.cell(0, 8, f"Customer Sales History - {selected_customer}", ln=True)

                        self.set_text_color(0, 0, 0)
                        self.ln(5)

                    def footer(self):
                        self.set_y(-15)
                        self.set_font("Arial", "I", 8)
                        self.set_text_color(100, 100, 100)
                        self.cell(0, 10, f"Page {self.page_no()} - Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 0, "C")


                pdf = PDF()
                pdf.add_page()

                # Group data by sale ID
                grouped_sales = sales_df.groupby("ID")

                for idx, (sale_id, group) in enumerate(grouped_sales):
                    customer = group["CUSTOMER"].iloc[0]
                    date = group["DATE"].iloc[0]
                    source = group["SOURCE"].iloc[0]
                    total_price = group["TOTAL PRICE"].iloc[0]
                    paid_amount = group["PAID AMOUNT"].iloc[0]
                    due_amount = group["DUE AMOUNT"].iloc[0]
                    products = group["PRODUCTS"].iloc[0]
                    quantities = group["QUANTITIES"].iloc[0]

                    pdf.set_font("Arial", "B", 10)
                    pdf.set_text_color(54, 95, 145)
                    pdf.cell(0, 8, f"Sale ID: {sale_id} | Date: {date} | Source: {source}", ln=True)

                    pdf.set_font("Arial", "", 9)
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(0, 6, f"Customer: {customer}", ln=True)
                    pdf.cell(0, 6, f"Products: {products}", ln=True)
                    pdf.cell(0, 6, f"Quantities: {quantities}", ln=True)
                    pdf.cell(0, 6, f"Total: Rs. {total_price:,.2f} | Paid: Rs. {paid_amount:,.2f} | Due: Rs. {due_amount:,.2f}", ln=True)
                    pdf.ln(2)

                    # Styled Payment History Table
                    pdf.set_font("Arial", "B", 9)
                    pdf.set_fill_color(166, 124, 33)
                    pdf.set_text_color(255, 255, 255)
                    headers = ["Date", "Amount Paid (Rs.)", "Remaining Due (Rs.)", "Note"]
                    col_widths = [60, 60, 60, 80]
                    for i, header in enumerate(headers):
                        pdf.cell(col_widths[i], 8, header, border=1, align="C", fill=True)
                    pdf.ln()

                    # Build payment breakdown
                    additional_payments = fetch_payments_for_sale(sale_id)
                    total_followup = sum([p[0] for p in additional_payments])
                    initial_payment = paid_amount - total_followup
                    running_due = total_price

                    payments = []

                    if initial_payment > 0:
                        running_due -= initial_payment
                        payments.append((
                            pd.to_datetime(date).strftime("%Y-%m-%d %I:%M %p"),
                            f"Rs. {initial_payment:,.2f}",
                            f"Rs. {running_due:,.2f}",
                            "Initial Payment"
                        ))

                    for amount, p_date, method, note in additional_payments:
                        running_due -= amount
                        payments.append((
                            pd.to_datetime(p_date).strftime("%Y-%m-%d %I:%M %p"),
                            f"Rs. {amount:,.2f}",
                            f"Rs. {running_due:,.2f}",
                            f"{note or '-'}"
                        ))


                    pdf.set_font("Arial", "", 9)
                    pdf.set_text_color(0, 0, 0)
                    for i, row in enumerate(payments):
                        is_even = i % 2 == 0
                        bg_color = (240, 240, 240) if is_even else (255, 255, 255)
                        pdf.set_fill_color(*bg_color)
                        for j, val in enumerate(row):
                            pdf.cell(col_widths[j], 8, val, border=1, fill=True)
                        pdf.ln()

                    pdf.ln(6)

                # Summary Section
                pdf.set_font("Arial", "B", 11)
                pdf.set_fill_color(245, 245, 245)
                pdf.set_text_color(0)
                pdf.cell(0, 8, f"Total Sales: Rs. {total_sales:,.2f}", ln=True, fill=True)
                pdf.set_text_color(255, 0, 0) if total_due > 0 else pdf.set_text_color(0, 128, 0)
                pdf.cell(0, 8, f"Total Due: Rs. {total_due:,.2f}", ln=True, fill=True)
                pdf.set_text_color(0)

                # Export as downloadable PDF
                pdf_buffer = io.BytesIO()
                pdf_output = pdf.output(dest='S').encode('latin-1')
                pdf_buffer.write(pdf_output)
                pdf_buffer.seek(0)

                st.download_button(
                    label="Download PDF",
                    data=pdf_buffer,
                    file_name=f"{selected_customer}_ledger.pdf",
                    mime="application/pdf"
                )



            # Display sales data in table format
            st.table(sales_df)


            # Show detailed payments per sale
            grouped_sales = sales_df.groupby("ID")  # ID is the sale_id

            for sale_id, group in grouped_sales:
                customer = group["CUSTOMER"].iloc[0]
                date = group["DATE"].iloc[0]
                source = group["SOURCE"].iloc[0]
                total_price = group["TOTAL PRICE"].iloc[0]
                paid_amount_from_sale = group["PAID AMOUNT"].iloc[0]  # This is total paid so far
                due_amount = group["DUE AMOUNT"].iloc[0]

                with st.expander(f"🧾 Sale ID: {sale_id} | Date: {date} | Source: {source}"):
                    st.markdown(f"""
                    **Customer:** {customer}  
                    **Total Price:** Rs. {total_price:,.2f}  
                    **Paid So Far:** Rs. {paid_amount_from_sale:,.2f}  
                    **Due:** Rs. {due_amount:,.2f}
                    """)

                    # Fetch all payments recorded after the initial sale
                    additional_payments = fetch_payments_for_sale(sale_id)

                    # Assume the first payment is initial, rest are installments
                    all_payments = []
                    running_due = total_price

                    # Only add initial payment if > 0
                    initial_payment = 0
                    if additional_payments:
                        # Total payments from payment table
                        total_follow_up_paid = sum([p[0] for p in additional_payments])
                        initial_payment = paid_amount_from_sale - total_follow_up_paid
                    else:
                        initial_payment = paid_amount_from_sale

                    # Record initial payment if it exists
                    if initial_payment > 0:
                        running_due -= initial_payment
                        all_payments.append({
                            "Date": pd.to_datetime(date).strftime("%Y-%m-%d %I:%M %p"),
                            "Amount Paid (Rs.)": f"Rs. {initial_payment:,.2f}",
                            "Remaining Due (Rs.)": f"Rs. {running_due:,.2f}",
                            "Note": "🟢 Initial Payment"
                        })

                    # Add follow-up payments
                    for amount, p_date, method, note in additional_payments:
                        running_due -= amount
                        all_payments.append({
                            "Date": pd.to_datetime(p_date).strftime("%Y-%m-%d %I:%M %p"),
                            "Amount Paid (Rs.)": f"Rs. {amount:,.2f}",
                            "Remaining Due (Rs.)": f"Rs. {running_due:,.2f}",
                            "Note": note or f"Method: {method}"
                        })

                    if all_payments:
                        st.subheader("💰 Payment History with Remaining Due")
                        payment_df = pd.DataFrame(all_payments)
                        st.table(payment_df)
                    else:
                        st.info("No payments recorded for this sale yet.")

                            # till here



        # Optional: Table of all customers
        # st.header("All Customers")
        # customers_df = pd.DataFrame(customers, columns=["Customer Name"])
        # st.table(customers_df)

                        
    elif sub_menu == "Expense":
        st.header("Miscellaneous Expenses")
        st.markdown("**Track all your business-related expenses like payments for services or supplies.**")


        # Expense form layout (use columns for better alignment)
        with st.form(key='expense_form'):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown('##### Expense Amount')
                # Expense amount input (validated for positive values)
                amount = st.number_input("Expense Amount (Rs.)", min_value=0.00, step=100.00, format="%.2f",label_visibility='collapsed')
            
            with col2:
                st.markdown('##### Person/Service Name')
                # Person/Service Name input
                person_name = st.text_input("Person/Service Name",label_visibility='collapsed')

            # Expense description input (multi-line)
            st.markdown('##### Description of the Expense')
            description = st.text_area("Description of the Expense", height=100,label_visibility='collapsed')

            # Submit button with form submission
            submit_button = st.form_submit_button(label="Add Expense")

        # Form submission logic
            if submit_button:
                if amount <= 0:
                    st.warning("Amount should be greater than 0.")
                elif not person_name.strip():
                    st.warning("Please provide the name of the person/service.")
                elif not description.strip():
                    st.warning("Please provide a description of the expense.")
                else:
                    try:
                        # Insert expense into database
                        insert_expense(amount, person_name, description)

                        # Show balloons
                        st.balloons()

                        # Clear form fields from session state
                        if "expense_form" in st.session_state:
                            del st.session_state["expense_form"]
                        st.session_state["Person/Service Name"] = ""
                        st.session_state["Description of the Expense"] = ""
                        st.session_state["Expense Amount (Rs.)"] = 0.00

                        # Wait for balloons to display
                        time.sleep(1.5)

                        # Refresh page
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error occurred while adding expense: {str(e)}")

        # Filters for total expenses
        st.header("Total Expenses")
        filter_option = st.selectbox(
            "Select a filter for total expenses:",
            ["Daily", "Weekly", "Monthly", "Last 30 Days"]
        )

        # If monthly filter is selected, ask for month
        selected_month = None
        if filter_option == "Monthly":
            selected_month = st.selectbox(
                "Select Month",
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                format_func=lambda x: datetime(2022, x, 1).strftime('%B')
            )

        # Get total expense based on the filter
        total_expense = fetch_total_expenses(filter_option, selected_month)

        # Display the total expense
        if total_expense is not None:
            st.markdown(
                            f"<h3 style='font-size: 24px; font-weight: bold;'>Total Expense for {filter_option}: Rs. {total_expense:.2f}</h3>",
                            unsafe_allow_html=True
                        )

        else:
            st.write("No expenses found for the selected filter.")

        # Display Expense History
        st.header("Expenses History")
        filter_option = st.selectbox(
            "Select a filter for expense history:",
            ["Daily", "Weekly", "Monthly", "Last 30 Days"]
        )

        # If monthly filter is selected, ask for month
        selected_month = None
        if filter_option == "Monthly":
            selected_month = st.selectbox(
                "Select Month",
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                format_func=lambda x: datetime(2022, x, 1).strftime('%B'),
                key="month_filter_selectbox"  # Add a unique key to avoid duplicate element IDs
            )

        # Fetch filtered expenses based on selected filter
        expenses_df = fetch_filtered_expenses(filter_option, selected_month)

        # Show filtered expenses history
        if not expenses_df.empty:
            # Convert expense_date to datetime and format it
            # Convert to datetime and sort by date descending (newest first)
            expenses_df['expense_date'] = pd.to_datetime(expenses_df['expense_date'])
            expenses_df = expenses_df.sort_values(by='expense_date', ascending=False)

            # Format the date for display
            expenses_df['expense_date'] = expenses_df['expense_date'].dt.strftime('%d-%m-%Y %I:%M %p')

            # Reorder and rename columns
            expenses_df = expenses_df[['expense_date', 'amount', 'person_name', 'description']]
            expenses_df.columns = ['Date', 'Amount', 'Person', 'Description']

            st.table(expenses_df)
        else:
            st.warning("No expenses found for the selected filter.")

    # Manage customers sub menu 
    # Manage customers sub-menu
    elif sub_menu == "Manage Customers":
        st.header("Manage Customers")

        # Sub-menu for Add, Update, Delete, and Bulk Upload
        action = st.radio("Choose an action", ("Add Customer", "Update Customer", "Delete Customer", "Bulk Customers Upload"))

        if action == "Add Customer":
            # Add Customer Section
            st.subheader("Add a New Customer")
            with st.form(key='add_customer_form'):
                c1,c2 = st.columns(2)
                with c1:
                    st.markdown('##### Customer Name : ')
                    new_customer_name = st.text_input("Customer Name:",label_visibility='collapsed')
                with c2:
                    st.markdown('##### Customer Number : ')
                    new_customer_number = st.text_input("Customer Number:",label_visibility='collapsed')
                submit_button = st.form_submit_button("Add Customer")

                if submit_button and new_customer_name and new_customer_number:
                    add_customer(new_customer_name, new_customer_number)
                    st.success(f"Customer '{new_customer_name}' added successfully!")

        elif action == "Update Customer":
            # Update Customer Section
            st.subheader("Update Customer Information")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, customer_name, customer_number FROM customers")
            customers = cursor.fetchall()
            conn.close()
            c1,c2,c3 = st.columns(3)
            if customers:
                with c1:
                    st.markdown('##### Select a customer to Update : ')
                    customer_dict = {f"{customer[1]} - {customer[2]}": customer[0] for customer in customers}
                    selected_customer = st.selectbox("Select a customer to update:", list(customer_dict.keys()),label_visibility='collapsed')

                if selected_customer:
                    customer_id = customer_dict[selected_customer]
                    selected_name, selected_number = selected_customer.split(" - ")
                    with c2:
                        st.markdown('##### Update Customer Name : ')
                        updated_name = st.text_input("Update Customer Name:", selected_name,label_visibility='collapsed')
                    with c3:
                        st.markdown('##### Update Customer Number : ')
                        updated_number = st.text_input("Update Customer Number:", selected_number,label_visibility='collapsed')

                    if st.button("Update Customer"):
                        update_customer(customer_id, updated_name, updated_number)
                        st.success(f"Customer '{updated_name}' updated successfully!")

        elif action == "Delete Customer":
            # Delete Customer Section
            st.subheader("Delete Customer")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, customer_name, customer_number FROM customers")
            customers = cursor.fetchall()
            conn.close()

            if customers:
                customer_dict = {f"{customer[1]} - {customer[2]}": customer[0] for customer in customers}
                delete_customer_name = st.selectbox("Select a customer to delete:", list(customer_dict.keys()))

                if delete_customer_name:
                    confirmation = st.radio(
                        f"Are you sure you want to delete '{delete_customer_name}'?",
                        options=["No", "Yes"]
                    )

                    if confirmation == "Yes":
                        if st.button(f"❌ Confirm Deletion of {delete_customer_name}"):
                            delete_customer_from_sales(customer_dict[delete_customer_name])
                            st.success(f"Customer '{delete_customer_name}' deleted successfully ✅")

        elif action == "Bulk Customers Upload":
            st.subheader("Bulk Upload Customers")

            # File uploader widget to upload Excel file
            uploaded_file = st.file_uploader("Choose an Excel file", type=['xlsx'])

            if uploaded_file:
                # Process the file
                upload_bulk_customers(uploaded_file)

            # Export button in the Bulk Upload section
            st.subheader(" Export Current Customer Data")
            export_button = st.button("Export Customer Data to Excel")
            if export_button:
                export_customers_to_excel()

        # Show all customers in a table
        st.subheader("All Customers")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, customer_name, customer_number FROM customers")
        customers = cursor.fetchall()
        conn.close()

        if customers:
            customers_df = pd.DataFrame(customers, columns=["ID", "Customer Name", "Customer Number"])
            st.table(customers_df)
        else:
            st.write("No customers found.")


    elif sub_menu == "Return Product":
        st.header("Return Products")

        # Fetch recent sales to choose from
        sales = get_filtered_sales(product_search=None, customer_search=None, date_filter=None)
        selected_sale = None
        sale_details = []
        sale_id = None

        if sales:
            recent_sales = [f"{sale[0]} - {sale[6]} - {sale[7].strftime('%Y-%m-%d')}" for sale in sales]
            st.markdown('### Select a Sale Record')
            selected_sale = st.selectbox("Select a Sale", recent_sales,label_visibility='collapsed')

        if selected_sale:
            sale_id = int(selected_sale.split(" - ")[0])
            try:
                sale_details = fetch_sale_details(sale_id)
            except Exception as e:
                st.error(f"Error fetching sale details: {e}")
                sale_details = []

        # Show table of products in this sale
        if sale_details:
            st.markdown("### Products in This Sale")
            for item in sale_details:
                item["Total"] = item["quantity"] * item["price"]

            table_data = [
                {
                    "Product": item["product_name"],
                    "Quantity": item["quantity"],
                    "Unit Price": f"Rs.{item['price']}",
                    "Total": f"Rs.{item['Total']}"
                }
                for item in sale_details
            ]
            st.table(table_data)

            # Get customer info for this sale
            customer_name = next((s[6] for s in sales if int(s[0]) == sale_id), "Unknown")
            
            # Show customer's current pending dues
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT customer_id FROM sales WHERE id = %s
            """, (sale_id,))
            customer_result = cursor.fetchone()
            
            if customer_result:
                customer_id = customer_result[0]
                cursor.execute("""
                    SELECT SUM(due_amount) 
                    FROM sales 
                    WHERE customer_id = %s AND credit_sale = TRUE AND due_amount > 0
                """, (customer_id,))
                total_due_result = cursor.fetchone()
                total_pending_dues = Decimal(str(total_due_result[0] or 0))
                
                if total_pending_dues > 0:
                    st.info(f"💰 **{customer_name}** has pending dues: Rs.{total_pending_dues:,.2f}")
                else:
                    st.success(f"✅ **{customer_name}** has no pending dues")
            
            conn.close()

            # Select Products to Return
            st.subheader(" Select Products to Return")

            product_names = [item['product_name'] for item in sale_details]
            selected_products = st.multiselect("Select Products", product_names,label_visibility='collapsed')

            returned_products = []

            # Collect return quantities and reasons for each selected product
            for product_name in selected_products:
                product_info = next(item for item in sale_details if item['product_name'] == product_name)
                max_qty = product_info['quantity']
                unit_price = product_info['price']

                col1, col2 = st.columns(2)
                with col1:
                    return_qty = st.number_input(f"Return Quantity for {product_name}", 
                                            min_value=1, max_value=max_qty, step=1, 
                                            key=f"{product_name}_qty")
                with col2:
                    reason = st.text_input(f"Reason for {product_name} (Optional)", 
                                        key=f"{product_name}_reason")

                returned_products.append({
                    "product_name": product_name,
                    "quantity": return_qty,
                    "unit_price": unit_price,
                    "reason": reason
                })

            if returned_products:
                # Calculate total return amount using Decimal
                
                total_return_amount = sum(Decimal(str(p["quantity"] * p["unit_price"])) for p in returned_products)
                st.info(f"💵 **Total Return Amount:** Rs.{total_return_amount:,.2f}")
                
                # Show what will happen with the return
                if total_pending_dues > 0:
                    payment_to_apply = min(total_return_amount, total_pending_dues)
                    excess_amount = total_return_amount - payment_to_apply
                    
                    st.markdown("### 🔄 Payment Allocation Preview")
                    if payment_to_apply > 0:
                        st.success(f"✅ Rs.{payment_to_apply:,.2f} will be applied to clear pending dues")
                    if excess_amount > 0:
                        st.warning(f"💰 Rs.{excess_amount:,.2f} will be paid to customer (excess refund)")
                else:
                    st.warning(f"💰 Rs.{total_return_amount:,.2f} will be paid to customer (full refund)")

            if returned_products and st.button("🔄 Process Return with Auto Payment"):
                
                return_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                success_count = 0
                error_messages = []

                # Process each returned product
                for product in returned_products:
                    return_amount = Decimal(str(product["quantity"] * product["unit_price"]))
                    
                    # Process return with auto payment
                    success, message = process_return_with_auto_payment(
                        sale_id=sale_id,
                        return_amount=return_amount,
                        customer_name=customer_name,
                        return_date=return_date,
                        product_name=product["product_name"],
                        quantity=product["quantity"],
                        reason=product["reason"]
                    )
                    
                    if success:
                        # Update stock
                        update_product_stock_after_return(product["product_name"], product["quantity"])
                        success_count += 1
                    else:
                        error_messages.append(f"{product['product_name']}: {message}")

                # Show results
                if success_count == len(returned_products):
                    st.success(f"✅ Successfully processed {success_count} return(s) with automatic payment allocation!")
                    st.balloons()
                    # Refresh the page to show updated data
                    st.rerun()
                elif success_count > 0:
                    st.warning(f"⚠️ Processed {success_count} out of {len(returned_products)} returns. Some errors occurred:")
                    for error in error_messages:
                        st.error(error)
                else:
                    st.error("❌ Failed to process returns:")
                    for error in error_messages:
                        st.error(error)

        # Return History (keep existing code)
        st.header("Return History")
        
        try:
            returned_items = fetch_returns_from_returns_table()
            if returned_items:
                df_returned = pd.DataFrame(returned_items)
                df_returned['return_date'] = pd.to_datetime(df_returned['return_date']).dt.strftime('%Y-%m-%d %H:%M:%S')

                if 'return_amount' in df_returned.columns:
                    total_returned_amount = df_returned['return_amount'].sum()
                    st.markdown(f"### Total Returned Amount: **Rs.{total_returned_amount:,.2f}**")

                st.table(df_returned)
            else:
                st.info("No returns recorded yet.")
        except Exception as e:
            st.error(f"Error fetching returned items: {e}")


        # --- Main Ledger Section ---
    from fpdf import FPDF
    # --- Main Ledger ---
    # --- Main Ledger ---
    if sub_menu == "Main Ledger":
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
                            footer_color = (100, 100, 100)  # Gray
                            self.set_text_color(*footer_color)
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
                                self.set_text_color(0, 0, 0)  # Reset to black after each cell
                            
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
                            pdf.table_row(row, col_widths, is_even_row)
                        
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
                        
                        # Save to temporary file
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
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
    if sub_menu == "Customer Ledger":
            st.header("Customer Ledger")

            # --- Fetch active customers (those with at least one sale) ---
            customers = fetch_customers()
            ledger_customers = []

            for customer_id, customer_name in customers:
                has_sales = bool(get_filtered_sales(None, customer_name, "All"))
                has_manual_txn = bool(fetch_customer_transactions(customer_name))
                has_payments_to = bool(fetch_payments_to_customer(customer_name))
                
                if has_sales or has_manual_txn or has_payments_to:
                    ledger_customers.append((customer_id, customer_name))

            customer_names = [name for _, name in ledger_customers]

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

                # Build products list with quantities in parentheses
                products_list = ""
                try:
                    if product_names:
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
                    products_list = product_names or ''

                # CUSTOMER PERSPECTIVE: Sale transaction
                # Backend: debit increases customer debt, credit for immediate cash sales
                # UI: debit → Money In (to customer ledger), credit → Money Out (from customer ledger)
                all_transactions.append({
                    'date': sale_date,
                    'type': 'sale',
                    'sale_id': sale_id,
                    'source': source,
                    'products': products_list,
                    'debit': float(total_price),  # Backend unchanged
                    'credit': 0.0 if source not in ['POS', 'Sales Module'] else float(total_price)  # Backend unchanged
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
                            'products': "",
                            'debit': 0.0,  # Backend unchanged
                            'credit': initial_payment,  # Backend unchanged
                            'payment_method': 'Cash',
                            'payment_note': 'Initial payment at time of sale'
                        })

                # Process additional payments with payment method and note
                for payment_data in additional_payments:
                    if len(payment_data) >= 4:
                        amount, pay_date, payment_method, payment_note = payment_data[:4]
                        is_automatic_return = (
                            payment_method == 'Return Credit' or
                            'Auto payment from return' in (payment_note or '')
                        )
                        if is_automatic_return:
                            continue
                    else:
                        amount, pay_date = payment_data[:2]
                        payment_method = 'Cash'
                        payment_note = None
                    
                    all_transactions.append({
                        'date': pd.to_datetime(pay_date),
                        'type': 'payment',
                        'sale_id': sale_id,
                        'products': "",
                        'debit': 0.0,  # Backend unchanged
                        'credit': float(amount),  # Backend unchanged
                        'payment_method': payment_method,
                        'payment_note': payment_note
                    })

            # --- Fetch returns for the customer ---
            try:
                all_returns = fetch_returns_from_returns_table()
                customer_returns = [r for r in all_returns if r.get('customer_name') == selected_customer_name]
                
                for return_item in customer_returns:
                    return_date = pd.to_datetime(return_item['return_date'])
                    return_amount = float(return_item['return_amount'])
                    product_name = return_item['product_name']
                    quantity = return_item['quantity']
                    sale_id = return_item['sale_id']
                    reason = return_item.get('reason', '')
                    
                    # Return transaction (Backend: credit reduces debt, unchanged)
                    all_transactions.append({
                        'date': return_date,
                        'type': 'return',
                        'sale_id': sale_id,
                        'source': 'Return',
                        'products': f"{product_name} (Qty: {quantity})",
                        'debit': 0.0,  # Backend unchanged
                        'credit': return_amount,  # Backend unchanged
                        'return_reason': reason
                    })
                    
            except Exception as e:
                st.warning(f"Could not fetch returns data: {e}")

            # --- Fetch payments made to customer (EXCLUDE automatic return payments) ---
            try:
                customer_payments_to = fetch_payments_to_customer(selected_customer_name)
                
                for payment in customer_payments_to:
                    payment_date = pd.to_datetime(payment['payment_date'])
                    payment_amount = float(payment['amount'])
                    payment_note = payment.get('note', '')
                    
                    is_automatic_return_payment = (
                        'return' in payment_note.lower() or 
                        'refund' in payment_note.lower() or 
                        'sale id' in payment_note.lower() or
                        payment_note.startswith('Excess refund from return')
                    )
                    
                    if not is_automatic_return_payment:
                        # Backend: debit because company is paying customer
                        all_transactions.append({
                            'date': payment_date,
                            'type': 'payment_to_customer',
                            'sale_id': None,
                            'source': 'Company Payment',
                            'products': "",
                            'debit': payment_amount,  # Backend unchanged
                            'credit': 0.0,  # Backend unchanged
                            'payment_note': payment_note
                        })
                    
            except Exception as e:
                st.warning(f"Could not fetch payment-to-customer data: {e}")
                
            # --- Fetch manual customer transactions ---
            try:
                manual_transactions = fetch_customer_transactions(selected_customer_name)
                
                for manual_txn in manual_transactions:
                    txn_date = pd.to_datetime(manual_txn['txn_date'])
                    txn_type = manual_txn['txn_type']  # 'debit' or 'credit'
                    amount = float(manual_txn['amount'])
                    
                    # Backend values unchanged
                    all_transactions.append({
                        'date': txn_date,
                        'type': 'manual_transaction',
                        'sale_id': None,
                        'source': 'Manual Entry',
                        'products': "",
                        'debit': amount if txn_type == 'debit' else 0.0,  # Backend unchanged
                        'credit': amount if txn_type == 'credit' else 0.0,  # Backend unchanged
                        'manual_description': manual_txn['description'],
                        'manual_reference': manual_txn.get('reference', ''),
                        'manual_category': manual_txn.get('category', '')
                    })
                    
            except Exception as e:
                st.warning(f"Could not fetch manual transactions: {e}")

            # --- Sort by date ---
            all_transactions.sort(key=lambda x: x['date'])

            # --- Opening balance before start_date (Backend calculation unchanged) ---
            opening_balance = sum(t['debit'] - t['credit'] for t in all_transactions if t['date'] < start_date)

            # --- Filter transactions for selected range ---
            monthly_transactions = [t for t in all_transactions if start_date <= t['date'] < end_date]

            # --- Build Ledger Data ---
            ledger_data = []
            running_balance = opening_balance
            serial = 1

            if opening_balance != 0:
                # UI CHANGE: Display Money In/Out based on sign, but backend calculation unchanged
                ledger_data.append({
                    'S.No': serial,
                    'Date': start_date.strftime("%d-%b-%Y"),
                    'TYPE': f"Opening Balance for {display_month_name}",
                    'Products': "",
                    'Method': "",
                    # UI MAPPING for opening balance display:
                    # Positive balance = customer owes company → show as Money In to customer's ledger
                    # Negative balance = company owes customer → show as Money Out from customer's ledger
                    'Money In': 0.0 if opening_balance >= 0 else abs(opening_balance),
                    'Money Out': abs(opening_balance) if opening_balance < 0 else 0.0,
                    'Balance': opening_balance
                })
                serial += 1

            for t in monthly_transactions:
                running_balance += t['debit'] - t['credit']  # Backend calculation unchanged
                
                # Enhanced transaction descriptions
                if t['type'] == 'sale':
                    type_desc = f"Sale ID: {t['sale_id']} ({t['source']})"
                    products = t['products']
                    method = ""
                elif t['type'] == 'initial_payment':
                    type_desc = f"Initial payment for Sale ID {t['sale_id']}"
                    products = ""
                    method = t.get('payment_method', 'Cash')
                elif t['type'] == 'payment':
                    payment_method = t.get('payment_method', 'Cash')
                    payment_note = t.get('payment_note', '')
                    note_text = f" - {payment_note}" if payment_note else ""
                    type_desc = f"Payment for Sale ID {t['sale_id']} ({payment_method}){note_text}"
                    products = ""
                    method = payment_method
                elif t['type'] == 'return':
                    reason_text = f" - {t.get('return_reason', '')}" if t.get('return_reason') else ""
                    type_desc = f"Return for Sale ID {t['sale_id']}{reason_text}"
                    products = t['products']
                    method = ""
                elif t['type'] == 'payment_to_customer':
                    note_text = f" - {t.get('payment_note', '')}" if t.get('payment_note') else ""
                    type_desc = f"Payment to Customer{note_text}"
                    products = ""
                    method = ""
                elif t['type'] == 'manual_transaction':
                    ref_text = f" [Ref: {t.get('manual_reference', '')}]" if t.get('manual_reference') else ""
                    cat_text = f" ({t.get('manual_category', '')})" if t.get('manual_category') else ""
                    type_desc = f"Manual Transaction - {t.get('manual_description', '')}{cat_text}{ref_text}"
                    products = ""
                    method = "Manual"
                else:
                    type_desc = f"Received for Sale ID {t['sale_id']}"
                    products = ""
                    method = t.get('payment_method', '')

                # UI MAPPING: Backend debit/credit values unchanged, but displayed as Money In/Out
                # debit (customer owes more) → Money In to customer ledger
                # credit (customer owes less) → Money Out from customer ledger
                ledger_data.append({
                    'S.No': serial,
                    'Date': t['date'].strftime("%d-%b-%Y"),
                    'TYPE': type_desc,
                    'Products': products,
                    'Method': method,
                    'Money In': t['debit'],  # debit → Money In (customer perspective)
                    'Money Out': t['credit'],  # credit → Money Out (customer perspective)
                    'Balance': running_balance
                })
                serial += 1
                
            # --- Create and display ledger ---
            if ledger_data:
                ledger_df = pd.DataFrame(ledger_data)
                display_df = ledger_df.copy()
                display_df['Money In'] = display_df['Money In'].map(lambda x: f"{x:.0f}")
                display_df['Money Out'] = display_df['Money Out'].map(lambda x: f"{x:.0f}")
                display_df['Balance'] = display_df['Balance'].map(lambda x: f"{x:.0f}")

                st.markdown(f"### Customer ledger - {selected_customer_name} - {display_month_name}")
                st.table(display_df)
                
                # --- Calculate Summary Metrics (backend calculations unchanged) ---
                monthly_debits = sum(t['debit'] for t in monthly_transactions)
                monthly_credits = sum(t['credit'] for t in monthly_transactions)
                monthly_returns = sum(t['credit'] for t in monthly_transactions if t['type'] == 'return')
                
                monthly_payments = sum(t['credit'] for t in monthly_transactions if t['type'] in ['payment', 'initial_payment'])
                monthly_payments_to_customer = sum(t['debit'] for t in monthly_transactions if t['type'] == 'payment_to_customer')
                
                total_sales = sum(t['debit'] for t in all_transactions if t['type'] == 'sale')
                total_returns = sum(t['credit'] for t in all_transactions if t['type'] == 'return')
                
                total_actual_payments_from_customer = sum(t['credit'] for t in all_transactions if t['type'] in ['payment', 'initial_payment'])
                total_payments_to_customer = sum(t['debit'] for t in all_transactions if t['type'] == 'payment_to_customer')
                
                total_cash_sales = sum(t['credit'] for t in all_transactions if t['type'] == 'sale' and t.get('source') in ['POS', 'Sales Module'])
                
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

                # --- Pay to Customer Section ---
                if final_balance < 0:
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
                                success = record_payment_to_customer(selected_customer_name, pay_amount, payment_note)
                                if success:
                                    st.success(f"✅ Payment of PKR {pay_amount:,.2f} recorded for {selected_customer_name}")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to record payment. Please try again.")
                            except Exception as e:
                                st.error(f"❌ Error recording payment: {e}")

                # --- Returns Summary ---
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

                # --- Payments to Customer Summary ---
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
                        payments_df = pd.DataFrame(payments_data)
                        st.table(payments_df)
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
                            logo_width = 30
                            logo_height = 20

                            # Background bar first
                            header_bg_color = (255, 255, 255)
                            self.set_fill_color(*header_bg_color)
                            self.rect(0, 0, self.page_width, 25, style='F')

                            # Add logo (draw on top of the background)
                            if os.path.exists(logo_path):
                                try:
                                    self.image(logo_path, x=self.left_margin, y=5, w=logo_width, h=logo_height)
                                except RuntimeError as e:
                                    print(f"Error loading image: {e}")

                            # Text: Company name and subtitle
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
                            footer_color = (100, 100, 100)
                            self.set_text_color(*footer_color)
                            self.cell(0, 10, f'Page {self.page_no()} - Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')

                        def section_title(self, title):
                            """Styled section title with underline"""
                            self.set_font('Arial', 'B', 12)
                            self.set_text_color(54, 95, 145)
                            self.cell(0, 8, title, 0, 1)
                            self.set_draw_color(54, 95, 145)
                            self.line(self.left_margin, self.get_y(), self.page_width - self.right_margin, self.get_y())
                            self.ln(3)
                            self.set_text_color(0, 0, 0)

                        def table_header(self, headers, col_widths):
                            """Styled table header"""
                            header_bg_color = (166, 124, 33)
                            header_text_color = (255, 255, 255)

                            self.set_font("Arial", "B", 10)
                            self.set_fill_color(*header_bg_color)
                            self.set_text_color(*header_text_color)
                            self.set_draw_color(23, 24, 22)

                            for i, header in enumerate(headers):
                                self.cell(col_widths[i], 8, header, border=1, align="C", fill=True)
                            self.ln()

                            # Reset text color to black for the rows
                            self.set_text_color(0, 0, 0)

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

                            # Estimate wrapped height for TYPE and Products columns
                            type_height = 0
                            products_height = 0

                            if "TYPE" in headers:
                                type_idx = headers.index("TYPE")
                                type_width = col_widths[type_idx]
                                type_lines = self.multi_cell(type_width, 5, str(row["TYPE"]), border=0, align="L", fill=False, split_only=True)
                                type_height = len(type_lines) * 5

                            if "Products" in headers and str(row["Products"]):
                                prod_idx = headers.index("Products")
                                prod_width = col_widths[prod_idx]
                                prod_lines = self.multi_cell(prod_width, 5, str(row["Products"]), border=0, align="L", fill=False, split_only=True)
                                products_height = len(prod_lines) * 5

                            max_cell_height = max(max_cell_height, type_height, products_height)

                            self.set_y(current_y)

                            for i, (col, width) in enumerate(zip(headers, col_widths)):
                                # UI CHANGE: Handle both "Money In"/"Money Out" AND "Debit"/"Credit" for compatibility
                                # Map Money In → Debit, Money Out → Credit for data access
                                if col in ["Money In", "Debit"]:
                                    # Money In column - access 'Money In' from row data
                                    data_col = "Money In" if "Money In" in row else "Debit"
                                    value = f"{float(row[data_col]):,.2f}" if float(row[data_col]) != 0 else "-"
                                    align = "R"
                                    self.cell(width, max_cell_height, value, border=1, align=align, fill=True)
                                    
                                elif col in ["Money Out", "Credit"]:
                                    # Money Out column - access 'Money Out' from row data
                                    data_col = "Money Out" if "Money Out" in row else "Credit"
                                    value = f"{float(row[data_col]):,.2f}" if float(row[data_col]) != 0 else "-"
                                    align = "R"
                                    
                                    # Special color for return credits (Money Out in returns)
                                    if is_return and float(row[data_col]) > 0:
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

                    def generate_customer_ledger_pdf(customer_name, ledger_df, total_received, total_sales, final_balance, total_returns=0, returns_data=None):
                        """Enhanced PDF generation with Money In/Out terminology"""
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
                        
                        # UI CHANGE: Column headers updated to Money In/Money Out
                        # WHY: Match the display DataFrame columns shown to user
                        headers = ["S.No", "Date", "TYPE", "Products", "Money In", "Money Out", "Balance"]
                        col_widths = [8, 20, 35, 50, 22, 22, 22]
                        
                        pdf.table_header(headers, col_widths)
                        
                        # Ledger Table Rows
                        for idx, row in ledger_df.iterrows():
                            is_even_row = idx % 2 == 0
                            pdf.table_row(row, col_widths, headers, is_even_row)
                        
                        # Add Returns Summary Table if there are returns
                        if returns_data and len(returns_data) > 0:
                            pdf.ln(10)
                            pdf.returns_summary_table(returns_data)
                        
                        # Add notes section - UPDATED with Money In/Out explanations
                        pdf.ln(10)
                        pdf.section_title("Notes")
                        pdf.set_font('Arial', '', 9)
                        notes_text = "* All amounts are in Pakistani Rupees (PKR)\n"
                        notes_text += "* Positive balance indicates customer owes you\n"
                        notes_text += "* Negative balance indicates you owe customer\n"
                        notes_text += "* Money In = Sales to customer (increases what they owe)\n"
                        notes_text += "* Money Out = Customer payments to you (decreases what they owe)\n"
                        if total_returns > 0:
                            notes_text += "* Returns are highlighted in orange and reduce customer balance\n"
                            notes_text += "* Return transactions show returned products and quantities"
                        
                        pdf.multi_cell(0, 5, notes_text)
                        
                        # Save to temporary file
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                        pdf.output(temp_file.name)
                        return temp_file.name

                    # --- PDF Generation Button ---
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
                else:
                    st.warning("No transactions found for the selected customer and period.")

                # [PDF generation code continues with same structure but updated column names]
                # Note: PDF generation code would follow same pattern - update headers to use
                # "Money In" and "Money Out" instead of "Debit" and "Credit" in display only
            else:
                st.warning("No transactions found for the selected customer and period.")
                
if __name__ == "__main__":
    sales_page()