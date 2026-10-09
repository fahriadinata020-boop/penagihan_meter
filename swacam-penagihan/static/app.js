// PLN SWACAM - Aplikasi 2: PENAGIHAN & WHATSAPP (impor tunggakan, kirim WA, riwayat WA, analitik)
// === State ===
let token=null, role=null;
function resetState(){ tgData=[]; tgPilih.clear(); rwData=[]; }
function afterLogin(){ showPage('page-dash'); checkDeviceStatus(false); loadInboxCount(); loadJamStatus(); }



function toggleDark(){
  const d=document.body.classList.toggle('dark');
  localStorage.setItem('swacam_dark', d?'1':'0');
  const ic=document.getElementById('dark-icon');
  if(ic) ic.className=d?'fa fa-sun':'fa fa-moon';
}
if(localStorage.getItem('swacam_dark')==='1'){
  document.body.classList.add('dark');
  document.addEventListener('DOMContentLoaded',()=>{
    const ic=document.getElementById('dark-icon'); if(ic) ic.className='fa fa-sun';
  });
}

async function requestNotifPermission(){
  if('Notification' in window && Notification.permission==='default')
    await Notification.requestPermission();
}
function sendBrowserNotif(title, body){
  if('Notification' in window && Notification.permission==='granted')
    new Notification(title, {body, icon:'/static/logo-pln.png'});
}

// === Toasts ===
function showToast(msg, type='success'){
  const tc=document.getElementById('toast-container');
  const t=document.createElement('div');
  const bg = type==='success'?'bg-emerald-600':type==='error'?'bg-rose-600':'bg-blue-600';
  const ic = type==='success'?'fa-check':type==='error'?'fa-triangle-exclamation':'fa-info';
  t.className=`${bg} text-white px-5 py-3.5 rounded-xl shadow-xl flex items-center gap-3 toast-enter pointer-events-auto min-w-[280px] border border-white/10`;
  t.innerHTML=`<div class="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center"><i class="fa ${ic} text-xs"></i></div><p class="text-sm font-bold">${msg}</p>`;
  tc.appendChild(t);
  setTimeout(()=>{t.classList.remove('toast-enter');t.classList.add('toast-active');},10);
  setTimeout(()=>{
    t.classList.remove('toast-active');t.classList.add('toast-exit');
    setTimeout(()=>t.remove(),300);
  }, 3500);
}

// === Auth ===
let isRegistering = false;
function toggleRegisterForm() {
  document.getElementById('login-body').style.display = 'none';
  document.getElementById('forgot-body').style.display = 'none';
  const rb = document.getElementById('register-body');
  isRegistering = !isRegistering;
  if (isRegistering) {
    rb.style.display = 'block';
  } else {
    document.getElementById('login-body').style.display = 'block';
    rb.style.display = 'none';
  }
}

function toggleForgotForm() {
  document.getElementById('register-body').style.display = 'none';
  isRegistering = false;
  const lb = document.getElementById('login-body');
  const fb = document.getElementById('forgot-body');
  const showingForgot = fb.style.display === 'block';
  if (showingForgot) {
    fb.style.display = 'none';
    lb.style.display = 'block';
  } else {
    lb.style.display = 'none';
    fb.style.display = 'block';
  }
}

async function doForgotPassword() {
  const u = document.getElementById('fp-user').value.trim();
  const n = document.getElementById('fp-name').value.trim();
  const err = document.getElementById('forgot-err'); err.classList.add('hidden');
  const btn = document.getElementById('forgot-btn'); btn.disabled = true;
  btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i><span>Mengirim...</span>';

  try {
    const res = await fetch('/api/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: u, full_name: n })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail || 'Gagal mengajukan reset password');

    btn.innerHTML = '<i class="fa fa-check"></i><span>Terkirim!</span>';
    btn.style.background = 'linear-gradient(135deg,#059669,#10b981)';
    setTimeout(() => {
      toggleForgotForm();
      showToast(d.message || 'Permintaan reset password terkirim ke Admin.', 'success');
      btn.disabled = false;
      btn.innerHTML = '<i class="fa fa-key"></i><span>AJUKAN RESET PASSWORD</span>';
      btn.style.background = 'linear-gradient(135deg,#001a3d,#003080)';
    }, 1500);
  } catch(e) {
    document.getElementById('forgot-err-text').textContent = e.message;
    err.classList.remove('hidden');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa fa-key"></i><span>AJUKAN RESET PASSWORD</span>';
  }
}

async function doRegister() {
  const n = document.getElementById('ru-name').value.trim();
  const ph = document.getElementById('ru-phone').value.trim();
  const u = document.getElementById('ru-user').value.trim();
  const p = document.getElementById('ru-pass').value;
  const err = document.getElementById('reg-err'); err.classList.add('hidden');
  const btn = document.getElementById('reg-btn'); btn.disabled = true;
  btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i><span>Memproses...</span>';

  try {
    const res = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full_name: n, username: u, password: p, phone_number: ph, role: 'petugas' })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail || 'Gagal mendaftar');
    
    btn.innerHTML = '<i class="fa fa-check"></i><span>Berhasil Daftar!</span>';
    btn.style.background = 'linear-gradient(135deg,#059669,#10b981)';
    setTimeout(() => {
      toggleRegisterForm();
      document.getElementById('lu').value = u;
      showToast('Pendaftaran berhasil! Akun Anda sedang menunggu persetujuan Admin.', 'success');
      btn.disabled = false;
      btn.innerHTML = '<i class="fa fa-user-plus"></i><span>DAFTARKAN AKUN</span>';
      btn.style.background = 'linear-gradient(135deg,#001a3d,#003080)';
    }, 1500);
  } catch(e) {
    document.getElementById('reg-err-text').textContent = e.message;
    err.classList.remove('hidden');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa fa-user-plus"></i><span>DAFTARKAN AKUN</span>';
  }
}

async function doLogin(){
  const u=document.getElementById('lu').value.trim(), p=document.getElementById('lp').value;
  const err=document.getElementById('login-err'); err.classList.add('hidden');
  const btn=document.getElementById('login-btn'); 
  
  btn.disabled=true;
  btn.innerHTML='<i class="fa fa-spinner fa-spin"></i><span>Memproses...</span>';
  try {
    const fd=new URLSearchParams(); fd.append('username',u); fd.append('password',p);
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:fd});
    if(!r.ok){const e=await r.json();throw new Error(e.detail||'Login gagal, periksa username/password');}
    const d=await r.json(); token=d.access_token; role=d.role; window.currentUser = {username: u, full_name: d.full_name || u, role: role};
    localStorage.setItem('swacam_token', token);
    btn.innerHTML='<i class="fa fa-check"></i><span>Berhasil!</span>';
    btn.style.background='linear-gradient(135deg,#059669,#10b981)';
    setTimeout(()=>{
      document.getElementById('login-modal').style.display='none';
      document.getElementById('sb-name').textContent=d.full_name||u;
      document.getElementById('sb-role').textContent=role;
      document.getElementById('sb-av').textContent=(d.full_name||u)[0].toUpperCase();
      if(role==='admin'){
        document.querySelectorAll('.admin-only').forEach(el=>el.classList.remove('hidden'));
        document.getElementById('role-badge').classList.remove('hidden');
      }
      afterLogin(); requestNotifPermission(); showToast(`Selamat datang, ${d.full_name||u}!`, 'success');
      btn.disabled=false; btn.innerHTML='<i class="fa fa-right-to-bracket"></i><span>Masuk ke Sistem</span>';
      btn.style.background='linear-gradient(135deg,#003d8f,#1a6fd4)';
    }, 700);
  } catch(e) {
    const errTxt=document.getElementById('login-err-text')||err;
    if(errTxt.tagName==='SPAN') errTxt.textContent=e.message; else err.textContent=e.message;
    err.classList.remove('hidden');
    btn.disabled=false; btn.innerHTML='<i class="fa fa-right-to-bracket"></i><span>Masuk ke Sistem</span>';
  }
}
function doLogout() {
  token=null; role=null; if(typeof resetState==='function') resetState();
  localStorage.removeItem('swacam_token');
  const s=document.getElementById('fast-auth-hide'); if(s) s.innerHTML='';
  document.getElementById('login-modal').style.display='flex';
  document.getElementById('lp').value='';
  document.getElementById('lu').value='';
  document.getElementById('login-body').style.display='block';
  document.getElementById('register-body').style.display='none';
  document.getElementById('forgot-body').style.display='none';
  isRegistering=false;
}

// === Pindah aplikasi tanpa login ulang ===
// Kedua aplikasi memakai tabel users & JWT_SECRET_KEY yang sama, jadi token dari satu aplikasi
// bisa dipakai di aplikasi lain. Token dikirim lewat hash URL (#sso=...) yang TIDAK ikut terkirim
// ke server dan langsung dihapus dari address bar setelah dibaca.
function openOtherApp(){
  const u=(window.SWACAM||{}).otherUrl;
  if(!u){ showToast('Alamat aplikasi lain belum diatur (PEER_APP_URL di config.php)','error'); return; }
  window.location.href=u.replace(/\/$/,'')+'/'+(token?'#sso='+encodeURIComponent(token):'');
}
function enterApp(nama, uname){
  document.getElementById('login-modal').style.display='none';
  document.getElementById('sb-name').textContent=nama||uname;
  document.getElementById('sb-role').textContent=role;
  document.getElementById('sb-av').textContent=(nama||uname||'U')[0].toUpperCase();
  if(role==='admin'){
    document.querySelectorAll('.admin-only').forEach(el=>el.classList.remove('hidden'));
    document.getElementById('role-badge').classList.remove('hidden');
  }
  afterLogin();
}
async function trySSO(){
  let t = null;
  const m=(location.hash||'').match(/^#sso=(.+)$/);
  if(m) {
    t=decodeURIComponent(m[1]);
    history.replaceState(null,'',location.pathname+location.search);
  } else {
    t = localStorage.getItem('swacam_token');
  }
  
  if(!t) return false;
  
  try{
    const r=await fetch('/api/users/me',{headers:{'Authorization':'Bearer '+t}});
    if(!r.ok) {
        localStorage.removeItem('swacam_token');
        return false;
    }
    const u=await r.json();
    token=t; role=u.role; window.currentUser=u;
    localStorage.setItem('swacam_token', t);
    enterApp(u.full_name, u.username);
    return true;
  }catch(e){ console.warn('Login/SSO gagal:', e.message); return false; }
}

// === Navigation ===
const PG={dash:'Dashboard Penagihan',tunggakan:'Impor Tunggakan & Kirim WA',riwayat:'Riwayat Pesan WhatsApp',analitik:'Analitik & Laporan Penagihan',inbox:'Kotak Masuk Balasan WA',users:'Kelola Petugas'};
function showPage(n, el){
  const key=n.replace('page-','');
  const pg=document.getElementById('page-'+key);
  if(!pg){ showToast('Halaman tidak ditemukan: '+key,'error'); return; }
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  pg.classList.add('active');
  document.getElementById('pg-title').textContent=PG[key] || key;
  document.querySelectorAll('.nav-item').forEach(i=>i.classList.remove('active'));
  if(el) el.classList.add('active');
  else {
    document.querySelectorAll('.nav-item').forEach(i=>{
      const oc=i.getAttribute('onclick')||'';
      if(oc.includes("'"+n+"'") || oc.includes('"'+n+'"') || oc.includes("'page-"+key+"'") || oc.includes('"page-'+key+'"')) i.classList.add('active');
    });
  }
  if(key==='dash') loadDash();
  if(key==='tunggakan') loadTunggakan();
  if(key==='riwayat') loadRiwayat();
  if(key==='analitik') loadAnalitik();
  if(key==='inbox') loadInbox();
  if(key==='users') loadUsers();
  closeSB();
}

// === Refresh (muat ulang halaman yang sedang aktif) ===
async function doRefresh(btn){
  const icon = btn?.querySelector('i');
  if(icon){ icon.classList.remove('fa-rotate-right'); icon.classList.add('fa-spinner','fa-spin'); }
  if(btn) btn.disabled = true;
  try {
    const aktif = document.querySelector('.page.active')?.id || '';
    if(aktif==='page-dash') await loadDash();
    else if(aktif==='page-tunggakan') await loadTunggakan();
    else if(aktif==='page-riwayat') await loadRiwayat();
    else if(aktif==='page-analitik') await loadAnalitik();
    else if(aktif==='page-inbox') await loadInbox();
    else if(aktif==='page-users') await loadUsers();
    showToast('✅ Data berhasil diperbarui', 'success');
  } catch(e) {
    showToast('❌ Gagal memperbarui: '+e.message, 'error');
  } finally {
    if(icon){ icon.classList.remove('fa-spinner','fa-spin'); icon.classList.add('fa-rotate-right'); }
    if(btn) btn.disabled = false;
  }
}


function toggleSB(){document.getElementById('sidebar').classList.toggle('open');document.getElementById('mob-overlay').classList.toggle('show');}
function closeSB(){document.getElementById('sidebar').classList.remove('open');document.getElementById('mob-overlay').classList.remove('show');}

// Login modal is visible by default via inline style
window.onload=async()=>{ if(await trySSO()) return; const s=document.getElementById('fast-auth-hide'); if(s) s.innerHTML=''; document.getElementById('login-modal').style.display='flex'; const lu=document.getElementById('lu'); if(lu) lu.focus(); };

// PWA Service Worker Registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js')
      .then(reg => console.log('SW registered:', reg.scope))
      .catch(err => console.log('SW reg failed:', err));
  });
}

// === Profile ===
async function openProfile() {
  const mod = document.getElementById('profile-modal');
  if(!mod) { console.error('profile-modal not found'); return; }
  mod.classList.remove('hidden');
  const passEl = document.getElementById('prof-pass');
  if(passEl) passEl.value = '';

  try {
    if(!token) throw new Error('Belum login');
    const r = await fetch('/api/users/me', {headers: {'Authorization': 'Bearer ' + token}});
    if (r.ok) { const u = await r.json(); window.currentUser = u; }
  } catch(e){ console.warn('Profile fetch:', e.message); }

  const cu = window.currentUser || {username: '-', full_name: '-', role: role||'-'};
  const nameEl = document.getElementById('prof-name');
  const userEl = document.getElementById('prof-user');
  const roleEl = document.getElementById('prof-role');
  const avEl   = document.getElementById('prof-av');
  const phoneEl = document.getElementById('prof-phone');
  if(nameEl) nameEl.value = cu.full_name || cu.username || '';
  if(phoneEl) phoneEl.value = cu.phone_number || '';
  if(userEl) userEl.value = cu.username || '';
  if(roleEl) roleEl.textContent = cu.role || '-';
  if(avEl) renderAvatar(avEl, cu);
}
window.openProfile = openProfile;

function renderAvatar(el, cu) {
  if (cu.foto_profil) {
    el.style.backgroundImage = `url('${cu.foto_profil}')`;
    el.textContent = '';
  } else {
    el.style.backgroundImage = '';
    el.textContent = (cu.full_name || cu.username || 'U')[0].toUpperCase();
  }
}

