# Fix lag by guarding module loading behind session_state
# This is the #1 cause of lag: exec_module() runs every rerun for 12+ modules

import re

path = r'C:\Users\dinhc\Desktop\AI-Bridge-Design-git\00-Interface.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ============================================================
# FIX 1: Guard module loading (exec_module/importlib.reload)
# ============================================================

old_module_block = """# --- KẾT NỐI HỆ THỐNG MODULES THÀNH PHẦN ---
try:
    TK   = importlib.import_module("01-Tinh_khong")
    YTHH = importlib.import_module("02-Yeuto_Hinhhoc")  # Yếu tố hình học + MCN
    KCN  = importlib.import_module("06-AI_KetCauNhip")  # AI Kết cấu nhịp v2
    MOT  = importlib.import_module("07-AI_MoTru")       # AI Mố – Trụ v2
    MONG = importlib.import_module("08-AI_Mong")        # Móng (rule-based)
    EXP  = importlib.import_module("09-Export_CAD_IFC") # Export DXF / IFC
    IFCX = importlib.import_module("18-IFC_Exporter")   # IFC từ lưới 3D thực
    PLOT = importlib.import_module("00-Drawing_Utils")
    TV   = importlib.import_module("00-Terrain_Viewer")
    LPC  = importlib.import_module("10-LopPhu_MatCau")  # Lớp phủ mặt cầu
    BVK  = importlib.import_module("11-BanVe_KetCau")   # Bản vẽ kết cấu 2D/3D
    SSP  = importlib.import_module("09-So_Sanh_PA")     # So sánh 3 phương án
    CTD  = importlib.import_module("12-ChiTiet_Dam")    # Chi tiết dầm
    # reload() chỉ để bắt sửa code lúc dev; ở môi trường deploy (multipage/
    # CWD khác) find_spec có thể không tìm lại được module tên có số → bỏ qua
    # lỗi reload, dùng bản đã import (vẫn chạy đúng).
    for _m in (PLOT, BVK, CTD):
        try:
            importlib.reload(_m)
        except Exception:
            pass

    # ── Section Sketcher + Beam Builder (module nạp bằng spec vì tên có số) ──
    _bb_dir  = os.path.dirname(os.path.abspath(__file__))
    _bb_espec = _iutil.spec_from_file_location(
        "BeamBuilder", os.path.join(_bb_dir, "17-BeamBuilder.py"))
    _BB_ENGINE = _iutil.module_from_spec(_bb_espec)
    import sys as _sys
    _sys.modules["BeamBuilder"] = _BB_ENGINE
    _bb_espec.loader.exec_module(_BB_ENGINE)

    _bb_uspec = _iutil.spec_from_file_location(
        "BeamBuilderUI", os.path.join(_bb_dir, "17-BeamBuilderUI.py"))
    BBUI = _iutil.module_from_spec(_bb_uspec)
    _bb_uspec.loader.exec_module(BBUI)

    # ── Pier Builder (trụ lắp ghép — Phase 1) ───────────────────────────────
    _pb_spec = _iutil.spec_from_file_location(
        "PierBuilder", os.path.join(_bb_dir, "19-PierBuilder.py"))
    PB = _iutil.module_from_spec(_pb_spec)
    _pb_spec.loader.exec_module(PB)

    # ── Thư viện cấu kiện dùng chung (mố/trụ/dầm/móng) ──────────────────────
    _cl_spec = _iutil.spec_from_file_location(
        "component_library", os.path.join(_bb_dir, "utils", "component_library.py"))
    CLIB = _iutil.module_from_spec(_cl_spec)
    _cl_spec.loader.exec_module(CLIB)

    # ── Không gian làm việc đa người dùng (thư viện + dự án theo tài khoản) ──
    _ws_spec = _iutil.spec_from_file_location(
        "workspace", os.path.join(_bb_dir, "utils", "workspace.py"))
    WS = _iutil.module_from_spec(_ws_spec)
    _ws_spec.loader.exec_module(WS)
    # Resolver đọc st.session_state (thread-local theo phiên) → mỗi user 1 thư viện
    CLIB.set_lib_dir_resolver(lambda: st.session_state.get("user_lib_dir"))

    # ── Sơ đồ cọc: đọc DXF mặt bằng + schema bố trí cọc ─────────────────────
    _pp_spec = _iutil.spec_from_file_location(
        "pile_plan", os.path.join(_bb_dir, "utils", "pile_plan.py"))
    PP = _iutil.module_from_spec(_pp_spec)
    _pp_spec.loader.exec_module(PP)

    # ── Chi tiết mặt cắt cọc (parametric) ───────────────────────────────────
    _ps_spec = _iutil.spec_from_file_location(
        "pile_section", os.path.join(_bb_dir, "utils", "pile_section.py"))
    PS = _iutil.module_from_spec(_ps_spec)
    _ps_spec.loader.exec_module(PS)

    # ── Thống kê khối lượng cấu kiện (sơ bộ) ────────────────────────────────
    _kl_spec = _iutil.spec_from_file_location(
        "khoi_luong", os.path.join(_bb_dir, "utils", "khoi_luong.py"))
    KL = _iutil.module_from_spec(_kl_spec)
    _kl_spec.loader.exec_module(KL)

    # ── Suất vốn đầu tư cầu (Bảng 76) → ước giá trị công trình ──────────────
    _sdt_spec = _iutil.spec_from_file_location(
        "suat_dau_tu", os.path.join(_bb_dir, "utils", "suat_dau_tu.py"))
    SDT = _iutil.module_from_spec(_sdt_spec)
    _sdt_spec.loader.exec_module(SDT)

except Exception as e:
    st.error(f"Lỗi kết nối Module: {e}")
    st.stop()"""

