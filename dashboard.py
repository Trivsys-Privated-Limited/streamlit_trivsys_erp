import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import *  # Fetch data from DB
from decimal import Decimal

# Function to process sales and purchase records
def get_total_credit_due():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(due_amount)
        FROM sales
        WHERE credit_sale = TRUE AND due_amount > 0
    """)
    total_due = cursor.fetchone()[0] or 0
    conn.close()
    return total_due

def process_records(records, date_column):
    if not records:
        return pd.DataFrame()  # Return empty DataFrame if no records found

    df = pd.DataFrame(records)

    # Ensure the date column exists before conversion
    if date_column not in df.columns:
        print(f"⚠ Warning: {date_column} column missing in data!")
        return pd.DataFrame()  # Return empty DataFrame

    df[date_column] = pd.to_datetime(df[date_column])  # Convert to datetime
    df['Day'] = df[date_column].dt.date
    df['Week'] = df[date_column].dt.to_period('W').astype(str)
    df['Month'] = df[date_column].dt.to_period('M').astype(str)

    # Ensure 'total_amount' exists and convert Decimal to float
    if 'total_amount' in df.columns:
        df['total_amount'] = df['total_amount'].apply(lambda x: float(x) if isinstance(x, Decimal) else x)

    return df

def insert_purchase_record(product_id, vendor_id, quantity, cost_price):
    """
    Inserts a purchase record into the database using cost price and updates stock.
    """
    total_cost = cost_price * quantity  # Purchase recorded using cost price
    query = """
        INSERT INTO purchases (product_id, vendor_id, quantity, cost_price, total_amount, purchase_date)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """
    values = (product_id, vendor_id, quantity, cost_price, total_cost)
    execute_query(query, values)

    # Update stock quantity in the products table
    update_stock_query = "UPDATE products SET stock = stock + %s WHERE id = %s"
    execute_query(update_stock_query, (quantity, product_id))

def show_purchase_module():
    st.title("🛒 Purchase Products")

    products = fetch_products()
    vendors = fetch_vendors()

    if not products:
        st.warning("No products available for purchase.")
        return

    if not vendors:
        st.warning("No vendors available.")
        return

    product_names = [f"{p['name']} (Stock: {p['stock']})" for p in products]
    selected_product = st.selectbox("Select Product", product_names, index=0)

    product = next((p for p in products if f"{p['name']} (Stock: {p['stock']})" == selected_product), None)

    if product:
        st.write(f"**Current Stock:** {product['stock']}")
        st.write(f"**Cost Price:** Rs. {product['cost_price']:.2f}")

        vendor_names = [v["name"] for v in vendors]
        selected_vendor = st.selectbox("Select Vendor", vendor_names)

        vendor = next((v for v in vendors if v["name"] == selected_vendor), None)

        quantity = st.number_input("Enter Quantity", min_value=1, step=1, value=1)

        if st.button("Confirm Purchase"):
            if vendor:
                insert_purchase_record(product["id"], vendor["id"], quantity, product["cost_price"])
                st.success(f"✅ Purchased {quantity} units of {product['name']} at Rs. {product['cost_price']} per unit.")
                st.rerun()

def save_tenant_logo(uploaded_file):
    # Save uploaded logo directly into existing static folder
    save_path = os.path.join("static", "tenant_logo.png")

    # Open and save image
    image = Image.open(uploaded_file)
    image.save(save_path)

    st.success("✅ Tenant logo uploaded successfully!")
    return save_path

def show_dashboard():
    # if st.button("← Back to Home", type="secondary"):
    #     st.session_state.page = "Home"
    #     st.rerun()
    

    # Fetch all data
    sales_records = fetch_sales_records()
    purchase_records = fetch_purchase_records()
    expense_records = fetch_expense_records()
    total_credit_due = get_total_credit_due()

    # Process records
    sales_df = process_records(sales_records, 'sale_date')
    purchase_df = process_records(purchase_records, 'purchase_date')

    # Process expense records
    expense_df = pd.DataFrame(expense_records)
    if 'expense_date' in expense_df.columns:
        expense_df['expense_date'] = pd.to_datetime(expense_df['expense_date'])
        expense_df['Day'] = expense_df['expense_date'].dt.date
        expense_df['Week'] = expense_df['expense_date'].dt.to_period('W').astype(str)
        expense_df['Month'] = expense_df['expense_date'].dt.to_period('M').astype(str)

        if 'amount' in expense_df.columns:
            expense_df['amount'] = expense_df['amount'].apply(lambda x: Decimal(x) if isinstance(x, Decimal) else Decimal(x))

    # Filter Section
    st.markdown("### Filter & Analysis")
    col_filter1, col_filter2 = st.columns([1, 1])
    
    with col_filter1:
        filter_option = st.selectbox(" Select Time Period:", ["Today", "Week", "Month", "Last 30 Days"])
    
    with col_filter2:
        if filter_option == "Month":
            selected_month = st.selectbox("Select Month:", range(1, 13), 
                                        format_func=lambda x: pd.Timestamp(year=pd.Timestamp.today().year, month=x, day=1).strftime('%B'))

    # Apply filters
    today_date = pd.Timestamp.today().normalize()
    start_of_week = pd.Timestamp.today() - pd.Timedelta(days=pd.Timestamp.today().weekday())
    start_of_week = start_of_week.normalize()
    end_of_week = start_of_week + pd.Timedelta(days=6)
    date_30_days_ago = pd.Timestamp.today() - pd.Timedelta(days=30)

    # Initialize filtered data
    sales_filtered = pd.DataFrame()
    purchases_filtered = pd.DataFrame()
    expense_filtered = pd.DataFrame()

    # Apply filtering logic
    if filter_option == "Today":
        if not sales_df.empty:
            sales_filtered = sales_df[sales_df['sale_date'].dt.normalize() == today_date]
        if not purchase_df.empty:
            purchases_filtered = purchase_df[purchase_df['purchase_date'].dt.normalize() == today_date]
        if not expense_df.empty:
            expense_filtered = expense_df[expense_df['expense_date'].dt.normalize() == today_date]
    elif filter_option == "Week":
        if not sales_df.empty:
            sales_filtered = sales_df[(sales_df['sale_date'] >= start_of_week) & (sales_df['sale_date'] <= end_of_week)]
        if not purchase_df.empty:
            purchases_filtered = purchase_df[(purchase_df['purchase_date'] >= start_of_week) & (purchase_df['purchase_date'] <= end_of_week)]
        if not expense_df.empty:
            expense_filtered = expense_df[(expense_df['expense_date'] >= start_of_week) & (expense_df['expense_date'] <= end_of_week)]
    elif filter_option == "Month":
        selected_year = today_date.year
        if not sales_df.empty:
            sales_filtered = sales_df[(sales_df['sale_date'].dt.month == selected_month) & (sales_df['sale_date'].dt.year == selected_year)]
        if not purchase_df.empty:
            purchases_filtered = purchase_df[(purchase_df['purchase_date'].dt.month == selected_month) & (purchase_df['purchase_date'].dt.year == selected_year)]
        if not expense_df.empty:
            expense_filtered = expense_df[(expense_df['expense_date'].dt.month == selected_month) & (expense_df['expense_date'].dt.year == selected_year)]
    elif filter_option == "Last 30 Days":
        if not sales_df.empty:
            sales_filtered = sales_df[sales_df['sale_date'] >= date_30_days_ago]
        if not purchase_df.empty:
            purchases_filtered = purchase_df[purchase_df['purchase_date'] >= date_30_days_ago]
        if not expense_df.empty:
            expense_filtered = expense_df[expense_df['expense_date'] >= date_30_days_ago]

    # Calculate metrics
    gross_sales = Decimal(sales_filtered['total_price'].sum() if not sales_filtered.empty else 0)
    total_purchases = Decimal(purchases_filtered['total_amount'].sum() if not purchases_filtered.empty else 0)
    total_expenses = Decimal(expense_filtered['amount'].sum() if not expense_filtered.empty else 0)

    # Handle returns
    try:
        returned_items = fetch_returns_from_returns_table()
        total_returned_amount = Decimal('0.0')
        
        if returned_items:
            df_returned = pd.DataFrame(returned_items)
            if 'return_amount' in df_returned.columns and 'return_date' in df_returned.columns:
                df_returned['return_date'] = pd.to_datetime(df_returned['return_date'])
                if filter_option == "Today":
                    df_returned = df_returned[df_returned['return_date'].dt.normalize() == today_date]
                elif filter_option == "Week":
                    df_returned = df_returned[
                        (df_returned['return_date'] >= start_of_week) & 
                        (df_returned['return_date'] <= end_of_week)
                    ]
                elif filter_option == "Month":
                    df_returned = df_returned[
                        (df_returned['return_date'].dt.month == selected_month) &
                        (df_returned['return_date'].dt.year == selected_year)
                    ]
                elif filter_option == "Last 30 Days":
                    df_returned = df_returned[df_returned['return_date'] >= date_30_days_ago]
                
                total_returned_amount = Decimal(df_returned['return_amount'].sum())
    except Exception as e:
        st.error(f"Error fetching returned items: {e}")
        total_returned_amount = Decimal('0.0')

    # Calculate final metrics
    net_sales = gross_sales - total_returned_amount
    if "products" not in st.session_state:
        from database import get_all_products
        st.session_state.products = get_all_products()

    total_inventory_valuation = sum(
        Decimal(str(product["cost_price"])) * Decimal(str(product["stock"]))
        for product in st.session_state.products
    )
    net_profit = net_sales - total_purchases - total_expenses
    cash_in_hand = max(Decimal('0.0'), net_profit - Decimal(total_credit_due))

    # Card styling
    def create_metric_card(icon, label, value, note, color="#FFFFFF", value_color="#23AA01"):
        return f"""
        <div class='metric-card' style='
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.12);
            border: 1px solid rgba(255,255,255,0.2);
            text-align: left;
            margin-bottom: 1rem;
        '>
            <div style='display: flex; align-items: center; margin-bottom: 10px;'>
                <span style='font-size: 24px; margin-right: 12px;'>{icon}</span>
                <strong style='font-size: 18px; color: #2c3e50;'>{label}</strong>
            </div>
            <div style='font-size: 28px; font-weight: bold; color: {value_color}; margin: 10px 0;'>
                {value}
            </div>
            <div style='font-size: 14px; color: #6c757d; font-style: italic;'>
                {note}
            </div>
        </div>
        """
    
    st.markdown("""
        <style>
        .metric-card {
            background-color: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.12);
            border: 1px solid rgba(255,255,255,0.2);
            margin-bottom: 1rem;
            text-align: left;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Row 1
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(create_metric_card(
            "", "Gross Sales", f"Rs {gross_sales:,.0f}", 
            "Total revenue generated", "#308320"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_metric_card(
            "", "Returns", f"Rs {total_returned_amount:,.0f}", 
            "Amount returned", "#C7CEEA", "#D32F2F"
        ), unsafe_allow_html=True)
    
    with col3:
        st.markdown(create_metric_card(
            "", "Purchases", f"Rs {total_purchases:,.0f}", 
            "Total procurement cost", "#C7CEEA", "#FF8C00"
        ), unsafe_allow_html=True)
    
    with col4:
        st.markdown(create_metric_card(
            "", "Expenses", f"Rs {total_expenses:,.0f}", 
            "Operational expenses", "#C7CEEA", "#4B0082"
        ), unsafe_allow_html=True)

    # Row 2
    col5, col6, col7, col8 = st.columns(4)
    
    # with col5:
    #     profit_color = "#C7CEEA" if net_profit >= 0 else "#FFB3BA"
    #     profit_text_color = "#007E33" if net_profit >= 0 else "#D32F2F"
    #     profit_icon = "📈" if net_profit >= 0 else "📉"
        
    #     st.markdown(create_metric_card(
    #         profit_icon, "Net Profit", f"Rs {net_profit:,.0f}", 
    #         "After all deductions", profit_color, profit_text_color
    #     ), unsafe_allow_html=True)
    
    with col5:
        st.markdown(create_metric_card(
            "", "Credit Due", f"Rs {total_credit_due:,.0f}", 
            "Outstanding receivables", "#C7CEEA", "#D2691E"
        ), unsafe_allow_html=True)
    
    # with col7:
    #     st.markdown(create_metric_card(
    #         "💵", "Cash in Hand", f"Rs {cash_in_hand:,.0f}", 
    #         "Available liquid funds", "#C7CEEA", "#228B22"
    #     ), unsafe_allow_html=True)
    
    # with col8:
    #     st.markdown(create_metric_card(
    #         "📦", "Inventory Value", f"Rs {total_inventory_valuation:,.0f}", 
    #         "Total stock valuation", "#C7CEEA", "#8B008B"
    #     ), unsafe_allow_html=True)

    # Summary Section
    st.markdown("---")
    st.markdown("### Period Summary")
    
    with open('static/card.css') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        card_html = f'''
        <div class="myCard">
        <div class="innerCard">
            <div class="frontSide">
            <h4 class="title">Period : {filter_option}</h4>
            <h4>Gross Revenue : Rs {gross_sales:,.0f}</h4>
            <h4>NET Revenue : Rs {net_sales:,.0f}</h4>
            <h4>Profit Margin : {(float(net_profit)/float(gross_sales)*100) if gross_sales > 0 else 0:.1f}%</h4>
            </div>
        <div class="backSide">
          <h4 class="title">Return Rate:</strong> {(float(total_returned_amount)/float(gross_sales)*100) if gross_sales > 0 else 0:.1f}%</h4>
          <h4>Expense Ratio:</strong> {(float(total_expenses)/float(gross_sales)*100) if gross_sales > 0 else 0:.1f}%</h4>
          <h4>Inventory Turnover:</strong> {(float(gross_sales)/float(total_inventory_valuation)) if total_inventory_valuation > 0 else 0:.2f}x</h4>
          <h4>Credit Outstanding:</strong> Rs {total_credit_due:,.0f}</h4>
        </div>
      </div>
    </div>
'''
    st.markdown(card_html, unsafe_allow_html=True)
        
    # Charts Section
    st.markdown("---")
    st.markdown("### VISUAL REPRESENTATIONS ")
    
    chart_col1, chart_col2 = st.columns([1, 1])
    
    with chart_col1:
        # Financial Breakdown Pie Chart
        labels = ["Net Sales", "Purchases", "Expenses", "Returns"]
        values = [float(net_sales), float(total_purchases), float(total_expenses), float(total_returned_amount)]
        colors = ["#36A2EB", "#FF6384", "#FFCE56", "#FF9F40"]

        fig_pie = go.Figure(data=[go.Pie(
            labels=labels, 
            values=values, 
            marker=dict(colors=colors, line=dict(color='#FFFFFF', width=2)),
            hole=0.4,
            textinfo='label+percent',
            textfont=dict(size=12)
        )])
        
        fig_pie.update_layout(
            title=dict(text="Financial Breakdown", font=dict(size=16, color='#2c3e50')),
            showlegend=True,
            height=400,
            margin=dict(t=50, b=50, l=50, r=50),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with chart_col2:
        # Performance Metrics Bar Chart
        metrics = ["Sales", "Purchases", "Expenses", "Profit"]
        metric_values = [float(gross_sales), float(total_purchases), float(total_expenses), float(net_profit)]
        bar_colors = ["#28a745", "#ffc107", "#dc3545", "#007bff" if net_profit >= 0 else "#dc3545"]
        
        fig_bar = go.Figure(data=[go.Bar(
            x=metrics,
            y=metric_values,
            marker=dict(color=bar_colors),
            text=[f"Rs {v:,.0f}" for v in metric_values],
            textposition='auto'
        )])
        
        fig_bar.update_layout(
            title=dict(text="Performance Overview", font=dict(size=16, color='#2c3e50')),
            xaxis=dict(title="Metrics"),
            yaxis=dict(title="Amount (Rs)"),
            height=400,
            margin=dict(t=50, b=50, l=50, r=50),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig_bar, use_container_width=True)
    # st.title("Upload Tenant Logo")
    # uploaded_logo = st.file_uploader("Choose a logo image", type=["png", "jpg", "jpeg"])
    # if uploaded_logo is not None:
    #     file_path = save_tenant_logo(uploaded_logo)
    #     st.image(file_path, caption="Uploaded Logo Preview", use_container_width=False, width=150)


    # Sales Data Display
    # Sales Data Display
    # if not sales_df.empty:
    #     st.header("📜 Sales History")
    #     st.write("Here is the list of all past sales.")

    #     # Add "All Time" filter to the date filter options
    #     date_filter = st.radio("Filter by", ["All Time", "Daily", "Weekly", "Last 30 Days", "Monthly"], index=0)

    #     # Show Month dropdown only if "Monthly" filter is selected
    #     selected_month = None
    #     if date_filter == "Monthly":
    #         months = list(calendar.month_name)[1:]  # List of months from January to December
    #         selected_month = st.selectbox("Select a Month", months)

    #     # Get product and customer search inputs
    #     product_search = st.text_input("Search by Product")
    #     customer_search = st.text_input("Search by Customer")

    #     # Call the updated function with the selected filters
    #     sales = get_filtered_sales(product_search, customer_search, date_filter, selected_month)

    #     if not sales:
    #         st.warning("No sales records found.")
    #     else:
    #         # Convert sales data to DataFrame
    #         sales_df = pd.DataFrame(sales, columns=["ID", "PRODUCTS", "QUANTITIES", "TOTAL PRICE", "PAID AMOUNT", "DUE AMOUNT", "CUSTOMER", "DATE", "SOURCE"])

    #         # Ensure 'TOTAL PRICE' is numeric for correct calculations
    #         if 'TOTAL PRICE' in sales_df.columns:
    #             sales_df['TOTAL PRICE'] = sales_df['TOTAL PRICE'].astype(float)

    #         # Display total sales at the top
    #         total_sales = sales_df['TOTAL PRICE'].sum() if 'TOTAL PRICE' in sales_df.columns else 0
    #         st.markdown(f"### Total Sales: **Rs.{total_sales:,.2f}**")

    #         # Display sales data in table format
    #         if date_filter == "Today":
    #             today_date = pd.Timestamp.today().normalize()
    #             sales_df = sales_df[sales_df['DATE'] == today_date.strftime('%Y-%m-%d')]
    #         sales_df['DATE'] = sales_df['DATE'].dt.strftime('%d-%m-%Y')  # Format the date column
            
    #         if not sales_df.empty:
    #             st.table(sales_df)
    #         else:
    #             st.write("No sales for today.")




    #     # Purchase Data Display

    # # Purchase History Display with st.table
    # if not purchase_df.empty:
    #     st.header("📜 Purchase History")
    #     st.write("Here is the summary of all past purchases.")

    #     # Ensure datetime format
    #     purchase_df['purchase_date'] = pd.to_datetime(purchase_df['purchase_date'], errors='coerce')
    #     purchase_df['Day'] = purchase_df['purchase_date'].dt.date
    #     purchase_df['Month'] = purchase_df['purchase_date'].dt.strftime('%Y-%B')

    #     # Filter Option
    #     filter_option = st.selectbox("Filter Purchases By:", ["Today", "Day", "Week", "Month"])

    #     if filter_option == "Today":
    #         today = pd.Timestamp.today().date()
    #         today_data = purchase_df[purchase_df['Day'] == today]

    #         total_today = today_data["total_amount"].sum()
    #         st.write(f"🗓️ **Total Purchases Today ({today.strftime('%d-%m-%Y')}): Rs. {total_today:.2f}**")

    #         if not today_data.empty:
    #             display_df = today_data[["purchase_date", "vendor_name", "product_name", "quantity", "cost_price", "total_amount"]].copy()
    #             display_df.columns = ["Date", "Vendor", "Product", "Qty", "Cost Price", "Total Amount"]
    #             display_df["Cost Price"] = display_df["Cost Price"].apply(lambda x: f"Rs. {x:.2f}")
    #             display_df["Total Amount"] = display_df["Total Amount"].apply(lambda x: f"Rs. {x:.2f}")
    #             st.table(display_df)

    #     elif filter_option == "Day":
    #         day_summary = purchase_df.groupby("Day")["total_amount"].sum().reset_index()
    #         day_summary.columns = ["Date", "Total Amount"]
    #         total_day = day_summary["Total Amount"].sum()
    #         day_summary["Total Amount"] = day_summary["Total Amount"].apply(lambda x: f"Rs. {x:.2f}")
    #         st.write(f"📅 **Total Purchases by Day: Rs. {total_day:.2f}**")
    #         st.table(day_summary)

    #     elif filter_option == "Week":
    #         today = pd.Timestamp.today().normalize()
    #         start_of_week = today - pd.Timedelta(days=today.weekday())
    #         end_of_week = start_of_week + pd.Timedelta(days=6)

    #         week_data = purchase_df[
    #             (purchase_df['purchase_date'] >= start_of_week) &
    #             (purchase_df['purchase_date'] <= end_of_week)
    #         ]
    #         week_summary = week_data.groupby("Day")["total_amount"].sum().reset_index()
    #         week_summary.columns = ["Date", "Total Amount"]
    #         total_week = week_summary["Total Amount"].sum()
    #         week_summary["Total Amount"] = week_summary["Total Amount"].apply(lambda x: f"Rs. {x:.2f}")
    #         st.write(f"📆 **This Week's Purchases ({start_of_week.strftime('%d-%m-%Y')} to {end_of_week.strftime('%d-%m-%Y')}): Rs. {total_week:.2f}**")
    #         st.table(week_summary)

    #     elif filter_option == "Month":
    #         month_summary = purchase_df.groupby("Month")["total_amount"].sum().reset_index()
    #         month_summary.columns = ["Month", "Total Amount"]
    #         total_month = month_summary["Total Amount"].sum()
    #         month_summary["Total Amount"] = month_summary["Total Amount"].apply(lambda x: f"Rs. {x:.2f}")
    #         st.write(f"🗓️ **Total Purchases by Month: Rs. {total_month:.2f}**")
    #         st.table(month_summary)

    #     else:
    #         st.warning("Please select a valid filter option.")
