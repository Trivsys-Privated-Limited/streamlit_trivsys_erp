import tempfile
from fpdf import FPDF
import streamlit as st
import pandas as pd
from datetime import datetime
from database import *
import math

def payroll_page():
    
    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.rerun()

    st.title("Payroll Management")

    # Menu options
    # Menu options
    # Add the selected class to the active menu item
    if 'choice' not in st.session_state:
        st.session_state.choice = "Add Employee"
    with st.sidebar:
    # Module Title

        st.markdown("### PAYROLL")
        
        # Navigation buttons
        menu_items = [
            "Add Employees",
            "Mark Payroll", 
            "View Payroll",
            "Salary Slips"
        ]
        
        for item in menu_items:
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.choice = item
                st.rerun()

    choice = st.session_state.choice
    # menu = ["Add Employees", "Mark Payroll", "View Payroll","Salary Slips"]    
    
    if choice == "Add Employees":
        st.header("Add or Delete Employee")
        c1,c2 = st.columns(2)
        with c1:
            st.markdown('#### Employee Name')
            name = st.text_input("Employee Name",label_visibility='collapsed')
        with c2:
            st.markdown('#### Phone Number')
            phone = st.text_input("WhatsApp Number (Optional)",label_visibility='collapsed')
        if st.button(" Add Employee"):
            if name.strip():
                add_new_employee(name, phone)
                st.success(f"✅ Employee {name} added successfully!")
            else:
                st.warning("⚠️ Name cannot be empty.")


        # Fetch employees from the database
        employees = fetch_employees()
        col1,col2 = st.columns(2)
        if not employees:
            st.warning("No employees found.")
        else:
            employee_names = [emp['name'] for emp in employees]
            with col1:
                st.markdown('##### Select Employee to Delete')
                selected_employee_name = st.selectbox("Select Employee to Delete", employee_names,label_visibility='collapsed')

            selected_employee = next(emp for emp in employees if emp['name'] == selected_employee_name)
            selected_employee_id = selected_employee['id']

            # Direct deletion on button click
            if st.button(f"Delete Employee {selected_employee_name}"):
                delete_employee(selected_employee_id)
                st.success(f"✅ Employee {selected_employee_name} deleted successfully.")
                st.rerun()  # Refresh UI after deletion
            # Display the employee list
            st.markdown("# Employee List")

            # Show employee table
            # Number of entries per page
            entries_per_page = 10

            # Total pages
            total_pages = math.ceil(len(employees) / entries_per_page)

            # Current page selector
            with col2:
                st.markdown('##### Page')
                current_page = st.number_input("Page", min_value=1, max_value=total_pages, step=1,label_visibility='collapsed')

            # Calculate start and end indices
            start_idx = (current_page - 1) * entries_per_page
            end_idx = start_idx + entries_per_page

            # Paginated data
            paginated_employees = employees[start_idx:end_idx]
            df = pd.DataFrame(paginated_employees)

            st.write(f"Showing page {current_page} of {total_pages}")
            st.table(df)



    elif choice == "Mark Payroll":
        st.subheader("Mark Payroll for Employees")

        # List of months
        months = ["January", "February", "March", "April", "May", "June", "July", 
                "August", "September", "October", "November", "December"]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('##### Select Month')
            month = st.selectbox("Select Month", months,label_visibility='collapsed')
        with col2:
            st.markdown('##### Enter Year')
            year = st.number_input("Enter Year", min_value=2000, max_value=2100, value=datetime.now().year,label_visibility='collapsed')

        # Fetch all employees
        employees = fetch_employees()

        # Fetch employees who have already been paid
        paid_employees = fetch_paid_employee_ids(month, year)  # Employee IDs

        # Filter out employees who have already been paid
        unpaid_employees = [emp for emp in employees if emp["id"] not in paid_employees]


        if not unpaid_employees:
            st.warning(f"✅ All employees have been paid for {month} {year}.")
        else:
            c1,c2 = st.columns(2)
            # Employee selection dropdown (only unpaid employees)
            emp_dict = {emp["name"]: emp["id"] for emp in unpaid_employees}
            with c1:
                st.markdown('##### Select Employee')
                selected_emp = st.selectbox("Select Employee", list(emp_dict.keys()),label_visibility='collapsed')

            # Salary input
            with c2:
                st.markdown("##### Salary")
                salary = st.number_input("Salary", min_value=0.0, format="%.2f",label_visibility='collapsed')

            # Get current date
            payment_date = datetime.now().strftime("%Y-%m-%d")

            # Mark as Paid button
            if st.button("Mark as Paid"):
                emp_id = emp_dict[selected_emp]
                mark_as_paid(emp_id, month, year, salary, payment_date)  # Pass payment_date
                st.success(f"✅ {selected_emp} marked as paid for {month} {year} on {payment_date}")
                st.rerun()


        # Show already paid employees
        st.write("### Paid Employees")
        payroll_data = fetch_payroll(month, year)

        if payroll_data:
            paid_df = pd.DataFrame(payroll_data, columns=["Employee", "Salary", "Paid", "Payment Date"])

            # Convert Paid status (1 -> ✅, 0 -> ❌)
            paid_df['Paid'] = paid_df['Paid'].apply(lambda x: "✅" if x == 1 else "❌")

            # Display formatted table
            st.table(paid_df)

        else:
            st.warning(f"No payroll records found for {month} {year}.")


    elif choice == "View Payroll":
        st.subheader("Payroll History")

        # Month and Year selection
        months = ["January", "February", "March", "April", "May", "June", "July", 
                "August", "September", "October", "November", "December"]
        c1,c2 = st.columns(2)
        with c1:
            st.markdown('##### Select Month')
            month = st.selectbox("Select Month", months,label_visibility='collapsed')
        with c2:
            st.markdown('##### Enter Year')
            year = st.number_input("Enter Year", min_value=2000, max_value=2100, value=datetime.now().year,label_visibility='collapsed')

        # Fetch payroll data
        payroll_data = fetch_payroll(month, year)

        if payroll_data:
            st.write(f"### Payroll for {month} {year}")

            # Convert to DataFrame
            payroll_df = pd.DataFrame(payroll_data, columns=["Employee", "Salary", "Paid", "Payment Date"])


            # Format Salary column (remove decimal if whole number, otherwise show 2 decimals)
            payroll_df['Salary'] = payroll_df['Salary'].apply(lambda x: f"{x:.2f}" if x % 1 else f"{int(x)}")

            # Convert Paid status to ✅ for paid and ❌ for unpaid
            payroll_df['Paid'] = payroll_df['Paid'].apply(lambda x: "✅" if x else "❌")

            # Display formatted table
            st.table(payroll_df)
        else:
            st.warning(f"No payroll records found for {month} {year}.")


    elif choice == "Salary Slips":
        # New Salary Slips section
        st.subheader("Employee Salary Slips")
        
        # Filter controls
        months = ["January", "February", "March", "April", "May", "June", "July", 
                 "August", "September", "October", "November", "December"]
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('##### Select Month')
            selected_month = st.selectbox("Select Month", months,label_visibility='collapsed')
        
        with col2:
            st.markdown('##### Select Year')
            selected_year = st.number_input("Select Year", min_value=2000, max_value=2100, value=datetime.now().year,label_visibility='collapsed')
        
        # Fetch all paid employee records for the selected month and year
        paid_employees = fetch_paid_employees_details(selected_month, selected_year)
        
        if not paid_employees:
            st.warning(f"No paid employees found for {selected_month} {selected_year}")
        else:
            st.success(f"Found {len(paid_employees)} employee salary records for {selected_month} {selected_year}")
            
            # Create expandable sections for each employee
            for employee in paid_employees:
                with st.expander(f"👤 {employee['name']} - PKR {employee['salary']}", expanded=False):
                    # Create two columns for employee details and actions
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        # Display employee details
                        st.markdown(f"**Employee Name:** {employee['name']}")
                        st.markdown(f"**Salary Amount:** PKR {employee['salary']}")
                        st.markdown(f"**Payment Date:** {employee['payment_date']}")
                        st.markdown(f"**WhatsApp:** {employee['whatsapp_number'] or 'Not provided'}")
                    
                    with col2:
                        # Generate and download salary slip button
                        if st.button(f"📄 Download Slip", key=f"slip_{employee['id']}_{selected_month}"):
                            with st.spinner("Generating salary slip..."):
                                try:
                                    pdf_path = generate_salary_slip(
                                        employee['id'], 
                                        employee['name'],
                                        employee['whatsapp_number'],
                                        selected_month, 
                                        selected_year, 
                                        employee['salary'],
                                        employee['payment_date']
                                    )
                                    
                                    # Show success message
                                    st.success("✅ Salary slip generated!")
                                    
                                    # Create download button
                                    with open(pdf_path, "rb") as f:
                                        file_name = f"Salary_Slip_{employee['name'].replace(' ', '_')}_{selected_month}_{selected_year}.pdf"
                                        
                                        st.download_button(
                                            label="⬇️ Download PDF",
                                            data=f,
                                            file_name=file_name,
                                            mime="application/pdf",
                                            key=f"download_{employee['id']}_{selected_month}"
                                        )
                                    
                                    # Clean up temporary file
                                    os.remove(pdf_path)
                                    
                                except Exception as e:
                                    st.error(f"Error generating salary slip: {str(e)}")

