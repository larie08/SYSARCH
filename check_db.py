from database import engine
from sqlalchemy import inspect

def check_tables():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("Existing tables:", tables)
    
    for table in tables:
        print(f"\nColumns in {table}:")
        for column in inspector.get_columns(table):
            print(f"- {column['name']}: {column['type']}")

if __name__ == "__main__":
    check_tables()