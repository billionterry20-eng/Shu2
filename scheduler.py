
import os
import threading
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from models import Account, SubmitRecord

class SchedulerService:
    """
    One scheduler for the whole app (single Gunicorn worker recommended).
    Each account has its own job id: acct_<id>
    """
    def __init__(self, db, tz: ZoneInfo):
        self.db = db
        self.tz = tz
        self._scheduler = BackgroundScheduler(timezone=str(tz))
        self._lock = threading.Lock()
        self._started = False

    @property
    def scheduler(self):
        return self._scheduler

    def start(self):
        with self._lock:
            if self._started:
                return
            self._scheduler.start(paused=False)
            self._started = True
            logging.info("Scheduler started.")

    def sync_account_jobs(self):
        """
        Ensure scheduler jobs match DB accounts: add/update/remove.
        """
        with self._lock:
            accounts = Account.query.all()
            desired_ids = set()
            for acc in accounts:
                job_id = f"acct_{acc.id}"
                desired_ids.add(job_id)
                # remove if disabled
                if not acc.enabled:
                    if self._scheduler.get_job(job_id):
                        self._scheduler.remove_job(job_id)
                    continue

                trigger = CronTrigger(hour=acc.schedule_hour, minute=acc.schedule_minute, timezone=str(self.tz))
                existing = self._scheduler.get_job(job_id)

                if existing:
                    # reschedule if time changed
                    existing.reschedule(trigger=trigger)
                else:
                    self._scheduler.add_job(
                        func=self._run_job,
                        trigger=trigger,
                        id=job_id,
                        args=[acc.id],
                        replace_existing=True,
                        max_instances=1,   # prevent overlap for the same account
                        coalesce=True,
                        misfire_grace_time=60 * 10,
                    )
            # cleanup removed accounts
            for job in self._scheduler.get_jobs():
                if job.id.startswith("acct_") and job.id not in desired_ids:
                    self._scheduler.remove_job(job.id)

            logging.info("Scheduler jobs synced. jobs=%s", [j.id for j in self._scheduler.get_jobs()])

    def _run_job(self, account_id: int):
        """
        Called by APScheduler thread.
        """
        try:
            self.execute_now(account_id=account_id, steps=None, from_scheduler=True)
        except Exception as e:
            logging.exception("Job crashed for account_id=%s: %s", account_id, e)

    # ---------------- Submission ----------------
    def submit_to_remote(self, account: str, password: str, steps: int) -> Dict[str, Any]:
        """
        Submits steps to the remote 'bushu' site.

        Because the remote site is not publicly indexed and may change,
        we implement a robust form-post strategy with configurable field names.
        """
        base_url = os.getenv("BUSHU_URL", "http://8.140.250.130/bushu/")
        timeout = int(os.getenv("REQUEST_TIMEOUT", "20"))

        # Field names can be overridden if the remote site uses different ones.
        # Defaults are based on the user's provided page source:
        #   xmphone - account, xmpwd - password, steps - steps
        field_account = os.getenv("FIELD_ACCOUNT", "xmphone")
        field_password = os.getenv("FIELD_PASSWORD", "xmpwd")
        field_steps = os.getenv("FIELD_STEPS", "steps")

        # Some sites require posting to a specific endpoint.
        post_url = os.getenv("BUSHU_POST_URL", base_url)

        payload = {
            field_account: account,
            field_password: password,
            field_steps: str(steps),
        }

        headers = {
            "User-Agent": os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; RenderBot/1.0)"),
            "Accept": "*/*",
        }

        try:
            # If remote requires cookies / a first GET, enable it.
            use_session = os.getenv("USE_SESSION", "1") == "1"
            if use_session:
                with requests.Session() as s:
                    s.headers.update(headers)
                    # best-effort warmup GET (ignore failure)
                    try:
                        s.get(base_url, timeout=timeout, allow_redirects=True)
                    except Exception:
                        pass
                    r = s.post(post_url, data=payload, timeout=timeout, allow_redirects=True)
            else:
                r = requests.post(post_url, data=payload, headers=headers, timeout=timeout, allow_redirects=True)

            text = r.text or ""
            ok = r.status_code == 200 and ("成功" in text or "success" in text.lower())
            # If site returns JSON, try parse
            try:
                j = r.json()
                # common patterns
                if isinstance(j, dict):
                    if j.get("success") is True or j.get("code") in (0, 200) or j.get("status") in ("ok", "success"):
                        ok = True
            except Exception:
                pass

            msg = "提交成功" if ok else f"服务器返回错误: {r.status_code}"
            return {
                "success": bool(ok),
                "message": msg,
                "status_code": r.status_code,
                "raw": (text[:3000] if text else "")  # truncate
            }
        except Exception as e:
            return {"success": False, "message": f"请求异常: {e}", "status_code": None, "raw": ""}

    def execute_now(self, account_id: int, steps: Optional[int] = None, from_scheduler: bool = False) -> Dict[str, Any]:
        acc = Account.query.get(account_id)
        if not acc:
            return {"success": False, "message": "账号不存在"}

        use_steps = int(steps) if steps is not None else int(acc.steps)

        res = self.submit_to_remote(account=acc.account, password=acc.password, steps=use_steps)

        status = "success" if res.get("success") else "failed"
        record = SubmitRecord(
            account_id=acc.id,
            account_name=acc.account,
            steps=use_steps,
            status=status,
            message=res.get("message"),
            raw=res.get("raw"),
        )
        self.db.session.add(record)
        self.db.session.commit()

        if from_scheduler:
            logging.info("Scheduled submit: %s steps=%s status=%s", acc.account, use_steps, status)
        else:
            logging.info("Manual submit: %s steps=%s status=%s", acc.account, use_steps, status)

        return {
            "success": res.get("success", False),
            "message": res.get("message", "unknown"),
            "account": acc.account,
            "steps": use_steps,
        }

    def execute_all_now(self) -> Dict[str, Any]:
        accounts = Account.query.filter_by(enabled=True).all()
        results = []
        ok_all = True
        for acc in accounts:
            r = self.execute_now(account_id=acc.id)
            results.append(r)
            if not r.get("success"):
                ok_all = False
        return {"success": ok_all, "message": "执行完成", "results": results}
