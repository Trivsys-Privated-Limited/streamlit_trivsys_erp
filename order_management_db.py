from fpdf import FPDF
import streamlit as st
import pandas as pd
from database import get_db_connection
from datetime import datetime


# ------------------------ DATABASE FUNCTIONS ------------------------

def add_customer_to_db(name, phone, email=None, address=None):
    """Add a new customer to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO customers (customer_name, customer_number, email, address, created_at) 
        VALUES (%s, %s, %s, %s, %s)
    """, (name, phone, email, address, datetime.now()))
    
    conn.commit()
    conn.close()

def get_all_customers():
    """Get all customers from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, customer_name, customer_number FROM customers ORDER BY customer_name")
    customers = cursor.fetchall()
    conn.close()
    return customers


def get_customer_measurements(customer_id):
    """Get measurements for a specific customer"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customer_measurements WHERE customer_id = %s", (customer_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        columns = [
            'id', 'customer_id', 'chest', 'shoulder', 'sleeve_length', 'neck',
            'waist', 'hip', 'kurta_length', 'shalwar_length', 'height', 'weight',
            'notes', 'created_at', 'updated_at', 'sherwani_length', 'sherwani_width',
            'sherwani_height', 'sherwani_thigh', 'sherwani_bottom', 'suit_length',
            'suit_chest', 'suit_waist', 'suit_shoulder', 'suit_sleeve', 'suit_neck',
            'suit_pant_length', 'suit_pant_width', 'suit_pant_height', 'suit_thigh',
            'suit_bottom', 'accessories', 'waistcoat', 'shoes', 'turban',
            'sherwani_knee', 'head_size', 'shoe_size', 'coat_type_id'  # 👈 Add this
        ]
        return dict(zip(columns, result))
    return {}



# Update the save_customer_measurements function to include coat_type
def save_customer_measurements(measurements_data, measurement_type):
    """Save or update customer measurements for specific type (sherwani/suit) with coat type"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get existing measurements to preserve other type's data
        existing = get_customer_measurements(measurements_data['customer_id'])
        
        if existing:
            # Update only the relevant fields based on measurement_type
            if measurement_type == 'sherwani':
                update_fields = {
                    'chest': measurements_data.get('chest'),
                    'shoulder': measurements_data.get('shoulder'),
                    'sleeve_length': measurements_data.get('sleeve_length'),
                    'neck': measurements_data.get('neck'),
                    'waist': measurements_data.get('waist'),
                    'hip': measurements_data.get('hip'),
                    'kurta_length': measurements_data.get('kurta_length'),
                    'shalwar_length': measurements_data.get('shalwar_length'),
                    'height': measurements_data.get('height'),
                    'weight': measurements_data.get('weight'),
                    'sherwani_length': measurements_data.get('sherwani_length'),
                    'sherwani_width': measurements_data.get('sherwani_width'),
                    'sherwani_height': measurements_data.get('sherwani_height'),
                    'sherwani_thigh': measurements_data.get('sherwani_thigh'),
                    'sherwani_bottom': measurements_data.get('sherwani_bottom'),
                    'sherwani_knee': measurements_data.get('sherwani_knee'),
                    'head_size': measurements_data.get('head_size'),
                    'shoe_size': measurements_data.get('shoe_size'),
                    'notes': measurements_data.get('notes', existing.get('notes', '')),
                }
            else:  # suit
                update_fields = {
                    'suit_length': measurements_data.get('suit_length'),
                    'suit_chest': measurements_data.get('suit_chest'),
                    'suit_waist': measurements_data.get('suit_waist'),
                    'suit_shoulder': measurements_data.get('suit_shoulder'),
                    'suit_sleeve': measurements_data.get('suit_sleeve'),
                    'suit_neck': measurements_data.get('suit_neck'),
                    'suit_pant_length': measurements_data.get('suit_pant_length'),
                    'suit_pant_width': measurements_data.get('suit_pant_width'),
                    'suit_pant_height': measurements_data.get('suit_pant_height'),
                    'suit_thigh': measurements_data.get('suit_thigh'),
                    'suit_bottom': measurements_data.get('suit_bottom'),
                    'height': measurements_data.get('height'),
                    'weight': measurements_data.get('weight'),
                    'head_size': measurements_data.get('head_size'),
                    'shoe_size': measurements_data.get('shoe_size'),
                    'notes': measurements_data.get('notes', existing.get('notes', '')),
                    'coat_type_id': measurements_data.get('coat_type_id'),  # Add coat type
                }
            
            # Always update accessories and checkboxes
            update_fields.update({
                'accessories': measurements_data.get('accessories'),
                'waistcoat': measurements_data.get('waistcoat'),
                'shoes': measurements_data.get('shoes'),
                'turban': measurements_data.get('turban')
            })
            
            # Build dynamic update query
            set_clause = ', '.join([f"{k}=%s" for k in update_fields.keys()])
            values = list(update_fields.values()) + [measurements_data['customer_id']]
            
            cursor.execute(f"UPDATE customer_measurements SET {set_clause} WHERE customer_id = %s", values)
            print(f"Updated {measurement_type} measurements for customer_id: {measurements_data['customer_id']}")
            
        else:
            # Insert new record with all fields
            all_fields = {
                'customer_id': measurements_data['customer_id'],
                'chest': measurements_data.get('chest', 0.0),
                'shoulder': measurements_data.get('shoulder', 0.0),
                'sleeve_length': measurements_data.get('sleeve_length', 0.0),
                'neck': measurements_data.get('neck', 0.0),
                'waist': measurements_data.get('waist', 0.0),
                'hip': measurements_data.get('hip', 0.0),
                'kurta_length': measurements_data.get('kurta_length', 0.0),
                'shalwar_length': measurements_data.get('shalwar_length', 0.0),
                'height': measurements_data.get('height', 0.0),
                'weight': measurements_data.get('weight', 0.0),
                'notes': measurements_data.get('notes', ''),
                'sherwani_length': measurements_data.get('sherwani_length', 0.0),
                'sherwani_width': measurements_data.get('sherwani_width', 0.0),
                'sherwani_height': measurements_data.get('sherwani_height', 0.0),
                'sherwani_thigh': measurements_data.get('sherwani_thigh', 0.0),
                'sherwani_bottom': measurements_data.get('sherwani_bottom', 0.0),
                'sherwani_knee': measurements_data.get('sherwani_knee', 0.0),
                'suit_length': measurements_data.get('suit_length', 0.0),
                'suit_chest': measurements_data.get('suit_chest', 0.0),
                'suit_waist': measurements_data.get('suit_waist', 0.0),
                'suit_shoulder': measurements_data.get('suit_shoulder', 0.0),
                'suit_sleeve': measurements_data.get('suit_sleeve', 0.0),
                'suit_neck': measurements_data.get('suit_neck', 0.0),
                'suit_pant_length': measurements_data.get('suit_pant_length', 0.0),
                'suit_pant_width': measurements_data.get('suit_pant_width', 0.0),
                'suit_pant_height': measurements_data.get('suit_pant_height', 0.0),
                'suit_thigh': measurements_data.get('suit_thigh', 0.0),
                'suit_bottom': measurements_data.get('suit_bottom', 0.0),
                'head_size': measurements_data.get('head_size', 0.0),
                'shoe_size': measurements_data.get('shoe_size', 0.0),
                'accessories': measurements_data.get('accessories', '{}'),
                'waistcoat': measurements_data.get('waistcoat', False),
                'shoes': measurements_data.get('shoes', False),
                'turban': measurements_data.get('turban', False),
                'coat_type_id': measurements_data.get('coat_type_id')  # Add coat type
            }
            
            columns = ', '.join(all_fields.keys())
            placeholders = ', '.join(['%s'] * len(all_fields))
            
            cursor.execute(f"INSERT INTO customer_measurements ({columns}) VALUES ({placeholders})", 
                         list(all_fields.values()))
            print(f"Inserted new measurements for customer_id: {measurements_data['customer_id']}")
        
        conn.commit()
        print("Database commit successful")
        
    except Exception as e:
        print(f"Database error: {str(e)}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_customer_measurements(customer_id):
    """Delete measurements for a specific customer"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM customer_measurements WHERE customer_id = %s", (customer_id,))
    conn.commit()
    conn.close()

