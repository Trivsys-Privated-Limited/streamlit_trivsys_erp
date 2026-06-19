# utils.py

def log_activity(activity, page):
    from database import insert_activity_log
    insert_activity_log(activity, page)
