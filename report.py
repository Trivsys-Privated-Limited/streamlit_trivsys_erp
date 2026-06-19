from datetime import datetime
import os
import time
import pdfkit
import streamlit as st
from PIL import Image
import base64

# Function to encode the logo image
def get_image_base64(path):
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def generate_receipt(cart_items, total, amount_paid):
    print(f"DEBUG: Amount Paid Received = {amount_paid}")  # Debug print
    # Format the current time in 12-hour format
    current_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

    # Calculate balance to return
    balance_to_return = max(amount_paid - total, 0)  # Prevent negative balance

    # Get logo (assuming it's in static folder)
    logo_path = os.path.join("static", "order_management.jpg")  # Change to .jpg if needed
    logo_base64 = get_image_base64(logo_path) if os.path.exists(logo_path) else None

    # Define the HTML receipt structure with blue theme
    receipt_html = f"""
    <html>
    <head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f0f8ff;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .receipt {{
            background-color: #ffffff;
            padding: 25px;
            border-radius: 8px;
            width: 80mm;  /* Standard receipt width */
            margin: 20px auto;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            border-top: 5px solid #1e90ff;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 15px;
        }}
        .logo img {{
            max-width: 120px;
            max-height: 80px;
        }}
        .receipt h1 {{
            color: #1e90ff;
            font-size: 22px;
            margin: 10px 0;
            text-align: center;
            font-weight: bold;
        }}
        .receipt .store-info {{
            text-align: center;
            margin-bottom: 15px;
            font-size: 12px;
            color: #555;
        }}
        .receipt .transaction-info {{
            font-size: 12px;
            margin-bottom: 15px;
            color: #555;
            border-bottom: 1px dashed #ddd;
            padding-bottom: 10px;
        }}
        .receipt table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }}
        .receipt table th {{
            background-color: #e6f2ff;
            color: #1e90ff;
            padding: 6px;
            text-align: left;
            font-size: 12px;
            border-bottom: 1px solid #1e90ff;
        }}
        .receipt table td {{
            padding: 6px;
            text-align: left;
            font-size: 12px;
            border-bottom: 1px solid #eee;
        }}
        .receipt .totals {{
            margin-top: 15px;
            border-top: 1px dashed #ddd;
            padding-top: 10px;
        }}
        .receipt .total-row {{
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
            font-size: 13px;
        }}
        .receipt .total-label {{
            font-weight: bold;
            color: #1e90ff;
        }}
        .receipt .total-value {{
            font-weight: bold;
        }}
        .receipt .balance {{
            color: #4CAF50;
        }}
        .receipt .footer {{
            margin-top: 20px;
            text-align: center;
            font-size: 11px;
            color: #777;
            border-top: 1px dashed #ddd;
            padding-top: 10px;
        }}
    </style>
    </head>
    <body>
    <div class="receipt">
        <div class="logo">
            {"<img src='data:image/png;base64," + logo_base64 + "' alt='Store Logo'>" if logo_base64 else ""}
        </div>
        <h1>HF DESIGN</h1>
        <div class="store-info">
            <p>123 Main Street, City Center</p>
            <p>Phone: +92 300 1234567</p>
        </div>
        <div class="transaction-info">
            <p><strong>Date:</strong> {current_time}</p>
            <p><strong>Invoice #:</strong> {int(time.time())}</p>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Item</th>
                    <th>Qty</th>
                    <th>Price</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Loop through cart items and add them to the receipt
    for item in cart_items:
        receipt_html += f"""
            <tr>
                <td>{item["name"]}</td>
                <td>{item["quantity"]}</td>
                <td>Rs.{item["price"]:.2f}</td>
                <td>Rs.{item["price"] * item["quantity"]:.2f}</td>
            </tr>
        """
    
    # Adding totals section
    receipt_html += f"""
            </tbody>
        </table>
        <div class="totals">
            <div class="total-row">
                <span class="total-label">Subtotal:</span>
                <span class="total-value">Rs.{total:.2f}</span>
            </div>
            <div class="total-row">
                <span class="total-label">Amount Paid:</span>
                <span class="total-value">Rs.{amount_paid:.2f}</span>
            </div>
            <div class="total-row">
                <span class="total-label">Balance:</span>
                <span class="total-value balance">Rs.{balance_to_return:.2f}</span>
            </div>
        </div>
        <div class="footer">
            <p>Thank you for shopping with us!</p>
            <p>www.mangosuperstore.com</p>
            <p>Returns within 7 days with receipt</p>
        </div>
    </div>
    </body>
    </html>
    """

    return receipt_html


def save_receipt_as_pdf(html_content):
    if not html_content:
        return ""
    
    # Define the receipts directory and ensure it exists
    receipt_dir = "receipts"
    if not os.path.exists(receipt_dir):
        os.makedirs(receipt_dir)

    # Generate a unique filename using timestamp
    timestamp = int(time.time())
    pdf_file_path = os.path.join(receipt_dir, f"receipt_{timestamp}.pdf")
    
    try:
        # Options for PDF generation
        # Fixed: Using a standard page size instead of custom '80mm' value
        options = {
            'page-size': 'A6',  # Using A6 which is closest to receipt size
            'margin-top': '5mm',
            'margin-right': '5mm',
            'margin-bottom': '5mm',
            'margin-left': '5mm',
            'encoding': "UTF-8",
            'quiet': '',
            # Optional - use custom width and height instead of standard page size
            'page-width': '80mm',
            'page-height': '200mm'  # Adjust height as needed
        }
        
        # Generate and save the PDF at the specified path
        pdfkit.from_string(html_content, pdf_file_path, options=options)
        print(f"PDF saved to: {pdf_file_path}")  # Log for debugging
        return pdf_file_path
    except Exception as e:
        print(f"Error saving PDF: {e}")
        # Fall back to HTML if PDF generation fails
        fallback_html_path = os.path.join(receipt_dir, f"receipt_{timestamp}.html")
        with open(fallback_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Fallback HTML saved to: {fallback_html_path}")
        return fallback_html_path

def main():
    st.title("Mango Super Store - Checkout")

    # Simulate adding items to cart
    if "cart" not in st.session_state:
        st.session_state.cart = []
    
    # Add products to the cart dynamically
    col1, col2, col3 = st.columns(3)
    with col1:
        product_name = st.text_input("Product Name")
    with col2:
        product_quantity = st.number_input("Quantity", min_value=1, step=1, value=1)
    with col3:
        product_price = st.number_input("Price (Rs.)", min_value=0.01, step=0.01, value=0.0)

    if st.button("➕ Add Product to Cart"):
        if product_name and product_quantity > 0 and product_price > 0:
            st.session_state.cart.append({
                "name": product_name,
                "quantity": product_quantity,
                "price": product_price
            })
            st.success(f"Added {product_quantity} x {product_name} to cart!")
    
    # Display the current cart in a more organized way
    if st.session_state.cart:
        st.subheader("Current Order")
        cart_table = "<table style='width:100%; border-collapse: collapse;'>"
        cart_table += """
        <tr style='background-color: #e6f2ff; color: #1e90ff;'>
            <th style='padding: 8px; text-align: left;'>Item</th>
            <th style='padding: 8px; text-align: right;'>Qty</th>
            <th style='padding: 8px; text-align: right;'>Price</th>
            <th style='padding: 8px; text-align: right;'>Total</th>
        </tr>
        """
        
        for item in st.session_state.cart:
            cart_table += f"""
            <tr style='border-bottom: 1px solid #eee;'>
                <td style='padding: 8px;'>{item['name']}</td>
                <td style='padding: 8px; text-align: right;'>{item['quantity']}</td>
                <td style='padding: 8px; text-align: right;'>Rs.{item['price']:.2f}</td>
                <td style='padding: 8px; text-align: right;'>Rs.{item['price'] * item['quantity']:.2f}</td>
            </tr>
            """
        
        cart_table += "</table>"
        st.markdown(cart_table, unsafe_allow_html=True)

    # Calculate subtotal
    subtotal = sum(item["quantity"] * item["price"] for item in st.session_state.cart)
    
    st.markdown(f"**Subtotal:** Rs.{subtotal:.2f}", unsafe_allow_html=True)

    if "amount_paid" not in st.session_state:
        st.session_state.amount_paid = 0.0

    # Let the user input amount paid
    st.session_state.amount_paid = st.number_input(
        "Amount Paid (Rs.):", 
        min_value=0.0, 
        value=float(round(subtotal)), 
        step=10.0,
        format="%.2f"
    )

    # Clear cart button
    if st.session_state.cart and st.button("🗑️ Clear Cart"):
        st.session_state.cart = []
        st.success("Cart cleared successfully!")
        st.rerun()

    if st.session_state.cart and st.button("🖨️ Generate Receipt", type="primary"):
        if st.session_state.amount_paid < subtotal:
            st.warning("Amount paid is less than the total. Customer still owes Rs.{:.2f}".format(subtotal - st.session_state.amount_paid))
        
        # Generate the HTML content using cart items, subtotal, and amount paid
        html_content = generate_receipt(st.session_state.cart, subtotal, st.session_state.amount_paid)
        
        # Save the receipt as a PDF
        receipt_file = save_receipt_as_pdf(html_content)
        
        if receipt_file:
            file_ext = os.path.splitext(receipt_file)[1].lower()
            mime_type = "application/pdf" if file_ext == ".pdf" else "text/html"
            file_name = f"MangoReceipt_{int(time.time())}{file_ext}"
            
            with open(receipt_file, "rb") as f:
                st.download_button(
                    "📥 Download Receipt", 
                    f, 
                    file_name=file_name, 
                    mime=mime_type
                )
            
            # Show a preview of the receipt
            st.success("Receipt generated successfully!")
            st.markdown("### Receipt Preview")
            st.components.v1.html(html_content, height=600, scrolling=True)
            
            os.remove(receipt_file)  # Cleanup the temp file after download
        else:
            st.error("Failed to generate receipt.")

if __name__ == "__main__":
    main()