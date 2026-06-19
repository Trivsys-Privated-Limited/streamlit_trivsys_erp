import streamlit as st
import pandas as pd
from database import *
from decimal import Decimal
from datetime import timedelta  # Add this import
import tempfile, os

if "tenant" in st.session_state and hasattr(st.session_state.tenant, "business_name"):
    business_name = st.session_state.tenant.business_name.upper()
else:
    business_name = "default_business_name"
if 'credit_sales_initialized' not in st.session_state:
    st.session_state.current_view = 'list'
    st.session_state.selected_invoice_id = None
    st.session_state.credit_sales_initialized = True,                                                                                                                                    


def credit_sales_history_page(fetch_credit_sales_history_fn, fetch_payments_for_sale_fn):
    if 'current_view' not in st.session_state:
        st.session_state.current_view = 'list'  # need to see again
    if 'selected_invoice_id' not in st.session_state:
        st.session_state.selected_invoice_id = None
    apply_invoice_styling()

    # fetch raw history rows from your existing function
    history_rows = fetch_credit_sales_history_fn()
    sales_data = build_sales_data_from_history(history_rows, fetch_payments_for_sale_fn)

    if st.session_state.current_view == 'list':
        show_invoice_list(sales_data)
    elif st.session_state.current_view == 'detail':
        selected_id = st.session_state.selected_invoice_id
        selected_invoice = next((s for s in sales_data if s["id"] == selected_id), None)
        if selected_invoice:
            show_invoice_detail(selected_invoice)
        else:
            st.error("Invoice not found!")
            st.session_state.current_view = 'list'
            st.session_state.selected_invoice_id = None


def apply_invoice_styling():
    st.markdown("""
    <style>
    /* Invoice List Table Styling */
    .invoice-table-container {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    /* Action button styling */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.4rem 1rem;
        font-weight: 500;
        font-size: 0.85rem;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        transform: translateY(-1px);
    }
    /* Status badges */
    .status-badge {
        padding: 0.35rem 0.85rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .status-paid { background: #d1fae5; color: #065f46; }
    .status-partial { background: #fef3c7; color: #92400e; }
    .status-unpaid { background: #fee2e2; color: #991b1b; }

    /* Invoice Detail Page */
    .invoice-header {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        color: white;
        padding: 2rem;
        border-radius: 12px 12px 0 0;
        margin-bottom: 0;
    }
    .invoice-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; }
    .invoice-subtitle { color: #cbd5e1; font-size: 1rem; }

    .invoice-body {
        background: white;
        padding: 2rem;
        border-radius: 0 0 12px 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .invoice-info-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 2rem;
        margin-bottom: 2rem;
        padding-bottom: 2rem;
        border-bottom: 2px solid #e2e8f0;
    }
    .info-block h4 {
        color: #64748b;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
        font-weight: 600;
    }
    .info-block p { color: #1e293b; font-size: 1.1rem; font-weight: 600; margin: 0.25rem 0; }

    .products-table { width: 100%; border-collapse: separate; border-spacing: 0; margin: 2rem 0; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .products-table thead { background: linear-gradient(135deg, #475569 0%, #334155 100%); color: white; }
    .products-table th { padding: 1rem; text-align: left; font-weight: 600; font-size: 0.9rem; text-transform: uppercase; }
    .products-table tbody tr { background: white; border-bottom: 1px solid #e2e8f0; }
    .products-table tbody tr:hover { background: #f8fafc; }
    .products-table td { padding: 1rem; color: #1e293b; }
    .products-table tbody tr:last-child { border-bottom: none; }

    .totals-section { background: #f8fafc; padding: 1.5rem; border-radius: 8px; margin-top: 2rem; }
    .total-row { display: flex; justify-content: space-between; padding: 0.75rem 0; font-size: 1.1rem; }
    .total-row.grand-total { border-top: 2px solid #cbd5e1; margin-top: 0.5rem; padding-top: 1rem; font-size: 1.5rem; font-weight: 700; color: #1e293b; }
    .total-row .label { color: #64748b; font-weight: 600; }
    .total-row .value { font-weight: 700; }
    .value.paid { color: #10b981; }
    .value.due { color: #ef4444; }

    .payment-history-section { background: #ecfdf5; border-left: 4px solid #10b981; padding: 1.5rem; border-radius: 8px; margin-top: 2rem; }
    .payment-history-title { font-size: 1.2rem; font-weight: 700; color: #065f46; margin-bottom: 1rem; }
    .payment-item { background: white; padding: 1rem; border-radius: 6px; margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center; }
    .no-payments { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 1rem 1.5rem; border-radius: 8px; color: #92400e; font-weight: 500; margin-top: 1rem; }
    .back-button { margin-bottom: 1.5rem; }

    /* small responsive tweak */
    @media(max-width: 800px) {
        .invoice-info-grid { grid-template-columns: 1fr; }
    }
    </style>
    """, unsafe_allow_html=True)

def build_sales_data_from_history(history_rows, fetch_payments_fn):
    """
    history_rows is expected to be a list of rows that fetch_credit_sales_history() returns.
    The function groups by Sale ID and constructs a list of sale dicts with products + totals + payments.
    """
    if not history_rows:
        return []

    # Convert to DataFrame for grouping like your original code
    df = pd.DataFrame(history_rows, columns=[
        "Sale ID", "Product", "Quantity", "Sale Price", "Customer", "Sale Date",
        "Source", "Paid Amount", "Due Amount"
    ])

    sales_data = []
    grouped = df.groupby("Sale ID")
    for sale_id, group in grouped:
        customer = group["Customer"].iloc[0]
        date_raw = group["Sale Date"].iloc[0]
        # normalize/format date
        try:
            date = pd.to_datetime(date_raw).strftime("%Y-%m-%d %I:%M %p")
        except Exception:
            date = str(date_raw)
        source = group["Source"].iloc[0]
        total_price = (group["Quantity"] * group["Sale Price"]).sum()
        paid_amount = float(group["Paid Amount"].iloc[0])
        due_amount = float(group["Due Amount"].iloc[0])

        # products list
        products = []
        for _, r in group.iterrows():
            products.append({
                "name": r["Product"],
                "quantity": int(r["Quantity"]),
                "sale_price": float(r["Sale Price"]),
                "total": float(r["Quantity"] * r["Sale Price"])
            })

        # fetch payments for this sale (preserve your function)
        payments_raw = fetch_payments_fn(sale_id) or []
        payments = []
        for p in payments_raw:
            # assuming payment tuple (amount, date) like your old code — adapt if different
            amount = float(p[0]) if len(p) > 0 else 0.0
            p_date = p[1] if len(p) > 1 else ""
            try:
                p_date_fmt = pd.to_datetime(p_date).strftime("%Y-%m-%d %I:%M %p")
            except Exception:
                p_date_fmt = str(p_date)
            payments.append({"date": p_date_fmt, "amount": amount})

        sales_data.append({
            "id": int(sale_id),
            "customer": customer,
            "date": date,
            "source": source,
            "total_price": float(total_price),
            "paid_amount": float(paid_amount),
            "due_amount": float(due_amount),
            "products": products,
            "payments": payments
        })

    # Sort newest first by id (optional)
    # sales_data = sorted(sales_data, key=lambda x: x["id"], reverse=True)
    sales_data = sorted(sales_data, key=lambda x: x["date"], reverse=True)
    return sales_data


