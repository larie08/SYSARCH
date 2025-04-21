from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    idno = Column(Integer, primary_key=True)
    lastname = Column(String, nullable=False)
    firstname = Column(String, nullable=False)
    middlename = Column(String)
    course = Column(String, nullable=False)
    year_level = Column(Integer, nullable=False)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    sessions = Column(Integer)
    address = Column(String)
    photo = Column(String)

class Reservation(Base):
    __tablename__ = 'reservations'
    
    id = Column(Integer, primary_key=True)
    idno = Column(Integer, ForeignKey('users.idno'), nullable=False)
    purpose = Column(String, nullable=False)
    lab = Column(String, nullable=False)
    time_in = Column(DateTime, nullable=False, default=datetime.utcnow)
    time_out = Column(DateTime)
    status = Column(String, default='Pending')