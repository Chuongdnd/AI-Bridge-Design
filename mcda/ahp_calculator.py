"""
mcda/ahp_calculator.py — Thuật toán AHP-Saaty: trọng số từ ma trận so sánh cặp
+ chỉ số nhất quán CR; kết hợp 2 cấp (nhóm × tiêu chí con) → trọng số tuyệt đối.
"""
import numpy as np

# Bảng Random Index (RI) theo Saaty, n = 1..10
RI_SAATY = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12,
            6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


def tinh_trong_so_ahp(ma_tran_so_sanh):
    """AHP-Saaty đầy đủ cho ma trận so sánh cặp n×n.

    B1: chuẩn hóa (chia mỗi phần tử cho tổng cột).
    B2: W_i = trung bình cộng mỗi hàng ma trận chuẩn hóa.
    B3: λ_max = Σ(tổng cột_j × W_j).
    B4: CI = (λ_max − n)/(n − 1).
    B5: CR = CI/RI (RI tra bảng Saaty).

    Trả dict: {trong_so, lambda_max, CI, CR, chap_nhan, ma_tran_chuan_hoa}.
    """
    A = np.asarray(ma_tran_so_sanh, dtype=float)
    n = A.shape[0]
    if n == 0:
        return {"trong_so": [], "lambda_max": 0.0, "CI": 0.0, "CR": 0.0,
                "chap_nhan": True, "ma_tran_chuan_hoa": []}
    if n == 1:
        return {"trong_so": [1.0], "lambda_max": 1.0, "CI": 0.0, "CR": 0.0,
                "chap_nhan": True, "ma_tran_chuan_hoa": [[1.0]]}

    col_sum = A.sum(axis=0)
    col_sum[col_sum <= 0] = 1e-12
    A_norm = A / col_sum                      # B1
    W = A_norm.mean(axis=1)                   # B2
    W = W / W.sum()
    lambda_max = float((col_sum * W).sum())   # B3
    CI = (lambda_max - n) / (n - 1)           # B4
    RI = RI_SAATY.get(n, 1.49)
    CR = (CI / RI) if RI > 0 else 0.0         # B5
    return {
        "trong_so":          [round(float(w), 4) for w in W],
        "lambda_max":        round(lambda_max, 4),
        "CI":                round(float(CI), 4),
        "CR":                round(float(CR), 4),
        "chap_nhan":         bool(CR <= 0.10),
        "ma_tran_chuan_hoa": np.round(A_norm, 4).tolist(),
    }


def goi_y_cap_mau_thuan(ma_tran_so_sanh, trong_so, labels=None):
    """Cặp (i, j) LỆCH NHẤT giữa a_ij khai báo và tỉ số trọng số w_i/w_j —
    gợi ý người dùng xem lại khi CR > 0.10. Trả (label_i, label_j, a_ij, w_ratio)."""
    A = np.asarray(ma_tran_so_sanh, dtype=float)
    W = np.asarray(trong_so, dtype=float)
    n = A.shape[0]
    worst, pair = -1.0, None
    for i in range(n):
        for j in range(i + 1, n):
            if W[j] <= 0:
                continue
            ratio = W[i] / W[j]
            dev = abs(np.log(max(A[i, j], 1e-9)) - np.log(max(ratio, 1e-9)))
            if dev > worst:
                worst, pair = dev, (i, j)
    if pair is None:
        return None
    i, j = pair
    li = labels[i] if labels else f"#{i+1}"
    lj = labels[j] if labels else f"#{j+1}"
    return (li, lj, round(float(A[i, j]), 3),
            round(float(W[i] / max(W[j], 1e-9)), 3))


def tinh_trong_so_tuyet_doi(trong_so_nhom, trong_so_con_theo_nhom):
    """Trọng số TUYỆT ĐỐI từng tiêu chí (thang 100):
        W_tuyệt_đối(tiêu chí) = W_con_trong_nhóm × W_nhóm × 100.
    Tổng phải = 100% — lệch (nhóm/con chưa chuẩn hóa) → CHUẨN HÓA LẠI + cờ cảnh báo.

    trong_so_nhom          : {nhom: w} (tổng ≈ 1)
    trong_so_con_theo_nhom : {nhom: {ma_tieu_chi: w_con}} (mỗi nhóm tổng ≈ 1)
    Trả (weights: {ma: %}, warning: str|None).
    """
    out = {}
    for nhom, w_nhom in (trong_so_nhom or {}).items():
        for ma, w_con in (trong_so_con_theo_nhom.get(nhom) or {}).items():
            out[ma] = float(w_con) * float(w_nhom) * 100.0
    tong = sum(out.values())
    warning = None
    if out and abs(tong - 100.0) > 0.5:
        warning = (f"Tổng trọng số tuyệt đối = {tong:.2f}% ≠ 100% — đã tự "
                   "chuẩn hóa lại (kiểm tra ma trận AHP nhóm/con).")
        out = {k: v / tong * 100.0 for k, v in out.items()}
    return {k: round(v, 2) for k, v in out.items()}, warning
