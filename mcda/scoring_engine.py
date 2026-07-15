"""
mcda/scoring_engine.py — Chấm điểm MCDA tổng hợp 3 phương án.

Điểm có trọng số của 1 tiêu chí = điểm_thô(0–10) × trọng_số_tuyệt_đối / 10
→ tổng S_j trên thang 100. Xếp loại: ≥85 Xuất sắc, ≥70 Tốt, ≥55 Đạt, <55 Cần
xem xét. Khuyến nghị PA điểm cao nhất; chênh < 5 điểm → 2 PA tương đương.
"""
from . import scoring_formulas as SF


XEP_LOAI = [(85.0, "Xuất sắc"), (70.0, "Tốt"), (55.0, "Đạt"),
            (-1e9, "Cần xem xét")]


def _xep_loai(diem):
    for nguong, ten in XEP_LOAI:
        if diem >= nguong:
            return ten
    return "Cần xem xét"


def cham_diem_mcda(du_lieu_3_pa, trong_so_tuyet_doi, danh_sach_tieu_chi):
    """Chấm điểm mọi PA × mọi tiêu chí ACTIVE.

    Trả dict:
      rows       : [{ma, ten, nhom, trong_so, {pa: diem_tho}, {pa: diem_ts}}]
      tong       : {pa: S_j}
      xep_loai   : {pa: str}
      nhom_diem  : {pa: {nhom: điểm nhóm (đã trọng số)}}
      nhom_max   : {nhom: tổng trọng số nhóm} (để radar chuẩn hóa 0–10)
      khuyen_nghi: {"pa": key, "tuong_duong": key|None, "chenh": float}
      bo_qua     : [tiêu chí active nhưng THIẾU dữ liệu → bỏ qua + lý do]
    """
    pas = {k: v for k, v in (du_lieu_3_pa or {}).items()}
    pa_keys = list(pas.keys())
    all_pa = list(pas.values())
    rows, bo_qua = [], []
    tong = {k: 0.0 for k in pa_keys}
    nhom_diem = {k: {} for k in pa_keys}
    nhom_max = {}

    for crit in (danh_sach_tieu_chi or []):
        if not crit.get("active"):
            continue
        w = float(trong_so_tuyet_doi.get(crit["ma"], 0) or 0)
        scorer = SF.SCORERS.get(crit.get("scorer"))
        if scorer is None:
            bo_qua.append((crit, "không có hàm chấm điểm"))
            continue
        # Thiếu dữ liệu nguồn ở PA nào → bỏ tiêu chí (không điền mặc định)
        src = crit.get("source") or f"manual_{crit['ma']}"
        thieu = [pas[k].get("label", k) for k in pa_keys
                 if pas[k].get(src) is None
                 and crit.get("scorer") in ("minmax",)]
        if thieu:
            bo_qua.append((crit, f"thiếu dữ liệu '{src}' ở {', '.join(thieu)}"))
            continue
        row = {"ma": crit["ma"], "ten": crit["ten"], "nhom": crit["nhom"],
               "trong_so": w, "tho": {}, "ts": {}}
        for k in pa_keys:
            tho = float(scorer(pas[k], all_pa, crit) or 0)
            ts = round(tho * w / 10.0, 2)
            row["tho"][k] = round(tho, 2)
            row["ts"][k] = ts
            tong[k] += ts
            nhom_diem[k][crit["nhom"]] = (nhom_diem[k].get(crit["nhom"], 0.0)
                                          + ts)
        nhom_max[crit["nhom"]] = nhom_max.get(crit["nhom"], 0.0) + w
        rows.append(row)

    tong = {k: round(v, 2) for k, v in tong.items()}
    xl = {k: _xep_loai(v) for k, v in tong.items()}

    khuyen_nghi = None
    if tong:
        rank = sorted(tong.items(), key=lambda kv: kv[1], reverse=True)
        best = rank[0]
        second = rank[1] if len(rank) > 1 else None
        chenh = round(best[1] - second[1], 2) if second else None
        khuyen_nghi = {
            "pa": best[0],
            "tuong_duong": (second[0] if (second and chenh is not None
                                          and chenh < 5.0) else None),
            "chenh": chenh,
        }
    return {"rows": rows, "tong": tong, "xep_loai": xl,
            "nhom_diem": nhom_diem, "nhom_max": nhom_max,
            "khuyen_nghi": khuyen_nghi, "bo_qua": bo_qua}
