# analyze lag causes in 00-Interface.py
import re, os, sys

sys.stdout.reconfigure(encoding='utf-8')

path = r'C:\Users\dinhc\Desktop\AI-Bridge-Design-git\00-Interface.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. JS injection blocks
injections = [(m.start(), m.group()[:60]) for m in re.finditer(r'_cc_theme\.html\(|st\.components\.v1\.html\(', content)]
print(f'=== JS injection calls: {len(injections)} ===')
for pos, snippet in injections:
    line = content[:pos].count('\n') + 1
    print(f'  L{line}: {snippet}')

# 2. setInterval / setTimeout
intervals = [(m.start(), m.group()[:70]) for m in re.finditer(r'setInterval|setTimeout', content)]
print(f'\n=== setInterval/setTimeout: {len(intervals)} ===')
for pos, snippet in intervals:
    line = content[:pos].count('\n') + 1
    print(f'  L{line}: {snippet}')

# 3. MutationObserver
obs = [(m.start(), m.group()[:70]) for m in re.finditer(r'MutationObserver', content)]
print(f'\n=== MutationObserver: {len(obs)} ===')
for pos, snippet in obs:
    line = content[:pos].count('\n') + 1
    print(f'  L{line}: {snippet}')

# 4. st.markdown with unsafe_html
md_calls = [(m.start(), m.group()[:50]) for m in re.finditer(r'st\.markdown\(', content)]
print(f'\n=== st.markdown calls: {len(md_calls)} ===')

# 5. functions/defs
defs = [m for m in re.finditer(r'^def |^    def ', content, re.MULTILINE)]
print(f'\n=== Total inner function defs: {len(defs)} ===')

# 6. st.cache usage
caches = [m for m in re.finditer(r'@st\.cache', content)]
print(f'\n=== st.cache usage: {len(caches)} ===')
for m in caches:
    line = content[:m.start()].count('\n') + 1
    print(f'  L{line}: {m.group()[:50]}')

# 7. Check for add_rows or other heavy operations
heavy = [(m.start(), m.group()[:80]) for m in re.finditer(r'add_rows|data_editor|dataframe|data_frame', content)]
print(f'\n=== Heavy data operations: {len(heavy)} ===')
for pos, snippet in heavy[:20]:
    line = content[:pos].count('\n') + 1
    print(f'  L{line}: {snippet}')

# 8. Find the main THUYET MINH tab rendering (the heaviest part)
print(f'\n=== Main sections in the flow ===')
main_start = content.find("\nwith _col_main:")
if main_start > 0:
    main_end = content.find("\n_icc_theme", main_start)  # approximate end
    section = content[main_start:main_start+3000]
    lines = section.split('\n')
    for i, l in enumerate(lines):
        stripped = l.strip()
        # Find tab markers or st.markdown with headers
        if 'selected_ribbon' in stripped or 'elif' in stripped or 'if ' in stripped:
            actual_line = content[:main_start].count('\n') + i + 1
            print(f'  L{actual_line}: {stripped[:100]}')

print(f'\n=== Dataset sizes in main flow ===')
# Check for large data loading patterns
data_loads = [(m.start(), m.group()[:100]) for m in re.finditer(r'(pd\.read_csv|pd\.read_excel|open\(.*\)|\.load\(|pickle\.load)', content)]
for pos, snippet in data_loads[:10]:
    line = content[:pos].count('\n') + 1
    print(f'  L{line}: {snippet}')