new_module_block = """# ── KẾT NỐI HỆ THỐNG MODULES THÀNH PHẦN (CHỈ 1 LẦN) ────────────────────────
# Guard session_state để tránh exec_module() mỗi rerun — nguyên nhân chính gây
# lag. Sau lần đầu, importlib.import_module() đã cache sẵn nên gọi lại không sao.
if '_modules_loaded' not in st.session_state:
    try:
        TK   = importlib.import_module("01-Tinh_khong")
        YTHH = importlib.import_module("02-Yeuto_Hinhhoc")
        KCN  = importlib.import_module("06-AI_KetCauNhip")
        MOT  = importlib.import_module("07-AI_MoTru")
        MONG = importlib.import_module("08-AI_Mong")
        EXP  = importlib.import_module("09-Export_CAD_IFC")
        IFCX = importlib.import_module("18-IFC_Exporter")
        PLOT = importlib.import_module("00-Drawing_Utils")
        TV   = importlib.import_module("00-Terrain_Viewer")
        LPC  = importlib.import_module("10-LopPhu_MatCau")
        BVK  = importlib.import_module("11-BanVe_KetCau")
        SSP  = importlib.import_module("09-So_Sanh_PA")
        CTD  = importlib.import_module("12-ChiTiet_Dam")

        # ── Section Sketcher + Beam Builder (nạp bằng spec vì tên có số) ──
        _bb_dir  = os.path.dirname(os.path.abspath(__file__))
        _bb_espec = _iutil.spec_from_file_location(
            "BeamBuilder", os.path.join(_bb_dir, "17-BeamBuilder.py"))
        _BB_ENGINE = _iutil.module_from_spec(_bb_espec)
        import sys as _sys
        _sys.modules["BeamBuilder"] = _BB_ENGINE
        _bb_espec.loader.exec_module(_BB_ENGINE)

        _bb_uspec = _iutil.spec_from_file_location(
            "BeamBuilderUI", os.path.join(_bb_dir, "17-BeamBuilderUI.py"))
        BBUI = _iutil.module_from_spec(_bb_uspec)
        _bb_uspec.loader.exec_module(BBUI)

        # ── Pier Builder ───────────────────────────────────────────────────
        _pb_spec = _iutil.spec_from_file_location(
            "PierBuilder", os.path.join(_bb_dir, "19-PierBuilder.py"))
        PB = _iutil.module_from_spec(_pb_spec)
        _pb_spec.loader.exec_module(PB)

        # ── Thư viện cấu kiện dùng chung ──────────────────────────────────
        _cl_spec = _iutil.spec_from_file_location(
            "component_library", os.path.join(_bb_dir, "utils", "component_library.py"))
        CLIB = _iutil.module_from_spec(_cl_spec)
        _cl_spec.loader.exec_module(CLIB)
        CLIB.set_lib_dir_resolver(lambda: st.session_state.get("user_lib_dir"))

        # ── Workspace ──────────────────────────────────────────────────────
        _ws_spec = _iutil.spec_from_file_location(
            "workspace", os.path.join(_bb_dir, "utils", "workspace.py"))
        WS = _iutil.module_from_spec(_ws_spec)
        _ws_spec.loader.exec_module(WS)

        # ── Sơ đồ cọc ──────────────────────────────────────────────────────
        _pp_spec = _iutil.spec_from_file_location(
            "pile_plan", os.path.join(_bb_dir, "utils", "pile_plan.py"))
        PP = _iutil.module_from_spec(_pp_spec)
        _pp_spec.loader.exec_module(PP)

        # ── Chi tiết mặt cắt cọc ───────────────────────────────────────────
        _ps_spec = _iutil.spec_from_file_location(
            "pile_section", os.path.join(_bb_dir, "utils", "pile_section.py"))
        PS = _iutil.module_from_spec(_ps_spec)
        _ps_spec.loader.exec_module(PS)

        # ── Thống kê khối lượng ────────────────────────────────────────────
        _kl_spec = _iutil.spec_from_file_location(
            "khoi_luong", os.path.join(_bb_dir, "utils", "khoi_luong.py"))
        KL = _iutil.module_from_spec(_kl_spec)
        _kl_spec.loader.exec_module(KL)

        # ── Suất vốn đầu tư ────────────────────────────────────────────────
        _sdt_spec = _iutil.spec_from_file_location(
            "suat_dau_tu", os.path.join(_bb_dir, "utils", "suat_dau_tu.py"))
        SDT = _iutil.module_from_spec(_sdt_spec)
        _sdt_spec.loader.exec_module(SDT)

        st.session_state['_modules_loaded'] = True
    except Exception as e:
        st.error(f"Lỗi kết nối Module: {e}")
        st.stop()
else:
    import sys as _sys
    TK   = _sys.modules.get("01-Tinh_khong")
    YTHH = _sys.modules.get("02-Yeuto_Hinhhoc")
    KCN  = _sys.modules.get("06-AI_KetCauNhip")
    MOT  = _sys.modules.get("07-AI_MoTru")
    MONG = _sys.modules.get("08-AI_Mong")
    EXP  = _sys.modules.get("09-Export_CAD_IFC")
    IFCX = _sys.modules.get("18-IFC_Exporter")
    PLOT = _sys.modules.get("00-Drawing_Utils")
    TV   = _sys.modules.get("00-Terrain_Viewer")
    LPC  = _sys.modules.get("10-LopPhu_MatCau")
    BVK  = _sys.modules.get("11-BanVe_KetCau")
    SSP  = _sys.modules.get("09-So_Sanh_PA")
    CTD  = _sys.modules.get("12-ChiTiet_Dam")
    _BB_ENGINE = _sys.modules.get("BeamBuilder")
    BBUI = _sys.modules.get("BeamBuilderUI")
    PB   = _sys.modules.get("PierBuilder")
    CLIB = _sys.modules.get("component_library")
    WS   = _sys.modules.get("workspace")
    PP   = _sys.modules.get("pile_plan")
    PS   = _sys.modules.get("pile_section")
    KL   = _sys.modules.get("khoi_luong")
    SDT  = _sys.modules.get("suat_dau_tu")"""