def show_invoice_list(sales_data):
    st.header("Credit Sales History")

    # Search and filters
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.markdown('#### Search')
        search = st.text_input("Search", placeholder="Search by customer or invoice ID...",label_visibility='collapsed')
    with col2:
        st.markdown('#### Status')
        status_filter = st.selectbox("Status", ["All", "Paid", "Partial Payment", "Unpaid"], key="status_filter",label_visibility='collapsed')
    with col3:
        st.write("")  # spacing
        st.write("")
        if st.button("Refresh", use_container_width=True, key="refresh_list"):
            st.session_state.current_view = 'list'
            st.session_state.selected_invoice_id = None
            st.rerun()

    st.markdown("---")
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1, 2, 2, 2, 2, 2, 2, 1.5])
    with col1:
        st.markdown('##### ID')
    with col2:
        st.markdown('##### Customer')
    with col3:
        st.markdown('##### Date')
    with col4:
        st.markdown('##### Total Price')
    with col5:
        st.markdown('##### Paid Amount')
    with col6:
        st.markdown('##### Due Amount')
    with col7:
        st.markdown('##### Status')
    with col8:
        st.markdown('##### Action')

    st.markdown('---')

    # Filter & search
    filtered = []
    for s in sales_data:
        # apply search
        if search:
            search_lower = search.lower()
            if not (search_lower in str(s['id']).lower() or search_lower in s['customer'].lower()):
                continue
        # apply status filter
        status = "Paid" if s['due_amount'] == 0 else ("Partial Payment" if s['paid_amount'] > 0 else "Unpaid")
        if status_filter != "All" and status != status_filter:
            continue
        s_copy = s.copy()
        s_copy['status'] = status
        filtered.append(s_copy)

    if not filtered:
        st.info("No credit sales found (matching filters).")
        return

    # Display rows
    for sale in filtered:
        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1, 2, 2, 2, 2, 2, 2, 1.5])
        with col1:
            st.write(f"**{sale['id']}**")
        with col2:
            st.write(sale['customer'])
        with col3:
            st.write(sale['date'])
        with col4:
            st.write(f"Rs. {sale['total_price']:,.2f}")
        with col5:
            st.write(f"Rs. {sale['paid_amount']:,.2f}")
        with col6:
            st.write(f"Rs. {sale['due_amount']:,.2f}")
        with col7:
            if sale['status'] == "Paid":
                st.markdown(f'<span class="status-badge status-paid">✓ {sale["status"]}</span>', unsafe_allow_html=True)
            elif sale['status'] == "Partial Payment":
                st.markdown(f'<span class="status-badge status-partial">⚠ {sale["status"]}</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="status-badge status-unpaid">⊘ {sale["status"]}</span>', unsafe_allow_html=True)
        with col8:
            if st.button("View", key=f"view_{sale['id']}", use_container_width=True):
                st.session_state.selected_invoice_id = sale['id']
                st.session_state.current_view = 'detail'
                st.rerun()
        st.markdown("---")


