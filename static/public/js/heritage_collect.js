// ── 全局状态 ────────────────────────────────────────────────
const selectedFiles = [];   // 维护已选照片文件列表（File 对象）

// ── 屏幕比例与方向自适配 ─────────────────────────────────────
function applyAdaptiveLayout() {
  const w = window.innerWidth || document.documentElement.clientWidth;
  const h = window.innerHeight || document.documentElement.clientHeight || 1;
  const ratio = w / h;
  const isLandscape = ratio > 1;
  const isDesktop = w >= 1024 || (w >= 900 && ratio >= 1.25);
  document.body.setAttribute('data-device', isDesktop ? 'desktop' : 'mobile');
  document.body.setAttribute('data-orientation', isLandscape ? 'landscape' : 'portrait');
}

// ── Toast 通知 ─────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 3000) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `show ${type}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = ''; }, duration);
}

// ── 获取当前 GPS 位置 ────────────────────────────────────────
function fetchLocation() {
  if (!navigator.geolocation) {
    showToast('当前浏览器不支持 GPS 定位', 'error');
    return;
  }

  const btn      = document.getElementById('btn-gps');
  const btnText  = document.getElementById('btn-gps-text');
  const badge    = document.getElementById('gps-status');

  btn.disabled = true;
  btnText.textContent = '定位中…';
  badge.className = 'gps-badge loading';
  badge.textContent = '定位中…';

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { longitude, latitude, altitude, accuracy } = pos.coords;
      document.getElementById('longitude').value = longitude.toFixed(8);
      document.getElementById('latitude').value  = latitude.toFixed(8);
      if (altitude !== null) {
        document.getElementById('altitude').value = altitude.toFixed(2);
      }
      document.getElementById('accuracy').value = `±${accuracy.toFixed(1)} m`;

      badge.className = 'gps-badge ok';
      badge.textContent = `已定位 ±${accuracy.toFixed(0)}m`;
      btnText.textContent = '重新获取';
      btn.disabled = false;

      // 清除错误提示
      const errEl = document.getElementById('err-location');
      if (errEl) { errEl.classList.add('hidden'); errEl.textContent = ''; }
      showToast('GPS 定位成功！', 'success', 2000);
    },
    (err) => {
      badge.className = 'gps-badge error';
      const messages = {
        1: '用户拒绝了定位权限，请在浏览器设置中开启',
        2: 'GPS 信号不可用，请移至开阔区域重试',
        3: '定位超时，请检查网络或重试',
      };
      badge.textContent = '定位失败';
      btnText.textContent = '重试定位';
      btn.disabled = false;
      showToast(messages[err.code] || '定位失败', 'error', 4000);
    },
    {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 10000,
    }
  );
}

// ── 照片选择处理 ─────────────────────────────────────────────
function handlePhotoSelect(input) {
  const MAX = 10;
  const newFiles = Array.from(input.files);

  for (const file of newFiles) {
    if (selectedFiles.length >= MAX) {
      showToast(`最多上传 ${MAX} 张照片`, 'info');
      break;
    }
    if (!file.type.startsWith('image/')) {
      showToast(`"${file.name}" 不是图片文件，已跳过`, 'error');
      continue;
    }
    selectedFiles.push(file);
    renderPreview(file, selectedFiles.length - 1);
  }

  input.value = '';
  updatePhotoCount();
}

function renderPreview(file, index) {
  const area  = document.getElementById('photo-preview-area');
  const addBtn = area.querySelector('.add-photo-btn');
  const reader = new FileReader();
  reader.onload = (e) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'preview-wrapper';
    wrapper.dataset.index = index;
    wrapper.innerHTML = `
      <img src="${e.target.result}" alt="预览" />
      ${index === 0 ? '<span style="position:absolute;bottom:2px;left:2px;background:rgba(0,0,0,.5);color:#fff;font-size:10px;padding:1px 5px;border-radius:4px;">封面</span>' : ''}
      <button class="remove-photo" onclick="removePhoto(${index})" title="移除">×</button>
    `;
    area.insertBefore(wrapper, addBtn);
  };
  reader.readAsDataURL(file);
}

function removePhoto(index) {
  selectedFiles.splice(index, 1);
  const area   = document.getElementById('photo-preview-area');
  area.querySelectorAll('.preview-wrapper').forEach(el => el.remove());
  selectedFiles.forEach((f, i) => renderPreview(f, i));
  updatePhotoCount();
}

function updatePhotoCount() {
  document.getElementById('photo-count').textContent = `已选 ${selectedFiles.length} 张`;
}

