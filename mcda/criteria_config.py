"""
mcda/criteria_config.py — BỘ TIÊU CHÍ MCDA động (thêm/bớt linh hoạt).

Mỗi tiêu chí là 1 dict:
    ma        : mã tiêu chí (A1, B2…)
    ten       : tên hiển thị
    nhom      : mã nhóm ('KT'|'TE'|'TC'|'MQ')
    formula   : 'threshold' (ngưỡng cố định) | 'minmax' (chuẩn hóa min-max)
    scorer    : khóa hàm chấm điểm trong scoring_formulas.SCORERS
    direction : 'smaller_better' | 'larger_better' | None (threshold tự xử lý)
    source    : trường dữ liệu nguồn trong dict phương án (data_adapter) —
                None = tiêu chí THỦ CÔNG (người dùng nhập giá trị từng PA)
    active    : bật/tắt qua giao diện
    custom    : True nếu do người dùng tự thêm

Bộ mặc định 10 tiêu chí / 4 nhóm theo file Tieu_chi_cham_diem_3PA_AHP.xlsx.
"""

# ── 4 nhóm chính ─────────────────────────────────────────────────────────────
GROUPS = {
    "KT": "Kỹ thuật",
    "TE": "Kinh tế",
    "TC": "Thi công",
    "MQ": "Mỹ quan",
}

# Trọng số nhóm MẶC ĐỊNH (%) khi người dùng bỏ qua khai báo AHP
DEFAULT_GROUP_WEIGHTS = {"KT": 35.0, "TE": 35.0, "TC": 20.0, "MQ": 10.0}

# Phân bổ con CHUẨN trong từng nhóm (tỉ lệ, tự chuẩn hóa theo tiêu chí active)
DEFAULT_SUB_WEIGHTS = {
    "A1": 0.40, "A2": 0.35, "A3": 0.25,
    "B1": 0.60, "B2": 0.40,
    "C1": 0.40, "C2": 0.35, "C3": 0.25,
    "D1": 0.60, "D2": 0.40,
}


def default_criteria():
    """Danh sách 10 tiêu chí mặc định (bản SAO — sửa thoải mái)."""
    return [
        # ── Nhóm KỸ THUẬT ────────────────────────────────────────────────
        dict(ma="A1", ten="Phù hợp khẩu độ (dư L_max so với L_min)",
             nhom="KT", formula="threshold", scorer="khau_do",
             direction=None, source="L_max_kha_nang", active=True, custom=False),
        dict(ma="A2", ten="Tỉ lệ L/H hợp lý",
             nhom="KT", formula="threshold", scorer="ty_le_LH",
             direction=None, source="ty_le_LH", active=True, custom=False),
        dict(ma="A3", ten="Số nhịp (ít nhịp → ít trụ)",
             nhom="KT", formula="minmax", scorer="minmax",
             direction="smaller_better", source="so_nhip", active=True,
             custom=False),
        # ── Nhóm KINH TẾ ─────────────────────────────────────────────────
        dict(ma="B1", ten="Suất đầu tư (triệu VND/m² — Module 12)",
             nhom="TE", formula="minmax", scorer="minmax",
             direction="smaller_better", source="suat_dau_tu", active=True,
             custom=False),
        dict(ma="B2", ten="Chi phí bảo trì (theo số nhịp/khe co giãn)",
             nhom="TE", formula="minmax", scorer="minmax",
             direction="smaller_better", source="so_nhip", active=True,
             custom=False),
        # ── Nhóm THI CÔNG ────────────────────────────────────────────────
        dict(ma="C1", ten="Thiết bị lao lắp (theo loại dầm)",
             nhom="TC", formula="threshold", scorer="thiet_bi",
             direction=None, source="loai_dam", active=True, custom=False),
        dict(ma="C2", ten="Tốc độ thi công (ngày/nhịp)",
             nhom="TC", formula="minmax", scorer="minmax",
             direction="smaller_better", source="ngay_thi_cong_nhip",
             active=True, custom=False),
        dict(ma="C3", ten="Diện tích bãi đúc yêu cầu (m²)",
             nhom="TC", formula="minmax", scorer="minmax",
             direction="smaller_better", source="dien_tich_bai_duc",
             active=True, custom=False),
        # ── Nhóm MỸ QUAN ─────────────────────────────────────────────────
        dict(ma="D1", ten="Chiều cao dầm (thanh mảnh)",
             nhom="MQ", formula="threshold", scorer="chieu_cao",
             direction=None, source="H_dam", active=True, custom=False),
        dict(ma="D2", ten="Bản đáy liền mạch (mặt dưới phẳng đẹp)",
             nhom="MQ", formula="threshold", scorer="ban_day",
             direction=None, source="co_ban_day", active=True, custom=False),
    ]


def active_by_group(criteria):
    """{nhom: [tiêu chí active]} — giữ thứ tự khai báo."""
    out = {g: [] for g in GROUPS}
    for c in criteria:
        if c.get("active") and c.get("nhom") in out:
            out[c["nhom"]].append(c)
    return out


def next_custom_ma(criteria, nhom):
    """Sinh mã tiêu chí mới cho nhóm (VD nhóm KT: A4, A5…)."""
    prefix = {"KT": "A", "TE": "B", "TC": "C", "MQ": "D"}.get(nhom, "X")
    nums = [int(str(c["ma"])[1:]) for c in criteria
            if str(c.get("ma", "")).startswith(prefix)
            and str(c["ma"])[1:].isdigit()]
    return f"{prefix}{(max(nums) + 1) if nums else 1}"
