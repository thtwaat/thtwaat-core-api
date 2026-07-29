import sys  
sys.path.append('.')  
from app.database.database import SessionLocal  
from app.users.model import User  
db = SessionLocal()  
u = db.query(User).filter(User.email=='admin@thtwaat.com').first()  
print(f'User: {u.email}, Active: {u.is_active}, Status: {u.status}')  