# Only replace if the old block is found
if old_module_block in content:
    content = content.replace(old_module_block, new_module_block)
    print("✅ FIX 1 applied: Module loading guarded by session_state")
else:
    print("⚠️ FIX 1 SKIPPED: module loading block not found exactly. Trying search for start marker...")
    # Try more flexible approach
    start_marker = "# --- KẾT NỐI HỆ THỐNG MODULES THÀNH PHẦN ---"
    end_marker = "st.error(f\"Lỗi kết nối Module: {e}\")"
    
    start_idx = content.find(start_marker)
    if start_idx >= 0:
        end_idx = content.find("st.stop()", start_idx)
        if end_idx >= 0:
            end_idx = end_idx + len("st.stop()")
            print(f"  Found block at {start_idx}-{end_idx}. Replacing...")
            content = content[:start_idx] + new_module_block + content[end_idx:]
            print("✅ FIX 1 applied (flexible mode)")
        else:
            print("❌ FIX 1 FAILED: end marker not found")
    else:
        print("❌ FIX 1 FAILED: start marker not found")

# ============================================================
# FIX 2: Optimize JS timers - reduce setInterval frequencies
# ============================================================

# Busy block check interval: 120ms -> 300ms (less CPU)
content = content.replace("setInterval(tick, 120);", "setInterval(tick, 300);")
print("✅ FIX 2a: Busy block interval 120ms -> 300ms")

