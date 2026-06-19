import os
import requests
import shopify
import streamlit as st
from utils import log_activity
from database import fetch_products, add_product, update_stock, update_price, update_image
from decimal import Decimal

# Initialize session state for credentials if not set
if "shop_url" not in st.session_state:
    st.session_state["shop_url"] = ""
if "access_token" not in st.session_state:
    st.session_state["access_token"] = ""

# # UI to enter Shopify credentials
# st.sidebar.header("Shopify Credentials")
# shop_url = st.sidebar.text_input("Shopify Shop URL", st.session_state["shop_url"])
# access_token = st.sidebar.text_input("Shopify Access Token", st.session_state["access_token"], type="password")

# # Button to save credentials
# if st.sidebar.button("Save Credentials"):
#     st.session_state["shop_url"] = shop_url
#     st.session_state["access_token"] = access_token
#     st.sidebar.success("Credentials saved successfully!")

# Setup Shopify API session
# Setup Shopify API session dynamically
def create_shopify_session():
    """Create Shopify session using credentials from session state."""
    if not st.session_state["shop_url"] or not st.session_state["access_token"]:
        st.error("Please enter Shopify credentials.")
        return None

    try:
        shop_name = st.session_state["shop_url"].split('.')[0]  # Extract shop name
        session = shopify.Session(f"https://{shop_name}.myshopify.com", "2025-01", st.session_state["access_token"])
        shopify.ShopifyResource.activate_session(session)
        return session
    except Exception as e:
        st.error(f"Error creating Shopify session: {e}")
        return None

# Set up Shopify API session (Updated method)
# Set up Shopify API session (Updated method)
def setup_shopify_api():
    """Initialize Shopify API session."""
    try:
        shop_url = st.session_state.get("shop_url", "")  # Get SHOP_URL from session state
        access_token = st.session_state.get("access_token", "")  # Get ACCESS_TOKEN from session state

        if not shop_url or not access_token:
            st.error("Shopify credentials are missing.")
            return None
        
        shop_name = shop_url.split('.')[0]  # Extract shop name from shop URL
        session = shopify.Session(f"https://{shop_name}.myshopify.com", "2025-01", access_token)
        shopify.ShopifyResource.activate_session(session)

        print("Shopify session successfully activated.")
        return session
    except Exception as e:
        print(f"Error creating Shopify session: {e}")
        st.error(f"Error creating Shopify session: {e}")
        return None


# Fetch and update products from Shopify to ERP
# Fetch and update products from Shopify to ERP
def fetch_and_update_products():
    """Fetch Shopify products and store them in the ERP inventory."""
    if not create_shopify_session():
        return "Shopify session not initialized."

    try:
        shop_products = shopify.Product.find()
        shop_products = list(shop_products) if shop_products else []
        st.success(f"Fetched {len(shop_products)} products from Shopify.")

        for product in shop_products:
            name = product.title
            price = product.variants[0].price
            stock = int(product.variants[0].inventory_quantity)
            image_url = product.image.src if product.image else None
            category = "Shopify"

            image_path = save_image(image_url, name) if image_url else None
            add_or_update_product(name, price, stock, category, image_path)

        return f"Fetched and updated {len(shop_products)} products."

    except Exception as e:
        st.error(f"Error fetching Shopify products: {e}")
        return f"Error: {e}"

# Save the product image to the static folder
def save_image(image_url, product_name):
    """Save the image from the URL to the static folder with the product name."""
    try:
        img_data = requests.get(image_url).content
        # Ensure the static folder exists
        if not os.path.exists('static'):
            os.makedirs('static')

        # Determine the image extension
        image_extension = image_url.split('.')[-1]
        if image_extension.lower() not in ['jpg', 'jpeg', 'png']:
            image_extension = 'jpg'  # Default to jpg if format is unrecognized

        # Save image with the product name and the correct extension
        image_path = f"static/{product_name.lower().replace(' ', '_')}.{image_extension}"
        with open(image_path, 'wb') as f:
            f.write(img_data)
        
        return image_path
    except Exception as e:
        print(f"Error downloading image for {product_name}: {e}")
        st.error(f"Error downloading image for {product_name}: {e}")
        return None

# Add or update a product in the ERP inventory
def add_or_update_product(name, price, stock, category, image_path):
    """Check if product exists in ERP, if not, add it. Otherwise, update stock and details."""
    existing_product = fetch_product_by_name(name)
    
    if existing_product:
        # Product exists, update stock and details
        print(f"Updating product: {name}")
        update_product(existing_product['id'], price, stock, image_path)
    else:
        # Product does not exist, add it
        print(f"Adding new product: {name}")
        add_product_in_erp(name, price, stock, category, image_path)

# In your integration script
def add_product_in_erp(name, price, stock, category, image_path):
    """Insert new product in ERP database."""
    add_product(name, price, stock, category, image_path)  # Ensure this matches the updated add_product function

# Update product details in ERP database
def update_product(product_id, price, stock, image_path):
    """Update product stock and price in ERP database."""
    update_stock(product_id, stock)
    update_price(product_id, price)
    if image_path:
        update_image(product_id, image_path)

