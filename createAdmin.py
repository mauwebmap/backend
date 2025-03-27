import argparse
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.users.models import Admin
from app.users.dependencies.auth import get_password_hash


def create_initial_admin(username: str, password: str):
    db = SessionLocal()
    try:
        existing_admin = db.query(Admin).filter(
            Admin.username == username
        ).first()

        if existing_admin:
            print(f"🟢 Admin {username} already exists")
            return

        hashed_password = get_password_hash(password)
        new_admin = Admin(
            username=username,
            hashed_password=hashed_password,
            is_admin=True,
            is_active=True
        )

        db.add(new_admin)
        db.commit()
        print(f"✅ Admin {username} created successfully")

    except Exception as e:
        db.rollback()
        print(f"🔴 Error: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)

    args = parser.parse_args()
    create_initial_admin(args.username, args.password)