def get_all_measurements():
    """Get all customer measurements with customer details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cm.*, c.name, c.phone 
        FROM customer_measurements cm
        JOIN customers c ON cm.customer_id = c.id
        ORDER BY cm.updated_at DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return results

def search_measurements_by_customer(search_term):
    """Search measurements by customer name or phone"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cm.*, c.name, c.phone 
        FROM customer_measurements cm
        JOIN customers c ON cm.customer_id = c.id
        WHERE c.name LIKE %s OR c.phone LIKE %s
        ORDER BY cm.updated_at DESC
    """, (f'%{search_term}%', f'%{search_term}%'))
    results = cursor.fetchall()
    conn.close()
    return results


# ------------------------ TAILOR MANAGEMENT FUNCTIONS ------------------------

# ------------------------ TAILOR MANAGEMENT FUNCTIONS ------------------------

def add_tailor_to_db(name, phone, address, specialization, capacity):
    """Add a new tailor to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO tailors (name, phone, address, specialization, daily_capacity, created_at) 
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (name, phone, address, specialization, capacity, datetime.now()))
    
    conn.commit()
    conn.close()

def get_all_tailors():
    """Get all tailors from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tailors ORDER BY name")
    tailors = cursor.fetchall()
    conn.close()
    return tailors

def get_all_tailors_as_dict():
    """Get all tailors as dict (for UI dropdowns etc.)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM tailors WHERE is_active = 1 ORDER BY name")
    tailors = cursor.fetchall()
    conn.close()
    return tailors

