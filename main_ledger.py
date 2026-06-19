# import streamlit as st
# import pandas as pd
# import calendar
# from datetime import datetime
# from purchase import fetch_grouped_purchase_orders
# from sales import fetch_filtered_expenses, get_filtered_sales


# def show_main_ledger():
#     st.title("📘 Main Ledger")

#     # Month selector
#     month_names = list(calendar.month_name)[1:]  # January to December
#     selected_month_name = st.selectbox("Select Month", month_names)
#     selected_month_number = month_names.index(selected_month_name) + 1
#     current_year = datetime.now().year

#     # --- Fetch & process data ---

#     # Fetch Sales
#     sales = get_filtered_sales(None, None, "Monthly", selected_month_name)
#     sales_df = pd.DataFrame(sales, columns=[
#         'sale_id', 'product_names', 'quantities', 'total_price',
#         'paid_amount', 'due_amount', 'customer_name', 'sale_date', 'source'
#     ])
#     sales_df['sale_date'] = pd.to_datetime(sales_df['sale_date']).dt.date

#     # Fetch Purchases
#     purchases = fetch_grouped_purchase_orders()
#     purchase_df = pd.DataFrame(purchases)
#     if not purchase_df.empty:
#         purchase_df['date'] = pd.to_datetime(purchase_df['date']).dt.date
#         purchase_df = purchase_df[purchase_df['date'].dt.month == selected_month_number]

#     # Fetch Expenses
#     expense_df = fetch_filtered_expenses("Monthly", selected_month_number)
#     if not expense_df.empty:
#         expense_df['expense_date'] = pd.to_datetime(expense_df['expense_date']).dt.date

#     # --- Combine per day ---
#     all_dates = pd.date_range(
#         start=f"{current_year}-{selected_month_number:02d}-01",
#         end=f"{current_year}-{selected_month_number:02d}-{calendar.monthrange(current_year, selected_month_number)[1]}"
#     ).date

#     ledger_data = []
#     for day in all_dates:
#         day_sales_total = sales_df[sales_df['sale_date'] == day]['total_price'].sum()
#         day_purchases_total = purchase_df[purchase_df['date'] == day]['total_amount'].sum() if not purchase_df.empty else 0
#         day_expenses_total = expense_df[expense_df['expense_date'] == day]['amount'].sum() if not expense_df.empty else 0
#         net_profit = day_sales_total - (day_purchases_total + day_expenses_total)

#         ledger_data.append({
#             'Date': day.strftime('%Y-%m-%d'),
#             'Total Sales': round(day_sales_total, 2),
#             'Total Purchases': round(day_purchases_total, 2),
#             'Total Expenses': round(day_expenses_total, 2),
#             'Net Profit': round(net_profit, 2)
#         })

#     ledger_df = pd.DataFrame(ledger_data)

#     # --- Display ---
#     st.subheader(f"Ledger Summary for {selected_month_name} {current_year}")
#     st.dataframe(ledger_df, use_container_width=True)

#     total_sales = ledger_df["Total Sales"].sum()
#     total_purchases = ledger_df["Total Purchases"].sum()
#     total_expenses = ledger_df["Total Expenses"].sum()
#     total_profit = ledger_df["Net Profit"].sum()

#     st.markdown("---")
#     st.markdown(f"✅ **Total Sales:** ₹{total_sales:,.2f}")
#     st.markdown(f"📦 **Total Purchases:** ₹{total_purchases:,.2f}")
#     st.markdown(f"💸 **Total Expenses:** ₹{total_expenses:,.2f}")
#     st.markdown(f"💰 **Net Profit:** ₹{total_profit:,.2f}")