# Fetch a product by name from ERP database
def fetch_product_by_name(name):
    """Check if the product exists in ERP by name."""
    products = fetch_products()
    for product in products:
        if product['name'] == name:
            return product
    return None

def update_shopify_inventory():
    """Update Shopify inventory and price based on ERP stock."""
    setup_shopify_api()
    
    # Get WH/Stock location ID
    location_id = get_location_id("WH/Stock")  # Ensure you use the exact name from Shopify
    if not location_id:
        st.error("Could not find WH/Stock location in Shopify.")
        return
    
    erp_products = fetch_products()  # Get products from ERP
    for product in erp_products:
        shop_product = find_shopify_product_by_name(product['name'])
        if shop_product:
            shop_variant = shop_product.variants[0]  # Assuming there's only one variant
            try:
                # Update the inventory at the correct location
                inventory_item_id = shop_variant.inventory_item_id
                update_inventory_level(inventory_item_id, location_id, product['stock'])
                print(f"Updated Shopify inventory for {product['name']} to {product['stock']} at WH/Stock.")
                
                # Update the price on Shopify
                variant_id = shop_variant.id  # Get variant ID
                update_shopify_price(variant_id, product['price'])  # Update price
                
            except Exception as e:
                print(f"Error updating Shopify inventory for {product['name']}: {e}")
                st.error(f"Error updating Shopify inventory for {product['name']}: {e}")

def update_inventory_level(inventory_item_id, location_id, available_quantity):
    """Update the inventory level for a specific item at a specific location."""
    setup_shopify_api()
    try:
        inventory_level = shopify.InventoryLevel.set(
            inventory_item_id=inventory_item_id,
            location_id=location_id,
            available=available_quantity
        )
        return inventory_level
    except Exception as e:
        print(f"Error updating inventory level: {e}")
        st.error(f"Error updating inventory level: {e}")

from decimal import Decimal
import shopify

def update_shopify_price(variant_id, new_price):
    """Update the price of a Shopify variant."""
    setup_shopify_api()  # Ensure Shopify API is set up
    
    try:
        print(f"Fetching variant with ID: {variant_id}")
        variant = shopify.Variant.find(variant_id)  # Fetch variant using ID
        
        if variant:
            print(f"Fetched variant: {variant}")

            # Convert to Decimal to avoid ArrowTypeError
            variant.price = float(new_price)  # ✅ Convert Decimal to float before assigning
            variant.save()  # Remove force=True
            
            message = f"✅ Updated price for variant {variant_id} to {new_price}."
        else:
            message = f"❌ Variant not found for ID {variant_id}."
    
    except Exception as e:
        message = f"❌ Error updating price: {e}"
    
    print(message)
    return message  # Ensure the function always returns a message


def get_location_id(location_name):
    """Fetch the Shopify location ID by name."""
    setup_shopify_api()
    try:
        locations = shopify.Location.find()
        for location in locations:
            if location.name == location_name:
                return location.id
    except Exception as e:
        print(f"Error fetching Shopify locations: {e}")
        st.error(f"Error fetching Shopify locations: {e}")
    return None



# Find a product in Shopify by name
def find_shopify_product_by_name(name):
    """Search for a product in Shopify by its name."""
    setup_shopify_api()
    try:
        products = shopify.Product.find(title=name)
        if products:
            return products[0]  # Return the first match
        return None
    except Exception as e:
        print(f"Error fetching Shopify product by name: {e}")
        st.error(f"Error fetching Shopify product by name: {e}")
        return None

# Streamlit Interface for Shopify sync buttons
def shopify_module():
    st.sidebar.title("PBS ERP")
    st.title("Shopify Integration")
            # Initialize Shopify credentials in session state
    if "shop_url" not in st.session_state:
        st.session_state.shop_url = ""
    if "access_token" not in st.session_state:
        st.session_state.access_token = ""
    if "shopify_credentials_saved" not in st.session_state:
        st.session_state.shopify_credentials_saved = False
    
    # If credentials are not saved, show input fields
    if not st.session_state.shopify_credentials_saved:
        st.subheader("Enter Shopify Credentials")
        c1,c2 = st.columns(2)
        with c1:
            shop_url = st.text_input("Shopify Shop URL",value=st.session_state.shop_url)
        with c2:
            access_token = st.text_input("Shopify Access Token", type="password",value=st.session_state.access_token)
        
        if st.button("Save Credentials"):
            st.session_state.shop_url = shop_url
            st.session_state.access_token = access_token
            st.session_state.shopify_credentials_saved = True
            st.success("Credentials saved successfully!")
            st.rerun()
    
    # Show sync buttons only if credentials are saved
    if st.session_state.shopify_credentials_saved:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Sync from Shopify"):
                try:
                    result = fetch_and_update_products()
                    st.success(result)
                    log_activity("Synced products from Shopify")
                except Exception as e:
                    st.error(f"Error syncing from Shopify: {str(e)}")
        
        with col2:
            if st.button("📤 Sync to Shopify"):
                try:
                    result = update_shopify_inventory()
                    st.success(result)
                    log_activity("Synced inventory to Shopify")
                except Exception as e:
                    st.error(f"Error syncing to Shopify: {str(e)}")
    
    # Create a column for the Shopify module
    col5 = st.columns(1)[0]