async function uploadPhoto(input) {
  if (!input.files || !input.files[0]) return;
  const fd = new FormData();
  fd.append('file', input.files[0]);
  try {
    const r = await fetch('/api/users/me/photo', {
      method: 'POST',
      headers: {'Authorization': 'Bearer ' + token},
      body: fd
    });
    const d = await r.json();
    if(!r.ok) throw new Error(d.detail || 'Gagal upload foto');
    window.currentUser.foto_profil = d.foto_profil;
    renderAvatar(document.getElementById('prof-av'), window.currentUser);
    showToast('Foto profil berhasil disimpan', 'success');
  } catch(e) { showToast(e.message, 'error'); }
  input.value = '';
}
window.uploadPhoto = uploadPhoto;

async function saveProfile() {
  const passEl = document.getElementById('prof-pass');
  const p = passEl ? passEl.value.trim() : '';
  if(!p) { showToast('Password baru tidak boleh kosong', 'error'); return; }
  try {
    const r = await fetch('/api/users/me/password', {
      method: 'PUT',
      headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
      body: JSON.stringify({new_password: p})
    });
    if(!r.ok){ const e = await r.json(); throw new Error(e.detail || 'Gagal mengubah password'); }
    showToast('Password berhasil diperbarui', 'success');
    if(passEl) passEl.value = '';
    document.getElementById('profile-modal').classList.add('hidden');
  } catch(e) { showToast(e.message, 'error'); }
}
window.saveProfile = saveProfile;

// Safety stub: prevent "generateCaptcha is not defined" error if called from old HTML cache
if(typeof generateCaptcha === 'undefined') window.generateCaptcha = function(){ /* removed */ };




async function savePhone() {
  const phoneEl = document.getElementById('prof-phone');
  const ph = phoneEl ? phoneEl.value.trim() : '';
  if(!ph) { showToast('Isi nomor WhatsApp dulu', 'error'); return; }
  try {
    const r = await fetch('/api/users/me/phone', {
      method: 'PUT',
      headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
      body: JSON.stringify({phone_number: ph})
    });
    const d = await r.json().catch(()=>({}));
    if(!r.ok){ throw new Error(d.detail || ('Gagal mengubah No. WA (HTTP ' + r.status + ')')); }
    if(phoneEl) phoneEl.value = d.phone_number || ph;
    showToast('Nomor WA tersimpan di database: ' + (d.phone_number || ph), 'success');
    if(window.currentUser) window.currentUser.phone_number = d.phone_number || ph;
  } catch(e) { showToast(e.message, 'error'); }
}
window.savePhone = savePhone;


// === Tagihan Menunggak -> WhatsApp manual (Fonnte) ===
let tgData=[], tgPilih=new Set(), tgTemplateAwal='', tgStop=false, tgSibuk=false;
let tgTpl={siap:false,list:[],jendela:null};   // template bertahap dari tabel wa_template
let tgAntreanTimer=null, tgAntreanId=null;   // antrean kirim WA yang dikerjakan SERVER
const tgEsc=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tgRp=n=>n==null?'-':'Rp '+Math.round(n).toLocaleString('id-ID');
const tgAuth=()=>({'Authorization':'Bearer '+token});
const tgBisaKirim=x=>!!x.no_hp&&(x.kategori==='MENUNGGAK'||x.boleh_pengingat===true);   // boleh_pengingat: pengingat ramah (tgl 15-17)
function tgBanner(){
  const box=document.getElementById('tg-notice'), txt=document.getElementById('tg-notice-txt');
  const blm=tgData.filter(x=>x.kategori==='BELUM_JATUH_TEMPO');
  if(!blm.length){ box.classList.add('hidden'); return null; }
  const sisa=Math.min(...blm.map(x=>x.sisa_hari||0)), tgl=(blm.find(x=>x.sisa_hari===sisa)||{}).jatuh_tempo;
  const t=`${blm.length} pelanggan belum lunas tetapi belum melewati batas pembayaran${tgl?' (tanggal '+parseInt(tgl.slice(8))+')':''}. Pesan WA tagihan baru bisa dikirim setelah tanggal tersebut, sekitar ${sisa} hari lagi.`+(blm.some(x=>x.boleh_pengingat)?` Pengingat ramah bisa dikirim sekarang (masa pengingat tanggal ${tgTpl.jendela?tgTpl.jendela.mulai+'-'+tgTpl.jendela.selesai:'15-17'}).`:'');
  txt.innerHTML='<b>Pemberitahuan:</b> '+tgEsc(t); box.classList.remove('hidden'); return t;
}
const tgJson=()=>({'Authorization':'Bearer '+token,'Content-Type':'application/json'});

function tgUnduhTemplate(e){ e.preventDefault(); window.open('/api/tunggakan/template?token='+token,'_blank'); }

async function loadTunggakan(){
  if(!token) return;
  tgInitDrop();
  try{
    if(!tgTemplateAwal){
      const r=await fetch('/api/tunggakan/pesan-default',{headers:tgAuth()});
      if(r.ok){
        const d=await r.json();
        tgTemplateAwal=d.template;
        document.getElementById('tg-template').value=d.template;
        document.getElementById('tg-batas').value=d.batas_tanggal;
        document.getElementById('tg-ph').textContent=d.placeholders.map(p=>'{'+p+'}').join('  ');
        document.getElementById('tg-warn-token').classList.toggle('hidden',d.token_fonnte_terisi);
        await tgInitTemplate();
      }
    }
    const r=await fetch('/api/tunggakan',{headers:tgAuth()});
    if(!r.ok) throw new Error('Gagal memuat data tunggakan');
    tgData=await r.json();
    tgPilih=new Set([...tgPilih].filter(id=>tgData.some(x=>x.id===id)));
    tgRender();
    if(!tgAntreanTimer) tgCekAntreanAktif();
  }catch(e){ showToast(e.message,'error'); }
}

// ── Template bertahap (#4, #5) ──
const tgKode=()=>tgTpl.siap?document.getElementById('tg-tpl-pilih').value:null;   // null = perilaku lama
const tgTemplate=()=>tgKode()==='AUTO'?'':document.getElementById('tg-template').value;
const tgNamaTpl=k=>((tgTpl.list.find(t=>t.kode===k)||{}).nama)||k;
async function tgInitTemplate(){
  try{
    const r=await fetch('/api/wa/template',{headers:tgAuth()});
    if(!r.ok) return;
    const d=await r.json();
    if(!d.siap||!d.templates.length) return;
    tgTpl={siap:true,list:d.templates.filter(t=>t.aktif),jendela:d.jendela};
    const sel=document.getElementById('tg-tpl-pilih');
    sel.innerHTML='<option value="AUTO">Otomatis (sesuai hari terlambat &amp; riwayat)</option>'+
      tgTpl.list.map(t=>`<option value="${tgEsc(t.kode)}">${tgEsc(t.nama)}</option>`).join('');
    sel.classList.remove('hidden');
    tgGantiTemplate();
  }catch(_){}
}
function tgGantiTemplate(){
  const kode=tgKode(), auto=kode==='AUTO';
  const box=document.getElementById('tg-tpl-auto'), ta=document.getElementById('tg-template');
  box.classList.toggle('hidden',!auto); ta.classList.toggle('hidden',auto);
  document.getElementById('tg-tpl-simpan').classList.toggle('hidden',auto);
  if(auto){
    const j=tgTpl.jendela||{mulai:15,selesai:17};
    box.innerHTML='<b>Sistem memilih template untuk tiap pelanggan:</b><ul class="list-disc ml-5 mt-2 space-y-1">'+
      tgTpl.list.map(t=>t.tahap===0
        ?`<li><b>${tgEsc(t.nama)}</b>: pelanggan yang belum jatuh tempo, hanya pada tanggal ${j.mulai}-${j.selesai}.</li>`
        :`<li><b>${tgEsc(t.nama)}</b>: terlambat ${t.hari_min}${t.hari_max==null?' hari atau lebih':'-'+t.hari_max+' hari'}.</li>`).join('')+
      '</ul><p class="mt-2 text-slate-500">Tahap tidak melompat: pelanggan yang belum pernah diingatkan selalu mulai dari pengingat pertama, lalu naik sesuai riwayat kirim dan hari terlambat.</p>';
  }else{
    const t=tgTpl.list.find(v=>v.kode===kode);
    if(t) ta.value=t.isi;
  }
}
function tgResetTemplate(){
  const t=tgTpl.list.find(v=>v.kode===tgKode());
  document.getElementById('tg-template').value=t?t.isi:tgTemplateAwal;
}
async function tgSimpanTemplate(){
  const kode=tgKode();
  if(!kode||kode==='AUTO') return;
  if(!confirm('Simpan isi pesan ini sebagai template "'+tgNamaTpl(kode)+'"? Pengiriman berikutnya memakai isi yang baru.')) return;
  try{
    const isi=document.getElementById('tg-template').value;
    const r=await fetch('/api/wa/template/'+encodeURIComponent(kode),{method:'PUT',headers:tgJson(),body:JSON.stringify({isi})});
    const d=await r.json();
    if(!r.ok) throw new Error(typeof d.detail==='string'?d.detail:'Gagal menyimpan template');
    const t=tgTpl.list.find(v=>v.kode===kode); if(t) t.isi=isi;
    showToast(d.message,'success');
  }catch(e){ showToast(e.message,'error'); }
}

const tgBatas=()=>parseInt(document.getElementById('tg-batas').value)||20;

async function tgUpload(){
  const f=document.getElementById('tg-file').files[0];
  if(!f){ showToast('Pilih file Excel/CSV terlebih dahulu','error'); return; }
  const btn=document.getElementById('tg-btn-upload');
  btn.disabled=true; btn.innerHTML='<i class="fa fa-spinner fa-spin"></i> Membaca...';
  try{
    const ganti=document.getElementById('tg-ganti').checked;
    if(ganti && !confirm('Mode GANTI DATA BULAN INI: data lama pada bulan yang sama dengan file ini, yang tidak ada di file baru, akan dihapus. Bulan lain tidak disentuh.\n(Riwayat pesan WA tetap tersimpan.)\n\nLanjutkan?')){ btn.disabled=false; btn.innerHTML='<i class="fa fa-cloud-arrow-up"></i> Upload &amp; Baca'; return; }
    const fd=new FormData(); fd.append('file',f); fd.append('batas_tanggal',tgBatas()); fd.append('mode',ganti?'ganti':'gabung');
    const r=await fetch('/api/tunggakan/upload',{method:'POST',headers:tgAuth(),body:fd});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'Gagal membaca file');
    const box=document.getElementById('tg-summary');
    box.innerHTML=`<div class="flex items-start gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2.5"><i class="fa fa-circle-check mt-0.5"></i><span><b>${tgEsc(d.nama_file||'File')}</b> terbaca: ${d.tersimpan||d.total_baris} data (${d.menunggak} menunggak, ${d.belum_jatuh_tempo} belum jatuh tempo, ${d.lunas} lunas). ${d.mode==='ganti'?`Disimpan sebagai <b>${(d.periode_tersimpan||[]).map(p=>'Data '+tgEsc(p)).join(', ')}</b>. Mode ganti data bulan ini: <b>${d.ditambahkan}</b> baru, <b>${d.diperbarui}</b> diperbarui, <b>${d.dihapus_dari_daftar_lama}</b> data lama dihapus.`:`Disimpan sebagai <b>${(d.periode_tersimpan||[]).map(p=>'Data '+tgEsc(p)).join(', ')||'data'}</b>. Data lama dipertahankan: <b>${d.ditambahkan}</b> baru ditambahkan, <b>${d.diperbarui}</b> diperbarui. Total tersimpan sekarang <b>${d.total_tersimpan}</b> data.`} Klik kartu di bawah untuk menyaring tabel.</span></div>
    <p class="mt-3 text-[11px] text-slate-500 flex flex-wrap items-center gap-1.5"><b>Kolom terbaca:</b> ${Object.entries(d.kolom_terbaca||{}).map(([k,v])=>`<span class="inline-flex items-center gap-1 bg-slate-100 text-slate-600 rounded-full px-2.5 py-1">${tgEsc(k)} <i class="fa fa-arrow-left-long text-[9px] text-slate-400"></i> <b>${tgEsc(v)}</b></span>`).join('')}</p>`+(d.peringatan||[]).map(w=>`<p class="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"><i class="fa fa-triangle-exclamation mr-1"></i>${tgEsc(w)}</p>`).join('');
    box.classList.remove('hidden');
    showToast(`${d.menunggak} menunggak, ${d.belum_jatuh_tempo} belum jatuh tempo`,'success');
    if(d.pemberitahuan){ showToast('Belum lewat tanggal '+d.batas_tanggal+': WA belum bisa dikirim','info'); try{sendBrowserNotif('Pemberitahuan Tunggakan',d.pemberitahuan);}catch(_){} }
    tgPilih.clear(); tgKat=''; tgSortK=''; tgPage=1;
    tgPeriode=(d.periode_tersimpan&&d.periode_tersimpan.length)?[...d.periode_tersimpan].sort((a,b)=>tgPerUrut(b)-tgPerUrut(a))[0]:null;
    document.getElementById('tg-ganti').checked=false;
    document.getElementById('tg-file').value=''; tgFilePicked();
    await loadTunggakan();
    document.getElementById('tg-stats').scrollIntoView({behavior:'smooth',block:'center'});
  }catch(e){ showToast(e.message,'error'); }
  finally{ btn.disabled=false; btn.innerHTML='<i class="fa fa-cloud-arrow-up"></i> Upload &amp; Baca'; }
}

