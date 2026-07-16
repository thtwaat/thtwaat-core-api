import warnings; warnings.filterwarnings('ignore')
import app.companies.model; import app.users.model; import app.auth.model
import app.apps.model; import app.storage.model; import app.notifications.model
import app.payments.model; import app.ai.model; import app.products.model
import app.api_keys.model; import app.webhooks.model; import app.features.ai_platform.database.models

from app.database.database import SessionLocal
from app.users.model import User
from app.companies.model import Company
from app.auth.service import AuthService

db = SessionLocal()
# Find qa@thtwaat.com user
user = db.query(User).filter(User.email == 'qa@thtwaat.com').first()
if user:
    print(f'Found: {user.email}')
    print(f'Hash type: {user.hashed_password[:10]}')
    svc = AuthService(db)
    test_passwords = ["Admin123!", "admin123", "password123", "Test1234!", "qatest123", "thtwaat123"]
    for pw in test_passwords:
        result = svc.verify_password(pw, user.hashed_password)
        print(f'  {pw}: {result}')
else:
    print('User not found')

# Also list companies
companies = db.query(Company).all()
print(f'\nCompanies: {len(companies)}')
for c in companies:
    print(f'  {c.name} | {c.slug}')
db.close()
