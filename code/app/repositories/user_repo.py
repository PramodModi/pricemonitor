import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models.user import User


class UserRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.scalar(
            select(User).where(User.email == email.strip().lower())
        )

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return self.db.get(User, user_id)

    def create(self, email: str) -> User:
        user = User(email=email.strip().lower())
        self.db.add(user)
        self.db.flush()
        return user

    def get_or_create(self, email: str) -> tuple[User, bool]:
        user = self.get_by_email(email)
        if user:
            return user, False
        user = self.create(email)
        return user, True