def get_orders_with_metadata():
    """Get all orders with metadata from sales table including current tailor info"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            s.id AS sale_id,
            c.customer_name,
            s.sale_date,
            s.source,
            s.paid_amount,
            s.due_amount,
            p.name AS product_name,
            si.quantity,
            si.sale_price,
            s.total_price,
            COALESCE(s.order_status, 'Pending') AS order_status,
            t.name AS current_tailor
        FROM sales s
        JOIN sale_items si ON s.id = si.sale_id
        JOIN products p ON si.product_id = p.id
        JOIN customers c ON s.customer_id = c.id
        LEFT JOIN tailors t ON s.assigned_tailor_id = t.id
        ORDER BY s.sale_date DESC
    """)
    result = cursor.fetchall()
    conn.close()
    return result

def update_order_status(sale_id, new_status):
    """Update order status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sales SET order_status = %s WHERE id = %s", (new_status, sale_id))
    conn.commit()
    conn.close()

def update_order_status_with_tailor(sale_id, new_status, tailor_id):
    """Update order status and assign tailor - FIXED VERSION"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update sales table
    cursor.execute("""
        UPDATE sales 
        SET order_status = %s, assigned_tailor_id = %s, tailor_assigned_date = %s 
        WHERE id = %s
    """, (new_status, tailor_id, datetime.now(), sale_id))
    
    # Insert into order_timeline with correct enum value
    # Map your status to the correct enum value
    timeline_status = "Sent to Tailor"  # This matches the enum value
    
    cursor.execute("""
        INSERT INTO order_timeline (sale_id, status, tailor_id, created_at)
        VALUES (%s, %s, %s, %s)
    """, (sale_id, timeline_status, tailor_id, datetime.now()))
    
    conn.commit()
    conn.close()

