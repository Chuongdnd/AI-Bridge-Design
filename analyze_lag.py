# analyze potential lag causes in 00-Interface.py
import re, os

path = r'C:\Users\dinhc\Desktop\AI-Bridge-Design-git\00-Interface.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print(f"Total chars: {sum(len(l) for l in lines)}")
print()

# 1. Count st.rerun / st.experimental_rerun
reruns = [(i+1, l.strip()) for i,l in enumerate(lines) if 'rerun' in l.lower() and '#' not in l.split('rerun')[0]]
print(f"=== st.rerun calls ({len(reruns)}) ===")
for num, line in reruns[:20]:
    print(f"  L{num}: {line[:100]}")

print()

# 2. Count session_state reads (get/setdefault/__getitem__/__setitem__)
ss_reads = [(i+1, l.strip()) for i,l in enumerate(lines) if 'st.session_state' in l]
print(f"=== st.session_state references ({len(ss_reads)}) ===")
# group by function context to see where they're called most
funcs = {}
for num, line in ss_reads:
    # find which function we're in
    for j in range(num-2, 0, -1):
        if lines[j].strip().startswith('def ') or lines[j].strip().startswith('    def '):
            func = lines[j].strip()
            funcs.setdefault(func, []).append(num)
            break
top_funcs = sorted(funcs.items(), key=lambda x: -len(x[1]))[:15]
print("Top functions by session_state usage:")
for fn, nums in top_funcs:
    print(f"  {fn}: {len(nums)} references")

print()

# 3. Check for heavy plotly operations (fig.show, plotly_chart, etc.)
plotly_calls = [(i+1, l.strip()) for i,l in enumerate(lines) if 'plotly_chart' in l or 'st.plotly' in l or 'fig.show' in l.lower()]
print(f"=== plotly_chart/fig.show calls ({len(plotly_calls)}) ===")
for num, line in plotly_calls[:15]:
    print(f"  L{num}: {line[:120]}")

print()

# 4. Check for large JS/CSS template strings
triple_quotes = []
for i, l in enumerate(lines):
    s = l.strip()
    if s.startswith('"""') or s.startswith("'''") or s.startswith('_cc_theme') or s.startswith('html('):
        triple_quotes.append((i+1, s[:80]))
print(f"=== Potential large template strings ({len(triple_quotes)}) ===")
for num, s in triple_quotes[:20]:
    print(f"  L{num}: {s}")

print()

# 5. Check for time.sleep or long operations
sleeps = [(i+1, l.strip()) for i,l in enumerate(lines) if 'time.sleep' in l]
print(f"=== time.sleep calls ({len(sleeps)}) ===")
for num, line in sleeps:
    print(f"  L{num}: {line[:100]}")

print()

# 6. Check for expensive operations in global scope (outside functions)
print("=== Global scope: non-function code ===")
in_global = True
global_code = []
for i, l in enumerate(lines):
    stripped = l.strip()
    if stripped.startswith('def ') or stripped.startswith('class '):
        in_global = False
    elif i == 0:
        pass
    elif stripped and not stripped.startswith('#') and not stripped.startswith('import ') and not stripped.startswith('from ') and not in_global:
        # check if we're back to global
        pass
    if in_global and stripped and not stripped.startswith('#') and not stripped.startswith('import ') and not stripped.startswith('from ') and not stripped.startswith('"""') and not stripped.startswith("'''"):
        global_code.append((i+1, stripped[:100]))
# limit to last 50 lines of global
for num, s in global_code[-50:]:
    print(f"  L{num}: {s}")

print()

# 7. Check for excessive form creation rebuilds
forms = [(i+1, l.strip()) for i,l in enumerate(lines) if 'st.form(' in l or 'with st.form' in l]
print(f"=== st.form references ({len(forms)}) ===")

# 8. Check inject_resizable_panels and inject_right_panel_ctl frequency
print()
print("=== Panel injection (runs every rerun) ===")
for i, l in enumerate(lines):
    if '_inject_resizable_panels' in l or '_inject_right_panel_ctl' in l or 'inject_' in l:
        print(f"  L{i+1}: {l.strip()[:100]}")

print()
print("=== st.markdown/inject calls ===")
injects = [(i+1, l.strip()) for i,l in enumerate(lines) if 'components.html' in l or 'inject' in l.lower()]
for num, line in injects[:20]:
    print(f"  L{num}: {line[:120]}")
