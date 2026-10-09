import sys; sys.stdout.reconfigure(encoding='utf-8')
with open('static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

import re
old_td = r"\$\{u\.status==='suspended'\|\|u\.status==='rejected'\?`<button onclick=\"usrApprove\(\$\{u\.id\},'active'\)\" class=\"text-xs px-2 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 font-semibold\"><i class=\"fa fa-rotate-left mr-1\"></i>Aktifkan</button>`:''\}\n\s*</td>"
new_td = """${u.status==='suspended'||u.status==='rejected'?`<button onclick="usrApprove(${u.id},'active')" class="text-xs px-2 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 font-semibold"><i class="fa fa-rotate-left mr-1"></i>Aktifkan</button>`:''}
<button onclick="usrHapus(${u.id},'${tgEsc(u.username||'')}')" class="text-xs px-2 py-1 rounded bg-rose-50 text-rose-600 border border-rose-200 hover:bg-rose-100 font-semibold ml-1" title="Hapus Permanen"><i class="fa fa-trash"></i></button>
</td>"""

content = re.sub(old_td, new_td, content)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("Regex replace applied")
