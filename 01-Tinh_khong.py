"""
Module 01 — Tĩnh không đường thủy nội địa (ĐTNĐ)
Phạm vi: Cầu vượt sông, kênh cấp I–VI (đề tài tập trung cấp IV–VI)
Căn cứ:
  - TCVN 8818:2022  Cầu đường bộ — Yêu cầu tĩnh không thông thuyền
  - QCVN 48:2012/BGTVT  Quy chuẩn kỹ thuật về đường thủy nội địa
"""

# ── Bảng tĩnh không theo TCVN 8818 ─────────────────────────────────────────
# mien → cap_song → loai_hinh → B_thong_thuyen (m)
#                → "H"       → H_thong_thuyen (m)
_DATA_TINH_KHONG = {
    "1": {  # Miền Bắc
        "1": {"1": 70,  "2": 85,  "H": 11.0},   # Cấp I
        "2": {"1": 40,  "2": 50,  "H": 9.5},    # Cấp II
        "3": {"1": 30,  "2": 40,  "H": 7.0},    # Cấp III
        "4": {"1": 25,  "2": 30,  "H": 6.0},    # Cấp IV  ← trọng tâm đề tài
        "5": {"1": 15,  "2": 20,  "H": 4.0},    # Cấp V   ← trọng tâm đề tài
        "6": {"1": 10,  "2": 10,  "H": 3.0},    # Cấp VI  ← trọng tâm đề tài
    },
    "2": {  # Miền Nam
        "1": {"1": 75,  "2": 120, "H": 11.0},
        "2": {"1": 50,  "2": 60,  "H": 9.5},
        "3": {"1": 30,  "2": 50,  "H": 7.0},
        "4": {"1": 25,  "2": 30,  "H": 6.0},
        "5": {"1": 15,  "2": 25,  "H": 4.0},
        "6": {"1": 10,  "2": 13,  "H": 3.0},
    },
}

_CAP_LABEL   = {"1":"I","2":"II","3":"III","4":"IV","5":"V","6":"VI"}
_HINH_LABEL  = {"1":"Kênh đào","2":"Sông tự nhiên"}
_MIEN_LABEL  = {"1":"Miền Bắc","2":"Miền Nam"}


def tra_cuu_tinh_khong_bridge(mien, cap_num, loai_hinh,
                               h1=0.0, h5=0.0, h10=0.0, h98=0.0, h_tn_tb=0.0):
    """
    Tra cứu tĩnh không đường thủy nội địa cho cầu vượt sông/kênh.

    Params
    ------
    mien      : '1' Miền Bắc | '2' Miền Nam
    cap_num   : '1'–'6'  (Cấp I–VI)
    loai_hinh : '1' Kênh đào | '2' Sông tự nhiên
    h1        : Cao độ MNCN — mực nước cao nhất (H1%) (m)
    h5        : Cao độ MNTT — mực nước thông thuyền (H5%) (m)
    h10       : Cao độ MNTC — mực nước thi công (H10%) (m)
    h98       : Cao độ MNTN — mực nước thấp nhất (H98%) (m)
    h_tn_tb   : Cao độ tự nhiên trung bình (m)

    Returns
    -------
    dict:
        status, B, H, day_dam, MNCN, MNTT, MNTC, MNTN, H_TN_TB, label
    """
    try:
        target = _DATA_TINH_KHONG[str(mien)][str(cap_num)]
    except KeyError:
        return {
            "status":  "error",
            "message": f"Không tìm thấy dữ liệu: miền={mien}, cấp sông={cap_num}",
        }

    B = float(target.get(str(loai_hinh), 0))
    H = float(target["H"])

    # Cao độ đáy dầm tối thiểu (TCVN 8818 điều 4.3):
    #   ĐK1: Đáy dầm ≥ MNCN + 0.50m  (an toàn va chạm tàu khi lũ)
    #   ĐK2: Đáy dầm ≥ MNTT + H_tt + 0.10m  (thông thuyền bình thường)
    #   Chọn giá trị lớn hơn
    cao_do_an_toan      = float(h1) + 0.50
    cao_do_thong_thuyen = float(h5) + H + 0.10
    cao_do_day_dam      = max(cao_do_an_toan, cao_do_thong_thuyen)

    return {
        "status":  "success",
        "B":       B,
        "H":       H,
        "H_TN_TB": float(h_tn_tb),
        "MNCN":    float(h1),
        "MNTT":    float(h5),
        "MNTC":    float(h10),
        "MNTN":    float(h98),
        "day_dam": round(cao_do_day_dam, 3),
        "label":   (
            f"Cầu vượt {_HINH_LABEL.get(str(loai_hinh),'?')} — "
            f"Cấp {_CAP_LABEL.get(str(cap_num),'?')} "
            f"({_MIEN_LABEL.get(str(mien),'?')})"
        ),
        "loai_doi_tuong_vuot": "Vượt sông",
    }