def update_order_status_clear_tailor(sale_id, new_status):
    """Update order status and clear tailor assignment - FIXED VERSION"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update sales table
    cursor.execute("""
        UPDATE sales 
        SET order_status = %s, assigned_tailor_id = NULL 
        WHERE id = %s
    """, (new_status, sale_id))
    
    # Insert into order_timeline with correct enum value
    # Map your status to the correct enum value
    if new_status == "Received from Tailor":
        timeline_status = "Received from Tailor"
    elif new_status == "Delivered":
        timeline_status = "Delivered"
    else:
        timeline_status = "Pending"
    
    cursor.execute("""
        INSERT INTO order_timeline (sale_id, status, created_at)
        VALUES (%s, %s, %s)
    """, (sale_id, timeline_status, datetime.now()))
    
    conn.commit()
    conn.close()

def add_tailor_transfer_history(sale_id, from_tailor, to_tailor):
    """Add a record of tailor transfer for tracking"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tailor_transfers (sale_id, from_tailor, to_tailor, transfer_date)
        VALUES (%s, %s, %s, %s)
    """, (sale_id, from_tailor, to_tailor, datetime.now()))
    conn.commit()
    conn.close()

def get_tailor_transfer_history(sale_id):
    """Get transfer history for an order"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sale_id, from_tailor, to_tailor, 
               DATE_FORMAT(transfer_date, '%Y-%m-%d %H:%i') AS transfer_date
        FROM tailor_transfers 
        WHERE sale_id = %s 
        ORDER BY transfer_date ASC
    """, (sale_id,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_current_tailor_workload():
    """Get current workload for each tailor"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            t.name,
            t.daily_capacity,
            COUNT(s.id) as current_orders,
            t.specialization
        FROM tailors t
        LEFT JOIN sales s ON t.id = s.assigned_tailor_id AND s.order_status LIKE 'With %'
        GROUP BY t.id, t.name, t.daily_capacity, t.specialization
        ORDER BY current_orders ASC
    """)
    result = cursor.fetchall()
    conn.close()
    return result

def get_orders_assigned_to_tailors():
    """Get orders currently assigned to tailors (With [Tailor Name] status)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            t.name AS tailor_name,
            s.id AS sale_id,
            c.customer_name,
            DATE_FORMAT(s.tailor_assigned_date, '%Y-%m-%d') AS assigned_date,
            s.order_status,
            SUM(si.quantity * si.sale_price) AS total_price
        FROM sales s
        JOIN sale_items si ON si.sale_id = s.id
        JOIN customers c ON s.customer_id = c.id
        JOIN tailors t ON s.assigned_tailor_id = t.id
        WHERE s.order_status LIKE 'With %' AND s.assigned_tailor_id IS NOT NULL
        GROUP BY s.id
        ORDER BY t.name, s.tailor_assigned_date DESC
    """
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return results

# ---------------------- Tailor payments management functions --------------------

def record_tailor_payment(tailor_id, amount, remarks):
    """Insert a new payment record for a tailor"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tailor_payments (tailor_id, amount_paid, remarks)
        VALUES (%s, %s, %s)
    """, (tailor_id, amount, remarks))
    conn.commit()
    conn.close()


def get_tailor_payments(tailor_id):
    """Fetch all payment records for a tailor"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT payment_date, amount_paid, COALESCE(remarks, '')
        FROM tailor_payments
        WHERE tailor_id = %s
        ORDER BY payment_date DESC
    """, (tailor_id,))
    result = cursor.fetchall()
    conn.close()
    return result


# NEW HELPER FUNCTION TO ADD ORDER TIMELINE ENTRY
def add_order_timeline_entry(sale_id, status, tailor_id=None, notes=None):
    """Add an entry to order_timeline table with proper enum handling"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Validate status against enum values
    valid_statuses = ['Pending', 'Sent to Tailor', 'Received from Tailor', 'Delivered']
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of: {valid_statuses}")
    
    cursor.execute("""
        INSERT INTO order_timeline (sale_id, status, tailor_id, notes, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (sale_id, status, tailor_id, notes, datetime.now()))
    
    conn.commit()
    conn.close()

# UPDATED FUNCTION TO HANDLE PROPER STATUS MAPPING
def update_order_with_timeline(sale_id, new_sales_status, timeline_status, tailor_id=None, clear_tailor=False):
    """Update order status in sales table and add timeline entry"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update sales table
    if clear_tailor:
        cursor.execute("""
            UPDATE sales 
            SET order_status = %s, assigned_tailor_id = NULL 
            WHERE id = %s
        """, (new_sales_status, sale_id))
    else:
        cursor.execute("""
            UPDATE sales 
            SET order_status = %s, assigned_tailor_id = %s, tailor_assigned_date = %s 
            WHERE id = %s
        """, (new_sales_status, tailor_id, datetime.now(), sale_id))
    
    # Add timeline entry
    cursor.execute("""
        INSERT INTO order_timeline (sale_id, status, tailor_id, created_at)
        VALUES (%s, %s, %s, %s)
    """, (sale_id, timeline_status, tailor_id, datetime.now()))
    
    conn.commit()
    conn.close()

import json
from datetime import datetime

def format_measurement_display(measurement_value):
    """Format measurement value for display"""
    if measurement_value and float(measurement_value) > 0:
        return f"{float(measurement_value):.1f}\""
    return "Not set"

def get_accessories_list(accessories_json, individual_accessories):
    """Get formatted list of accessories"""
    accessories_list = []
    
    # Add individual boolean accessories
    if individual_accessories.get('waistcoat'):
        accessories_list.append("Waistcoat")
    if individual_accessories.get('shoes'):
        accessories_list.append("Shoes")
    if individual_accessories.get('turban'):
        accessories_list.append("Turban")
    
    # Add JSON accessories
    try:
        if isinstance(accessories_json, str):
            acc_dict = json.loads(accessories_json)
        else:
            acc_dict = accessories_json or {}
        
        for key, value in acc_dict.items():
            if value:
                accessories_list.append(key.replace('_', ' ').title())
    except:
        pass
    
    return accessories_list if accessories_list else ["None selected"]

def validate_measurements(measurements_data):
    """Validate measurement data before saving"""
    errors = []
    
    # Check for required customer_id
    if not measurements_data.get('customer_id'):
        errors.append("Customer ID is required")
    
    # Validate numeric fields
    numeric_fields = [
        'chest', 'shoulder', 'sleeve_length', 'neck', 'waist', 'hip',
        'kurta_length', 'shalwar_length', 'height', 'weight',
        'sherwani_length', 'sherwani_width', 'sherwani_height',
        'sherwani_thigh', 'sherwani_bottom', 'suit_length', 'suit_chest',
        'suit_waist', 'suit_shoulder', 'suit_sleeve', 'suit_neck',
        'suit_pant_length', 'suit_pant_width', 'suit_pant_height',
        'suit_thigh', 'suit_bottom'
    ]
    
    for field in numeric_fields:
        value = measurements_data.get(field, 0)
        try:
            float_value = float(value)
            if float_value < 0:
                errors.append(f"{field.replace('_', ' ').title()} cannot be negative")
        except (ValueError, TypeError):
            errors.append(f"{field.replace('_', ' ').title()} must be a valid number")
    
    return errors

def create_measurement_summary(measurements):
    """Create a summary of measurements for reports"""
    if not measurements:
        return "No measurements available"
    
    summary = {
        'basic': {
            'chest': measurements.get('chest', 0),
            'waist': measurements.get('waist', 0),
            'shoulder': measurements.get('shoulder', 0),
            'height': measurements.get('height', 0),
            'weight': measurements.get('weight', 0)
        },
        'sherwani': {
            'length': measurements.get('sherwani_length', 0),
            'width': measurements.get('sherwani_width', 0),
            'height': measurements.get('sherwani_height', 0)
        },
        'suit': {
            'length': measurements.get('suit_length', 0),
            'chest': measurements.get('suit_chest', 0),
            'pant_length': measurements.get('suit_pant_length', 0)
        },
        'accessories': get_accessories_list(
            measurements.get('accessories', '{}'),
            {
                'waistcoat': measurements.get('waistcoat', False),
                'shoes': measurements.get('shoes', False),
                'turban': measurements.get('turban', False)
            }
        ),
        'last_updated': measurements.get('updated_at', 'Unknown')
    }
    
    return summary

def export_measurements_to_dict(customer_id):
    """Export customer measurements in a structured format for reports/printing"""
    measurements = get_customer_measurements(customer_id)
    if not measurements:
        return None
    
    # Get customer details
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, phone, email FROM customers WHERE id = %s", (customer_id,))
    customer = cursor.fetchone()
    conn.close()
    
    if not customer:
        return None
    
    export_data = {
        'customer_info': {
            'name': customer[0],
            'phone': customer[1],
            'email': customer[2] or 'Not provided'
        },
        'measurements': {
            'basic': {
                'chest': float(measurements.get('chest', 0)),
                'shoulder': float(measurements.get('shoulder', 0)),
                'sleeve_length': float(measurements.get('sleeve_length', 0)),
                'neck': float(measurements.get('neck', 0)),
                'waist': float(measurements.get('waist', 0)),
                'hip': float(measurements.get('hip', 0)),
                'height': float(measurements.get('height', 0)),
                'weight': float(measurements.get('weight', 0))
            },
            'sherwani': {
                'length': float(measurements.get('sherwani_length', 0)),
                'width': float(measurements.get('sherwani_width', 0)),
                'height': float(measurements.get('sherwani_height', 0)),
                'thigh': float(measurements.get('sherwani_thigh', 0)),
                'bottom': float(measurements.get('sherwani_bottom', 0)),
                'kurta_length': float(measurements.get('kurta_length', 0)),
                'shalwar_length': float(measurements.get('shalwar_length', 0))
            },
            'suit': {
                'length': float(measurements.get('suit_length', 0)),
                'chest': float(measurements.get('suit_chest', 0)),
                'waist': float(measurements.get('suit_waist', 0)),
                'shoulder': float(measurements.get('suit_shoulder', 0)),
                'sleeve': float(measurements.get('suit_sleeve', 0)),
                'neck': float(measurements.get('suit_neck', 0)),
                'pant_length': float(measurements.get('suit_pant_length', 0)),
                'pant_width': float(measurements.get('suit_pant_width', 0)),
                'pant_height': float(measurements.get('suit_pant_height', 0)),
                'thigh': float(measurements.get('suit_thigh', 0)),
                'bottom': float(measurements.get('suit_bottom', 0))
            }
        },
        'accessories': get_accessories_list(
            measurements.get('accessories', '{}'),
            {
                'waistcoat': measurements.get('waistcoat', False),
                'shoes': measurements.get('shoes', False),
                'turban': measurements.get('turban', False)
            }
        ),
        'notes': measurements.get('notes', ''),
        'created_at': measurements.get('created_at'),
        'updated_at': measurements.get('updated_at')
    }
    
    return export_data    



# ------------------------ COAT MANAGEMENT FUNCTIONS ------------------------

def add_coat_type_to_db(coat_name, description=None):
    """Add a new coat type to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO coat_types (coat_name, description, created_at) 
        VALUES (%s, %s, %s)
    """, (coat_name, description, datetime.now()))
    
    conn.commit()
    conn.close()

