import psycopg2
import mysql.connector

# Odoo PostgreSQL connection details
ODOO_DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'odoo_db',  # Updated with your real database name
    'user': 'admin',     # Updated with your real username
    'password': 'admin', # Updated with your real password
}

# MySQL ERP database connection details
MYSQL_DB_CONFIG = {
    'host': 'localhost',  # Replace with your MySQL ERP DB host
    'database': 'my_database',  # Use 'database' instead of 'dbname'
    'user': 'my_user',   # Replace with your MySQL username
    'password': 'ashiq',  # Replace with your MySQL password
}


# Fetch products from Odoo PostgreSQL database
def fetch_products_from_odoo():
    try:
        # Connect to the Odoo PostgreSQL database
        connection = psycopg2.connect(**ODOO_DB_CONFIG)
        cursor = connection.cursor()

        # Query to fetch products from Odoo
        query = """
        SELECT id, name, default_code, list_price, type
        FROM product_template
        """
        cursor.execute(query)

        # Fetch all product rows
        products = cursor.fetchall()

        cursor.close()
        connection.close()

        # Process the products to ensure 'name' is a string (taking the default language)
        processed_products = []
        for product in products:
            product_id = product[0]
            name = product[1]
            if isinstance(name, dict):  # Handling the name as a dictionary (for multi-language support)
                name = name.get('en_US', 'Unknown')  # Default to 'en_US' or any other fallback
            sku = product[2]
            price = product[3]
            type_ = product[4]
            processed_products.append((product_id, name, sku, price, type_))

        return processed_products

    except Exception as error:
        print(f"Error fetching products from Odoo: {error}")
        return []


# Insert products into MySQL ERP database
def insert_products_into_mysql(products):
    try:
        # Connect to the MySQL ERP database
        connection = mysql.connector.connect(**MYSQL_DB_CONFIG)
        cursor = connection.cursor()

        # Insert each product into the MySQL ERP database
        for product in products:
            # Debug print to check what data is being passed
            print(f"Preparing to insert product: {product}")
            
            # Check the structure of the data being passed
            if isinstance(product, tuple) and len(product) == 5:
                query = """
                INSERT INTO products (odoo_product_id, name, sku, price, type)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (product[0], product[1], product[2], product[3], product[4]))
            else:
                print(f"Skipping invalid product format: {product}")

        # Commit changes to the MySQL database
        connection.commit()

        cursor.close()
        connection.close()

        print(f"{len(products)} products inserted into MySQL ERP.")

    except Exception as error:
        print(f"Error inserting products into MySQL: {error}")


# Main function
def main():
    # Fetch products from Odoo
    odoo_products = fetch_products_from_odoo()

    if odoo_products:
        # Insert products into MySQL ERP if products are fetched
        insert_products_into_mysql(odoo_products)
    else:
        print("No products fetched from Odoo.")

if __name__ == "__main__":
    main()
