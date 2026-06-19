from zk import ZK, const
from datetime import datetime, timedelta
from database import get_db_connection
from pyzk.zk.attendance import Attendance

class ZKDevice:
    def __init__(self, ip='192.168.100.240', port=4370):
        self.ip = ip
        self.port = port
        self.zk = ZK(self.ip, port=self.port)  # Connect directly with IP and port
        self.connection = None

    def connect(self):
        """Connect to the ZKTeco device"""
        try:
            self.connection = self.zk.connect()
            if self.connection:
                print("Successfully connected to device")
                return True
            print("Connection failed")
            return False
        except Exception as e:
            print(f"Device connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from the device"""
        if self.connection:
            self.zk.disconnect()
            print("Disconnected from device")

    def fetch_attendance(self):
        """Fetch attendance records from the device"""
        if not self.connect():
            return []

        try:
            # Get all attendance records
            attendance = self.zk.get_attendance()
            print(f"Attendance data type: {type(attendance)}")
            if len(attendance) > 0:
                print(f"First record type: {type(attendance[0])}")
            print(f"Attendance data: {attendance}")
            
            if isinstance(attendance, list):
                if attendance:
                    print(f"Fetched {len(attendance)} attendance records")
                    return attendance
                print("No attendance records found")
                return []
            else:
                print("Attendance is not a list. Structure needs to be handled differently.")
                return []
        except Exception as e:
            print(f"Error fetching attendance: {e}")
            return []
        finally:
            self.disconnect()


    def sync_with_database(self):
        """Sync device attendance with database"""
        device_attendance = self.fetch_attendance()
        if not device_attendance:
            return False

        conn = get_db_connection()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            synced_count = 0

            # Group all punches by user and date
            attendance_by_user_date = {}
            for record in device_attendance:
                user_id = record.user_id
                timestamp = record.timestamp

                # Convert timestamp if needed
                if not isinstance(timestamp, datetime):
                    timestamp = datetime.fromtimestamp(timestamp)

                # Filter only recent records (last 90 days)
                if timestamp < datetime.today() - timedelta(days=90):
                    continue

                date_key = (user_id, timestamp.date())
                
                if date_key not in attendance_by_user_date:
                    attendance_by_user_date[date_key] = {
                        'punches': [timestamp]
                    }
                else:
                    # Add this punch to the list
                    attendance_by_user_date[date_key]['punches'].append(timestamp)

            # Process the grouped attendance
            for (user_id, date), data in attendance_by_user_date.items():
                # Sort punches chronologically
                punches = sorted(data['punches'])
                
                # Set check-in to first punch of the day
                check_in = punches[0]
                
                # Set check-out to last punch of the day
                # But only if there's more than one punch, otherwise NULL
                check_out = punches[-1] if len(punches) > 1 else None

                # Check for duplicate entry
                cursor.execute(
                    "SELECT id FROM attendance WHERE employee_id = %s AND DATE(check_in_time) = %s",
                    (user_id, date)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    cursor.execute(
                        """
                        UPDATE attendance 
                        SET check_in_time = %s, check_out_time = %s 
                        WHERE employee_id = %s AND DATE(check_in_time) = %s
                        """,
                        (check_in, check_out, user_id, date)
                    )
                else:
                    # Insert new record
                    cursor.execute(
                        """
                        INSERT INTO attendance 
                        (employee_id, status, check_in_time, check_out_time, date) 
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (user_id, 'Present', check_in, check_out, date)
                    )
                synced_count += 1

            conn.commit()
            print(f"Successfully synced {synced_count} attendance records")
            return True
        except Exception as e:
            print(f"Error syncing attendance: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()




    def _convert_pyzkdatetime(self, zk_timestamp):
        """Convert pyzk device timestamp to Python datetime"""
        return datetime.fromtimestamp(zk_timestamp)

    def get_users(self):
        """Get all users from the device"""
        if not self.connect():
            return []

        try:
            # The correct method is get_users() not get_user()
            users = self.connection.get_users()
            return users
        except Exception as e:
            print(f"Error fetching users: {e}")
            return []
        finally:
            self.disconnect()