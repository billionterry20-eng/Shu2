
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

from scheduler import SchedulerService

TZ = ZoneInfo("Asia/Shanghai")

db = SQLAlchemy()

def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///bushu.db")
    # Render uses "postgres://" sometimes; SQLAlchemy expects "postgresql://"
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_AS_ASCII"] = False

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    db.init_app(app)

    from models import Account, SubmitRecord  # noqa

    scheduler_service = SchedulerService(db=db, tz=TZ)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "time": datetime.now(TZ).isoformat()})

    # -------------------- Accounts API --------------------
    @app.get("/api/accounts")
    def list_accounts():
        accounts = Account.query.order_by(Account.id.desc()).all()
        return jsonify({"success": True, "data": [a.to_dict() for a in accounts]})

    @app.post("/api/accounts")
    def create_account():
        data = request.get_json(force=True)
        account = Account(
            account=data.get("account", "").strip(),
            password=data.get("password", ""),
            steps=int(data.get("steps", 89888)),
            schedule_hour=int(data.get("schedule_hour", 0)),
            schedule_minute=int(data.get("schedule_minute", 5)),
            enabled=bool(data.get("enabled", True)),
        )
        if not account.account or not account.password:
            return jsonify({"success": False, "message": "账号和密码不能为空"}), 400

        db.session.add(account)
        db.session.commit()

        scheduler_service.sync_account_jobs()
        return jsonify({"success": True, "message": "账号添加成功", "data": account.to_dict()})

    @app.get("/api/accounts/<int:account_id>")
    def get_account(account_id: int):
        account = Account.query.get_or_404(account_id)
        return jsonify({"success": True, "data": account.to_dict(include_password=True)})

    @app.put("/api/accounts/<int:account_id>")
    def update_account(account_id: int):
        account = Account.query.get_or_404(account_id)
        data = request.get_json(force=True)

        account.account = data.get("account", account.account).strip()
        account.password = data.get("password", account.password)
        account.steps = int(data.get("steps", account.steps))
        account.schedule_hour = int(data.get("schedule_hour", account.schedule_hour))
        account.schedule_minute = int(data.get("schedule_minute", account.schedule_minute))
        account.enabled = bool(data.get("enabled", account.enabled))

        if not account.account or not account.password:
            return jsonify({"success": False, "message": "账号和密码不能为空"}), 400

        db.session.commit()
        scheduler_service.sync_account_jobs()
        return jsonify({"success": True, "message": "账号更新成功", "data": account.to_dict()})

    @app.delete("/api/accounts/<int:account_id>")
    def delete_account(account_id: int):
        account = Account.query.get_or_404(account_id)
        # delete records too
        SubmitRecord.query.filter_by(account_id=account.id).delete()
        db.session.delete(account)
        db.session.commit()

        scheduler_service.sync_account_jobs()
        return jsonify({"success": True, "message": "账号删除成功"})

    @app.post("/api/accounts/<int:account_id>/toggle")
    def toggle_account(account_id: int):
        account = Account.query.get_or_404(account_id)
        account.enabled = not account.enabled
        db.session.commit()

        scheduler_service.sync_account_jobs()
        return jsonify({"success": True, "message": "已启用" if account.enabled else "已禁用", "data": account.to_dict()})

    @app.post("/api/accounts/<int:account_id>/execute")
    def execute_account(account_id: int):
        data = request.get_json(silent=True) or {}
        steps = data.get("steps")
        result = scheduler_service.execute_now(account_id=account_id, steps=steps)
        status_code = 200 if result.get("success") else 500
        return jsonify(result), status_code

    @app.post("/api/accounts/execute-all")
    def execute_all():
        result = scheduler_service.execute_all_now()
        status_code = 200 if result.get("success") else 500
        return jsonify(result), status_code

    # -------------------- Records API --------------------
    @app.get("/api/records/today")
    def records_today():
        start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
        records = SubmitRecord.query.filter(SubmitRecord.created_at >= start, SubmitRecord.created_at <= end).order_by(SubmitRecord.id.desc()).limit(200).all()
        return jsonify({"success": True, "data": [r.to_dict() for r in records]})

    @app.get("/api/records")
    def records_all():
        limit = int(request.args.get("limit", 200))
        records = SubmitRecord.query.order_by(SubmitRecord.id.desc()).limit(limit).all()
        return jsonify({"success": True, "data": [r.to_dict() for r in records]})

    @app.get("/api/records/statistics")
    def statistics():
        from sqlalchemy import func
        total = Account.query.count()
        enabled = Account.query.filter_by(enabled=True).count()

        start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
        today_success = SubmitRecord.query.filter(SubmitRecord.created_at >= start, SubmitRecord.created_at <= end, SubmitRecord.status == "success").count()
        today_failed = SubmitRecord.query.filter(SubmitRecord.created_at >= start, SubmitRecord.created_at <= end, SubmitRecord.status == "failed").count()

        return jsonify({
            "success": True,
            "data": {
                "accounts": {"total": total, "enabled": enabled},
                "today": {"success": today_success, "failed": today_failed}
            }
        })

    @app.post("/api/test")
    def test_submit():
        data = request.get_json(force=True)
        account = data.get("account", "").strip()
        password = data.get("password", "")
        steps = int(data.get("steps", 89888))
        if not account or not password:
            return jsonify({"success": False, "message": "账号和密码不能为空"}), 400
        res = scheduler_service.submit_to_remote(account=account, password=password, steps=steps)
        return jsonify(res), (200 if res.get("success") else 500)

    # -------------------- Startup init --------------------
    with app.app_context():
        db.create_all()

        # seed default account from env or hardcoded (as requested)
        default_account = os.getenv("DEFAULT_ACCOUNT", "Tbh2356@163.com")
        default_password = os.getenv("DEFAULT_PASSWORD", "112233qq")
        from models import Account
        if Account.query.count() == 0:
            a = Account(
                account=default_account,
                password=default_password,
                steps=int(os.getenv("DEFAULT_STEPS", "89888")),
                schedule_hour=int(os.getenv("DEFAULT_SCHEDULE_HOUR", "0")),
                schedule_minute=int(os.getenv("DEFAULT_SCHEDULE_MINUTE", "5")),
                enabled=True,
            )
            db.session.add(a)
            db.session.commit()

        # Start scheduler & sync jobs once app is ready
        scheduler_service.start()
        scheduler_service.sync_account_jobs()

    return app

app = create_app()