// ── Tampilan data keseluruhan: kartu ringkasan, urut, halaman, panel detail ──
let tgKat='', tgSortK='', tgSortDir=1, tgPage=1, tgPer=25, tgDropInit=false;
let tgPeriode=null;   // null = belum dipilih (otomatis bulan terbaru) | '' = semua bulan | 'Agustus 2026'
const BLN=['januari','februari','maret','april','mei','juni','juli','agustus','september','oktober','november','desember'];
function tgPerUrut(p){ const m=String(p||'').toLowerCase().match(/([a-z]+)\s+(\d{4})/); return m&&BLN.indexOf(m[1])>=0?(+m[2])*100+BLN.indexOf(m[1])+1:0; }
const tgDaftarPeriode=()=>{ const h={}; tgData.forEach(x=>{ const k=x.periode||'Tanpa periode'; h[k]=(h[k]||0)+1; }); return Object.entries(h).sort((a,b)=>tgPerUrut(b[0])-tgPerUrut(a[0])||a[0].localeCompare(b[0])); };
const tgByPeriode=()=>tgPeriode===''||tgPeriode===null?tgData:tgData.filter(x=>(x.periode||'Tanpa periode')===tgPeriode);
function tgSetPeriode(p){ tgPeriode=p; tgKat=''; tgPage=1; tgPilih.clear(); tgRender(); }
function tgRenderPeriode(){
  const daftar=tgDaftarPeriode(), box=document.getElementById('tg-periode');
  if(tgPeriode===null||(tgPeriode!==''&&!daftar.some(d=>d[0]===tgPeriode))) tgPeriode=daftar.length?daftar[0][0]:'';
  if(!daftar.length){ box.innerHTML=''; box.classList.add('hidden'); return; }
  box.classList.remove('hidden');
  const chip=(k,l,n)=>`<button type="button" class="tg-per ${tgPeriode===k?'on':''}" onclick="tgSetPeriode(${JSON.stringify(k).replace(/"/g,'&quot;')})"><i class="fa ${k===''?'fa-layer-group':'fa-folder'}"></i>${tgEsc(l)}<span>${n}</span></button>`;
  box.innerHTML='<span class="tg-per-l"><i class="fa fa-calendar-days mr-1"></i>Pilih bulan data</span>'
    +daftar.map(d=>chip(d[0],'Data '+d[0],d[1])).join('')+(daftar.length>1?chip('','Semua bulan',tgData.length):'')
    +(tgPeriode?`<button type="button" class="tg-per-del" onclick="tgHapusPeriode()" title="Hapus seluruh data bulan ini"><i class="fa fa-trash"></i> Hapus data ${tgEsc(tgPeriode)}</button>`:'');
}
async function tgHapusPeriode(){
  const p=tgPeriode; if(!p) return;
  const n=tgData.filter(x=>(x.periode||'Tanpa periode')===p).length;
  if(!confirm(`Hapus seluruh Data ${p} (${n} baris) dari daftar?\nRiwayat pesan WA yang sudah terkirim tetap tersimpan.`)) return;
  try{
    const r=await fetch('/api/tunggakan/periode/'+encodeURIComponent(p),{method:'DELETE',headers:tgAuth()}), d=await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(d.detail||'Gagal menghapus');
    showToast(d.message||'Data dihapus','success'); tgPeriode=null; tgPilih.clear(); await loadTunggakan();
  }catch(e){ showToast(e.message,'error'); }
}
const KAT_URUT={MENUNGGAK:0,BELUM_JATUH_TEMPO:1,LUNAS:2};
const tgWarna=s=>{ let h=0; for(const c of String(s||'?')) h=(h*31+c.charCodeAt(0))%360; return h; };
const tgAv=(nama,lg)=>{ const h=tgWarna(nama); return `<span class="tg-av${lg?' lg':''}" style="background:hsl(${h} 75% 92%);color:hsl(${h} 55% 32%)">${tgEsc((String(nama||'?').trim()[0]||'?').toUpperCase())}</span>`; };
const tgNm=x=>x.nama?tgEsc(x.nama):'<span class="text-slate-400 italic">Tanpa nama</span>';
const tgBayar=x=>x.kategori==='LUNAS'?'<span class="badge bg-emerald-100 text-emerald-700">LUNAS</span>'
  :x.kategori==='BELUM_JATUH_TEMPO'?'<span class="badge bg-sky-100 text-sky-700">BELUM JATUH TEMPO</span>'
  :'<span class="badge bg-amber-100 text-amber-700">MENUNGGAK</span>';
const tgTerlambat=x=>x.kategori==='LUNAS'?'<span class="text-slate-300">-</span>'
  :x.kategori==='BELUM_JATUH_TEMPO'?'<span class="text-sky-600 font-bold">Sisa '+x.sisa_hari+' hari</span>'
  :'<span class="text-amber-600 font-bold">'+(x.hari_terlambat==null?'-':x.hari_terlambat+' hari')+'</span>';

function tgBadge(x){
  if(x.wa_status==='TERKIRIM') return `<span class="badge bg-emerald-100 text-emerald-700" title="${tgEsc(x.wa_waktu)}">TERKIRIM${x.wa_jumlah_kirim>1?' ×'+x.wa_jumlah_kirim:''}</span>`;
  if(x.wa_status==='GAGAL') return `<span class="badge bg-rose-100 text-rose-700" title="${tgEsc(x.wa_respon)}">GAGAL</span>`;
  if(x.kategori==='LUNAS') return '<span class="text-slate-300">-</span>';
  return '<span class="badge bg-slate-100 text-slate-600">BELUM</span>';
}
function tgSaran(x){
  if(x.kategori==='LUNAS') return '';
  if(!tgBisaKirim(x)) return x.tahap_terakhir_nama?'<div class="text-[10px] text-slate-400 mt-1">Terakhir: '+tgEsc(x.tahap_terakhir_nama)+'</div>':'';
  const t=[];
  if(x.tahap_terakhir_nama) t.push('Terakhir: '+tgEsc(x.tahap_terakhir_nama));
  if(x.saran_template_nama) t.push('<span class="text-emerald-600 font-semibold">Saran: '+tgEsc(x.saran_template_nama)+'</span>');
  return t.length?'<div class="text-[10px] text-slate-400 mt-1 leading-tight">'+t.join('<br>')+'</div>':'';
}
function tgRiwayat(idpel){ document.getElementById('rw-q').value=idpel; rwSt=''; document.getElementById('rw-status').value=''; sheetTutup(); showPage('page-riwayat'); }

// Kartu ringkasan: dihitung dari seluruh data tersimpan, jadi tetap muncul setelah halaman dimuat ulang
const TG_KARTU=[
  {k:'',ic:'fa-layer-group',l:'Semua data',c:'#1a6fd4',bg:'#eff6ff'},
  {k:'MENUNGGAK',ic:'fa-hourglass-end',l:'Menunggak',c:'#d97706',bg:'#fffbeb'},
  {k:'BELUM_JATUH_TEMPO',ic:'fa-calendar-day',l:'Belum jatuh tempo',c:'#0284c7',bg:'#f0f9ff'},
  {k:'LUNAS',ic:'fa-circle-check',l:'Sudah lunas',c:'#059669',bg:'#ecfdf5'},
  {k:'TANPA_WA',ic:'fa-phone-slash',l:'Tanpa nomor WA valid',c:'#e11d48',bg:'#fff1f2'},
];
function tgHitung(){
  const src=tgByPeriode(), h={'':src.length,MENUNGGAK:0,BELUM_JATUH_TEMPO:0,LUNAS:0,TANPA_WA:0}, nom={MENUNGGAK:0,BELUM_JATUH_TEMPO:0,LUNAS:0};
  src.forEach(x=>{ h[x.kategori]=(h[x.kategori]||0)+1; nom[x.kategori]=(nom[x.kategori]||0)+(x.nominal||0); if(x.kategori!=='LUNAS'&&!x.no_hp) h.TANPA_WA++; });
  return {h,nom};
}
function tgRenderStats(){
  const {h,nom}=tgHitung(), tot=h['']||0;
  const sub={'':tgData.length?(tgPeriode?'Data '+tgPeriode:'Seluruh bulan'):'Belum ada data',MENUNGGAK:nom.MENUNGGAK?tgRp(nom.MENUNGGAK):'',BELUM_JATUH_TEMPO:nom.BELUM_JATUH_TEMPO?tgRp(nom.BELUM_JATUH_TEMPO):'',LUNAS:nom.LUNAS?tgRp(nom.LUNAS):'',TANPA_WA:h.TANPA_WA?'Perlu dilengkapi':'Semua punya nomor'};
  document.getElementById('tg-stats').innerHTML=TG_KARTU.map(c=>`<button type="button" class="tg-stat ${tgKat===c.k?'on':''}" style="--c:${c.c};--bg:${c.bg}" onclick="tgSetKat('${c.k}',true)" aria-label="Tampilkan: ${c.l}">
    <div class="top"><span class="ic"><i class="fa ${c.ic}"></i></span><span class="go"><i class="fa fa-filter"></i> ${tgKat===c.k&&c.k?'Aktif':'Saring'}</span></div>
    <div class="n">${h[c.k]||0}</div><div class="l">${c.l}</div><div class="s">${tgEsc(sub[c.k])}</div>
    <div class="bar"><i style="width:${tot?Math.round((h[c.k]||0)/tot*100):0}%"></i></div></button>`).join('');
}
function tgSetKat(k,scroll){
  tgKat=(k&&tgKat===k)?'':k; tgPage=1; tgRender();
  if(scroll) document.getElementById('tg-table-card').scrollIntoView({behavior:'smooth',block:'start'});
}
function tgSort(k){
  if(tgSortK===k) tgSortDir=-tgSortDir; else { tgSortK=k; tgSortDir=1; }
  tgPage=1; tgRender();
}
function tgNilai(x,k){
  if(k==='hari') return x.kategori==='BELUM_JATUH_TEMPO'?-(x.sisa_hari||0):(x.hari_terlambat==null?-9999:x.hari_terlambat);
  if(k==='nominal') return x.nominal==null?-1:x.nominal;
  return (x[k]==null?'':String(x[k])).toLowerCase();
}
function tgFiltered(){
  const q=document.getElementById('tg-search').value.trim().toLowerCase(), fs=document.getElementById('tg-filter').value;
  const rows=tgByPeriode().filter(x=>{
    if(tgKat==='TANPA_WA'){ if(x.kategori==='LUNAS'||x.no_hp) return false; }
    else if(tgKat&&x.kategori!==tgKat) return false;
    if(fs&&x.wa_status!==fs) return false;
    return !q||(x.id_pelanggan||'').toLowerCase().includes(q)||(x.nama||'').toLowerCase().includes(q)||(x.no_hp||'').includes(q.replace(/\D/g,'')||'\u0000');
  });
  if(tgSortK){
    rows.sort((a,b)=>{ const A=tgNilai(a,tgSortK),B=tgNilai(b,tgSortK);
      return (typeof A==='number'?A-B:String(A).localeCompare(String(B),'id',{numeric:true}))*tgSortDir; });
  } else {   // bawaan: menunggak paling lama dulu, lalu belum jatuh tempo, lalu lunas
    rows.sort((a,b)=>(KAT_URUT[a.kategori]-KAT_URUT[b.kategori])||((b.hari_terlambat||0)-(a.hari_terlambat||0))||(a.id-b.id));
  }
  return rows;
}
function tgPagerHtml(total,per,page,fn){
  const pages=Math.max(1,Math.ceil(total/per)), a=total?(page-1)*per+1:0, b=Math.min(total,page*per);
  let s=Math.max(1,page-2), e=Math.min(pages,s+4); s=Math.max(1,e-4);
  let nums=''; for(let i=s;i<=e;i++) nums+=`<button class="${i===page?'on':''}" onclick="${fn}(${i})">${i}</button>`;
  return `<span>Menampilkan <b>${a}–${b}</b> dari <b>${total}</b> data</span>
    <span class="pg"><button ${page<=1?'disabled':''} onclick="${fn}(${page-1})" aria-label="Sebelumnya"><i class="fa fa-chevron-left"></i></button>${nums}<button ${page>=pages?'disabled':''} onclick="${fn}(${page+1})" aria-label="Berikutnya"><i class="fa fa-chevron-right"></i></button></span>`;
}
function tgGo(p){ tgPage=p; tgRender(); }

function tgRender(){
  tgRenderPeriode(); tgRenderStats(); tgBanner();
  document.getElementById('tg-judul').textContent=tgPeriode?'Data '+tgPeriode:'Data pelanggan (semua bulan)';
  const rows=tgFiltered(), total=rows.length, pages=Math.max(1,Math.ceil(total/tgPer));
  if(tgPage>pages) tgPage=pages;
  document.getElementById('tg-count').textContent=total+(total!==tgByPeriode().length?' / '+tgByPeriode().length:'');
  const fi=document.getElementById('tg-filter-info'), kc=TG_KARTU.find(c=>c.k===tgKat);
  fi.classList.toggle('hidden',!tgKat); if(tgKat) fi.textContent='Saringan: '+kc.l;
  document.querySelectorAll('#tg-table-card .tg-th').forEach(th=>{
    const i=th.querySelector('i'), on=i.dataset.k===tgSortK; th.classList.toggle('s-on',on);
    i.className='fa '+(on?(tgSortDir>0?'fa-sort-up':'fa-sort-down'):'fa-sort');
  });
  const tb=document.getElementById('tg-body');
  if(!rows.length){
    tb.innerHTML='<tr><td colspan="11" class="text-center py-12 text-slate-400"><i class="fa fa-inbox text-2xl block mb-2 opacity-40"></i>'+(tgData.length?'Tidak ada data yang cocok dengan saringan.':'Belum ada data. Upload file Excel terlebih dahulu.')+'</td></tr>';
    document.getElementById('tg-pager').innerHTML=''; tgHitungPilih(); return;
  }
  tb.innerHTML=rows.slice((tgPage-1)*tgPer,tgPage*tgPer).map(x=>{
    const ok=tgBisaKirim(x), adaHp=!!x.no_hp, alasan=x.kategori==='LUNAS'?'Sudah lunas':(x.kategori==='BELUM_JATUH_TEMPO'?'Belum lewat tanggal batas':'Nomor WA tidak valid');
    return `<tr onclick="tgDetail(${x.id})">
      <td onclick="event.stopPropagation()"><input type="checkbox" ${tgPilih.has(x.id)?'checked':''} onchange="tgToggle(${x.id},this.checked)"></td>
      <td class="font-mono">${tgEsc(x.id_pelanggan)}</td>
      <td><div class="flex items-center gap-2.5">${tgAv(x.nama)}<span class="font-semibold text-slate-700">${tgNm(x)}</span></div></td>
      <td>${adaHp?tgEsc(x.no_hp):(x.kategori==='LUNAS'?'<span class="text-slate-300">-</span>':'<span class="text-rose-500 text-xs font-bold">Tidak valid</span>')}</td>
      <td>${tgEsc(x.periode||'-')}</td>
      <td class="whitespace-nowrap">${tgRp(x.nominal)}</td>
      <td class="whitespace-nowrap">${tgEsc(x.jatuh_tempo||'-')}</td>
      <td class="whitespace-nowrap">${tgTerlambat(x)}</td>
      <td>${tgBayar(x)}</td>
      <td>${tgBadge(x)}${tgSaran(x)}</td>
      <td class="text-center whitespace-nowrap" onclick="event.stopPropagation()">
        <button ${ok?'':'disabled'} title="${ok?'Kirim pesan WA':alasan}" onclick="tgPreview(${x.id})" class="bg-emerald-50 text-emerald-600 border border-emerald-200 px-2 py-1 rounded text-[11px] font-bold hover:bg-emerald-100 disabled:opacity-40 disabled:cursor-not-allowed mb-1"><i class="fa-brands fa-whatsapp"></i> Kirim</button>
        ${x.kategori!=='LUNAS'?`<button onclick="tgTandaiLunas(${x.id})" class="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-1 rounded text-[11px] font-bold hover:bg-emerald-100 mb-1" title="Tandai lunas"><i class="fa fa-check"></i></button>`:''}
        <button onclick="tgEditData(${x.id})" class="bg-blue-50 text-blue-600 border border-blue-200 px-2 py-1 rounded text-[11px] font-bold hover:bg-blue-100 mb-1" title="Edit Data"><i class="fa fa-pen"></i></button>
        <button onclick="tgRiwayat('${tgEsc(x.id_pelanggan)}')" class="text-slate-400 hover:text-blue-600 px-2" title="Riwayat pesan pelanggan ini"><i class="fa fa-clock-rotate-left"></i></button>
        <button onclick="tgHapus(${x.id})" class="text-rose-400 hover:text-rose-600 px-2" title="Hapus dari daftar"><i class="fa fa-trash"></i></button>
      </td></tr>`;
  }).join('');
  document.getElementById('tg-pager').innerHTML=tgPagerHtml(total,tgPer,tgPage,'tgGo');
  tgHitungPilih();
}