// ── 表单提交 ─────────────────────────────────────────────────
async function submitForm() {
  document.querySelectorAll('[id^="err-"]').forEach(el => {
    el.classList.add('hidden');
    el.textContent = '';
  });

  const btn  = document.getElementById('btn-submit');
  const icon = document.getElementById('submit-icon');
  const text = document.getElementById('submit-text');

  btn.disabled = true;
  icon.classList.add('spinner');
  text.textContent = '提交中…';

  const fd = new FormData();
  const fields = [
    'survey_code', 'name', 'former_name', 'era', 'category', 'heritage_type',
    'longitude', 'latitude', 'coordinate_system', 'altitude', 'area',
    'province', 'city', 'county', 'township', 'village', 'address',
    'protection_level', 'ownership', 'preservation_status',
    'damage_cause', 'threat_factors', 'description',
  ];
  for (const id of fields) {
    const el = document.getElementById(id);
    if (el) {
      fd.append(id, el.value);
    }
  }
  for (const file of selectedFiles) {
    fd.append('photos', file, file.name);
  }

  fd.append('csrfmiddlewaretoken', getCsrf());

  try {
    const res  = await fetch(window.location.href, { method: 'POST', body: fd });
    const data = await res.json();

    if (data.success) {
      document.getElementById('success-msg').textContent = data.message;
      document.getElementById('success-modal').classList.remove('hidden');
      if (data.photo_warnings && data.photo_warnings.length) {
        showToast('部分照片处理异常：\n' + data.photo_warnings.join('\n'), 'error', 6000);
      }
    } else {
      if (data.errors) {
        for (const [field, msg] of Object.entries(data.errors)) {
          const errEl = document.getElementById(`err-${field}`);
          if (errEl) {
            errEl.textContent = msg;
            errEl.classList.remove('hidden');
          } else {
            showToast(`${field}：${msg}`, 'error');
          }
        }
      }
      showToast(data.message || '提交失败，请检查表单', 'error', 4000);
    }
  } catch (e) {
    showToast('网络错误，请稍后重试', 'error', 4000);
  } finally {
    btn.disabled = false;
    icon.classList.remove('spinner');
    text.textContent = '提交采集数据';
  }
}

// ── 表单重置（继续采集） ──────────────────────────────────────
function resetForm() {
  document.getElementById('success-modal').classList.add('hidden');

  const keepFields = ['province', 'city', 'county', 'township', 'village', 'collect_unit'];
  const allInputs = document.querySelectorAll('input:not([readonly]), select, textarea');
  allInputs.forEach(el => {
    if (!keepFields.includes(el.id)) {
      el.value = '';
    }
  });

  const coordinateSystem = document.getElementById('coordinate_system');
  if (coordinateSystem) coordinateSystem.value = 'CGCS2000';
  const protectionLevel = document.getElementById('protection_level');
  if (protectionLevel) protectionLevel.value = 'DS';
  const ownership = document.getElementById('ownership');
  if (ownership) ownership.value = 'state';
  const preservationStatus = document.getElementById('preservation_status');
  if (preservationStatus) preservationStatus.value = '一般';

  document.getElementById('gps-status').className = 'gps-badge idle';
  document.getElementById('gps-status').textContent = '未定位';
  document.getElementById('btn-gps-text').textContent = '获取当前位置';
  document.getElementById('btn-gps').disabled = false;
  document.getElementById('accuracy').value = '';

  selectedFiles.splice(0, selectedFiles.length);
  const area   = document.getElementById('photo-preview-area');
  area.querySelectorAll('.preview-wrapper').forEach(el => el.remove());
  updatePhotoCount();

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function goBack() {
  window.history.back();
}

// ── CSRF Token 获取 ──────────────────────────────────────────
function getCsrf() {
  const name = 'csrftoken';
  const cookies = document.cookie.split(';');
  for (let c of cookies) {
    c = c.trim();
    if (c.startsWith(name + '=')) {
      return decodeURIComponent(c.slice(name.length + 1));
    }
  }
  const el = document.querySelector('[name=csrfmiddlewaretoken]');
  return el ? el.value : '';
}

// ── 页面加载后自动尝试定位（非强制，失败不报错） ──────────────
document.addEventListener('DOMContentLoaded', () => {
  applyAdaptiveLayout();

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(() => {}, () => {}, {
      enableHighAccuracy: false,
      timeout: 5000,
      maximumAge: 30000,
    });
  }
});

window.addEventListener('resize', applyAdaptiveLayout);
window.addEventListener('orientationchange', applyAdaptiveLayout);
