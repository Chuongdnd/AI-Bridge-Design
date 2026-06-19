import sys, re
sys.stdout.reconfigure(encoding='utf-8')

path = r'c:\Users\dinhc\Documents\AI-Bridge-Design-main\00-Interface.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# Count FFFD
fffd_count = c.count('�')
print(f'FFFD count: {fffd_count}')

# Show contexts around FFFD
for m in re.finditer('�', c)[:10]:
    ctx = c[max(0, m.start()-20):m.start()+20]
    print(f'  pos {m.start()}: {repr(ctx)}')

# Check specific emoji
for emoji, name in [('\U0001F3D7', 'U+1F3D7 🏗'), ('\U0001F3DB', 'U+1F3DB 🏛'), ('\U0001F4D0', 'U+1F4D0 📐')]:
    found = emoji in c
    print(f'{name}: {"FOUND" if found else "MISSING"}')

# Find "UTH" in topbar context
idx = c.find(">🏗️ UTH<")
if idx < 0:
    idx = c.find('UTH</div>')
    print(f'UTH context: {repr(c[max(0,idx-25):idx+12]) if idx>0 else "NOT FOUND"}')
else:
    print(f'Topbar UTH OK')