// ── Panel detail pelanggan (klik baris) ──
function sheetBuka(){ document.getElementById('sheet-ov').classList.add('show'); const s=document.getElementById('sheet'); s.classList.add('show'); s.setAttribute('aria-hidden','false'); }
function sheetTutup(){ document.getElementById('sheet-ov').classList.remove('show'); const s=document.getElementById('sheet'); s.classList.remove('show'); s.setAttribute('aria-hidden','true'); }
document.addEventListener('keydown',e=>{ if(e.key==='Escape') sheetTutup(); });
function tgSalin(t,label){ navigator.clipboard.writeText(t).then(()=>showToast((label||'Teks')+' disalin','success'),()=>showToast('Tidak bisa menyalin','error')); }
const sh=(k,v,full)=>`<div class="sh-it ${full?'full':''}"><div class="k">${k}</div><div class="v">${v}</div></div>`;

async function tgDetail(id){
  const x=tgData.find(v=>v.id===id); if(!x) return;
  const ok=tgBisaKirim(x), alasan=x.kategori==='LUNAS'?'Sudah lunas':(x.kategori==='BELUM_JATUH_TEMPO'?'Belum lewat tanggal batas':'Nomor WA tidak valid');
  document.getElementById('sheet-head').innerHTML=`${tgAv(x.nama,true)}<div class="min-w-0"><p class="font-extrabold text-slate-800 truncate">${tgNm(x)}</p><p class="text-xs text-slate-400 font-mono">${tgEsc(x.id_pelanggan)}</p></div>`;
  document.getElementById('sheet-body').innerHTML=`
    <div class="flex flex-wrap gap-2 mb-4">${tgBayar(x)} ${tgBadge(x)}</div>
    <div class="sh-grid">
      ${sh('Tagihan',tgRp(x.nominal))}${sh('Periode',tgEsc(x.periode||'-'))}
      ${sh('Jatuh tempo',tgEsc(x.jatuh_tempo||'-'))}${sh('Keterlambatan',tgTerlambat(x))}
      ${sh('No. WA',x.no_hp?tgEsc(x.no_hp):'<span class="text-rose-500">Tidak valid / kosong</span>')}${sh('Dikirimi WA',(x.wa_jumlah_kirim||0)+'×'+(x.wa_waktu?'<div class="text-[11px] font-medium text-slate-400">terakhir '+tgEsc(x.wa_waktu)+'</div>':''))}
      ${sh('Alamat',tgEsc(x.alamat||'-'),true)}
      ${x.saran_template_nama&&ok?sh('Saran pesan','<span class="text-emerald-600">'+tgEsc(x.saran_template_nama)+'</span>',true):''}
      ${sh('Diunggah',tgEsc((x.diupload_oleh||'-')+(x.diupload_pada?' · '+x.diupload_pada:''))+(x.sumber_file?'<div class="text-[11px] font-medium text-slate-400"><i class="fa fa-file-excel mr-1"></i>'+tgEsc(x.sumber_file)+'</div>':''),true)}
    </div>
    <p class="sh-h3"><i class="fa fa-clock-rotate-left text-emerald-500"></i>Riwayat pesan WhatsApp</p>
    <div id="sheet-riw" class="text-xs text-slate-400"><i class="fa fa-spinner fa-spin mr-1"></i>Memuat...</div>`;
  document.getElementById('sheet-foot').innerHTML=`
    <button class="sh-btn wa" ${ok?'':'disabled'} title="${ok?'':alasan}" onclick="sheetTutup();tgPreview(${x.id})"><i class="fa-brands fa-whatsapp"></i> Kirim WA</button>
    ${x.kategori!=='LUNAS'?`<button class="sh-btn" style="background:#ecfdf5;color:#059669;border-color:#a7f3d0" onclick="tgTandaiLunas(${x.id})" title="Tandai pelanggan ini sudah lunas"><i class="fa fa-circle-check"></i> Lunas</button>`:''}
    <button class="sh-btn" style="background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe" onclick="tgEditData(${x.id})" title="Edit nama atau nomor WA pelanggan ini"><i class="fa fa-pen"></i> Edit</button>
    <button class="sh-btn" onclick="tgSalin('${tgEsc(x.id_pelanggan)}','IDPEL')"><i class="fa fa-copy"></i> IDPEL</button>
    <button class="sh-btn" ${x.no_hp?'':'disabled'} onclick="tgSalin('${tgEsc(x.no_hp||'')}','Nomor WA')"><i class="fa fa-copy"></i> No. WA</button>
    <button class="sh-btn" onclick="tgRiwayat('${tgEsc(x.id_pelanggan)}')"><i class="fa fa-up-right-from-square"></i> Semua riwayat</button>
    <button class="sh-btn del ml-auto" onclick="sheetTutup();tgHapus(${x.id})"><i class="fa fa-trash"></i></button>`;
  sheetBuka();
  try{
    const r=await fetch('/api/wa/riwayat/'+encodeURIComponent(x.id_pelanggan),{headers:tgAuth()}), d=await r.json();
    const box=document.getElementById('sheet-riw'); if(!box) return;
    if(!r.ok) throw new Error(typeof d.detail==='string'?d.detail:'Gagal memuat');
    box.innerHTML=d.length?d.map(m=>`<div class="sh-msg" onclick="this.classList.toggle('open')">
        <div class="flex items-center gap-2 flex-wrap"><span class="badge ${rwBadge(m.status)}">${tgEsc(m.status)}</span>
        <span class="text-[11px] text-slate-500">${tgEsc(m.waktu_kirim||'')}</span><span class="text-[11px] text-slate-400 ml-auto">${m.template_kode?tgEsc(tgNamaTpl(m.template_kode)):'Standar'} <i class="fa fa-chevron-down text-[9px]"></i></span></div>
        ${m.balasan?'<p class="text-[11px] text-emerald-700 mt-1.5"><i class="fa fa-reply mr-1"></i>'+tgEsc(m.balasan)+'</p>':''}
        <pre>${tgEsc(m.pesan||'')}</pre></div>`).join(''):'Belum ada pesan yang dikirim ke pelanggan ini.';
  }catch(e){ const b=document.getElementById('sheet-riw'); if(b) b.textContent=e.message; }
}

