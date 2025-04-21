import sqlite3
from models import User, Reservation
from database import db_session

def migrate_data():
    # Connect to SQLite database
    sqlite_conn = sqlite3.connect('users.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    try:
        # Migrate users
        sqlite_cursor.execute("SELECT * FROM users")
        users = sqlite_cursor.fetchall()
        for user in users:
            new_user = User(
                idno=user[0],
                lastname=user[1],
                firstname=user[2],
                middlename=user[3],
                course=user[4],
                year_level=user[5],
                email=user[6],
                username=user[7],
                password=user[8],
                sessions=user[9],
                address=user[10],
                photo=user[11]
            )
            db_session.add(new_user)
        
        # Migrate reservations
        sqlite_cursor.execute("SELECT * FROM reservations")
        reservations = sqlite_cursor.fetchall()
        for reservation in reservations:
            new_reservation = Reservation(
                id=reservation[0],
                idno=reservation[1],
                purpose=reservation[2],
                lab=reservation[3],
                time_in=reservation[4],
                time_out=reservation[5],
                status=reservation[6]
            )
            db_session.add(new_reservation)
        
        db_session.commit()
        print("Data migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        db_session.rollback()
    finally:
        sqlite_conn.close()
        db_session.remove()

if __name__ == "__main__":
    migrate_data()