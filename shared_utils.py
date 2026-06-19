from database import get_db_connection

def generate_unique_sale_id():
    """
    Generate a unique sale ID by finding the maximum ID in the sales table and incrementing it.
    """
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

def add_sale_items(sale_id, product_id, quantity, sale_price):
    """
    Add items to the sale_items table for a given sale ID.
    """
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