def get_all_coat_types():
    """Get all coat types from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, coat_name, description FROM coat_types ORDER BY coat_name")
    coat_types = cursor.fetchall()
    conn.close()
    return coat_types

def delete_coat_type(coat_id):
    """Delete a coat type from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM coat_types WHERE id = %s", (coat_id,))
    conn.commit()
    conn.close()

def update_coat_type(coat_id, coat_name, description=None):
    """Update a coat type in database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE coat_types 
        SET coat_name = %s, description = %s, updated_at = %s 
        WHERE id = %s
    """, (coat_name, description, datetime.now(), coat_id))
    conn.commit()
    conn.close()


def get_coat_name_by_id(coat_id):
    """Get coat name by ID"""
    if coat_id is None:
        return "No coat selected"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT coat_name FROM coat_types WHERE id = %s", (coat_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return result[0]
    return "Unknown coat type"
 

# For assigning the multiple items to the different tailor
from datetime import datetime
import pandas as pd

def get_orders_with_item_details():
    """Get all orders with individual item details and their statuses"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            s.id AS sale_id,
            c.customer_name,
            s.sale_date,
            s.source,
            s.paid_amount,
            s.due_amount,
            s.total_price,
            si.id AS item_id,
            p.name AS product_name,
            si.quantity,
            si.sale_price,
            (si.quantity * si.sale_price) AS item_total,
            COALESCE(si.item_status, 'Pending') AS item_status,
            t.name AS current_tailor,
            si.tailor_assigned_date
        FROM sales s
        JOIN sale_items si ON s.id = si.sale_id
        JOIN products p ON si.product_id = p.id
        JOIN customers c ON s.customer_id = c.id
        LEFT JOIN tailors t ON si.assigned_tailor_id = t.id
        ORDER BY s.sale_date DESC, si.id ASC
    """)
    result = cursor.fetchall()
    conn.close()
    return result

