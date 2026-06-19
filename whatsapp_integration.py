import pandas as pd
import streamlit as st
import requests
from attendance import fetch_employees
def process_employee_data(employees):
    """
    Process the employee data to extract name and whatsapp_number.
    Returns a dictionary of employee names as keys and whatsapp numbers as values.
    """
    emp_options = {}

    for emp in employees:
        name = emp.get("name", "Unknown")
        whatsapp_number = emp.get("whatsapp_number", "")

        if whatsapp_number:
            emp_options[f"{name} ({whatsapp_number})"] = whatsapp_number.replace(" ", "")
        else:
            emp_options[f"{name} (N/A)"] = ''

    return emp_options


# Initialize session state for logs if not already initialized
if "whatsapp_logs" not in st.session_state:
    st.session_state["whatsapp_logs"] = []

INSTANCE_ID = "instance108547"  # Replace with your instance ID
TOKEN = "bgas9v9uhv4d1smx"  # Replace with your API token
API_URL = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"  # API endpoint for UltraMSG
HEADERS = {"Content-Type": "application/json"}  # Required headers for the API request

def send_whatsapp_message(phone, message):
    """
    Send a WhatsApp message using the Meta API and handle errors properly.
    """
    payload = {"token": TOKEN, "to": phone, "body": message}  # Request payload
    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload)  # Send the request
        response_data = response.json()  # Parse JSON response

        # Handle different API error cases
        if response.status_code == 401:
            log_entry = "❌ Error: API token is expired or invalid."
        elif response.status_code == 403:
            log_entry = "❌ Error: Access forbidden. Check API permissions."
        elif response.status_code == 400:
            log_entry = f"❌ Bad request: {response_data.get('error', {}).get('message', 'Unknown error')}"
        elif response.status_code == 200 and response_data.get("sent", False):
            log_entry = f"✅ Message sent to {phone}: {message}"
        else:
            log_entry = f"❌ Failed to send message to {phone}: {response_data}"

        # Avoid duplicate logs
        if log_entry not in st.session_state["whatsapp_logs"]:
            st.session_state["whatsapp_logs"].append(log_entry)

        return response.status_code == 200 and response_data.get("sent", False)

    except requests.exceptions.RequestException as e:
        log_entry = f"❌ Error sending message: {e}"

        if log_entry not in st.session_state["whatsapp_logs"]:
            st.session_state["whatsapp_logs"].append(log_entry)

        return False  # Return False if there was an exception

    
def fetch_whatsapp_logs():
    """
    Fetch logs of sent WhatsApp messages from session state.
    """
    return st.session_state.get("whatsapp_logs", [])  # Use .get() to avoid KeyError


def whatsapp_page():

    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.rerun()    
        
    st.sidebar.title("PBS ERP")
    """
    Streamlit page to send WhatsApp messages to selected employees or manually entered phone numbers.
    """
    st.title("WhatsApp Messaging")

    # Ensure whatsapp_logs is initialized
    if "whatsapp_logs" not in st.session_state:
        st.session_state["whatsapp_logs"] = []

    employees = fetch_employees()  # Fetch employee data from the database

    if not employees:
        st.warning("⚠ No employees found in the database.")  # Show warning if no employees are found
        return

    # Use the process_employee_data function to prepare employee options
    emp_options = process_employee_data(employees)
    c1,c2 = st.columns(2)
    # Multi-select for bulk employee selection
    with c1:
        st.markdown('##### Select Employees')
        selected_bulk_employees = st.multiselect(" **Select Employees**", list(emp_options.keys()), key="bulk_employee_select",label_visibility='collapsed')

    # Input field for manual phone number entry
    with c2:
        st.markdown('##### Enter Phone Number Manually')
        phone_input = st.text_input("**Or Enter Phone Number Manually**", key="manual_phone_input",label_visibility='collapsed')
        
    # Input field for message content
    message = st.text_area("📝 **Enter Your Message**", key="manual_message_input")

    # Logic for sending messages when the button is pressed
    if st.button("Send Message", key="send_bulk_message"):
        selected_numbers = set()

        # Add selected employee phone numbers to the set
        for emp in selected_bulk_employees:
            phone = emp_options.get(emp)
            if phone:
                selected_numbers.add(phone)

        # Add manually entered phone number to the set if provided
        if phone_input.strip():
            selected_numbers.add(phone_input.strip())

        # Validation for user input
        if not selected_numbers:
            st.warning("⚠ Please select an employee or enter a phone number.")  # Warn if no phone number is selected
        elif not message.strip():
            st.warning("⚠ Message cannot be empty.")  # Warn if no message is entered
        else:
            # Send message to each selected number and count successful messages
            success_count = sum(1 if send_whatsapp_message(phone, message) else 0 for phone in selected_numbers)
            st.success(f"✅ Messages sent to {success_count} employees!")  # Show success message

    # Display WhatsApp message logs
    st.header("📜 Message Logs")
    logs = fetch_whatsapp_logs()  # Fetch logs from WhatsApp integration
    if logs:
        log_df = pd.DataFrame(logs, columns=["Log"])  # Display logs in a table format
        st.dataframe(log_df)
    else:
        st.write("No WhatsApp messages sent yet.")





if __name__ == "__main__":
    whatsapp_page()  # Run the WhatsApp page function
