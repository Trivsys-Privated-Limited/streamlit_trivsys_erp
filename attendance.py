import streamlit as st
import pandas as pd
from database import *  # Ensure to import functions like get_db_connection
from sqlalchemy import create_engine
from datetime import datetime
from zk_device import ZKDevice
import threading
import time

def fetch_daily_attendance(date=None):
    """Fetch attendance records grouped by day with Duration"""
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()

        cursor = conn.cursor(dictionary=True)

        query = """
                SELECT 
                    DATE(a.check_in_time) AS Date,
                    e.id AS EmployeeID,
                    e.name AS Employee, 
                    a.status AS Status,
                    a.check_in_time AS CheckIn,
                    a.check_out_time AS CheckOut,
                    CASE 
                        WHEN a.check_out_time IS NOT NULL 
                        THEN TIMEDIFF(a.check_out_time, a.check_in_time)
                        ELSE NULL
                    END AS Duration
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
        """

        params = []
        if date:
            query += " WHERE DATE(a.check_in_time) = %s"
            params.append(date)

        query += " ORDER BY a.check_in_time DESC"

        cursor.execute(query, params if params else None)
        results = cursor.fetchall()
        conn.close()

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)

        # Convert datetime columns to 12-hour format
        if 'CheckIn' in df.columns:
            df['CheckIn'] = df['CheckIn'].apply(lambda x: x.strftime('%I:%M %p') if x else '')

        if 'CheckOut' in df.columns:
            df['CheckOut'] = df['CheckOut'].apply(lambda x: x.strftime('%I:%M %p') if x and pd.notnull(x) else '')


        # Duration already calculated by SQL, just format it for better display
        if 'Duration' in df.columns:
            df['Duration'] = df['Duration'].apply(lambda x: str(x) if pd.notnull(x) else '')


        return df

    except Exception as e:
        print(f"Error fetching daily attendance: {e}")
        return pd.DataFrame()



