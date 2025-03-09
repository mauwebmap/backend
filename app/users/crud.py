
from sqlalchemy.orm import Session
from app.users.models.models import Admin

def get_admin_by_username(db: Session, username: str):
    return db.query(Admin).filter(Admin.username == username).first()