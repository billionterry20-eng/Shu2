
const API_BASE = '';

document.addEventListener('DOMContentLoaded', () => {
  loadStatistics();
  loadAccounts();
  loadTodayRecords();
  updateBeijingTime();
  setInterval(updateBeijingTime, 1000);
  setInterval(loadStatistics, 30000);
  setInterval(loadTodayRecords, 60000);
});

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'), 2600);
}

function updateBeijingTime() {
  const now = new Date();
  const beijing = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }));
  const str = beijing.toLocaleTimeString('zh-CN', { hour12:false });
  document.getElementById('beijing-time').textContent = str;
}

function loadStatistics() {
  fetch(`${API_BASE}/api/records/statistics`)
    .then(r=>r.json())
    .then(d=>{
      if (!d.success) return;
      document.getElementById('stat-total-accounts').textContent = d.data.accounts.total;
      document.getElementById('stat-enabled-accounts').textContent = d.data.accounts.enabled;
      document.getElementById('stat-today-success').textContent = d.data.today.success;
      document.getElementById('stat-today-failed').textContent = d.data.today.failed;
    })
    .catch(()=>{});
}

function loadAccounts() {
  fetch(`${API_BASE}/api/accounts`)
    .then(r=>r.json())
    .then(d=>{
      if (!d.success) return;
      renderAccounts(d.data || []);
    })
    .catch(()=>toast('加载账号失败'));
}

function renderAccounts(accounts) {
  const box = document.getElementById('accounts-list');
  if (!accounts.length) {
    box.innerHTML = '<div class="meta">暂无账号</div>';
    return;
  }
  box.innerHTML = accounts.map(a => `
    <div class="item">
      <div>
        <div><b>${escapeHtml(a.account)}</b></div>
        <div class="meta">步数：${Number(a.steps).toLocaleString()} ｜ 时间：${a.schedule_time}</div>
      </div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap; justify-content:flex-end;">
        <span class="tag ${a.enabled ? 'on':'off'}">${a.enabled ? '已启用':'已禁用'}</span>
        <button class="btn small secondary" onclick="editAccount(${a.id})">编辑</button>
        <button class="btn small" onclick="executeAccount(${a.id})">立即执行</button>
        <button class="btn small secondary" onclick="toggleAccount(${a.id})">切换</button>
        <button class="btn small danger" onclick="deleteAccount(${a.id})">删除</button>
      </div>
    </div>
  `).join('');
}

function resetForm() {
  document.getElementById('edit-account-id').value = '';
  document.getElementById('modal-account').value = '';
  document.getElementById('modal-password').value = '';
  document.getElementById('modal-steps').value = '89888';
  document.getElementById('modal-hour').value = '0';
  document.getElementById('modal-minute').value = '5';
}

function editAccount(id) {
  fetch(`${API_BASE}/api/accounts/${id}`)
    .then(r=>r.json())
    .then(d=>{
      if (!d.success) return toast(d.message || '读取失败');
      const a = d.data;
      document.getElementById('edit-account-id').value = a.id;
      document.getElementById('modal-account').value = a.account;
      document.getElementById('modal-password').value = a.password;
      document.getElementById('modal-steps').value = a.steps;
      document.getElementById('modal-hour').value = a.schedule_hour;
      document.getElementById('modal-minute').value = a.schedule_minute;
      toast('已载入，可修改后保存');
    })
    .catch(()=>toast('读取失败'));
}

function saveAccount() {
  const id = document.getElementById('edit-account-id').value;
  const account = document.getElementById('modal-account').value.trim();
  const password = document.getElementById('modal-password').value;
  const steps = parseInt(document.getElementById('modal-steps').value) || 89888;
  const hour = parseInt(document.getElementById('modal-hour').value) || 0;
  const minute = parseInt(document.getElementById('modal-minute').value) || 5;

  if (!account || !password) return toast('账号和密码不能为空');

  const payload = { account, password, steps, schedule_hour: hour, schedule_minute: minute, enabled: true };
  const url = id ? `${API_BASE}/api/accounts/${id}` : `${API_BASE}/api/accounts`;
  const method = id ? 'PUT' : 'POST';

  fetch(url, { method, headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
    .then(r=>r.json())
    .then(d=>{
      if (!d.success) return toast(d.message || '保存失败');
      toast('保存成功');
      resetForm();
      loadAccounts();
      loadStatistics();
    })
    .catch(()=>toast('保存失败'));
}

function toggleAccount(id) {
  fetch(`${API_BASE}/api/accounts/${id}/toggle`, { method:'POST' })
    .then(r=>r.json())
    .then(d=>{
      if (!d.success) return toast(d.message || '操作失败');
      toast(d.message || 'OK');
      loadAccounts();
      loadStatistics();
    })
    .catch(()=>toast('操作失败'));
}

function deleteAccount(id) {
  if (!confirm('确定删除该账号及其记录？')) return;
  fetch(`${API_BASE}/api/accounts/${id}`, { method:'DELETE' })
    .then(r=>r.json())
    .then(d=>{
      if (!d.success) return toast(d.message || '删除失败');
      toast('删除成功');
      loadAccounts();
      loadStatistics();
      loadTodayRecords();
    })
    .catch(()=>toast('删除失败'));
}

function executeAccount(id) {
  toast('正在执行...');
  fetch(`${API_BASE}/api/accounts/${id}/execute`, { method:'POST' })
    .then(r=>r.json())
    .then(d=>{
      toast(d.message || (d.success ? '执行成功' : '执行失败'));
      loadStatistics();
      loadTodayRecords();
    })
    .catch(()=>toast('执行失败'));
}

function executeAllAccounts() {
  if (!confirm('立即执行所有启用账号？')) return;
  toast('正在执行所有账号...');
  fetch(`${API_BASE}/api/accounts/execute-all`, { method:'POST' })
    .then(r=>r.json())
    .then(d=>{
      toast(d.message || (d.success ? '完成' : '部分失败'));
      loadStatistics();
      loadTodayRecords();
    })
    .catch(()=>toast('执行失败'));
}

function loadTodayRecords() {
  fetch(`${API_BASE}/api/records/today`)
    .then(r=>r.json())
    .then(d=>{
      if (!d.success) return;
      const rows = (d.data || []).map(rec => `
        <tr>
          <td>${escapeHtml(rec.account_name)}</td>
          <td>${Number(rec.steps).toLocaleString()}</td>
          <td>${escapeHtml(rec.status)}</td>
          <td>${escapeHtml(rec.message || '-')}</td>
          <td>${escapeHtml(rec.created_at)}</td>
        </tr>
      `).join('');
      document.getElementById('records-list').innerHTML = rows || '<tr><td colspan="5" style="color:#9fb0cf;padding:14px;">暂无记录</td></tr>';
    })
    .catch(()=>{});
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}