def register_device_employees():
    """Register employees from device to database"""
    zk = ZKDevice()
    device_employees = zk.get_users()

    if not device_employees:
        return False, "No employees found on device"

    conn = get_db_connection()
    if not conn:
        return False, "Failed to connect to database"

    try:
        cursor = conn.cursor()
        registered = 0
        
        for employee in device_employees:
            # Adjust this based on your device's employee data structure
            user_id = employee.user_id if hasattr(employee, 'user_id') else employee.get('id')
            name = employee.name if hasattr(employee, 'name') else employee.get('name', f"Employee {user_id}")
            
            # Check if employee exists
            cursor.execute("SELECT id FROM employees WHERE id = %s", (user_id,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO employees (id, name) VALUES (%s, %s)",
                    (user_id, name)
                )
                registered += 1
        
        conn.commit()
        return True, f"Successfully registered {registered} employees"
    except Exception as e:
        return False, f"Error registering employees: {e}"
    finally:
        conn.close()




# Function to fetch all attendance records from the database
def fetch_attendance(employee_name=None):
    try:
        engine = create_engine(f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}")

        # Updated query to include check_in_time and check_out_time
        query = """
            SELECT e.id AS EmployeeID, e.name AS Employee, a.status AS Status, 
                   a.check_in_time AS CheckInTime, a.check_out_time AS CheckOutTime,
                   TIMEDIFF(a.check_out_time, a.check_in_time) AS Duration
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE a.check_in_time IS NOT NULL
        """
        
        params = []
        if employee_name:
            query += " AND e.name LIKE %s"
            params.append(f"%{employee_name}%")
        
        query += " ORDER BY a.check_in_time DESC"

        df = pd.read_sql(query, engine, params=params if params else None)

        if df.empty:
            st.warning("No attendance records found.")
        else:
            st.dataframe(df)  # Using dataframe for better display
    except Exception as e:
        st.error(f"Error fetching attendance: {e}")


# Function to start the auto-sync process
def start_auto_sync(interval_minutes=5):
    """Start automatic syncing with the device"""
    def sync_loop():
        zk = ZKDevice()
        while True:
            try:
                print(f"Syncing with device at {datetime.now()}")
                if zk.sync_with_database():
                    print("Sync successful")
                else:
                    print("Sync failed")
            except Exception as e:
                print(f"Sync error: {e}")
            time.sleep(interval_minutes * 60)
    
    # Start the sync thread
    sync_thread = threading.Thread(target=sync_loop, daemon=True)
    sync_thread.start()

# Streamlit page for attendance management
# Streamlit page for attendance management
def attendance_page():
    # Start auto-sync when page loads
    if 'sync_started' not in st.session_state:
        start_auto_sync()
        st.session_state.sync_started = True

    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.rerun()

    st.title("Attendance Management")
    #  trying new submenu
    if 'submenu' not in st.session_state:
        st.session_state.submenu = "View Daily Attendance"
    with st.sidebar:
    # Module Title

        st.markdown("### Attendance Management")
        
        # Navigation buttons
        menu_items = [
            "View Daily Attendance",
            "Manage Employees", 
        ]
        
        for item in menu_items:
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.submenu = item
                st.rerun()

    submenu = st.session_state.submenu

    # submenu = st.sidebar.selectbox("Select Action", ["View Daily Attendance", "Manage Employees"])


    if submenu == "View Daily Attendance":
        st.header("View Daily Attendance")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Date selector for attendance viewing
            selected_date = st.date_input("Select Date", value=datetime.now().date())
        
        # Sync button
        if st.button("Sync with Biometric Device"):
            with st.spinner("Syncing attendance data..."):
                zk = ZKDevice()
                if zk.sync_with_database():
                    st.success("✅ Sync completed successfully!")
                else:
                    st.error("❌ Sync failed. Check device connection.")

        # Display daily attendance
        with st.spinner("Loading attendance records..."):
            daily_attendance = fetch_daily_attendance(selected_date)
            
            if not daily_attendance.empty:
                # Rename columns for better display
                if 'EmployeeID' in daily_attendance.columns and 'Employee' in daily_attendance.columns:
                    display_df = daily_attendance.rename(columns={
                        'EmployeeID': 'ID',
                        'Employee': 'Name',
                        'Status': 'Status',
                        'CheckIn': 'Check In',
                        'CheckOut': 'Check Out'
                    })
                    
                    # Reorder columns if needed
                    column_order = ['ID', 'Name', 'Status', 'Check In', 'Check Out']
                    display_columns = [col for col in column_order if col in display_df.columns]
                    display_df = display_df[display_columns]
                    
                    # Display as a table
                    st.table(display_df)
                else:
                    st.table(daily_attendance)
            else:
                st.info(f"No attendance records found for {selected_date}.")
        
        # Add search functionality
        st.subheader("Search Attendance")
        search_employee = st.text_input("Search Employee by Name:")
        if search_employee:
            engine = create_engine(f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}")
            query = """
                SELECT DATE(a.check_in_time) AS Date, e.name AS Employee, 
                       a.status AS Status, a.check_in_time AS CheckIn, 
                       a.check_out_time AS CheckOut, 
                       TIMEDIFF(a.check_out_time, a.check_in_time) AS Duration
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE e.name LIKE %s
                ORDER BY a.check_in_time DESC
            """
            search_df = pd.read_sql(query, engine, params=(f"%{search_employee}%",))  # Notice the trailing comma
            if not search_df.empty:
                st.table(search_df)  # Using st.table() instead of st.dataframe() for a static table
            else:
                st.info(f"No records found for '{search_employee}'")


    elif submenu == "Manage Employees":
        st.header("Employee Management")
        
        # Radio buttons for navigation
        action = st.radio(
            "Select Action:",
            ["View Employees", "Sync with Device", "Add New or Delete", "Update Details", "Clear All"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        st.divider()
        
        if action == "View Employees":
            st.subheader("Current Employees")
            employees = fetch_employees()

            if employees:
                first_emp = employees[0]
                
                if isinstance(first_emp, dict):
                    employee_list = [{'ID': emp['id'], 'Name': emp['name'], 'Phone': emp['whatsapp_number']} for emp in employees]
                elif isinstance(first_emp, tuple):
                    employee_list = [{'ID': emp[0], 'Name': emp[1], 'Phone': emp[2]} for emp in employees]
                else:
                    st.error("Unknown employee data format")
                    st.stop()

                st.table(employee_list)
            else:
                st.info("No employees found in the database.")


        
        elif action == "Sync with Device":
            st.subheader("Sync with Device")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("""
                **Instructions:**
                - Connect your biometric device
                - Click the button to fetch employees
                - Employees will be saved with their device IDs
                """)
            
            with col2:
                if st.button("🔄 Fetch & Save", help="Fetch employees from connected device"):
                    with st.spinner("Fetching employees from device..."):
                        zk = ZKDevice()
                        device_employees = zk.get_users()

                        if device_employees:
                            success_count = 0
                            for employee in device_employees:
                                try:
                                    user_id = getattr(employee, 'user_id', None) or getattr(employee, 'uid', None)
                                    name = getattr(employee, 'name', f"Employee {user_id}")
                                    add_new_employee(name=name, phone="", emp_id=int(user_id))
                                    success_count += 1
                                except Exception as e:
                                    st.error(f"Error processing employee: {e}")

                            st.success(f"Successfully saved {success_count} employees from device")
                            st.rerun()
                        else:
                            st.error("No employees found on device or connection failed")
        
        elif action == "Add New or Delete":
            st.subheader("Add New Employee")
            
            with st.form("add_employee_form"):
                c1,c2 = st.columns(2)
                with c1:
                    st.markdown('#### Full Name')
                    new_name = st.text_input("Full Name", placeholder="Enter employee name",label_visibility='collapsed')
                with c2:
                    st.markdown('#### Phone Number')
                    new_phone = st.text_input("Phone Number", placeholder="Enter phone number",label_visibility='collapsed')
                
                if st.form_submit_button("Add Employee"):
                    if new_name and new_phone:
                        add_new_employee(new_name, new_phone)
                        st.success(f"Employee '{new_name}' added successfully!")
                        
                    else:
                        st.warning("Please enter both name and phone number")

            # Divider
            st.divider()
            st.subheader("Delete Existing Employees")

            # Fetch employees
            employees = fetch_employees()

            if employees:
                first_emp = employees[0]
                if isinstance(first_emp, dict):
                    employee_list = [{'ID': emp['id'], 'Name': emp['name'], 'Phone': emp['whatsapp_number']} for emp in employees]
                elif isinstance(first_emp, tuple):
                    employee_list = [{'ID': emp[0], 'Name': emp[1], 'Phone': emp[2]} for emp in employees]
                else:
                    st.error("Unknown employee data format")
                    st.stop()

                # Dropdown to select an employee to delete
                employee_to_delete = st.selectbox(
                    "Select an employee to delete",
                    options=[(emp['ID'], emp['Name']) for emp in employee_list],
                    format_func=lambda x: f"{x[1]} (ID: {x[0]})"
                )

                if st.button("🗑️ Delete Selected Employee"):
                    delete_employee(employee_to_delete[0])
                    st.success(f"Employee {employee_to_delete[1]} (ID: {employee_to_delete[0]}) deleted successfully.")
                    
            else:
                st.info("No employees found in the database.")


        
        elif action == "Update Details":
            st.subheader("Update Employee Details")
            employees = fetch_employees()
            
            if not employees:
                st.info("No employees available to update")
            else:
                employee_options = {f"{emp['id']} - {emp['name']}": emp for emp in employees}
                selected = st.selectbox("Select Employee", options=list(employee_options.keys()))
                
                employee = employee_options[selected]
                
                with st.form("update_employee_form"):
                    new_name = st.text_input("Name", value=employee['name'])
                    new_phone = st.text_input("Phone", value=employee['whatsapp_number'])
                    
                    if st.form_submit_button("🔄 Update"):
                        update_employee(employee['id'], new_name, new_phone)
                        st.success("Employee updated successfully! You can check in view employees section!"  )
                        
        
        elif action == "Clear All":
            st.subheader("Clear All Employees")
            st.warning("This will permanently delete all employee records!")
            
            if st.button("Confirm Clear All"):
                clear_all_employees()
                st.success("All employees have been cleared!")
                