def update_item_status_with_tailor(sale_item_id, new_status, tailor_id):
    """Update individual item status and assign tailor"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update sale_items table
    cursor.execute("""
        UPDATE sale_items 
        SET item_status = %s, assigned_tailor_id = %s, tailor_assigned_date = %s 
        WHERE id = %s
    """, (new_status, tailor_id, datetime.now(), sale_item_id))
    
    # Add timeline entry
    timeline_status = "Sent to Tailor"
    cursor.execute("""
        INSERT INTO item_timeline (sale_item_id, status, tailor_id, created_at)
        VALUES (%s, %s, %s, %s)
    """, (sale_item_id, timeline_status, tailor_id, datetime.now()))
    
    conn.commit()
    conn.close()

def update_item_status_clear_tailor(sale_item_id, new_status):
    """Update item status and clear tailor assignment"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update sale_items table
    cursor.execute("""
        UPDATE sale_items 
        SET item_status = %s, assigned_tailor_id = NULL 
        WHERE id = %s
    """, (new_status, sale_item_id))
    
    # Add timeline entry
    timeline_status = new_status if new_status in ["Received from Tailor", "Delivered"] else "Pending"
    cursor.execute("""
        INSERT INTO item_timeline (sale_item_id, status, created_at)
        VALUES (%s, %s, %s)
    """, (sale_item_id, timeline_status, datetime.now()))
    
    conn.commit()
    conn.close()