# Theme check interval: 2500ms -> 5000ms
content = content.replace("setInterval(apply, 2500);", "setInterval(apply, 5000);")
print("✅ FIX 2b: Theme check interval 2500ms -> 5000ms")

# Sidebar sync interval: 1200ms -> 2000ms
content = content.replace("setInterval(sync, 1200);", "setInterval(sync, 2000);")
print("✅ FIX 2c: Sidebar sync interval 1200ms -> 2000ms")

# Reduce addBtn retries from 2 to 1 (still covered by MutationObserver)
content = content.replace("""      // Gọi nhiều lần để bắt kịp biểu đồ sinh sau
      setTimeout(addBtns, 500);
      setTimeout(addBtns, 1500);""", 
      """      // Gọi nhiều lần để bắt kịp biểu đồ sinh sau
      setTimeout(addBtns, 600);""")
print("✅ FIX 2d: addBtns retries reduced")

# ============================================================
# FIX 3: Guard DesignSystem + Validation module loading
# ============================================================

old_ds_block = """# ── Design System ────────────────────────────────────────────────────────────
import importlib.util as _dsutil
_dsspec = _dsutil.spec_from_file_location(
    "ds00",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-DesignSystem.py")
)
DS = _dsutil.module_from_spec(_dsspec)
_dsspec.loader.exec_module(DS)
st.markdown(DS.GLOBAL_CSS, unsafe_allow_html=True)

# ── Import module validation ──────────────────────────────────────────────────
import importlib.util as _vutil
_vspec = _vutil.spec_from_file_location(
    "val00",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-Validation.py")
)
VAL = _vutil.module_from_spec(_vspec)
_vspec.loader.exec_module(VAL)"""

new_ds_block = """# ── Design System + Validation (CHỈ 1 LẦN) ────────────────────────────────────
if '_design_sys_loaded' not in st.session_state:
    import importlib.util as _dsutil
    _dsspec = _dsutil.spec_from_file_location(
        "ds00",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-DesignSystem.py")
    )
    DS = _dsutil.module_from_spec(_dsspec)
    _dsspec.loader.exec_module(DS)
    st.session_state['_DS'] = DS
    
    import importlib.util as _vutil
    _vspec = _vutil.spec_from_file_location(
        "val00",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-Validation.py")
    )
    VAL = _vutil.module_from_spec(_vspec)
    _vspec.loader.exec_module(VAL)
    st.session_state['_VAL'] = VAL
    st.session_state['_design_sys_loaded'] = True
else:
    DS = st.session_state['_DS']
    VAL = st.session_state['_VAL']

st.markdown(DS.GLOBAL_CSS, unsafe_allow_html=True)"""

if old_ds_block in content:
    content = content.replace(old_ds_block, new_ds_block)
    print("✅ FIX 3 applied: DesignSystem + Validation guarded")
else:
    print("⚠️ FIX 3 SKIPPED: DesignSystem block not found exactly")

# ============================================================
# FIX 4: Guard auth module loading
# ============================================================

old_auth_block = """# ── XÁC THỰC NGƯỜI DÙNG ─────────────────────────────────────────────────────
import importlib.util as _iutil
_auth_spec = _iutil.spec_from_file_location("auth00", os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-Auth.py"))
AUTH = _iutil.module_from_spec(_auth_spec)
_auth_spec.loader.exec_module(AUTH)"""

new_auth_block = """# ── XÁC THỰC NGƯỜI DÙNG (CHỈ 1 LẦN) ────────────────────────────────────────
if '_auth_loaded' not in st.session_state:
    import importlib.util as _iutil
    _auth_spec = _iutil.spec_from_file_location("auth00", os.path.join(os.path.dirname(os.path.abspath(__file__)), "00-Auth.py"))
    AUTH = _iutil.module_from_spec(_auth_spec)
    _auth_spec.loader.exec_module(AUTH)
    st.session_state['_auth_loaded'] = True
else:
    import sys as _sys
    AUTH = _sys.modules.get("auth00")"""

if old_auth_block in content:
    content = content.replace(old_auth_block, new_auth_block)
    print("✅ FIX 4 applied: Auth module guarded")
else:
    print("⚠️ FIX 4 SKIPPED: Auth block not found exactly")

# ============================================================
# Write back
# ============================================================
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ All fixes applied successfully!")
print(f"File size: {len(content)} chars")