def generate_salary_slip(employee_id, employee_name, whatsapp_number, month, year, salary, payment_date):
    """
    Generate a salary slip PDF for an employee
    
    Args:
        employee_id: Employee ID
        employee_name: Employee name
        whatsapp_number: Employee WhatsApp number
        month: Month of payment
        year: Year of payment
        salary: Salary amount
        payment_date: Date when payment was made
        
    Returns:
        str: Path to the generated PDF file
    """
    class SalarySlipPDF(FPDF):
        def __init__(self):
            super().__init__()
            self.page_width = 210  # A4 width in mm
            self.left_margin = 10
            self.right_margin = 10
            self.set_margins(self.left_margin, 10, self.right_margin)
            self.set_auto_page_break(auto=True, margin=15)
        
        def header(self):
            import os
            logo_path = "static/order_management.jpg"
            logo_width = 30
            logo_height = 15

            # Background bar
            header_bg_color = (54, 95, 145)  # Dark blue header
            self.set_fill_color(*header_bg_color)
            self.rect(0, 0, self.page_width, 25, style='F')  # full-width header bar

            # Add logo
            if os.path.exists(logo_path):
                try:
                    self.image(logo_path, x=self.left_margin, y=5, w=logo_width, h=logo_height)
                except RuntimeError as e:
                    print(f"Error loading image: {e}")

            # Company name and report title
            self.set_text_color(255, 255, 255)  # White text
            self.set_font('Arial', 'B', 16)
            self.set_xy(self.left_margin + logo_width + 5, 8)
            self.cell(0, 8, "HF DESIGN", ln=True)

            self.set_font('Arial', '', 11)
            self.set_x(self.left_margin + logo_width + 5)
            self.cell(0, 8, f"Salary Slip - {month} {year}", ln=True)

            # Reset text color and add some spacing
            self.set_text_color(0, 0, 0)
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            footer_color = (100, 100, 100)  # Gray
            self.set_text_color(*footer_color)
            self.cell(0, 10, f'Page {self.page_no()} - Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')
        
        def section_title(self, title):
            """Styled section title with underline"""
            self.set_font('Arial', 'B', 12)
            self.set_text_color(54, 95, 145)  # Dark blue
            self.cell(0, 8, title, 0, 1)
            self.set_draw_color(54, 95, 145)
            self.line(self.left_margin, self.get_y(), self.page_width - self.right_margin, self.get_y())
            self.ln(3)
            self.set_text_color(0, 0, 0)  # Reset to black
            
        def info_field(self, label, value, width_ratio=[1, 2]):
            """Display a field with label and value"""
            total_width = self.page_width - self.left_margin - self.right_margin
            label_width = total_width * (width_ratio[0] / sum(width_ratio))
            value_width = total_width * (width_ratio[1] / sum(width_ratio))
            
            self.set_font('Arial', 'B', 10)
            self.cell(label_width, 7, label, 0, 0)
            
            self.set_font('Arial', '', 10)
            self.cell(value_width, 7, str(value), 0, 1)
            
        def add_signature_section(self):
            """Add signature section at the bottom of the page"""
            self.ln(20)
            
            # Add signature lines
            self.set_draw_color(0, 0, 0)
            
            # Employee signature
            self.line(self.left_margin + 10, self.get_y(), self.left_margin + 70, self.get_y())
            self.set_font('Arial', '', 10)
            self.set_xy(self.left_margin + 10, self.get_y() + 2)
            self.cell(60, 5, "Employee Signature", 0, 0, 'C')
            
            # Employer signature
            x_pos = self.page_width - self.right_margin - 70
            self.line(x_pos, self.get_y() - 2, x_pos + 60, self.get_y() - 2)
            self.set_xy(x_pos, self.get_y())
            self.cell(60, 5, "Employer Signature", 0, 0, 'C')

    # Create PDF
    pdf = SalarySlipPDF()
    pdf.add_page()
    
    # Title for the salary slip
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, "SALARY SLIP", 0, 1, 'C')
    pdf.ln(5)
    
    # Employee Information Section
    pdf.section_title("Employee Information")
    pdf.set_font('Arial', '', 10)
    
    # Create a formatted table for employee info
    pdf.info_field("Employee Name:", employee_name)
    pdf.info_field("WhatsApp Number:", whatsapp_number if whatsapp_number else "N/A")
    pdf.info_field("Payment Period:", f"{month} {year}")
    pdf.info_field("Payment Date:", payment_date)
    pdf.ln(5)
    
    # Salary Details Section
    pdf.section_title("Salary Details")
    
    # Draw salary details with a clean table look
    # Header row
    pdf.set_fill_color(54, 95, 145)  # Dark blue
    pdf.set_text_color(255, 255, 255)  # White text
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(130, 8, "Description", 1, 0, 'L', True)
    pdf.cell(50, 8, "Amount (PKR)", 1, 1, 'R', True)
    
    # Reset text color
    pdf.set_text_color(0, 0, 0)
    
    # Basic salary row
    pdf.set_font('Arial', '', 10)
    pdf.cell(130, 8, "Basic Salary", 1, 0)
    pdf.cell(50, 8, f"{salary:,.2f}", 1, 1, 'R')
    
    # Total row with bold formatting
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(240, 240, 240)  # Light gray
    pdf.cell(130, 8, "Net Salary", 1, 0, 'L', True)
    pdf.cell(50, 8, f"{salary:,.2f}", 1, 1, 'R', True)
    
    # Notes section
    pdf.ln(10)
    pdf.section_title("Notes")
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, "* This is an official salary payment record.\n* All amounts are in Pakistani Rupees (PKR).\n* Please contact HR for any discrepancies.")
    
    # Add signature lines
    pdf.add_signature_section()
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(temp_file.name)
    return temp_file.name