
import re
import glob

for f in ['tunggakan.py', 'wa_riwayat.py', 'wa_antrean.py', 'auth.py']:
    content = open(f, encoding='utf-8').read()
    routes = re.findall(r'@router\.(get|post|put|delete)\([\''\"]([^\''\"]+)[\''\"]\)', content)
    for m, p in routes:
        print(f'{f:15} {m.upper():6} {p}')