def show_invoice_detail(invoice_data):
    # Back button
    if st.button("← Back to Sales History", key=f"back_{invoice_data['id']}"):
        st.session_state.current_view = 'list'
        st.session_state.selected_invoice_id = None
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Determine status
    if invoice_data['due_amount'] == 0:
        status = "PAID"
        status_class = "status-paid"
    elif invoice_data['paid_amount'] > 0:
        status = "PARTIAL PAYMENT"
        status_class = "status-partial"
    else:
        status = "UNPAID"
        status_class = "status-unpaid"

    # Invoice Header
    st.markdown(f"""
    <div class="invoice-header">
        <div class="invoice-title">Invoice #{invoice_data['id']}</div>
        <div class="invoice-subtitle">
            {invoice_data['date']} • {invoice_data['source']}
            <span class="status-badge {status_class}" style="margin-left: 1rem;">{status}</span>
        </div>
    </div>
    <div class="invoice-body">
        <div class="invoice-info-grid">
            <div class="info-block">
                <h4>Bill To</h4>
                <p>👤 {invoice_data['customer']}</p>
            </div>
            <div class="info-block">
                <h4>Invoice Date</h4>
                <p>📅 {invoice_data['date']}</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Products Table (build HTML)
    
    st.markdown("""<h3 style="color: #1e293b; margin-bottom: 1rem;">📦 Products</h3>""", unsafe_allow_html=True)
    table_html = '<table class="products-table"><thead><tr>'
    table_html += '<th>#</th><th>Product Name</th><th>Quantity</th><th>Unit Price</th><th>Total Price</th>'
    table_html += '</tr></thead>'
    
    for idx, product in enumerate(invoice_data['products'], 1):
        table_html += f"""<tbody>
        <tr>
            <td>{idx}</td>
            <td><strong>{product['name']}</strong></td>
            <td>{product['quantity']}</td>
            <td>Rs. {product['sale_price']:,.2f}</td>
            <td><strong>Rs. {product['total']:,.2f}</strong></td>
        </tr>"""
    
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

    # Totals
    st.markdown(f"""
    <div class="totals-section">
        <div class="total-row">
            <span class="label">Subtotal:</span>
            <span class="value">Rs. {invoice_data['total_price']:,.2f}</span>
        </div>
        <div class="total-row grand-total">
            <span class="label">Total Amount:</span>
            <span class="value">Rs. {invoice_data['total_price']:,.2f}</span>
        </div>
        <div class="total-row">
            <span class="label">Paid Amount:</span>
            <span class="value paid">Rs. {invoice_data['paid_amount']:,.2f}</span>
        </div>
        <div class="total-row">
            <span class="label">Due Amount:</span>
            <span class="value due">Rs. {invoice_data['due_amount']:,.2f}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Payment History
    if invoice_data.get('payments') and len(invoice_data['payments']) > 0:
        st.markdown("""<div class="payment-history-section"><div class="payment-history-title"><h4>Payment History</h4></div>""", unsafe_allow_html=True)
        for payment in invoice_data['payments']:
            st.markdown(f"""
            <div class="payment-item">
                <span><strong>Payment on {payment['date']}</strong></span>
                <span style="color: #10b981; font-weight: 700; font-size: 1.1rem;">Rs. {payment['amount']:,.2f}</span>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="no-payments">⚠️ No payments recorded for this invoice yet.</div>""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Main page function
# -------------------------

def record_customer_payment(full_payment,customer_id, payment_amount, payment_method="Cash", payment_note=None):
    """
    Record payment for a customer across multiple sales using FIFO (First In, First Out) approach
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Start transaction
        conn.autocommit = False
        
        # Get all pending sales for this customer ordered by date (FIFO)
        cursor.execute("""
            SELECT id, due_amount
            FROM sales
            WHERE customer_id = %s AND credit_sale = TRUE AND due_amount > 0
            ORDER BY sale_date ASC
        """, (customer_id,))
        pending_sales = cursor.fetchall()
        
        remaining_payment = payment_amount
        
        for sale_id, due_amount in pending_sales:
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
            """, (payment_for_this_sale, payment_for_this_sale, sale_id))
            
            # Record the payment in payments table with payment method and note
            cursor.execute("""
                INSERT INTO payments (full_payment,sale_id, amount, payment_date, payment_method, payment_note)
                VALUES (%s,%s, %s, NOW(), %s, %s)
            """, (full_payment,sale_id, payment_for_this_sale, payment_method, payment_note))
            
            remaining_payment -= payment_for_this_sale
        
        # Commit transaction
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        # Rollback transaction on error
        conn.rollback()
        conn.close()
        st.error(f"Error recording payment: {str(e)}")
        return False


# At the time of invoice generation, save the PDF file permanently:
def generate_and_save_credit_invoice(sale_data):
    pdf = CreditSalePDF(customer_name=sale_data['customer'], sale_id=sale_data['sale_id'])
    pdf.add_page()
    pdf.add_sale_details(sale_data)

    # Create the directory if it doesn't exist
    invoice_dir = "invoices/credit_sales"
    os.makedirs(invoice_dir, exist_ok=True)

    # Filename with timestamp
    date_str = datetime.strptime(sale_data['date'], "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d_%H%M%S")
    filename = f"credit_invoice_{sale_data['sale_id']}_{date_str}.pdf"
    filepath = os.path.join(invoice_dir, filename)

    # Save the PDF
    pdf.output(filepath)
    return filepath, filename



def fetch_credit_sales_history():
    """Fetch credit sales history with customer and product details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id AS sale_id, p.name AS product_name, si.quantity, si.sale_price, c.customer_name, s.sale_date, s.source, s.paid_amount, s.due_amount
        FROM sales s
        JOIN sale_items si ON s.id = si.sale_id
        JOIN products p ON si.product_id = p.id
        JOIN customers c ON s.customer_id = c.id
        WHERE s.credit_sale = TRUE
        ORDER BY s.sale_date DESC
    """)
    history = cursor.fetchall()
    conn.close()
    return history

def get_or_create_customer(customer_name):
    """Fetch or create a customer and return their ID."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the customer already exists
    cursor.execute("SELECT id FROM customers WHERE customer_name = %s", (customer_name,))
    result = cursor.fetchone()

    if result:
        customer_id = result[0]
    else:
        # If customer doesn't exist, create a new customer
        cursor.execute("INSERT INTO customers (customer_name) VALUES (%s)", (customer_name,))
        conn.commit()
        customer_id = cursor.lastrowid

    conn.close()
    return customer_id


def add_credit_sale(cart, customer_id, paid_amount,sale_date):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Calculate total price and due amount for the entire cart
        # Convert to Decimal for consistent calculation
        total_price = Decimal(str(sum(item["quantity"] * item["sale_price"] for item in cart)))
        
        # Ensure paid_amount is also Decimal
        if not isinstance(paid_amount, Decimal):
            paid_amount = Decimal(str(paid_amount))
            
        due_amount = total_price - paid_amount

        # Get the current date and calculate payment due date
        current_date = datetime.now()
        payment_due_date = current_date + timedelta(weeks=1)

        # Insert a single record for the entire credit sale (sale record)
        cursor.execute("""
            INSERT INTO sales (customer_id, total_price, paid_amount, due_amount, credit_sale, payment_due_date, sale_date, source)
            VALUES (%s, %s, %s, %s, TRUE, %s, %s, 'Credit Sales')
        """, (customer_id, float(total_price), float(paid_amount), float(due_amount), payment_due_date, sale_date))
        
        # Get the sale_id from the inserted sale record
        sale_id = cursor.lastrowid

        # Insert each item from the cart into the sale_items table under the same sale_id
        for item in cart:
            # Ensure that sale_price exists; if not, set it to 0.00
            sale_price = item.get("sale_price")
            if sale_price is None:
                sale_price = Decimal("0.00")  # or you might use the product's price as a fallback
            else:
                # Convert to Decimal for consistency
                sale_price = Decimal(str(sale_price))

            cursor.execute("""
                INSERT INTO sale_items (sale_id, product_id, quantity, sale_price)
                VALUES (%s, %s, %s, %s)
            """, (sale_id, item["product_id"], item["quantity"], float(sale_price)))

            # Deduct stock from the product
            cursor.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (item["quantity"], item["product_id"]))

        conn.commit()
        return sale_id  # Return the sale_id instead of True

    except Exception as e:
        st.error(f"Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def record_payment(sale_id, amount, payment_method="Cash", payment_note=None):
    """Record a payment towards a credit sale with payment method and note."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Insert the payment into the 'payments' table with payment method and note
        cursor.execute("""
            INSERT INTO payments (sale_id, amount, payment_date, payment_method, payment_note)
            VALUES (%s, %s, NOW(), %s, %s)
        """, (sale_id, amount, payment_method, payment_note))
        conn.commit()

        # Now update the paid_amount and due_amount in the 'sales' table
        cursor.execute("""
            UPDATE sales
            SET paid_amount = paid_amount + %s,
                due_amount = due_amount - %s
            WHERE id = %s
        """, (amount, amount, sale_id))
        conn.commit()

        return True
    except Exception as e:
        st.error(f"Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
        

def fetch_products():
    """Fetch the list of products."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, stock, price FROM products")
    products = cursor.fetchall()
    conn.close()
    return products

def fetch_customers():
    """Fetch the list of customers."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, customer_name FROM customers")
    customers = cursor.fetchall()
    conn.close()
    return customers

def get_customer_balance(customer_id):
    """Get the outstanding balance for a customer."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(cs.total_price) - IFNULL(SUM(p.amount), 0) AS balance
        FROM sales cs
        LEFT JOIN payments p ON cs.id = p.sale_id
        WHERE cs.customer_id = %s AND cs.credit_sale = TRUE
    """, (customer_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result[0] is not None else 0

def fetch_payments_for_sale(sale_id):
    """Fetch payments for a specific sale with payment method and note details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT amount, payment_date, payment_method, payment_note
        FROM payments
        WHERE sale_id = %s
        ORDER BY payment_date DESC
    """, (sale_id,))
    payments = cursor.fetchall()
    conn.close()
    return payments


from fpdf import FPDF

class CreditSalePDF(FPDF):
    def __init__(self, customer_name, sale_id):
        super().__init__()
        self.page_width = 210
        self.left_margin = 10
        self.right_margin = 10
        self.customer_name = customer_name
        self.sale_id = sale_id
        self.set_auto_page_break(auto=True, margin=15)
        self.theme_color = (255, 255, 255)  # White theme
        self.header_text_color = (0, 0, 0)  # Golden text
        self.logo_path = "static/trivsys.png"
        self.logo_width = 30
        self.logo_height = 20

    def header(self):
        # Background
        self.set_fill_color(*self.theme_color)
        self.rect(0, 0, self.page_width, 25, style='F')

        # Logo
        if os.path.exists(self.logo_path):
            try:
                self.image(self.logo_path, x=self.left_margin, y=5, w=self.logo_width, h=self.logo_height)
            except RuntimeError as e:
                print(f"Logo error: {e}")

        # Header Title
        self.set_text_color(*self.header_text_color)
        self.set_font('Arial', 'B', 16)
        self.set_xy(self.left_margin + self.logo_width + 5, 8)
        self.cell(0, 8, business_name, ln=True)

        # Subtitle
        self.set_font('Arial', '', 11)
        self.set_x(self.left_margin + self.logo_width + 5)
        self.cell(0, 8, f"Credit Sale Invoice - {self.customer_name}", ln=True)

        self.set_text_color(0, 0, 0)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Page {self.page_no()} - Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')

    def add_sale_details(self, sale_data):
        self.set_font('Arial', '', 11)
        self.cell(0, 8, f"Sale ID: {sale_data['sale_id']}", ln=True)
        self.cell(0, 8, f"Customer: {sale_data['customer']}", ln=True)
        self.cell(0, 8, f"Date: {sale_data['date']}", ln=True)
        self.cell(0, 8, f"Source: {sale_data['source']}", ln=True)
        self.ln(5)

        # Table Headers
        self.set_fill_color(166, 124, 33)  # Blue fill
        self.set_text_color(255, 255, 255)  # White text
        self.set_font('Arial', 'B', 11)

        self.cell(70, 8, "Product", 1, 0, 'C', fill=True)
        self.cell(30, 8, "Quantity", 1, 0, 'C', fill=True)
        self.cell(40, 8, "Unit Price", 1, 0, 'C', fill=True)
        self.cell(40, 8, "Total", 1, 1, 'C', fill=True)

        # Reset text color to black for the table rows
        self.set_text_color(0, 0, 0)

        # Table Rows
        self.set_font('Arial', '', 11)
        for item in sale_data['products']:
            # Calculate height required for product name
            product_name = item['product'].split(' (Stock')[0] if ' (Stock' in item['product'] else item['product']
            line_height = 8
            text_width = 70
            num_lines = len(self.multi_cell(text_width, line_height, product_name, border=0, align='L', split_only=True))
            cell_height = line_height * num_lines

            x = self.get_x()
            y = self.get_y()

            # Product (wrapped)
            self.multi_cell(70, line_height, product_name, border=1)
            self.set_xy(x + 70, y)

            # Quantity
            self.cell(30, cell_height, str(item['quantity']), 1, 0)

            # Unit Price - handle both sale_price and unit_price cases
            unit_price = item.get('sale_price', item.get('unit_price', 0.00))
            self.cell(40, cell_height, f"Rs. {float(unit_price):.2f}", 1, 0)

            # Total
            self.cell(40, cell_height, f"Rs. {item['total']:.2f}", 1, 1)

        self.ln(5)
        self.cell(0, 8, f"Total Price: Rs. {sale_data['total_price']:.2f}", ln=True)
        self.cell(0, 8, f"Paid Amount: Rs. {sale_data['paid_amount']:.2f}", ln=True)
        self.cell(0, 8, f"Due Amount: Rs. {sale_data['due_amount']:.2f}", ln=True)


def credit_sales_page():
    
    if st.button("Back to Home"):
        st.session_state.current_view = 'list'
        st.session_state.selected_invoice_id = None
        st.session_state.credit_sales_initialized = False
        st.session_state.page = "Home"
        st.rerun()

    # trying new sidebar.....

    # Initialize session state for navigation if not exists
    if 'sub_menu' not in st.session_state:
        st.session_state.sub_menu = "Record Credit Sale"
    with st.sidebar:
    # Module Title

        st.markdown("### Credit Sales")
        
        # Navigation buttons
        menu_items = [
            "Record Credit Sale",
            "Credit Sales History", 
            "Update Payment",
            "All Invoices"
        ]
        
        for item in menu_items:
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.sub_menu = item
                st.rerun()

    sub_menu = st.session_state.sub_menu

    if sub_menu == "Record Credit Sale":
        st.header(" Create a Sale on Credit")

        # Fetch products and customers from the database
        products = fetch_products()
        customers = fetch_customers()

        if not products:
            st.warning("No products available for credit sales.")
            return

        if not customers:
            st.warning("No customers available. Please add customers.")
            return

        # Session state for cart
        if "credit_sales_cart" not in st.session_state:
            st.session_state.credit_sales_cart = []

        # Dropdowns
        c1,c2 = st.columns(2)
        with c1:
            customer_names = {c[1]: c[0] for c in customers}
            st.markdown('#### Select Customer')
            selected_customer_name = st.selectbox("Customer", list(customer_names.keys()),label_visibility='collapsed')
            customer_id = customer_names[selected_customer_name]
        with c2:
            product_options = {f"{p[1]} (Stock: {p[2]}, Base Price: Rs.{p[3]:,.2f})": (p[0], p[2], p[3]) for p in products}
            st.markdown('#### Select Product')
            selected_product = st.selectbox("Select Product", list(product_options.keys()),label_visibility='collapsed')
            product_id, stock, base_price = product_options[selected_product]

        # ===== NEW DYNAMIC PRICING SECTION =====

        c1,c2 = st.columns(2)

        with c2:
            st.subheader("Set Sale Price")
            
            # Option to use base price or set custom price
            price_option = st.radio(
                "Choose pricing option:",
                ["Use Default Price", "Set Custom Price"],
                horizontal=True
            )
            
            if price_option == "Use Default Price":
                sale_price = float(base_price)
                st.info(f"Using Default price: Rs. {base_price:,.2f}")
            else:
                sale_price = st.number_input(
                    "Enter Custom Sale Price", 
                    min_value=0.01, 
                    step=0.01, 
                    value=float(base_price),
                    help="Set a custom price for this specific sale"
                )
                
                # Convert base_price to float for comparison
                base_price_float = float(base_price)
                
                # Show price comparison
                if sale_price > base_price_float:
                    st.success(f"💰 Premium pricing: Rs. {sale_price - base_price_float:,.2f} above base price")
                elif sale_price < base_price_float:
                    st.warning(f"🏷️ Discounted pricing: Rs. {base_price_float - sale_price:,.2f} below base price")
                else:
                    st.info("Same as Default price")

            # ===== OPTIONAL: UPDATE BASE PRICE =====
            with st.expander("🔧 Update Product Default Price (Optional)"):
                st.write("This will update the product's Default price in inventory for future sales")
                new_base_price = st.number_input(
                    "New Price", 
                    min_value=0.01, 
                    step=0.01, 
                    value=float(base_price),
                    key="new_base_price"
                )
                
                if st.button("Update Price"):
                    if abs(new_base_price - float(base_price)) > 0.01:  # Check for meaningful difference
                        update_price(product_id, new_base_price)
                        st.success(f"Base price updated from Rs. {base_price:,.2f} to Rs. {new_base_price:,.2f}")
                        st.rerun()  # Refresh to show new base price
                    else:
                        st.info("No change in base price")

        with c1:
            # ===== QUANTITY SECTION =====
            st.markdown('### Quantity ')
            quantity = st.number_input("quantity", min_value=1, step=1, value=1,label_visibility='collapsed')

            # Disable Add to Cart button if stock is 0 or quantity exceeds stock
            if stock == 0:
                st.warning("This product is out of stock!")
                add_to_cart_disabled = True
            elif quantity > stock:
                st.warning(f"Only {stock} units available! Please enter a valid quantity.")
                add_to_cart_disabled = True
            else:
                add_to_cart_disabled = False
            st.markdown('#### Enter Date')
            sale_date = st.date_input(label = 'enter date', label_visibility='collapsed')
        # Add to cart
        if st.button("Add to Cart", disabled=add_to_cart_disabled):
            st.session_state.credit_sales_cart.append({
                "product_id": product_id,
                "product_name": selected_product,
                "quantity": quantity,
                "sale_price": sale_price  # Use the custom sale price
            })
            st.success(f"Added {quantity} units of {selected_product} to cart at Rs. {sale_price:,.2f} each")

        # Display cart
        if st.session_state.credit_sales_cart:
            st.subheader("Cart")
            cart_df = pd.DataFrame(st.session_state.credit_sales_cart)
            cart_df["Total Price"] = cart_df["quantity"] * cart_df["sale_price"]
            
            # Format the display
            display_df = cart_df[["product_name", "quantity", "sale_price", "Total Price"]].copy()
            display_df.columns = ["Product", "Quantity", "Unit Price (Rs.)", "Total (Rs.)"]
            st.table(display_df)

            # Grand total
            grand_total = sum(item["quantity"] * item["sale_price"] for item in st.session_state.credit_sales_cart)
            st.markdown(f"### Total Price: Rs. {grand_total:,.2f}")

            # Paid and due amount
            paid_amount = Decimal(st.number_input("Enter Paid Amount", min_value=0.00, step=10.00, format="%.2f"))
            due_amount = Decimal(grand_total) - paid_amount
            st.markdown(f"##### 🔻 Amount Remaining : Rs. {due_amount:,.2f}")

            if st.button("Create Sale"):
                # Get the current date and time properly
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Call add_credit_sale and get the sale_id
                sale_id = add_credit_sale(cart=st.session_state.credit_sales_cart, customer_id=customer_id, paid_amount=paid_amount,sale_date=sale_date)

                if sale_id:
                    # Create PDF
                    pdf = CreditSalePDF(selected_customer_name, sale_id)
                    pdf.add_page()
                    pdf.add_sale_details({
                        "sale_id": sale_id,
                        "customer": selected_customer_name,
                        "date": now,
                        "source": "Credit Sales",
                        "products": [
                            {
                                "product": item["product_name"],
                                "quantity": item["quantity"],
                                "unit_price": item["sale_price"],
                                "total": item["quantity"] * item["sale_price"]
                            } for item in st.session_state.credit_sales_cart
                        ],
                        "total_price": grand_total,
                        "paid_amount": float(paid_amount),
                        "due_amount": float(due_amount)
                    })

                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
                        pdf.output(tmpfile.name)

                    with open(tmpfile.name, "rb") as f:
                        st.download_button(
                        label="Download Invoice PDF",
                        data=f.read(),
                        file_name=f"Credit_Invoice_{sale_id}.pdf",
                        mime="application/pdf"
                    )
                        
                    st.success(f"Credit sale recorded successfully for {len(st.session_state.credit_sales_cart)} products.")
                    st.session_state.credit_sales_cart = []
                else:
                    st.error("Failed to finalize the credit sale.")
          


 
    # elif sub_menu == "Customer Ledger":
    #     from main_ledger import customer_ledger
    #     customer_ledger()


    elif sub_menu == "Credit Sales History":
    
        # -------------------------
        # Example usage: call this function with your actual fetch functions
        # -------------------------
        # Replace the two stubs below with your real functions already in the app.
        # def fetch_credit_sales_history(): ...
        # def fetch_payments_for_sale(sale_id): ...

        # import or reference your real functions here
        try:
            # calling names you already have in your project
            credit_sales_history_page(fetch_credit_sales_history, fetch_payments_for_sale)
        except Exception as e:
            st.error(f"Error loading Credit Sales page: {e}")

    elif sub_menu == "Update Payment":
        st.header("Update Payment Installment")
        
        # Fetch credit sales with pending dues
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Show total outstanding due across all credit sales
        cursor.execute("""
            SELECT SUM(due_amount)
            FROM sales
            WHERE credit_sale = TRUE AND due_amount > 0
        """)
        total_due_all = cursor.fetchone()[0] or 0
        st.info(f"*Total Due Across All Customers:* Rs.{Decimal(total_due_all):,.2f}")
        
        # Payment mode selection
        st.markdown("### Choose Payment Mode")
        payment_mode = st.radio(
            "Select how you want to record payment:",
            options=["Customer-Based Payment", "Individual Sale Payment"],
            index=0,
        )
        
        st.markdown("---")
        
        if payment_mode == "Customer-Based Payment":
            # ====================
            # CUSTOMER-BASED PAYMENT MODE
            # ====================
            
            # Fetch customers with pending dues
            cursor.execute("""
                SELECT c.id, c.customer_name, SUM(s.due_amount) as total_due, COUNT(s.id) as pending_sales
                FROM sales s
                JOIN customers c ON s.customer_id = c.id
                WHERE s.credit_sale = TRUE AND s.due_amount > 0
                GROUP BY c.id, c.customer_name
                ORDER BY total_due DESC
            """)
            customers_with_dues = cursor.fetchall()
            
            if not customers_with_dues:
                st.info("✅ All credit sales are fully paid!")
            else:
                # Customer selection
                st.markdown("### Select Customer")
                customer_options = {
                    f"👤 {customer[1]} | 💰 Total Due: Rs.{customer[2]:,.2f} | 📊 {customer[3]} Pending Sales": 
                    customer[0] for customer in customers_with_dues
                }
                
                selected_customer_display = st.selectbox("Select a Customer to Record Payment", list(customer_options.keys()))
                selected_customer_id = customer_options[selected_customer_display]
                
                # Get selected customer details
                selected_customer = next(c for c in customers_with_dues if c[0] == selected_customer_id)
                customer_name = selected_customer[1]
                total_customer_due = selected_customer[2]
                
                # Show customer's pending sales breakdown
                st.markdown(f"#### Pending Sales for {customer_name}")
                cursor.execute("""
                    SELECT id, sale_date, total_price, paid_amount, due_amount
                    FROM sales
                    WHERE customer_id = %s AND credit_sale = TRUE AND due_amount > 0
                    ORDER BY sale_date ASC
                """, (selected_customer_id,))
                pending_sales = cursor.fetchall()
                # ** OLD DISPLAY***

                # # Display pending sales in a nice format
                # for sale in pending_sales:
                #     sale_id, sale_date, total_price, paid_amount, due_amount = sale
                #     st.markdown(f"🧾 **Sale ID {sale_id}** | 📅 {sale_date} | 💰 Total: Rs.{total_price:,.2f} | ✅ Paid: Rs.{paid_amount:,.2f} | ❌ Due: Rs.{due_amount:,.2f}")
    
                # st.success(f"💵 **Total Outstanding for {customer_name}:** Rs.{total_customer_due:,.2f}")
                # Styled Pending Sales Table (same look as main invoice list)
    # ================================================
                st.markdown("---")

                # Table headers
                col1, col2, col3, col4, col5 = st.columns([1, 2, 2, 2, 2])
                with col1:
                    st.markdown('##### Inv. ID')
                with col2:
                    st.markdown('##### Date')
                with col3:
                    st.markdown('##### Total Price')
                with col4:
                    st.markdown('##### Paid Amount')
                with col5:
                    st.markdown('##### Due Amount')

                st.markdown('---')

                # Check if any pending invoices exist
                if not pending_sales:
                    st.info(f"No pending invoices for {customer_name}.")
                else:
                    # Display all invoices
                    for sale in pending_sales:
                        sale_id, sale_date, total_price, paid_amount, due_amount = sale
                        status = "Paid" if due_amount == 0 else ("Partial Payment" if paid_amount > 0 else "Unpaid")

                        col1, col2, col3, col4, col5= st.columns([1, 2, 2, 2, 2])
                        with col1:
                            if due_amount:
                                st.markdown(f"###### {sale_id}")
                        with col2:
                            st.markdown(f'###### {sale_date}')
                        with col3:
                            st.markdown(f"###### Rs. {total_price:,.2f}")
                        with col4:
                            st.markdown(f"###### Rs. {paid_amount:,.2f}")
                        with col5:
                            st.markdown(f"###### Rs. {due_amount:,.2f}")
                        
                        st.markdown("---")

                # Show total outstanding
                st.success(f"💵 **Total Outstanding for {customer_name}:** Rs.{total_customer_due:,.2f}")
                # Payment input
                st.markdown(f"### 💳 Enter Payment for  {customer_name}")
                
                # Create columns for payment details
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f'##### Payment Amount - Max: Rs.{total_customer_due:,.2f}')
                    payment_amount = Decimal(st.number_input(
                        f"Payment Amount (Rs.) - Max: Rs.{total_customer_due:,.2f}", 
                        min_value=0.00, 
                        max_value=float(total_customer_due),
                        step=10.00, 
                        format="%.2f",
                        label_visibility='collapsed'
                    ))
                    full_payment = payment_amount
                
                with col2:
                    st.markdown(f'##### Payment Method')
                    payment_method = st.selectbox(
                        "💳 Payment Method",
                        options=["Cash", "Bank Transfer"],
                        index=0,
                        label_visibility='collapsed'
                    )
                
                # Payment note (optional)
                payment_note = st.text_input(
                    "📝 Payment Note (Optional)",
                    placeholder="Enter any additional notes about this payment...",
                    help="This note will appear in the customer ledger"
                )
                
                # Show payment allocation preview
                if payment_amount > 0:
                    st.markdown("### 🔍 Payment Allocation Preview")
                    remaining_payment = payment_amount
                    allocation_preview = []
                    
                    for sale in pending_sales:
                        sale_id, sale_date, total_price, paid_amount, due_amount = sale
                        if remaining_payment <= 0:
                            allocation_preview.append((sale_id, 0, due_amount, "No Payment"))
                        elif remaining_payment >= due_amount:
                            allocation_preview.append((sale_id, due_amount, 0, "✅ Fully Paid"))
                            remaining_payment -= due_amount
                        else:
                            allocation_preview.append((sale_id, remaining_payment, due_amount - remaining_payment, "⚠️ Partial Payment"))
                            remaining_payment = 0
                    
                    # Display allocation table
                    for preview in allocation_preview:
                        sale_id, payment_for_sale, remaining_due, status = preview
                        if payment_for_sale > 0:
                            st.success(f"🧾 Sale ID {sale_id}: Pay Rs.{payment_for_sale:,.2f} | Remaining Due: Rs.{remaining_due:,.2f} | {status}")
                        else:
                            st.info(f"🧾 Sale ID {sale_id}: Pay Rs.{payment_for_sale:,.2f} | Remaining Due: Rs.{remaining_due:,.2f} | {status}")
                    
                    # Show payment method info
                    st.info(f"💳 **Payment Method:** {payment_method}")
                    if payment_note:
                        st.info(f"📝 **Note:** {payment_note}")
                
                # Submit Payment button
                if st.button(" Submit Customer Payment", key="customer_payment"):
                    if payment_amount <= 0:
                        st.warning("⚠️ Please enter a valid payment amount.")
                    elif payment_amount > total_customer_due:
                        st.warning("⚠️ Payment exceeds the total due amount.")
                    else:
                        success = record_customer_payment(
                            full_payment,
                            customer_id=selected_customer_id, 
                            payment_amount=payment_amount,
                            payment_method=payment_method,
                            payment_note=payment_note if payment_note else None,
                            
                        )
                        if success:
                            st.success("✅ Payment recorded successfully!")
                            st.balloons()
                            # Refresh the page data
                            st.rerun()
                        else:
                            st.error("❌ Failed to record payment.")
                
                # Show recent payment history for this customer
                st.markdown(f"### Recent Payment History for {customer_name}")
                cursor.execute("""
                    SELECT p.amount, p.payment_date, s.id as sale_id, p.payment_method, p.payment_note
                    FROM payments p
                    JOIN sales s ON p.sale_id = s.id
                    WHERE s.customer_id = %s
                    ORDER BY p.payment_date DESC
                    LIMIT 10
                """, (selected_customer_id,))
                recent_payments = cursor.fetchall()
                
                if recent_payments:
                    df = pd.DataFrame(recent_payments, columns=["Amount (Rs.)", "Payment Date", "Sale ID", "Method", "Note"])
                    df["Payment Date"] = pd.to_datetime(df["Payment Date"]).dt.strftime("%Y-%m-%d %I:%M %p")
                    df["Note"] = df["Note"].fillna("N/A")
                    df.index = range(1, len(df)+1)
                    df.index.name = "Sr. No."
                    st.table(df)
                    
                    total_customer_payments = sum([float(p[0]) for p in recent_payments])
                    st.info(f"💵 **Recent Payments Total:** Rs.{total_customer_payments:,.2f}")
                else:
                    st.info("🕵️ No recent payments found for this customer.")
        
        else:
            # ====================
            # INDIVIDUAL SALE PAYMENT MODE
            # ====================
            
            cursor.execute("""
                SELECT s.id, c.customer_name, s.sale_date, s.total_price, s.paid_amount, s.due_amount
                FROM sales s
                JOIN customers c ON s.customer_id = c.id
                WHERE s.credit_sale = TRUE AND s.due_amount > 0
                ORDER BY s.sale_date DESC
            """)
            credit_sales = cursor.fetchall()
            
            if not credit_sales:
                st.info("✅ All credit sales are fully paid!")
            else:
                # Selection options
                st.markdown("### Select Sale ID")
                options = {
                    f"🧾 ID {s[0]} | 👤 {s[1]} | 📅 {s[2]} | 💰 Total: Rs.{s[3]:,.2f} | ✅ Paid: Rs.{s[4]:,.2f} | ❌ Due: Rs.{s[5]:,.2f}":
                    s[0] for s in credit_sales
                }
                
                selected = st.selectbox("Select a Credit Sale to Record Payment", list(options.keys()))
                selected_sale_id = options[selected]
                
                # Payment input
                st.markdown("### Enter Payment Details")
                
                # Fetch the due amount for the selected sale
                cursor.execute("SELECT due_amount FROM sales WHERE id = %s", (selected_sale_id,))
                due_amount = cursor.fetchone()[0]
                
                # Create columns for payment details
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f'##### Payment Amount - Max Due: Rs.{due_amount:,.2f}')
                    payment_amount = Decimal(st.number_input(
                        f"Payment Amount (Rs.) - Max Due: Rs.{due_amount:,.2f}", 
                        min_value=0.00, 
                        max_value=float(due_amount),
                        step=10.00, 
                        format="%.2f",
                        label_visibility='collapsed'
                    ))
                
                with col2:
                    st.markdown('##### Payment Method')
                    payment_method = st.selectbox(
                        "💳 Payment Method",
                        options=["Cash", "Bank Transfer"],
                        index=0,
                        label_visibility='collapsed'
                    )
                
                # Payment note (optional)
                payment_note = st.text_input(
                    "📝 Payment Note (Optional)",
                    placeholder="Enter any additional notes about this payment...",
                    help="This note will appear in the customer ledger"
                )
                
                # Show payment method info
                if payment_amount > 0:
                    st.info(f"💳 **Payment Method:** {payment_method}")
                    if payment_note:
                        st.info(f"📝 **Note:** {payment_note}")
                
                # Submit Payment button with validation
                if st.button(" Submit Sale Payment", key="individual_payment"):
                    if payment_amount <= 0:
                        st.warning("⚠️ Please enter a valid payment amount.")
                    elif payment_amount > due_amount:
                        st.warning("⚠️ Payment exceeds the due amount. Please enter a valid amount.")
                    else:
                        success = record_payment(
                            sale_id=selected_sale_id, 
                            amount=payment_amount,
                            payment_method=payment_method,
                            payment_note=payment_note if payment_note else None
                        )
                        if success:
                            st.success("✅ Payment recorded successfully!")
                            st.balloons()
                        else:
                            st.error("❌ Failed to record payment.")
                
                # Fetch and show updated status
                cursor.execute("SELECT paid_amount, due_amount FROM sales WHERE id = %s", (selected_sale_id,))
                updated_sale = cursor.fetchone()
                
                if updated_sale:
                    paid, due = updated_sale
                    st.markdown(f"### Updated Payment Status")
                    st.success(f"**Paid:** Rs.{paid:,.2f} &nbsp;&nbsp;&nbsp;&nbsp; **Due:** Rs.{due:,.2f}")
                
                # Fetch payment history for this specific sale
                cursor.execute("""
                    SELECT amount, payment_date, payment_method, payment_note
                    FROM payments
                    WHERE sale_id = %s
                    ORDER BY payment_date DESC
                """, (selected_sale_id,))
                payments = cursor.fetchall()
                
                if payments:
                    st.markdown("### 📜 Payment History for This Sale")
                    df = pd.DataFrame(payments, columns=["Amount (Rs.)", "Date", "Method", "Note"])
                    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d %I:%M %p")
                    df["Note"] = df["Note"].fillna("N/A")
                    df.index = range(1, len(df)+1)
                    df.index.name = "Sr. No."
                    st.table(df)
                    
                    # Show total paid summary for this sale
                    total_paid = sum([float(p[0]) for p in payments])
                    st.success(f"💵 **Total Paid for This Sale:** Rs.{total_paid:,.2f}")
                else:
                    st.info("🕵️ No payments made for this sale yet.")
        
        conn.close()

    elif sub_menu == "All Invoices":
        st.title("All Credit Sale Invoices")
        
        # Add search functionality at the top
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input("Search by Invoice ID or Customer Name")
        with col2:
            st.write("")  # For alignment
            st.write("")  # For alignment
        
        history = fetch_credit_sales_history()
        
        # Group by sale_id
        grouped_sales = {}
        for row in history:
            sale_id, product_name, quantity, sale_price, customer_name, sale_date, source, paid_amount, due_amount = row
            if sale_id not in grouped_sales:
                grouped_sales[sale_id] = {
                    "sale_id": sale_id,
                    "customer": customer_name,
                    "date": sale_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": source,
                    "paid": float(paid_amount),
                    "due": float(due_amount),
                    "items": []
                }
            grouped_sales[sale_id]["items"].append({
                "product": product_name,
                "quantity": quantity,
                "sale_price": float(sale_price),
                "total": float(quantity) * float(sale_price)
            })

        # Filter results based on search term
        if search_term:
            filtered_sales = {
                k: v for k, v in grouped_sales.items() 
                if search_term.lower() in str(k).lower() or 
                search_term.lower() in v['customer'].lower()
            }
        else:
            filtered_sales = grouped_sales

        # Display each sale in an expander
        for sale_id, sale_data in filtered_sales.items():
            with st.expander(f"Invoice #{sale_id} - {sale_data['customer']} - {sale_data['date']}"):
                st.markdown(f"**Customer:** {sale_data['customer']}")
                st.markdown(f"**Date:** {sale_data['date']}")
                st.markdown(f"**Source:** {sale_data['source']}")
                st.markdown(f"**Paid:** Rs. {sale_data['paid']:.2f}")
                st.markdown(f"**Due:** Rs. {sale_data['due']:.2f}")
                
                st.markdown("**Products:**")
                for item in sale_data["items"]:
                    st.markdown(
                        f"- {item['product']} | Qty: {item['quantity']} | "
                        f"Unit Price: Rs. {item['sale_price']:.2f} | "
                        f"Total: Rs. {item['total']:.2f}"
                    )
                
                # Payment history
                payments = fetch_payments_for_sale(sale_id)
                if payments:
                    st.markdown("**Payments Made:**")
                    for payment in payments:
                        amount = payment[0]
                        payment_date = payment[1]
                        st.write(f"- Rs. {float(amount):.2f} on {pd.to_datetime(payment_date).strftime('%Y-%m-%d %I:%M %p')}")

                
                # Add regenerate PDF button
                st.markdown("---")
                st.markdown("### Invoice PDF")
                
                # Prepare data for PDF generation
                pdf_data = {
                    "sale_id": sale_id,
                    "customer": sale_data['customer'],
                    "date": sale_data['date'],
                    "source": sale_data['source'],
                    "products": sale_data['items'],
                    "total_price": sum(item['total'] for item in sale_data['items']),
                    "paid_amount": sale_data['paid'],
                    "due_amount": sale_data['due']
                }
                
                # Generate PDF in memory
                pdf = CreditSalePDF(customer_name=pdf_data['customer'], sale_id=pdf_data['sale_id'])
                pdf.add_page()
                pdf.add_sale_details(pdf_data)
                
                # Create download button
                pdf_bytes = pdf.output(dest='S').encode('latin1')
                st.download_button(
                    label="📄 Regenerate & Download Invoice",
                    data=pdf_bytes,
                    file_name=f"Credit_Invoice_{sale_id}.pdf",
                    mime="application/pdf",
                    key=f"download_{sale_id}"  # Unique key for each button
                )
