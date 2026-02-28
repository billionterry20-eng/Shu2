
# 步数定时提交（Flask + Render）

## 功能
- 默认账号：Tbh2356@163.com / 112233qq（可用环境变量覆盖）
- 默认：北京时间 00:05 自动提交，默认步数 89888
- 多账号管理：每个账号独立步数、独立定时（Cron），互不冲突（同账号 `max_instances=1` 防重叠）
- 记录每次提交结果（成功/失败/时间/信息）

## 部署到 Render（Web Service）
1. 新建 Web Service，连接 GitHub 仓库
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2`
   - ⚠️ workers 必须 1（否则多个进程会重复定时）
4. Environment（可选）：
   - `BUSHU_URL`：默认 `http://8.140.250.130/bushu/`
   - `BUSHU_POST_URL`：如果实际提交地址不是同一个 URL，在这里填真实 POST 地址
   - `FIELD_ACCOUNT` / `FIELD_PASSWORD` / `FIELD_STEPS`：远端表单字段名（默认 xmphone/xmpwd/steps）
   - `DEFAULT_ACCOUNT` / `DEFAULT_PASSWORD`：覆盖默认账号密码
   - `DEFAULT_STEPS`：覆盖默认步数（默认 89888）
   - `DEFAULT_SCHEDULE_HOUR` / `DEFAULT_SCHEDULE_MINUTE`：覆盖默认时间（默认 0/5）
   - `DATABASE_URL`：Render Postgres 可自动注入；不填则用 sqlite

## 本地运行
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

打开 http://127.0.0.1:5000

## 说明
我无法在当前对话环境里直接访问你的远端步数站点做“实际提交成功”验证（网络不可用/不可控）。
所以项目内做了：
- `/api/test` 测试接口（前端可用），会把远端返回的状态码、关键文本记录下来，方便你现场确认。
- 每次提交会写入提交记录，可从网页查看“今日记录”。