// ── Ekspor tampilan ke CSV ──
function unduhCsv(nama,baris){
  const esc=v=>'"'+String(v==null?'':v).replace(/"/g,'""')+'"';
  const blob=new Blob(['\ufeff'+baris.map(r=>r.map(esc).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=nama; document.body.appendChild(a); a.click(); a.remove();
}
function tgEksporCsv(){
  const rows=tgFiltered(); if(!rows.length){ showToast('Tidak ada data untuk diekspor','error'); return; }
  unduhCsv('data_pelanggan_'+new Date().toISOString().slice(0,10)+'.csv',[['ID Pelanggan','Nama','No WA','Alamat','Periode','Tagihan','Jatuh Tempo','Pembayaran','Status WA']]
    .concat(rows.map(x=>[x.id_pelanggan,x.nama,x.no_hp,x.alamat,x.periode,x.nominal,x.jatuh_tempo,x.kategori,x.wa_status])));
  showToast(rows.length+' baris diekspor','success');
}

// ── Dropzone & stepper ──
function tgFilePicked(){
  const f=document.getElementById('tg-file').files[0], d=document.getElementById('tg-drop');
  d.classList.toggle('has-file',!!f);
  document.getElementById('tg-drop-t').textContent=f?f.name:'Tarik file ke sini, atau klik untuk memilih';
  document.getElementById('tg-drop-s').textContent=f?(f.size/1024).toFixed(f.size>1048576?0:1)+' KB · siap diunggah, tekan "Upload & Baca"':'.xlsx, .xlsm, atau .csv · maksimal 5 MB';
}
function tgStep(n){ const i=document.getElementById('tg-batas'); i.value=Math.min(31,Math.max(1,(parseInt(i.value)||20)+n)); }
function tgInitDrop(){
  if(tgDropInit) return; tgDropInit=true;
  const d=document.getElementById('tg-drop'), inp=document.getElementById('tg-file');
  ['dragenter','dragover'].forEach(ev=>d.addEventListener(ev,e=>{ e.preventDefault(); d.classList.add('drag'); }));
  ['dragleave','drop'].forEach(ev=>d.addEventListener(ev,e=>{ e.preventDefault(); d.classList.remove('drag'); }));
  d.addEventListener('drop',e=>{ if(e.dataTransfer.files.length){ inp.files=e.dataTransfer.files; tgFilePicked(); } });
}

function tgToggle(id,on){ on?tgPilih.add(id):tgPilih.delete(id); tgHitungPilih(); }
function tgHitungPilih(){
  const dipilih=tgData.filter(x=>tgPilih.has(x.id)), bisaKirim=dipilih.filter(tgBisaKirim).length;
  document.getElementById('tg-sel').textContent=bisaKirim;
  const bar=document.getElementById('tg-bulk'); bar.classList.toggle('hidden',!dipilih.length);
  document.getElementById('tg-bulk-n').textContent=dipilih.length;
  document.getElementById('tg-bulk-info').textContent=dipilih.length?`${bisaKirim} bisa dikirimi WA, ${dipilih.length-bisaKirim} tidak (lunas / belum jatuh tempo / tanpa nomor)`:'';
  const semua=tgFiltered(), all=document.getElementById('tg-all');
  if(all){ const n=semua.filter(x=>tgPilih.has(x.id)).length; all.checked=semua.length>0&&n===semua.length; all.indeterminate=n>0&&n<semua.length; }
  const adaLunas=tgByPeriode().some(x=>x.kategori==='LUNAS'), bl=document.getElementById('tg-btn-lunas');
  if(bl) bl.classList.toggle('hidden',!adaLunas);
}
function tgPilihSemua(on){
  tgFiltered().forEach(x=>on?tgPilih.add(x.id):tgPilih.delete(x.id));
  tgRender();
}

async function tgPreview(id){
  try{
    const x=tgData.find(v=>v.id===id);
    const r=await fetch('/api/tunggakan/preview',{method:'POST',headers:tgJson(),body:JSON.stringify({id,template:tgTemplate(),template_kode:tgKode(),batas_tanggal:tgBatas()})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'Gagal membuat pratinjau');
    document.getElementById('tg-m-nama').textContent=x.nama||x.id_pelanggan;
    document.getElementById('tg-m-hp').textContent=d.no_hp+(d.template_kode?'  ·  Template: '+tgNamaTpl(d.template_kode):'');
    document.getElementById('tg-m-pesan').textContent=d.pesan;
    document.getElementById('tg-m-kirim').onclick=async()=>{
      const btn=document.getElementById('tg-m-kirim'); btn.disabled=true;
      const ok=await tgKirim(id,true); btn.disabled=false;
      if(ok!==null) tgTutupModal();
    };
    document.getElementById('tg-modal').classList.remove('hidden');
  }catch(e){ showToast(e.message,'error'); }
}
function tgTutupModal(){ document.getElementById('tg-modal').classList.add('hidden'); }

// return true/false = hasil kirim, null = dibatalkan
async function tgKirim(id,tampilToast,ulang=false){
  const x=tgData.find(v=>v.id===id);
  try{
    const r=await fetch(`/api/tunggakan/${id}/kirim`,{method:'POST',headers:tgJson(),
      body:JSON.stringify({template:tgTemplate(),template_kode:tgKode(),batas_tanggal:tgBatas(),kirim_ulang:ulang})});
    const d=await r.json();
    if(r.status===409){
      if(tampilToast && confirm(`Pesan untuk ${x?(x.nama||x.id_pelanggan):'pelanggan ini'} sudah pernah terkirim.\nKirim ulang?`)) return tgKirim(id,tampilToast,true);
      return null;
    }
    if(!r.ok) throw new Error(d.detail||'Gagal mengirim');
    if(tampilToast) showToast(d.berhasil?'Pesan WA berhasil dikirim':'Gagal kirim: '+d.keterangan, d.berhasil?'success':'error');
    if(x){ x.wa_status=d.wa_status; }
    await loadTunggakan();
    return d.berhasil;
  }catch(e){ if(tampilToast) showToast(e.message,'error'); return false; }
}

// Kirim massal: browser HANYA membuat antrean. Pengiriman dikerjakan worker di server dengan jeda otomatis,
// jadi tab boleh ditutup. Hasil tetap tercatat (tabel wa_antrean & wa_riwayat).
async function tgKirimTerpilih(){
  if(tgSibuk) return;
  const ids=tgData.filter(x=>tgPilih.has(x.id)&&tgBisaKirim(x)).map(x=>x.id);
  if(!ids.length){ showToast(tgPilih.size?'Data yang dipilih tidak ada yang bisa dikirimi WA (lunas / belum jatuh tempo / tanpa nomor)':'Centang pelanggan yang akan dikirimi WA','error'); return; }
  const sudah=ids.filter(id=>(tgData.find(v=>v.id===id)||{}).wa_status==='TERKIRIM').length;
  let pesan=`Kirim pesan WhatsApp ke ${ids.length} pelanggan?\n\nPesan dikirim oleh server satu per satu dengan jeda otomatis. Halaman ini boleh ditutup.`;
  if(sudah) pesan+=`\n\n${sudah} di antaranya sudah pernah dikirimi dan akan dilewati.`;
  if(tgKode()==='AUTO') pesan+='\n\nIsi pesan dipilih otomatis untuk tiap pelanggan (pengingat ramah / pertama / kedua / terakhir).';
  if(!confirm(pesan)) return;
  tgSibuk=true;
  try{
    const r=await fetch('/api/tunggakan/antrean',{method:'POST',headers:tgJson(),
      body:JSON.stringify({ids,template:tgTemplate(),template_kode:tgKode(),batas_tanggal:tgBatas(),kirim_ulang:false})});
    const d=await r.json();
    if(!r.ok){
      if(r.status===409 && d.detail && d.detail.batch_id){ tgPantauAntrean(d.detail.batch_id); throw new Error(d.detail.pesan); }
      throw new Error(typeof d.detail==='string'?d.detail:'Gagal membuat antrean');
    }
    tgPilih.clear(); tgRender();
    const rinci=Object.entries(d.per_template||{}).map(([k,n])=>n+'× '+(k==='standar'?'pesan standar':tgNamaTpl(k))).join(', ');
    showToast(`${d.diantrekan} pesan masuk antrean server (${rinci}; sekitar ${d.perkiraan_menit} menit)`+(d.dilewati.length?`. ${d.dilewati.length} dilewati: ${[...new Set(d.dilewati.map(z=>z.alasan))].join('; ')}`:''),'success');
    tgPantauAntrean(d.batch_id);
  }catch(e){ showToast(e.message,'error'); }
  finally{ tgSibuk=false; }
}

async function tgCekAntreanAktif(){
  try{
    const r=await fetch('/api/tunggakan/antrean/aktif',{headers:tgAuth()});
    if(!r.ok) return;
    const d=await r.json();
    if(d.batch) tgPantauAntrean(d.batch.id);
  }catch(_){}
}

function tgTampilProgress(d){
  const proses=d.terkirim+d.gagal+d.dilewati;
  document.getElementById('tg-progress-txt').textContent=
    `Antrean #${d.id} berjalan di server: ${proses} dari ${d.total} diproses (${d.terkirim} terkirim, ${d.gagal} gagal${d.dilewati?', '+d.dilewati+' dilewati':''}). Halaman ini boleh ditutup.`;
}

function tgPantauAntrean(id){
  tgAntreanId=id;
  if(tgAntreanTimer) clearInterval(tgAntreanTimer);
  document.getElementById('tg-progress').classList.remove('hidden');
  const cek=async()=>{
    try{
      const r=await fetch('/api/tunggakan/antrean/'+id,{headers:tgAuth()});
      if(!r.ok) return;
      const d=await r.json();
      tgTampilProgress(d);
      await loadTunggakan();                       // segarkan kolom Status WA di tabel
      if(d.status!=='MENUNGGU' && d.status!=='BERJALAN'){
        clearInterval(tgAntreanTimer); tgAntreanTimer=null; tgAntreanId=null;
        document.getElementById('tg-progress').classList.add('hidden');
        showToast(`Antrean ${d.status==='DIBATALKAN'?'dihentikan':'selesai'}: ${d.terkirim} terkirim, ${d.gagal} gagal${d.dilewati?', '+d.dilewati+' dilewati':''}`, d.gagal?'info':'success');
      }
    }catch(_){}
  };
  cek();
  tgAntreanTimer=setInterval(cek,3000);
}

async function tgBatalAntrean(){
  if(!tgAntreanId) return;
  if(!confirm('Hentikan antrean? Pesan yang belum terkirim akan dibatalkan (yang sudah terkirim tidak bisa ditarik).')) return;
  try{
    const r=await fetch(`/api/tunggakan/antrean/${tgAntreanId}/batal`,{method:'POST',headers:tgAuth()});
    const d=await r.json().catch(()=>({}));
    showToast(r.ok?(d.message||'Antrean dihentikan'):(d.detail||'Gagal menghentikan antrean'), r.ok?'info':'error');
  }catch(e){ showToast(e.message,'error'); }
}

async function tgHapus(id){
  const x=tgData.find(v=>v.id===id)||{};
  if(!confirm(`Hapus ${x.nama||x.id_pelanggan||'pelanggan ini'} (${x.periode||'-'}) dari daftar?\nRiwayat pesan WA tetap tersimpan.`)) return;
  const r=await fetch('/api/tunggakan/'+id,{method:'DELETE',headers:tgAuth()});
  if(r.ok){ tgPilih.delete(id); loadTunggakan(); } else showToast('Gagal menghapus','error');
}
async function tgHapusMassal(ids,teks){
  if(!ids.length) return;
  if(!confirm(teks)) return;
  try{
    const r=await fetch('/api/tunggakan/hapus-massal',{method:'POST',headers:tgJson(),body:JSON.stringify({ids})}), d=await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(typeof d.detail==='string'?d.detail:'Gagal menghapus');
    ids.forEach(i=>tgPilih.delete(i)); showToast(d.message||'Data dihapus','success'); await loadTunggakan();
  }catch(e){ showToast(e.message,'error'); }
}
function tgHapusTerpilih(){
  const ids=[...tgPilih]; if(!ids.length){ showToast('Centang data yang akan dihapus','error'); return; }
  tgHapusMassal(ids,`Hapus ${ids.length} data yang dipilih dari daftar?\nRiwayat pesan WA yang sudah terkirim tetap tersimpan.`);
}
function tgHapusLunas(){
  const rows=tgByPeriode().filter(x=>x.kategori==='LUNAS');
  if(!rows.length){ showToast('Tidak ada data lunas','info'); return; }
  tgHapusMassal(rows.map(x=>x.id),`Hapus ${rows.length} data yang sudah LUNAS${tgPeriode?' pada Data '+tgPeriode:''}?\nData menunggak tidak ikut terhapus.`);
}
async function tgHapusSemua(){
  if(!tgData.length) return;
  if(!confirm('Kosongkan SEMUA bulan di daftar tunggakan? Status WA di daftar ini ikut terhapus, tetapi riwayat pesan yang sudah dikirim tetap tersimpan di database.')) return;
  const r=await fetch('/api/tunggakan',{method:'DELETE',headers:tgAuth()});
  if(r.ok){ tgPilih.clear(); document.getElementById('tg-summary').classList.add('hidden'); loadTunggakan(); } else showToast('Gagal mengosongkan','error');
}

// ── Riwayat pesan WA per pelanggan (#8) ──
let rwData=[], rwSt='', rwPilih=new Set();
const rwBadge=s=>({TERKIRIM:'bg-sky-100 text-sky-700',DITERIMA:'bg-indigo-100 text-indigo-700',DIBACA:'bg-emerald-100 text-emerald-700',GAGAL:'bg-rose-100 text-rose-700',ANTRE:'bg-slate-100 text-slate-600'}[s]||'bg-slate-100 text-slate-600');
const rwIkon=s=>({TERKIRIM:'fa-check',DITERIMA:'fa-check-double',DIBACA:'fa-check-double',GAGAL:'fa-xmark',ANTRE:'fa-clock'}[s]||'fa-circle');
const rwBadgeHtml=x=>`<span class="badge ${rwBadge(x.status)}" title="${tgEsc(x.respon||'')}"><i class="fa ${rwIkon(x.status)} mr-1"></i>${tgEsc(x.status)}</span>`;
const RW_KARTU=[
  {k:'',ic:'fa-comments',l:'Semua pesan',c:'#1a6fd4',bg:'#eff6ff'},
  {k:'TERKIRIM',ic:'fa-paper-plane',l:'Terkirim',c:'#0284c7',bg:'#f0f9ff'},
  {k:'BALASAN',ic:'fa-reply',l:'Ada balasan',c:'#d97706',bg:'#fffbeb'},
  {k:'GAGAL',ic:'fa-triangle-exclamation',l:'Gagal',c:'#e11d48',bg:'#fff1f2'},
];
const rwCocok=(x,k)=>!k||(k==='BALASAN'?!!x.balasan:x.status===k);
function rwSetSt(k,scroll){
  rwSt=(k&&rwSt===k)?'':k; document.getElementById('rw-status').value=rwSt; rwRender();
  if(scroll) document.getElementById('rw-body').closest('.tg-card').scrollIntoView({behavior:'smooth',block:'start'});
}
function rwRenderStats(){
  const tot=rwData.length;
  document.getElementById('rw-stats').innerHTML=RW_KARTU.map(c=>{
    const n=rwData.filter(x=>rwCocok(x,c.k)).length;
    return `<button type="button" class="tg-stat ${rwSt===c.k?'on':''}" style="--c:${c.c};--bg:${c.bg}" onclick="rwSetSt('${c.k}',true)" aria-label="Tampilkan: ${c.l}">
      <div class="top"><span class="ic"><i class="fa ${c.ic}"></i></span><span class="go"><i class="fa fa-filter"></i> ${rwSt===c.k&&c.k?'Aktif':'Saring'}</span></div>
      <div class="n">${n}</div><div class="l">${c.l}</div><div class="s">${tot&&c.k?Math.round(n/tot*100)+'% dari semua pesan':''}</div>
      <div class="bar"><i style="width:${tot?Math.round(n/tot*100):0}%"></i></div></button>`; }).join('');
}
function rwBarisTampil(){ return rwData.filter(x=>rwCocok(x,rwSt)); }
function rwUpdateBar(){
  const n=rwPilih.size, btn=document.getElementById('rw-hapus-btn');
  if(btn){ btn.classList.toggle('hidden',!n); document.getElementById('rw-hapus-n').textContent='Hapus terpilih ('+n+')'; }
  const all=document.getElementById('rw-all'), tampil=rwBarisTampil();
  if(all){ const dipilih=tampil.filter(x=>rwPilih.has(x.id)).length; all.checked=tampil.length>0&&dipilih===tampil.length; all.indeterminate=dipilih>0&&dipilih<tampil.length; }
}
function rwToggle(id,on){ if(on) rwPilih.add(id); else rwPilih.delete(id); rwUpdateBar(); }
function rwPilihSemua(on){ rwBarisTampil().forEach(x=>{ if(on) rwPilih.add(x.id); else rwPilih.delete(x.id); }); rwRender(); }
const RW_AKIBAT='\n\nYang dihapus hanya catatan di dashboard. Pesan WhatsApp yang sudah terkirim tidak ditarik.\nPerhatian: jeda minimum antar-pesan dan tahap pengingat pelanggan ini dihitung dari riwayat, jadi ikut berubah. Tindakan ini tidak bisa dibatalkan.';
async function rwHapusIds(ids,teks){
  if(!ids.length) return;
  if(!confirm(teks+RW_AKIBAT)) return;
  try{
    const r=ids.length===1
      ? await fetch('/api/wa/riwayat/'+ids[0],{method:'DELETE',headers:tgAuth()})
      : await fetch('/api/wa/riwayat/hapus-massal',{method:'POST',headers:tgJson(),body:JSON.stringify({ids})});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(typeof d.detail==='string'?d.detail:'Gagal menghapus');
    ids.forEach(i=>rwPilih.delete(i)); sheetTutup(); showToast(d.message||'Pesan dihapus','success'); await loadRiwayat();
  }catch(e){ showToast(e.message,'error'); }
}
function rwHapus(id){
  const x=rwData.find(v=>v.id===id)||{};
  rwHapusIds([id],`Hapus pesan ke ${x.nama||x.id_pelanggan||'pelanggan ini'} (${x.waktu_kirim||'-'}) dari riwayat?`);
}
function rwHapusTerpilih(){
  const ids=[...rwPilih]; if(!ids.length){ showToast('Centang pesan yang akan dihapus','error'); return; }
  rwHapusIds(ids,`Hapus ${ids.length} pesan yang dipilih dari riwayat?`);
}
function rwRender(){
  rwRenderStats();
  const rows=rwBarisTampil(), tb=document.getElementById('rw-body');
  document.getElementById('rw-count').textContent=rows.length;
  if(!rows.length){ rwUpdateBar(); tb.innerHTML='<tr><td colspan="10" class="text-center py-12 text-slate-400"><i class="fa fa-inbox text-2xl block mb-2 opacity-40"></i>Belum ada pesan yang cocok.</td></tr>'; return; }
  tb.innerHTML=rows.map(x=>`<tr onclick="rwDetail(${x.id})" class="${rwPilih.has(x.id)?'bg-rose-50/60':''}">
      <td onclick="event.stopPropagation()"><input type="checkbox" ${rwPilih.has(x.id)?'checked':''} onchange="rwToggle(${x.id},this.checked);this.closest('tr').classList.toggle('bg-rose-50/60',this.checked)"></td>
      <td class="whitespace-nowrap">${tgEsc(x.waktu_kirim||'-')}</td>
      <td class="font-mono">${tgEsc(x.id_pelanggan)}</td>
      <td><div class="flex items-center gap-2.5">${tgAv(x.nama)}<span class="font-semibold text-slate-700">${tgNm(x)}</span></div></td>
      <td>${tgEsc(x.no_hp)}</td>
      <td>${x.template_kode?tgEsc(tgNamaTpl(x.template_kode)):'<span class="text-slate-400">Standar</span>'}</td>
      <td>${rwBadgeHtml(x)}</td>
      <td class="whitespace-nowrap text-xs">${x.waktu_dibaca?tgEsc(x.waktu_dibaca):'<span class="text-slate-300">-</span>'}</td>
      <td class="text-xs max-w-[200px]">${x.balasan?'<span class="text-emerald-700">'+tgEsc(x.balasan)+'</span><br><span class="text-slate-400">'+tgEsc(x.waktu_balasan||'')+'</span>':'<span class="text-slate-300">-</span>'}</td>
      <td class="text-center"><button type="button" class="sh-btn" style="padding:5px 10px" onclick="event.stopPropagation();rwDetail(${x.id})"><i class="fa fa-eye"></i> Lihat</button>
        <button type="button" class="sh-btn" style="padding:5px 9px;color:#e11d48" title="Hapus dari riwayat" onclick="event.stopPropagation();rwHapus(${x.id})"><i class="fa fa-trash"></i></button></td></tr>`).join('');
  rwUpdateBar();
}
async function loadRiwayat(){
  if(!token) return;
  const q=document.getElementById('rw-q').value.trim();
  const tb=document.getElementById('rw-body');
  tb.innerHTML='<tr><td colspan="10" class="text-center py-10 text-slate-400"><i class="fa fa-spinner fa-spin mr-2"></i>Memuat riwayat...</td></tr>';
  try{
    const r=await fetch('/api/wa/riwayat?limit=1000'+(q?'&q='+encodeURIComponent(q):''),{headers:tgAuth()});
    const d=await r.json();
    if(!r.ok) throw new Error(typeof d.detail==='string'?d.detail:'Gagal memuat riwayat');
    rwData=d; { const ada=new Set(d.map(v=>v.id)); [...rwPilih].forEach(i=>{ if(!ada.has(i)) rwPilih.delete(i); }); } document.getElementById('rw-status').value=rwSt; rwRender();
    if(!tgTpl.siap && !tgTpl.list.length) tgInitTemplate().then(rwRender).catch(()=>{});
  }catch(e){ rwData=[]; rwRenderStats(); tb.innerHTML='<tr><td colspan="10" class="text-center py-10 text-rose-500">'+tgEsc(e.message)+'</td></tr>'; }
}
function rwDetail(id){
  const x=rwData.find(v=>v.id===id); if(!x) return;
  const rank={ANTRE:0,TERKIRIM:1,DITERIMA:2,DIBACA:3}[x.status]??0, gagal=x.status==='GAGAL';
  const jam=t=>t?tgEsc(String(t).slice(5,16).replace('-','/')):'';
  const steps=[['Terkirim','fa-paper-plane',rank>=1,x.waktu_kirim],['Diterima','fa-check-double',rank>=2,x.waktu_diterima],['Dibaca','fa-envelope-open',rank>=3,x.waktu_dibaca],['Dibalas','fa-reply',!!x.balasan,x.waktu_balasan]];
  document.getElementById('sheet-head').innerHTML=`${tgAv(x.nama,true)}<div class="min-w-0"><p class="font-extrabold text-slate-800 truncate">${tgNm(x)}</p><p class="text-xs text-slate-400"><span class="font-mono">${tgEsc(x.id_pelanggan)}</span> · ${tgEsc(x.no_hp)}</p></div>`;
  document.getElementById('sheet-body').innerHTML=`
    ${gagal?`<div class="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2.5 mb-4"><i class="fa fa-triangle-exclamation mr-1"></i>Pesan gagal dikirim${x.respon?': '+tgEsc(x.respon):'.'}</div>`
      :`<div class="tl">${steps.map(s=>`<div class="st ${s[2]?'on':''}"><div class="dot"><i class="fa ${s[1]}"></i></div>${s[0]}<small>${s[2]&&s[3]?jam(s[3]):'&nbsp;'}</small></div>`).join('')}</div>`}
    <p class="sh-h3"><i class="fa-brands fa-whatsapp text-emerald-500"></i>Isi percakapan</p>
    <div class="wa-chat">
      <div class="wa-b out">${tgEsc(x.pesan||'(isi pesan tidak tersimpan)')}<span class="tm">${tgEsc(x.waktu_kirim||'')} ${gagal?'':'<i class="fa '+rwIkon(x.status)+(rank>=3?' text-sky-500':'')+'"></i>'}</span></div>
      ${x.balasan?`<div class="wa-b in">${tgEsc(x.balasan)}<span class="tm">${tgEsc(x.waktu_balasan||'')}</span></div>`:''}
    </div>
    <p class="sh-h3"><i class="fa fa-circle-info text-slate-400"></i>Rincian</p>
    <div class="sh-grid">
      ${sh('Status',rwBadgeHtml(x))}${sh('Template',x.template_kode?tgEsc(tgNamaTpl(x.template_kode)):'Standar')}
      ${sh('Periode',tgEsc(x.periode||'-'))}${sh('Tagihan',tgRp(x.nominal))}
      ${sh('Dikirim oleh',tgEsc(x.dikirim_oleh||'-'))}${sh('Batch antrean',x.batch_id?'#'+x.batch_id:'Kirim langsung')}
      ${sh('Respon server',tgEsc(x.respon||'-'),true)}
    </div>`;
  document.getElementById('sheet-foot').innerHTML=`
    <button class="sh-btn" onclick="tgSalin(${JSON.stringify(x.pesan||'').replace(/"/g,'&quot;')},'Isi pesan')"><i class="fa fa-copy"></i> Salin pesan</button>
    <button class="sh-btn" onclick="sheetTutup();document.getElementById('rw-q').value='${tgEsc(x.id_pelanggan)}';loadRiwayat()"><i class="fa fa-filter"></i> Pesan pelanggan ini</button>
    <button class="sh-btn" style="color:#e11d48" onclick="rwHapus(${x.id})"><i class="fa fa-trash"></i> Hapus</button>`;
  sheetBuka();
}
function rwEksporCsv(){
  const rows=rwData.filter(x=>rwCocok(x,rwSt)); if(!rows.length){ showToast('Tidak ada data untuk diekspor','error'); return; }
  unduhCsv('riwayat_wa_'+new Date().toISOString().slice(0,10)+'.csv',[['Waktu kirim','ID Pelanggan','Nama','No WA','Template','Status','Dibaca','Balasan','Pesan']]
    .concat(rows.map(x=>[x.waktu_kirim,x.id_pelanggan,x.nama,x.no_hp,x.template_kode||'Standar',x.status,x.waktu_dibaca,x.balasan,x.pesan])));
  showToast(rows.length+' baris diekspor','success');
}

// ── Analitik & Laporan (admin) ──
let anData=null, anPeriode=null, anChart={};
const anNum=n=>n==null?'-':Math.round(n).toLocaleString('id-ID');
const anPct=v=>v==null?'-':v.toFixed(1).replace('.',',')+'%';
const anPendek=p=>String(p||'').replace('Januari','Jan').replace('Februari','Feb').replace('Agustus','Agu').replace('September','Sep').replace('Oktober','Okt').replace('November','Nov').replace('Desember','Des');
function anDelta(v,bagusNaik,satuan){
  if(v==null) return '<span class="an-d an-d0">vs bulan lalu: -</span>';
  if(v===0) return '<span class="an-d an-d0">tetap</span>';
  const naik=v>0, baik=naik===bagusNaik;
  const txt=satuan==='rp'?'Rp '+Math.abs(Math.round(v)).toLocaleString('id-ID'):Math.abs(v).toFixed(1).replace('.',',')+' poin';
  return `<span class="an-d ${baik?'an-dg':'an-db'}"><i class="fa fa-arrow-${naik?'up':'down'}"></i> ${txt}</span>`;
}
async function loadAnalitik(){
  if(!token) return;
  try{
    const r=await fetch('/api/analitik',{headers:tgAuth()}), d=await r.json();
    if(!r.ok) throw new Error(typeof d.detail==='string'?d.detail:'Gagal memuat analitik');
    anData=d;
    if(anPeriode===null||!d.bulan.some(b=>b.periode===anPeriode)) anPeriode=d.bulan.length?d.bulan[d.bulan.length-1].periode:'';
    anRender();
  }catch(e){ showToast(e.message,'error'); }
}
function anPilih(p){ anPeriode=p; anRender(); }
function anScroll(id){ document.getElementById(id).scrollIntoView({behavior:'smooth',block:'start'}); }
function anUnduh(jenis){
  if(!anData||!anData.bulan.length){ showToast('Belum ada data untuk dilaporkan','error'); return; }
  window.open('/api/analitik/laporan/'+jenis+'?periode='+encodeURIComponent(anPeriode)+'&token='+token,'_blank');
}
function anRender(){
  const d=anData, ada=d&&d.bulan.length;
  document.getElementById('an-empty').classList.toggle('hidden',!!ada);
  document.getElementById('an-body').classList.toggle('hidden',!ada);
  if(!ada) return;
  const bln=d.bulan, cur=bln.find(b=>b.periode===anPeriode)||bln[bln.length-1];
  // pilihan bulan (terbaru dulu)
  document.getElementById('an-chips').innerHTML='<span class="tg-per-l"><i class="fa fa-calendar-days mr-1"></i>Bulan yang dilaporkan</span>'
    +[...bln].reverse().map(b=>`<button type="button" class="tg-per ${b.periode===cur.periode?'on':''}" onclick="anPilih(${JSON.stringify(b.periode).replace(/"/g,'&quot;')})"><i class="fa fa-folder"></i>${tgEsc(b.periode)}<span>${b.total}</span></button>`).join('');
  // KPI
  const dl=cur.delta, K=[
    {ic:'fa-sack-xmark',l:'Nominal belum lunas',n:tgRp(cur.nominal_belum_lunas),s:anDelta(dl.nominal_belum_lunas,false,'rp'),c:'#d97706',bg:'#fffbeb',go:'an-sec-trend'},
    {ic:'fa-reply',l:'Pesan dibalas',n:anPct(cur.persen_balasan),s:anDelta(dl.persen_balasan,true),c:'#7c3aed',bg:'#f5f3ff',go:'an-sec-wa',sub:cur.wa_balasan+' balasan'},
  ];
  document.getElementById('an-kpi').innerHTML=K.map(k=>`<button type="button" class="tg-stat" style="--c:${k.c};--bg:${k.bg}" onclick="anScroll('${k.go}')" aria-label="Lihat grafik terkait">
    <div class="top"><span class="ic"><i class="fa ${k.ic}"></i></span><span class="go"><i class="fa fa-arrow-down"></i> Lihat</span></div>
    <div class="n" style="font-size:${k.n.length>9?'1.3rem':'1.75rem'}">${tgEsc(k.n)}</div><div class="l">${k.l}</div><div class="s">${k.sub?tgEsc(k.sub):'&nbsp;'}</div><div class="mt-2">${k.s}</div></button>`).join('');
  anCharts(bln,cur);
  document.getElementById('an-wa-note').classList.toggle('hidden',d.webhook_aktif||!bln.some(b=>b.wa_terkirim));
  // tabel bulan
  document.getElementById('an-tb-bulan').innerHTML=[...bln].reverse().map(b=>`<tr onclick="anPilih(${JSON.stringify(b.periode).replace(/"/g,'&quot;')});anScroll('an-kpi')" class="${b.periode===cur.periode?'an-row-on':''}">
    <td class="font-bold text-slate-700"><i class="fa fa-folder text-amber-400 mr-2"></i>${tgEsc(b.periode)}</td>
    <td class="text-right">${b.total}</td><td class="text-right text-emerald-600 font-semibold">${b.lunas}</td><td class="text-right text-amber-600 font-semibold">${b.menunggak}</td>
    <td class="text-right whitespace-nowrap">${tgRp(b.nominal_belum_lunas)}</td>
    <td style="min-width:150px"><div class="flex items-center gap-2"><div class="an-bar"><i style="width:${b.persen_lunas||0}%;background:#10b981"></i></div><b class="text-xs w-12">${anPct(b.persen_lunas)}</b></div></td>
    <td class="text-right">${b.wa_terkirim}</td><td class="text-right">${anPct(b.persen_baca)}</td><td class="text-right">${anPct(b.persen_balasan)}</td></tr>`).join('');
  // tabel template
  const tp=d.template;
  document.getElementById('an-tb-tpl').innerHTML=tp.length?tp.map((t,i)=>`<tr onclick="anTplInfo(${i})">
    <td><div class="font-bold text-slate-700">${tgEsc(t.nama)} ${t.terbaik?'<span class="badge bg-amber-100 text-amber-700"><i class="fa fa-trophy mr-1"></i>TERBAIK</span>':''} ${t.data_cukup?'':'<span class="badge bg-slate-100 text-slate-500">DATA SEDIKIT</span>'}</div>
      <div class="text-[10px] text-slate-400">${t.tahap==null?'Tanpa tahap':'Tahap '+t.tahap} · ${tgEsc(t.kode)}</div></td>
    <td class="text-right">${t.pesan}</td><td class="text-right">${t.pelanggan}</td><td class="text-right">${anPct(t.persen_baca)}</td><td class="text-right">${anPct(t.persen_balasan)}</td>
    <td class="text-right font-bold text-emerald-600">${t.lunas}</td>
    <td><div class="flex items-center gap-2"><div class="an-bar"><i style="width:${t.konversi||0}%;background:${t.terbaik?'#f59e0b':'#1a6fd4'}"></i></div><b class="text-xs w-12">${anPct(t.konversi)}</b></div></td>
    <td class="text-right">${t.rata_hari==null?'-':String(t.rata_hari).replace('.',',')+' hari'}</td></tr>`).join('')
    :'<tr><td colspan="8" class="text-center py-10 text-slate-400">Belum ada pesan WhatsApp yang terkirim.</td></tr>';
  document.getElementById('an-tpl-note').textContent=(d.catatan||[])[2]||'';
}
function anTplInfo(i){
  const t=anData.template[i]; if(!t) return;
  document.getElementById('sheet-head').innerHTML=`<span class="tg-av lg" style="background:#fef3c7;color:#b45309"><i class="fa fa-comment-dots"></i></span><div class="min-w-0"><p class="font-extrabold text-slate-800">${tgEsc(t.nama)}</p><p class="text-xs text-slate-400">${t.tahap==null?'Tanpa tahap':'Tahap '+t.tahap} · ${tgEsc(t.kode)}</p></div>`;
  document.getElementById('sheet-body').innerHTML=`<div class="sh-grid">
    ${sh('Pesan terkirim',t.pesan)}${sh('Pelanggan menerima',t.pelanggan)}
    ${sh('Dibaca',t.dibaca+' ('+anPct(t.persen_baca)+')')}${sh('Dibalas',t.balasan+' ('+anPct(t.persen_balasan)+')')}
    ${sh('Lunas setelahnya',t.lunas)}${sh('Konversi',anPct(t.konversi))}
    ${sh('Rata-rata hari sampai lunas',t.rata_hari==null?'-':String(t.rata_hari).replace('.',',')+' hari',true)}</div>
    <p class="text-[11px] text-slate-500 bg-slate-50 rounded-lg p-3 mt-4 leading-relaxed">${t.data_cukup?'':'<b>Data masih sedikit</b> (kurang dari 5 pelanggan), jadi persentasenya belum bisa diandalkan. '}Konversi menunjukkan hubungan waktu: pelanggan lunas setelah menerima template ini. Pelanggan bisa saja membayar tanpa dipengaruhi pesan.</p>`;
  document.getElementById('sheet-foot').innerHTML='<button class="sh-btn" onclick="sheetTutup()">Tutup</button>';
  sheetBuka();
}
function anCharts(bln,cur){
  const gelap=document.body.classList.contains('dark'), tick=gelap?'#94a3b8':'#64748b', grid=gelap?'rgba(148,163,184,.15)':'rgba(100,116,139,.12)';
  const lab=bln.map(b=>anPendek(b.periode)), sel=bln.map(b=>b.periode===cur.periode);
  const base={responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
    plugins:{legend:{position:'bottom',labels:{boxWidth:10,usePointStyle:true,color:tick,font:{size:11}}}},
    onClick:(e,els)=>{ if(els.length) anPilih(bln[els[0].index].periode); },
    onHover:(e,els)=>{ e.native.target.style.cursor=els.length?'pointer':'default'; }};
  const sc=(pos,extra)=>Object.assign({position:pos,ticks:{color:tick},grid:{color:grid}},extra||{});
  const buat=(id,cfg)=>{ if(anChart[id]) anChart[id].destroy(); anChart[id]=new Chart(document.getElementById(id),cfg); };
  buat('an-c-trend',{data:{labels:lab,datasets:[
    {type:'bar',order:2,label:'Nominal belum lunas (juta Rp)',data:bln.map(b=>+(b.nominal_belum_lunas/1e6).toFixed(2)),yAxisID:'y',borderRadius:6,
      backgroundColor:sel.map(s=>s?'#d97706':'rgba(217,119,6,.35)')},
    {type:'line',order:1,label:'% lunas',data:bln.map(b=>b.persen_lunas),yAxisID:'y1',borderColor:'#10b981',backgroundColor:'#10b981',tension:.3,pointRadius:sel.map(s=>s?7:4),pointHoverRadius:8}]},
    options:Object.assign({},base,{scales:{x:{ticks:{color:tick},grid:{display:false}},y:sc('left',{beginAtZero:true,title:{display:true,text:'Juta Rp',color:tick}}),
      y1:sc('right',{min:0,max:100,grid:{drawOnChartArea:false},ticks:{color:tick,callback:v=>v+'%'}})}})});
  buat('an-c-wa',{data:{labels:lab,datasets:[
    {type:'bar',order:3,label:'Pesan terkirim',data:bln.map(b=>b.wa_terkirim),yAxisID:'y',borderRadius:6,backgroundColor:sel.map(s=>s?'#1a6fd4':'rgba(26,111,212,.35)')},
    {type:'line',order:1,label:'% dibaca',data:bln.map(b=>b.persen_baca),yAxisID:'y1',borderColor:'#059669',backgroundColor:'#059669',tension:.3,spanGaps:true,pointRadius:4},
    {type:'line',order:1,label:'% dibalas',data:bln.map(b=>b.persen_balasan),yAxisID:'y1',borderColor:'#7c3aed',backgroundColor:'#7c3aed',tension:.3,spanGaps:true,pointRadius:4}]},
    options:Object.assign({},base,{scales:{x:{ticks:{color:tick},grid:{display:false}},y:sc('left',{beginAtZero:true,title:{display:true,text:'Pesan',color:tick}}),
      y1:sc('right',{min:0,max:100,grid:{drawOnChartArea:false},ticks:{color:tick,callback:v=>v+'%'}})}})});
}


// === Dashboard Penagihan (animasi) ===
let dbDonut=null, dbBar=null;
function dbCount(el, to, fmt, ms=1100){
  const t0=performance.now(); fmt=fmt||(v=>Math.round(v).toLocaleString('id-ID'));
  (function f(t){ const p=Math.min(1,(t-t0)/ms), e=1-Math.pow(1-p,3); el.textContent=fmt(to*e); if(p<1) requestAnimationFrame(f); })(t0);
}
const dbRp=v=>v>=1e9?'Rp '+(v/1e9).toFixed(1).replace('.',',')+' M':v>=1e6?'Rp '+(v/1e6).toFixed(1).replace('.',',')+' jt':'Rp '+Math.round(v).toLocaleString('id-ID');
async function loadDash(){
  if(!token) return;
  const cu=window.currentUser||{};
  const h=new Date().getHours(), s=h<11?'Selamat pagi':h<15?'Selamat siang':h<18?'Selamat sore':'Selamat malam';
  document.getElementById('db-hello').textContent=`${s}, ${cu.full_name||cu.username||'Admin'}`;
  const H={'Authorization':'Bearer '+token};
  let tg=[], rw=[];
  try{ const r=await fetch('/api/tunggakan',{headers:H}); if(r.ok) tg=await r.json(); }catch(e){}
  try{ const r=await fetch('/api/wa/riwayat?limit=1000',{headers:H}); if(r.ok) rw=await r.json(); }catch(e){}
  const cnt=k=>tg.filter(x=>x.kategori===k).length;
  const tung=tg.filter(x=>x.kategori==='MENUNGGAK');
  const nom=tung.reduce((a,x)=>a+(x.nominal||0),0);
  const dikirim=tung.filter(x=>x.wa_status==='TERKIRIM').length;
  const pct=tung.length?Math.round(dikirim*100/tung.length):0;
  document.getElementById('db-sub').textContent=tg.length?`${tung.length} pelanggan menunggak dengan total ${dbRp(nom)}. ${rw.length} pesan WA tercatat.`:'Belum ada data. Mulai dengan mengimpor file tunggakan.';
  [['k-total',tg.length],['k-tunggak',tung.length],['k-belum',cnt('BELUM_JATUH_TEMPO')],['k-lunas',cnt('LUNAS')]].forEach(([id,v])=>dbCount(document.getElementById(id),v));
  dbCount(document.getElementById('k-nominal'),nom,dbRp);
  // donut
  const col=getComputedStyle(document.body).getPropertyValue('color')||'#334155';
  if(dbDonut) dbDonut.destroy();
  dbDonut=new Chart(document.getElementById('db-donut'),{type:'doughnut',data:{labels:['Menunggak','Belum jatuh tempo','Lunas'],datasets:[{data:[tung.length,cnt('BELUM_JATUH_TEMPO'),cnt('LUNAS')],backgroundColor:['#e11d48','#f59e0b','#10b981'],borderWidth:0,hoverOffset:10}]},options:{maintainAspectRatio:false,cutout:'68%',animation:{animateRotate:true,duration:1400,easing:'easeOutQuart'},plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:8,font:{size:11}}}}}});
  // bar per periode
  const per={}; tg.forEach(x=>{ if(x.kategori==='LUNAS') return; const k=x.periode||'Tanpa periode'; per[k]=(per[k]||0)+(x.nominal||0); });
  const ks=Object.keys(per).sort((a,b)=>tgPerUrut(a)-tgPerUrut(b));
  if(dbBar) dbBar.destroy();
  dbBar=new Chart(document.getElementById('db-bar'),{type:'bar',data:{labels:ks,datasets:[{label:'Nominal',data:ks.map(k=>per[k]),borderRadius:10,backgroundColor:'#1a6fd4',hoverBackgroundColor:'#fbbf24'}]},options:{maintainAspectRatio:false,animation:{duration:1300,easing:'easeOutBack',delay:c=>c.dataIndex*120},plugins:{legend:{display:false}},scales:{x:{grid:{display:false}},y:{ticks:{callback:v=>dbRp(v)},grid:{color:'rgba(148,163,184,.2)'}}}}});
  // ring WA
  const len=314, ring=document.getElementById('db-ring-v');
  ring.style.setProperty('--off',len-len*pct/100); ring.style.animation='none'; void ring.getBoundingClientRect(); ring.style.animation='';
  dbCount(document.getElementById('db-ring-t'),pct,v=>Math.round(v)+'%');
  const st=k=>rw.filter(x=>x.status===k).length;
  document.getElementById('db-wa-det').innerHTML=`<div><b class="text-slate-700">${dikirim}</b> dari ${tung.length} menunggak sudah dikirimi</div><div><span class="text-sky-600 font-bold">${st('TERKIRIM')}</span> terkirim · <span class="text-emerald-600 font-bold">${st('DIBACA')}</span> dibaca</div><div><span class="text-violet-600 font-bold">${rw.filter(x=>x.balasan).length}</span> dibalas · <span class="text-rose-600 font-bold">${st('GAGAL')}</span> gagal</div>`;
  // top menunggak
  const top=[...tung].sort((a,b)=>(b.hari_terlambat||0)-(a.hari_terlambat||0)).slice(0,6);
  document.getElementById('db-top').innerHTML=top.length?top.map((x,i)=>`<div class="db-row" style="--i:${i}">${tgAv(x.nama,false)}<div class="flex-1 min-w-0"><div class="font-semibold truncate">${tgNm(x)}</div><div class="text-[10px] text-slate-400">${tgEsc(x.id_pelanggan)} · ${tgEsc(x.periode||'-')}</div></div><div class="text-right"><div class="font-bold text-rose-600">${tgRp(x.nominal)}</div><div class="text-[10px] text-slate-400">${x.hari_terlambat||0} hari terlambat</div></div></div>`).join(''):'<p class="text-xs text-slate-400 py-6 text-center">Tidak ada tagihan menunggak. 🎉</p>';
}


// ============================================================
// FITUR 2a: Tandai Lunas Manual
// ============================================================
async function tgTandaiLunas(id){
  const x=tgData.find(v=>v.id===id); if(!x) return;
  if(!confirm(`Tandai ${x.nama||x.id_pelanggan} sebagai LUNAS?\n\nStatus pembayaran akan diubah ke LUNAS dan waktu pelunasan dicatat sekarang.`)) return;
  try{
    const r=await fetch(`/api/tunggakan/${id}`,{method:'PUT',headers:tgJson(),body:JSON.stringify({status_bayar:'LUNAS'})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'Gagal mengupdate');
    showToast(`${x.nama||x.id_pelanggan} ditandai LUNAS ✅`,'success');
    sheetTutup();
    await loadTunggakan();
  }catch(e){ showToast(e.message,'error'); }
}

// ============================================================
// FITUR 2b: Edit Data Kontak Pelanggan
// ============================================================
function tgEditData(id){
  const x=tgData.find(v=>v.id===id); if(!x) return;
  // Buat modal inline jika belum ada
  let mod=document.getElementById('tg-edit-modal');
  if(!mod){
    mod=document.createElement('div');
    mod.id='tg-edit-modal';
    mod.className='hidden fixed inset-0 z-[260] bg-black/50 flex items-center justify-center p-4';
    mod.innerHTML=`<div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
      <div class="px-5 py-4 border-b border-slate-100 flex items-center">
        <p class="font-bold text-slate-800 text-sm"><i class="fa fa-pen text-blue-500 mr-2"></i>Edit Data Pelanggan</p>
        <button onclick="document.getElementById('tg-edit-modal').classList.add('hidden')" class="ml-auto text-slate-400 hover:text-slate-700"><i class="fa fa-xmark"></i></button>
      </div>
      <div class="p-5 space-y-4">
        <div><label class="block text-xs font-bold text-slate-500 mb-1">NAMA</label><input id="te-nama" class="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" placeholder="Nama pelanggan"></div>
        <div><label class="block text-xs font-bold text-slate-500 mb-1">NOMOR WHATSAPP</label><input id="te-hp" class="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" placeholder="628xxx (tanpa + dan spasi)"></div>
        <div><label class="block text-xs font-bold text-slate-500 mb-1">ALAMAT</label><input id="te-alamat" class="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" placeholder="Alamat pelanggan"></div>
      </div>
      <div class="px-5 py-4 border-t border-slate-100 flex justify-end gap-3">
        <button onclick="document.getElementById('tg-edit-modal').classList.add('hidden')" class="px-4 py-2 text-sm font-semibold text-slate-500">Batal</button>
        <button id="te-save" class="btn-p"><i class="fa fa-floppy-disk"></i> Simpan</button>
      </div>
    </div>`;
    document.body.appendChild(mod);
  }
  document.getElementById('te-nama').value=x.nama||'';
  document.getElementById('te-hp').value=x.no_hp||'';
  document.getElementById('te-alamat').value=x.alamat||'';
  mod.classList.remove('hidden');
  document.getElementById('te-save').onclick=async()=>{
    const btn=document.getElementById('te-save'); btn.disabled=true; btn.innerHTML='<i class="fa fa-spinner fa-spin"></i> Menyimpan...';
    try{
      const body={nama:document.getElementById('te-nama').value.trim(),no_hp:document.getElementById('te-hp').value.trim(),alamat:document.getElementById('te-alamat').value.trim()};
      const r=await fetch(`/api/tunggakan/${id}`,{method:'PUT',headers:tgJson(),body:JSON.stringify(body)});
      const d=await r.json();
      if(!r.ok) throw new Error(d.detail||'Gagal menyimpan');
      showToast('Data pelanggan berhasil diperbarui ✅','success');
      mod.classList.add('hidden');
      await loadTunggakan();
      tgDetail(id);
    }catch(e){ showToast(e.message,'error'); }
    finally{ btn.disabled=false; btn.innerHTML='<i class="fa fa-floppy-disk"></i> Simpan'; }
  };
}

// ============================================================
// FITUR 1: Sinkronisasi dari Catat Meter
// ============================================================
async function tgSyncMeter(){
  if(!token) return;
  // Muat daftar periode dari Catat Meter
  let periodeList=[];
  try{
    const r=await fetch('/api/tunggakan/sync-meter/periode',{headers:tgAuth()});
    if(r.ok) periodeList=await r.json();
  }catch(e){ showToast('Gagal memuat periode dari Catat Meter: '+e.message,'error'); return; }
  if(!periodeList.length){ showToast('Tidak ada data di Catat Meter yang bisa disinkronkan (status SUCCESS/VALID)','info'); return; }

  // Buat modal pilih periode
  let mod=document.getElementById('tg-sync-modal');
  if(!mod){
    mod=document.createElement('div');
    mod.id='tg-sync-modal';
    mod.className='hidden fixed inset-0 z-[260] bg-black/50 flex items-center justify-center p-4';
    mod.innerHTML=`<div class="bg-white rounded-2xl shadow-2xl w-full max-w-md">
      <div class="px-5 py-4 border-b border-slate-100 flex items-center">
        <p class="font-bold text-slate-800 text-sm"><i class="fa fa-rotate text-blue-500 mr-2"></i>Tarik Data dari Catat Meter</p>
        <button onclick="document.getElementById('tg-sync-modal').classList.add('hidden')" class="ml-auto text-slate-400 hover:text-slate-700"><i class="fa fa-xmark"></i></button>
      </div>
      <div class="p-5">
        <p class="text-xs text-slate-500 mb-3">Pilih periode yang ingin ditarik dari database Catat Meter (status SUCCESS/VALID). Data akan langsung dimasukkan ke tabel tagihan tanpa perlu ekspor Excel.</p>
        <div><label class="block text-xs font-bold text-slate-500 mb-1">PILIH PERIODE</label><select id="tsm-periode" class="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"></select></div>
        <div class="mt-3"><label class="block text-xs font-bold text-slate-500 mb-1">BATAS TANGGAL BAYAR</label><input id="tsm-batas" type="number" min="1" max="31" value="20" class="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"></div>
        <div id="tsm-result" class="hidden mt-3 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2"></div>
      </div>
      <div class="px-5 py-4 border-t border-slate-100 flex justify-end gap-3">
        <button onclick="document.getElementById('tg-sync-modal').classList.add('hidden')" class="px-4 py-2 text-sm font-semibold text-slate-500">Batal</button>
        <button id="tsm-btn" class="btn-p"><i class="fa fa-rotate"></i> Tarik Data</button>
      </div>
    </div>`;
    document.body.appendChild(mod);
  }
  const sel=document.getElementById('tsm-periode');
  sel.innerHTML=periodeList.map(p=>`<option value="${tgEsc(String(p))}">${tgEsc(String(p))}</option>`).join('');
  document.getElementById('tsm-result').classList.add('hidden');
  mod.classList.remove('hidden');
  document.getElementById('tsm-btn').onclick=async()=>{
    const btn=document.getElementById('tsm-btn'); btn.disabled=true; btn.innerHTML='<i class="fa fa-spinner fa-spin"></i> Menarik...';
    const res=document.getElementById('tsm-result');
    try{
      const periode=document.getElementById('tsm-periode').value;
      const batas=parseInt(document.getElementById('tsm-batas').value)||20;
      const r=await fetch('/api/tunggakan/sync-meter',{method:'POST',headers:tgJson(),body:JSON.stringify({periode,batas_tanggal:batas})});
      const d=await r.json();
      if(!r.ok) throw new Error(d.detail||'Gagal menarik data');
      res.innerHTML=`<i class="fa fa-circle-check mr-1"></i><b>${d.ditambahkan||0}</b> baru ditambahkan, <b>${d.diperbarui||0}</b> diperbarui dari periode <b>${tgEsc(periode)}</b>.`;
      res.classList.remove('hidden');
      showToast(`Sinkronisasi selesai: ${d.ditambahkan||0} baru, ${d.diperbarui||0} diperbarui`,'success');
      await loadTunggakan();
    }catch(e){ showToast(e.message,'error'); }
    finally{ btn.disabled=false; btn.innerHTML='<i class="fa fa-rotate"></i> Tarik Data'; }
  };
}

// ============================================================
// FITUR 4: Status Perangkat Fonnte (topbar widget)
// ============================================================
async function checkDeviceStatus(force=false){
  if(!token) return;
  const dot=document.getElementById('tb-fonnte-dot');
  const txt=document.getElementById('tb-fonnte-text');
  const wrap=document.getElementById('tb-fonnte-status');
  if(!dot||!txt||!wrap) return;
  if(!force && wrap._lastCheck && (Date.now()-wrap._lastCheck)<60000) return; // cache 60s
  wrap._lastCheck=Date.now();
  try{
    const r=await fetch('/api/wa/status-perangkat',{headers:tgAuth()});
    if(!r.ok){ dot.className='w-2 h-2 rounded-full bg-rose-400'; txt.textContent='WA Error'; return; }
    const d=await r.json();
    const online=d.status==='online'||d.status==='connected';
    dot.className='w-2 h-2 rounded-full '+(online?'bg-emerald-400':'bg-rose-400');
    let label=online?'WA Online':'WA Terputus';
    if(d.quota!=null) label+=` · ${d.quota} pesan`;
    txt.textContent=label;
    wrap.title=`Status: ${d.status||'-'} | ${d.message||''} (klik untuk refresh)`;
  }catch(e){
    if(dot){ dot.className='w-2 h-2 rounded-full bg-slate-400'; txt.textContent='WA -'; }
  }
}

// ============================================================
// FITUR 5: Jam Operasional (topbar widget + modal)
// ============================================================
async function loadJamStatus(){
  if(!token) return;
  const el=document.getElementById('tb-jam-text');
  if(!el) return;
  try{
    const r=await fetch('/api/tunggakan/antrean/jam-operasional',{headers:tgAuth()});
    if(!r.ok) return;
    const d=await r.json();
    if(d.aktif) el.textContent=`${d.mulai||'08:00'} - ${d.selesai||'17:00'}`;
    else el.textContent='Jam ops: nonaktif';
  }catch(e){}
}

function openJamOperasionalModal(){
  if(!token){ showToast('Harus login dulu','error'); return; }
  let mod=document.getElementById('tg-jam-modal');
  if(!mod){
    mod=document.createElement('div');
    mod.id='tg-jam-modal';
    mod.className='hidden fixed inset-0 z-[260] bg-black/50 flex items-center justify-center p-4';
    mod.innerHTML=`<div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
      <div class="px-5 py-4 border-b border-slate-100 flex items-center">
        <p class="font-bold text-slate-800 text-sm"><i class="fa fa-clock text-blue-500 mr-2"></i>Atur Jam Operasional Pengiriman WA</p>
        <button onclick="document.getElementById('tg-jam-modal').classList.add('hidden')" class="ml-auto text-slate-400 hover:text-slate-700"><i class="fa fa-xmark"></i></button>
      </div>
      <div class="p-5 space-y-4">
        <p class="text-xs text-slate-500">Pesan WA hanya akan dikirim dalam jam yang ditentukan. Di luar jam ini, worker otomatis pause dan lanjut keesokan harinya.</p>
        <label class="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" id="jam-aktif" class="w-4 h-4 accent-blue-600">
          <span class="text-sm font-semibold text-slate-700">Aktifkan pembatasan jam operasional</span>
        </label>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="block text-xs font-bold text-slate-500 mb-1">JAM MULAI</label><input type="time" id="jam-mulai" value="08:00" class="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"></div>
          <div><label class="block text-xs font-bold text-slate-500 mb-1">JAM SELESAI</label><input type="time" id="jam-selesai" value="17:00" class="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"></div>
        </div>
      </div>
      <div class="px-5 py-4 border-t border-slate-100 flex justify-end gap-3">
        <button onclick="document.getElementById('tg-jam-modal').classList.add('hidden')" class="px-4 py-2 text-sm font-semibold text-slate-500">Batal</button>
        <button id="jam-save" class="btn-p"><i class="fa fa-floppy-disk"></i> Simpan</button>
      </div>
    </div>`;
    document.body.appendChild(mod);
  }
  // Muat data terkini
  fetch('/api/tunggakan/antrean/jam-operasional',{headers:tgAuth()}).then(r=>r.json()).then(d=>{
    document.getElementById('jam-aktif').checked=!!d.aktif;
    document.getElementById('jam-mulai').value=d.mulai||'08:00';
    document.getElementById('jam-selesai').value=d.selesai||'17:00';
  }).catch(()=>{});
  mod.classList.remove('hidden');
  document.getElementById('jam-save').onclick=async()=>{
    const btn=document.getElementById('jam-save'); btn.disabled=true; btn.innerHTML='<i class="fa fa-spinner fa-spin"></i> Menyimpan...';
    try{
      const body={aktif:document.getElementById('jam-aktif').checked,mulai:document.getElementById('jam-mulai').value,selesai:document.getElementById('jam-selesai').value};
      const r=await fetch('/api/tunggakan/antrean/jam-operasional',{method:'PUT',headers:tgJson(),body:JSON.stringify(body)});
      const d=await r.json();
      if(!r.ok) throw new Error(d.detail||'Gagal menyimpan');
      showToast(d.message||'Jam operasional disimpan','success');
      mod.classList.add('hidden');
      loadJamStatus();
    }catch(e){ showToast(e.message,'error'); }
    finally{ btn.disabled=false; btn.innerHTML='<i class="fa fa-floppy-disk"></i> Simpan'; }
  };
}

// ============================================================
// FITUR 3: Kotak Masuk Balasan WA
// ============================================================
let inboxData=[];
async function loadInbox(){
  if(!token) return;
  const tb=document.getElementById('inbox-body');
  const ct=document.getElementById('inbox-count');
  if(!tb) return;
  tb.innerHTML='<tr><td colspan="6" class="text-center py-10 text-slate-400"><i class="fa fa-spinner fa-spin mr-2"></i>Memuat balasan...</td></tr>';
  try{
    const r=await fetch('/api/wa/inbox?limit=200',{headers:tgAuth()});
    if(!r.ok) throw new Error('Gagal memuat inbox');
    inboxData=await r.json();
    if(ct) ct.textContent=inboxData.length;
    if(!inboxData.length){
      tb.innerHTML='<tr><td colspan="6" class="text-center py-12 text-slate-400"><i class="fa fa-inbox text-2xl block mb-2 opacity-40"></i>Belum ada balasan dari pelanggan.</td></tr>'; return;
    }
    tb.innerHTML=inboxData.map(m=>`<tr class="hover:bg-purple-50 cursor-default">
      <td class="text-xs text-slate-500 whitespace-nowrap">${tgEsc(m.waktu_balasan||m.updated_at||'-')}</td>
      <td class="font-mono text-xs">${tgEsc(m.id_pelanggan||'-')}</td>
      <td><div class="flex items-center gap-2">${tgAv(m.nama)}<span class="font-semibold text-slate-700">${tgEsc(m.nama||'-')}</span></div></td>
      <td class="font-mono text-xs">${tgEsc(m.no_hp||'-')}</td>
      <td class="max-w-xs"><div class="text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-2 py-1 whitespace-pre-wrap break-words">${tgEsc(m.balasan||'-')}</div></td>
      <td class="text-center whitespace-nowrap">
        <button onclick="tgRiwayat('${tgEsc(m.id_pelanggan)}')" class="text-xs px-2 py-1 rounded bg-sky-50 text-sky-600 border border-sky-200 hover:bg-sky-100 font-semibold"><i class="fa fa-clock-rotate-left mr-1"></i>Riwayat</button>
      </td>
    </tr>`).join('');
  }catch(e){ tb.innerHTML=`<tr><td colspan="6" class="text-center py-10 text-rose-400">${tgEsc(e.message)}</td></tr>`; }
}

async function loadInboxCount(){
  if(!token) return;
  try{
    const r=await fetch('/api/wa/inbox/count',{headers:tgAuth()});
    if(!r.ok) return;
    const d=await r.json();
    const n=d.count||0;
    ['tb-inbox-badge','sb-inbox-badge'].forEach(id=>{
      const el=document.getElementById(id); if(!el) return;
      el.textContent=n; el.classList.toggle('hidden',n===0);
    });
  }catch(e){}
}

// ============================================================
// FITUR 6: Manajemen User / Kelola Petugas (Admin Only)
// ============================================================
let usersData=[];
async function loadUsers(){
  if(!token) return;
  const tb=document.getElementById('usr-body');
  if(!tb) return;
  tb.innerHTML='<tr><td colspan="7" class="text-center py-10 text-slate-400"><i class="fa fa-spinner fa-spin mr-2"></i>Memuat daftar petugas...</td></tr>';
  try{
    const r=await fetch('/api/admin/users',{headers:tgAuth()});
    if(!r.ok){ if(r.status===403){ tb.innerHTML='<tr><td colspan="7" class="text-center py-10 text-slate-400">Hanya admin yang dapat mengakses halaman ini.</td></tr>'; return; } throw new Error('Gagal memuat'); }
    usersData=await r.json();
    // Update badge pending di sidebar
    const pending=usersData.filter(u=>u.status==='pending').length;
    ['sb-users-badge'].forEach(id=>{ const el=document.getElementById(id); if(!el) return; el.textContent=pending; el.classList.toggle('hidden',pending===0); });
    if(!usersData.length){ tb.innerHTML='<tr><td colspan="7" class="text-center py-10 text-slate-400">Belum ada petugas terdaftar.</td></tr>'; return; }
    tb.innerHTML=usersData.map(u=>{
      const isPending=u.status==='pending', isActive=u.status==='active', isReset=u.reset_password_requested;
      return `<tr class="hover:bg-slate-50">
        <td><div class="flex items-center gap-2">${tgAv(u.full_name)}<div><div class="font-semibold text-slate-700 text-sm">${tgEsc(u.full_name||'-')}</div><div class="text-[11px] text-slate-400">@${tgEsc(u.username||'-')}</div></div></div></td>
        <td class="text-xs text-slate-500">${tgEsc(u.phone_number||'-')}</td>
        <td><span class="badge ${u.role==='admin'?'bg-blue-100 text-blue-700':'bg-slate-100 text-slate-600'}">${tgEsc(u.role||'-')}</span></td>
        <td><span class="badge ${isPending?'bg-amber-100 text-amber-700':isActive?'bg-emerald-100 text-emerald-700':'bg-rose-100 text-rose-700'}">${tgEsc(u.status||'-')}</span>${isReset?'<span class="badge bg-orange-100 text-orange-700 ml-1"><i class="fa fa-key mr-1"></i>Reset</span>':''}</td>
        <td class="text-xs text-slate-500">${tgEsc(u.created_at||'-')}</td>
        <td class="whitespace-nowrap text-center">
          ${isPending?`<button onclick="usrApprove(${u.id},'active')" class="text-xs px-2 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 font-semibold mr-1"><i class="fa fa-check mr-1"></i>Setujui</button><button onclick="usrApprove(${u.id},'rejected')" class="text-xs px-2 py-1 rounded bg-rose-50 text-rose-600 border border-rose-200 hover:bg-rose-100 font-semibold"><i class="fa fa-xmark mr-1"></i>Tolak</button>`:''}
          ${isActive && !isPending?`<button onclick="usrApprove(${u.id},'suspended')" class="text-xs px-2 py-1 rounded bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200 font-semibold"><i class="fa fa-ban mr-1"></i>Suspend</button>`:''}
          ${u.status==='suspended'||u.status==='rejected'?`<button onclick="usrApprove(${u.id},'active')" class="text-xs px-2 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 font-semibold"><i class="fa fa-rotate-left mr-1"></i>Aktifkan</button>`:''}
<button onclick="usrHapus(${u.id},'${tgEsc(u.username||'')}')" class="text-xs px-2 py-1 rounded bg-rose-50 text-rose-600 border border-rose-200 hover:bg-rose-100 font-semibold ml-1" title="Hapus Permanen"><i class="fa fa-trash"></i></button>
</td>
        <td class="text-center">
          ${isReset?`<button onclick="usrResetPass(${u.id},'${tgEsc(u.username||'')}',${isReset})" class="text-xs px-2 py-1 rounded bg-orange-50 text-orange-700 border border-orange-200 hover:bg-orange-100 font-semibold"><i class="fa fa-key mr-1"></i>Reset PW</button>`:`<button onclick="usrResetPass(${u.id},'${tgEsc(u.username||'')}',false)" class="text-xs px-2 py-1 rounded bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100"><i class="fa fa-key"></i></button>`}
        </td>
      </tr>`;
    }).join('');
  }catch(e){ tb.innerHTML=`<tr><td colspan="7" class="text-center py-10 text-rose-400">${tgEsc(e.message)}</td></tr>`; }
}

async function usrApprove(id, status){
  const u=usersData.find(v=>v.id===id); if(!u) return;
  const label={active:'Setujui / Aktifkan',rejected:'Tolak',suspended:'Suspend'}[status]||status;
  if(!confirm(`${label} akun @${u.username}?`)) return;
  try{
    const r=await fetch(`/api/admin/users/${id}/status`,{method:'PUT',headers:tgJson(),body:JSON.stringify({status})});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'Gagal mengupdate status');
    showToast(d.message||`Status akun @${u.username} diubah ke ${status}`,'success');
    await loadUsers();
  }catch(e){ showToast(e.message,'error'); }
}

async function usrResetPass(id, username, hasRequest){
  const u=usersData.find(v=>v.id===id);
  const msg=hasRequest?`Akun @${username} mengajukan reset password.\n\nKlik OK untuk mereset password ke nilai default (username-nya).`:
    `Reset password akun @${username} ke nilai default (username-nya)?`;
  if(!confirm(msg)) return;
  try{
    const r=await fetch(`/api/admin/users/${id}/reset-password`,{method:'POST',headers:tgJson()});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'Gagal reset password');
    showToast(d.message||`Password @${username} berhasil direset`,'success');
    await loadUsers();
  }catch(e){ showToast(e.message,'error'); }
}
async function saveBasicProfile() {
    const uname = document.getElementById('prof-user').value.trim();
    const fname = document.getElementById('prof-name').value.trim();
    if(!uname || !fname) { showToast('Username dan Nama Lengkap tidak boleh kosong', 'error'); return; }
    
    try {
        const r = await fetch('/api/users/me/profile', {
            method: 'PUT',
            headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
            body: JSON.stringify({username: uname, full_name: fname})
        });
        const d = await r.json();
        if(!r.ok) throw new Error(d.detail || 'Gagal menyimpan profil');
        
        if (d.new_token) {
            token = d.new_token;
            localStorage.setItem('swacam_token', token);
        }
        
        if (window.currentUser) {
            window.currentUser.username = d.username;
            window.currentUser.full_name = d.full_name;
        }
        
        // update top right sidebar
        document.getElementById('sb-name').textContent = d.full_name;
        document.getElementById('sb-av').textContent = d.full_name[0].toUpperCase();
        
        showToast(d.message || 'Profil berhasil diperbarui', 'success');
    } catch(e) {
        showToast(e.message, 'error');
    }
}


async function usrHapus(id, username){
  if(!confirm(`Yakin ingin MENGHAPUS PERMANEN akun @${username}?`)) return;
  try{
    const r=await fetch('/api/admin/users/'+id,{method:'DELETE',headers:tgAuth()});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'Gagal menghapus');
    showToast(d.message||`Akun @${username} berhasil dihapus`,'success');
    await loadUsers();
  }catch(e){ showToast(e.message,'error'); }
}

// === Auto Logout (Idle Timeout) ===
let idleTimer = null;
const IDLE_TIMEOUT = 60000; // 1 menit (60 detik)

function resetIdleTimer() {
  // Jangan mulai timer jika sedang tidak login (token kosong)
  if (!token) return;
  
  if (idleTimer) clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {
    if (token) {
      showToast('Sesi Anda telah berakhir karena tidak ada aktivitas.', 'error');
      doLogout();
    }
  }, IDLE_TIMEOUT);
}

// Pasang event listener ke seluruh halaman
['mousemove', 'mousedown', 'keypress', 'DOMMouseScroll', 'mousewheel', 'touchmove', 'MSPointerMove', 'scroll'].forEach(evt => 
  document.addEventListener(evt, resetIdleTimer, true)
);

// Panggil sekali untuk memulai (nanti akan tertahan kalau belum login)
setInterval(() => {
  if (token && !idleTimer) resetIdleTimer();
}, 2000);
