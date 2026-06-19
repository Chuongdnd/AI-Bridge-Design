"""Fix mojibake in 00-Interface.py caused by PowerShell Get-Content CP1252 misread."""
import os

path = os.path.join(os.path.dirname(__file__), '00-Interface.py')

# Step 1: Read raw bytes, fix emoji that had undefined CP1252 bytes (0x8F, 0x90)
with open(path, 'rb') as f:
    raw = f.read()

# Corrupted patterns -> correct UTF-8 bytes
# 🏗️ U+1F3D7 U+FE0F: bytes F0 9F [8F->FFFD] 97  EF B8 [8F->FFFD]
# 🏛️ U+1F3DB U+FE0F: bytes F0 9F [8F->FFFD] 9B  EF B8 [8F->FFFD]
# 📐  U+1F4D0:        bytes F0 9F 93 [90->FFFD]
bad_good = [
    # Longest patterns first (avoid partial matches)
    (bytes.fromhex('c3b0c5b8efbfbde28094c3afc2b8efbfbd'), '🏗️'.encode('utf-8')),
    (bytes.fromhex('c3b0c5b8efbfbde280bac3afc2b8efbfbd'), '🏛️'.encode('utf-8')),
    (bytes.fromhex('c3b0c5b8efbfbde28094'), '🏗'.encode('utf-8')),
    (bytes.fromhex('c3b0c5b8efbfbde280ba'), '🏛'.encode('utf-8')),
    (bytes.fromhex('c3b0c5b8e2809cefbfbd'), '📐'.encode('utf-8')),
]

for bad, good in bad_good:
    n = raw.count(bad)
    if n:
        name = good.decode('utf-8')
        print(f'  Fixing {repr(name)}: {n} occurrence(s)')
    raw = raw.replace(bad, good)

# Step 2: Decode current bytes as UTF-8
content = raw.decode('utf-8', errors='replace')

# Step 3: Reverse mojibake: CP1252-encode -> UTF-8-decode
fixed = content.encode('cp1252', errors='ignore').decode('utf-8', errors='replace')

# Step 4: Write back
with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(fixed)

n_lines = fixed.count('\n') + 1
ok_vn = 'THUYẾT' in fixed
ok_chao = 'Chào mừng' in fixed
print(f'Done. Lines: {n_lines}')
print(f'THUYẾT in file: {ok_vn}')
print(f'Chào mừng in file: {ok_chao}')
