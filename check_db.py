import sys
sys.path.append('.')
from app.database.database import SessionLocal
from app.users.model import User
from app.companies.model import Company
from app.auth.model import RefreshToken, OTPCode, MFASettings
from app.billing.model import StripeSubscription
from app.notifications.model import Notification


def main():
    db = SessionLocal()
    users = db.query(User).all()
    print("USERS IN DATABASE:")
    for u in users:
        print(f'User: {u.email}, Password hash: {u.hashed_password}')

if __name__ == "__main__":
    main()
