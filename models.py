
from datetime import datetime
from zoneinfo import ZoneInfo

from app import db, TZ

class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(200), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    steps = db.Column(db.Integer, nullable=False, default=89888)
    schedule_hour = db.Column(db.Integer, nullable=False, default=0)
    schedule_minute = db.Column(db.Integer, nullable=False, default=5)
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(TZ))

    def to_dict(self, include_password=False):
        d = {
            "id": self.id,
            "account": self.account,
            "steps": self.steps,
            "schedule_hour": self.schedule_hour,
            "schedule_minute": self.schedule_minute,
            "schedule_time": f"{int(self.schedule_hour):02d}:{int(self.schedule_minute):02d}",
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_password:
            d["password"] = self.password
        return d


class SubmitRecord(db.Model):
    __tablename__ = "submit_records"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    account_name = db.Column(db.String(200), nullable=False)

    steps = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # success / failed
    message = db.Column(db.Text, nullable=True)
    raw = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(TZ))

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "steps": self.steps,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
