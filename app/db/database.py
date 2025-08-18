from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()  # Load first!

DATABASE_URL = os.getenv("DATABASE_URL") 
print("DATABASE_URL =", DATABASE_URL)

engine = create_engine(DATABASE_URL)
Base = declarative_base()


def get_db():
    db = sessionmaker(bind=engine,expire_on_commit=False)()
    try:
        yield db
    finally:
        db.close()
