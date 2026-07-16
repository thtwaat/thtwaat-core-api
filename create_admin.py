"""
Script to create a stable admin user for THTWAAT platform QA/testing.
Creates admin@thtwaat.com with password Admin123! using proper bcrypt hash.
"""
import warnings; warnings.filterwarnings('ignore')
import app.companies.model; import app.users.model; import app.auth.model
import app.apps.model; import app.storage.model; import app.notifications.model
import app.payments.model; import app.ai.model; import app.products.model
import app.api_keys.model; import app.webhooks.model; import app.features.ai_platform.database.models

from app.database.database import SessionLocal
from app.users.model import User, UserStatus
from app.companies.model import Company
from app.auth.service import AuthService
from app.rbac.enums import EnterpriseRole
from sqlalchemy import select

db = SessionLocal()

# Check if QA company already exists
stmt = select(Company).where(Company.slug == 'qa-test-co-001')
qa_company = db.scalar(stmt)

if not qa_company:
    print("QA company not found - finding first available company...")
    qa_company = db.query(Company).first()

print(f"Using company: {qa_company.name} ({qa_company.slug}) id={qa_company.id}")

svc = AuthService(db)

# Check if admin user already exists
stmt = select(User).where(User.email == 'admin@thtwaat.com')
existing_admin = db.scalar(stmt)

if existing_admin:
    print(f"Admin user already exists: {existing_admin.email}")
    # Update password to bcrypt
    existing_admin.hashed_password = svc.get_password_hash("Admin123!")
    db.commit()
    print("Password updated to Admin123! (bcrypt)")
else:
    # Create new admin user
    new_admin = User(
        company_id=qa_company.id,
        email='admin@thtwaat.com',
        hashed_password=svc.get_password_hash("Admin123!"),
        first_name='Admin',
        last_name='THTWAAT',
        role=EnterpriseRole.ADMIN,
        status=UserStatus.ACTIVE,
        is_active=True,
        email_verified=True,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    print(f"Created admin user: admin@thtwaat.com | password: Admin123! | id: {new_admin.id}")

# Also fix qa@thtwaat.com dummy_hash
stmt = select(User).where(User.email == 'qa@thtwaat.com')
qa_user = db.scalar(stmt)
if qa_user:
    qa_user.hashed_password = svc.get_password_hash("QaTest123!")
    db.commit()
    print(f"Fixed qa@thtwaat.com password to QaTest123! (bcrypt)")

# Verify login works
print("\n--- Verifying login ---")
stmt = select(User).where(User.email == 'admin@thtwaat.com')
admin = db.scalar(stmt)
if admin:
    print(f"Admin found: {admin.email} | status: {admin.status} | is_active: {admin.is_active}")
    ok = svc.verify_password("Admin123!", admin.hashed_password)
    print(f"Password Admin123! verifies: {ok}")

db.close()
print("\nDone!")