def add_item_tailor_transfer_history(sale_item_id, from_tailor, to_tailor):
    """Add a record of item tailor transfer"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO item_tailor_transfers (sale_item_id, from_tailor, to_tailor, transfer_date)
        VALUES (%s, %s, %s, %s)
    """, (sale_item_id, from_tailor, to_tailor, datetime.now()))
    conn.commit()
    conn.close()

def get_item_tailor_transfer_history(sale_item_id):
    """Get transfer history for an item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sale_item_id, from_tailor, to_tailor, 
               DATE_FORMAT(transfer_date, '%Y-%m-%d %H:%i') AS transfer_date
        FROM item_tailor_transfers 
        WHERE sale_item_id = %s 
        ORDER BY transfer_date ASC
    """, (sale_item_id,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_order_completion_status(sale_id):
    """Get overall order completion status based on individual items"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total_items,
            SUM(CASE WHEN item_status = 'Delivered' THEN 1 ELSE 0 END) as delivered_items,
            SUM(CASE WHEN item_status = 'Pending' THEN 1 ELSE 0 END) as pending_items,
            SUM(CASE WHEN item_status LIKE 'With %' THEN 1 ELSE 0 END) as with_tailor_items,
            SUM(CASE WHEN item_status = 'Received from Tailor' THEN 1 ELSE 0 END) as received_items
        FROM sale_items 
        WHERE sale_id = %s
    """, (sale_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_items_assigned_to_tailors():
    """Get items currently assigned to tailors"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            t.name AS tailor_name,
            s.id AS sale_id,
            c.customer_name,
            p.name AS product_name,
            si.quantity,
            si.item_status,
            DATE_FORMAT(si.tailor_assigned_date, '%Y-%m-%d') AS assigned_date,
            (si.quantity * si.sale_price) AS item_total
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        JOIN customers c ON s.customer_id = c.id
        JOIN products p ON si.product_id = p.id
        JOIN tailors t ON si.assigned_tailor_id = t.id
        WHERE si.item_status LIKE 'With %' AND si.assigned_tailor_id IS NOT NULL
        ORDER BY t.name, si.tailor_assigned_date DESC
    """)
    result = cursor.fetchall()
    conn.close()
    return result

def get_item_timeline(sale_item_id):
    """Get timeline history for a specific item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            it.status,
            t.name AS tailor_name,
            it.notes,
            DATE_FORMAT(it.created_at, '%Y-%m-%d %H:%i') AS created_at
        FROM item_timeline it
        LEFT JOIN tailors t ON it.tailor_id = t.id
        WHERE it.sale_item_id = %s
        ORDER BY it.created_at DESC
    """, (sale_item_id,))
    result = cursor.fetchall()
    conn.close()
    return result

def update_overall_order_status(sale_id):
    """Update overall order status based on individual item statuses"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get item status summary
    status_summary = get_order_completion_status(sale_id)
    total_items, delivered_items, pending_items, with_tailor_items, received_items = status_summary
    
    # Determine overall status
    if delivered_items == total_items:
        overall_status = "Delivered"
    elif pending_items == total_items:
        overall_status = "Pending"
    elif with_tailor_items > 0:
        overall_status = "In Progress"
    elif received_items > 0:
        overall_status = "Ready for Delivery"
    else:
        overall_status = "Mixed Status"
    
    # Update sales table
    cursor.execute("""
        UPDATE sales 
        SET order_status = %s 
        WHERE id = %s
    """, (overall_status, sale_id))
    
    conn.commit()
    conn.close()
    return overall_status