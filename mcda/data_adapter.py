"""
mcda/data_adapter.py — Trích xuất thông số 3 PHƯƠNG ÁN từ Session State web app
(KHÔNG nhập tay như Excel). Thiếu trường nào → cảnh báo rõ trường + Module
nguồn, KHÔNG tự điền mặc định gây sai lệch.

Nguồn:
  • design_data['kcn_3_pa']       — Module 06 (3 phương án kết cấu nhịp)
  • utils/suat_dau_tu (Module 12) — suất đầu tư triệu VND/m² từng PA
  • KCN.BEAM_CATALOG              — L_max KHẢ NĂNG của loại dầm
  • KCN._L_nhip_min(B_tk, goc)    — L_min YÊU CẦU theo tĩnh không
  • session 'mcda_manual_values'  — giá trị THỦ CÔNG (C2 ngày/nhịp, C3 bãi đúc…)
"""
import os
import importlib.util

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PA_KEYS = ["pa1_chi_phi", "pa2_my_quan", "pa3_ml"]
PA_LABELS = {"pa1_chi_phi": "PA1 — Chi phí",
             "pa2_my_quan": "PA2 — Mỹ quan",
             "pa3_ml":      "PA3 — ML"}


def _load(path_name, mod_name):
    spec = importlib.util.spec_from_file_location(
        mod_name, os.path.join(_DIR, path_name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _kcn_mod():
    return _load("06-AI_KetCauNhip.py", "_mcda_kcn")


def _sdt_mod():
    return _load(os.path.join("utils", "suat_dau_tu.py"), "_mcda_sdt")


def _L_max_catalog(kcn, loai_dam):
    """L_max KHẢ NĂNG của loại dầm theo BEAM_CATALOG (m)."""
    ls = [float(r[1]) for r in getattr(kcn, "BEAM_CATALOG", [])
          if str(r[0]).strip().lower() == str(loai_dam or "").strip().lower()]
    return max(ls) if ls else None


def lay_du_lieu_3_pa(session_state):
    """Trả (du_lieu: {pa_key: dict}, warnings: list[str]).

    Mỗi PA gồm: loai_dam, L_max_kha_nang, L_min_yeu_cau, L_thuc_te, H_dam,
    so_nhip, khoang_cach_dam, so_dam_mc, co_ban_day, suat_dau_tu,
    ngay_thi_cong_nhip (thủ công), dien_tich_bai_duc (thủ công)."""
    ss = session_state
    d = ss.get("design_data") or {}
    warnings = []
    kcn3 = d.get("kcn_3_pa") or {}
    if not kcn3:
        return {}, ["Thiếu kết quả 3 phương án (design_data['kcn_3_pa'] — "
                    "Module 06). Chạy ⚙️ OPTIONS → Tính toán trước."]

    try:
        KCN = _kcn_mod()
    except Exception as e:
        return {}, [f"Không nạp được Module 06 (06-AI_KetCauNhip.py): {e}"]
    try:
        SDT = _sdt_mod()
    except Exception as e:
        SDT = None
        warnings.append(f"Không nạp được Module 12 (utils/suat_dau_tu.py): {e} "
                        "— thiếu B1 suất đầu tư.")

    B_tk = float(d.get("B", 0) or 0)
    goc = float(d.get("goc_giao", 90) or 90)
    L_min = None
    if B_tk > 0:
        try:
            L_min = float(KCN._L_nhip_min(B_tk, goc))
        except Exception:
            L_min = None
    if L_min is None:
        warnings.append("Thiếu bề rộng tĩnh không B (hộp thoại Thủy văn) — "
                        "không tính được L_min yêu cầu cho A1.")

    geo = d.get("geo_logic") or {}
    L_cau = float(geo.get("L_cau", 0) or 0)
    bc = float(d.get("bc") or d.get("b_cau") or 0)
    mong = d.get("mong_result") or {}
    manual = ss.get("mcda_manual_values") or {}

    out = {}
    for k in PA_KEYS:
        plan = kcn3.get(k) or (kcn3.get("pa3_ai") if k == "pa3_ml" else None)
        if not isinstance(plan, dict):
            warnings.append(f"Thiếu phương án '{k}' trong kcn_3_pa (Module 06).")
            continue
        loai = str(plan.get("loai_dam", "") or "")
        L = float(plan.get("chieu_dai", 0) or 0)
        H = float(plan.get("chieu_cao_dam") or plan.get("chieu_cao", 0) or 0)
        n_nhip = int(plan.get("tong_so_nhip", 0) or 0)
        try:
            co_bd = bool(KCN.co_ban_day_lien_mach(loai))
        except Exception:
            co_bd = False
        pa = {
            "label":           PA_LABELS.get(k, k),
            "loai_dam":        loai,
            "L_max_kha_nang":  _L_max_catalog(KCN, loai),
            "L_min_yeu_cau":   L_min,
            "L_thuc_te":       L,
            "H_dam":           H,
            "so_nhip":         n_nhip,
            "khoang_cach_dam": float(plan.get("khoang_cach_dam", 0) or 0),
            "so_dam_mc":       int(plan.get("so_luong_dam")
                                   or plan.get("so_luong_dam_mcn", 0) or 0),
            "co_ban_day":      co_bd,
        }
        if pa["L_max_kha_nang"] is None:
            warnings.append(f"{pa['label']}: loại dầm '{loai}' không có trong "
                            "BEAM_CATALOG (Module 06) — thiếu L_max cho A1.")
        if H <= 0:
            warnings.append(f"{pa['label']}: thiếu chiều cao dầm H (Module 06) "
                            "— A2/D1 không chấm được.")
        # ── B1: suất đầu tư (Module 12) — tính theo loại dầm/móng của PA ─────
        pa["suat_dau_tu"] = None
        if SDT is not None and L_cau > 0 and bc > 0:
            try:
                code = SDT.suggest(loai, str(mong.get("loai_mong", "") or ""), L)
                pa["suat_dau_tu"] = float(
                    SDT.compute(SDT.deck_area(L_cau, bc), code).get("suat", 0)
                    or 0) or None
            except Exception:
                pa["suat_dau_tu"] = None
        if pa["suat_dau_tu"] is None:
            warnings.append(f"{pa['label']}: thiếu SUẤT ĐẦU TƯ (Module 12 — "
                            "cần L_cầu + bề rộng bc, chạy pipeline trước).")
        # ── C2/C3: dữ liệu THỦ CÔNG (không có trong hệ thống) ────────────────
        for fld, mod in (("ngay_thi_cong_nhip", "C2 — tốc độ thi công"),
                         ("dien_tich_bai_duc", "C3 — bãi đúc")):
            v = (manual.get(k) or {}).get(fld)
            pa[fld] = float(v) if v not in (None, "", 0) else None
            if pa[fld] is None:
                warnings.append(
                    f"{pa['label']}: thiếu '{fld}' ({mod}) — nhập ở mục "
                    "'Dữ liệu thủ công' hoặc tắt tiêu chí tương ứng.")
        # Giá trị thủ công của tiêu chí CUSTOM (manual_<ma>)
        for kk, vv in (manual.get(k) or {}).items():
            if kk.startswith("manual_"):
                try:
                    pa[kk] = float(vv)
                except (TypeError, ValueError):
                    pass
        out[k] = pa
    return out, warnings
