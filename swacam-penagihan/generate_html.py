import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('static/index.php', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove PHP header (require_once config.php)
content = content.replace("<?php\nrequire_once __DIR__ . '/config.php';\n?>\n", "")

# 2. Replace <base href> PHP tag with empty (same-origin)
content = re.sub(
    r'<base href="<\?php echo htmlspecialchars\(API_BASE_URL, ENT_QUOTES\); \?>/"\s*>',
    '',
    content
)

# 3. Replace style.css PHP cache-bust with simple version
content = re.sub(
    r"<\?php echo filemtime\(__DIR__\.'/style\.css'\); \?>",
    str(int(__import__('time').time())),
    content
)

# 4. Replace window.SWACAM PHP line
content = re.sub(
    r'window\.SWACAM=\{app:"penagihan",otherUrl:"<\?php echo htmlspecialchars\(PEER_APP_URL, ENT_QUOTES\); \?>"\};',
    'window.SWACAM={app:"penagihan",otherUrl:""};',
    content
)

# 5. Replace app.js PHP cache-bust
content = re.sub(
    r"<\?php echo filemtime\(__DIR__\.'/app\.js'\); \?>",
    str(int(__import__('time').time())),
    content
)

# 6. Remove any remaining PHP tags (just in case)
content = re.sub(r'<\?php.*?\?>', '', content)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("index.html created successfully!")
print(f"Size: {len(content)} bytes")

# Verify no PHP remains
if '<?php' in content or '<?=' in content:
    print("WARNING: PHP tags still remain!")
else:
    print("OK: No PHP tags remaining")
