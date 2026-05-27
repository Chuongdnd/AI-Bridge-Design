import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

# =========================================================
# MODULE 1: HUẤN LUYỆN AI
# =========================================================
def train_bridge_ai_system(file_path):
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy file tại {file_path}")
        return None
    try:
        df = pd.read_excel(file_path, sheet_name='MainSpan')
        df.columns = [str(c).strip() for c in df.columns]
        
        col_tk = next((c for c in df.columns if 'tĩnh không B' in c), None)
        col_len = next((c for c in df.columns if 'Chiều dài dầm' in c), None)
        col_type = next((c for c in df.columns if 'Loại dầm' in c), None)
        col_bcau = next((c for c in df.columns if 'B_cầu' in c), None)
        col_dist = next((c for c in df.columns if 'K/c dầm' in c), None)
        col_h = next((c for c in df.columns if 'H_dầm' in c), None)

        for col in [col_tk, col_len, col_dist, col_bcau, col_h]:
            if col: df[col] = pd.to_numeric(df[col], errors='coerce')

        df_clean = df.dropna(subset=[col_tk, col_len, col_type, col_h]).copy()
        
        le_env = LabelEncoder()
        env_data = df_clean['Môi trường'].astype(str) if 'Môi trường' in df_clean.columns else pd.Series(['Vượt sông']*len(df_clean))
        df_clean['Env_Enc'] = le_env.fit_transform(env_data)
        
        le_type = LabelEncoder()
        df_clean['Type_Enc'] = le_type.fit_transform(df_clean[col_type])

        X = df_clean[[col_tk, 'Env_Enc']]
        m_type = RandomForestClassifier(n_estimators=100, random_state=42).fit(X, df_clean['Type_Enc'])
        m_len = RandomForestRegressor(n_estimators=100, random_state=42).fit(X, df_clean[col_len])
        m_height = RandomForestRegressor(n_estimators=100, random_state=42).fit(df_clean[['Type_Enc', col_len]], df_clean[col_h])
        m_dist = RandomForestRegressor(n_estimators=100, random_state=42).fit(df_clean[['Type_Enc', col_bcau]], df_clean[col_dist].fillna(1.0))

        return {
            'type': m_type, 'len': m_len, 'h': m_height, 'dist': m_dist,
            'le_env': le_env, 'le_type': le_type, 'count': len(df_clean)
        }
    except Exception as e:
        print(f"Lỗi huấn luyện: {e}")
        return None

# =========================================================
# MODULE 2: AI THUẦN (LEGACY)
# =========================================================
def predict_main_span_legacy(b_tk, goc, b_cau, env, models, L_cau_tong=None):
    try:
        env_enc = models['le_env'].transform([env])[0]
    except:
        env_enc = 0

    t_idx = models['type'].predict([[b_tk, env_enc]])[0]
    t_f = models['le_type'].inverse_transform([t_idx])[0]
    t_f_str = str(t_f).strip()
    if env == "Đô thị" and b_tk <= 20:
        t_f_str = "T ngược"

    l_ai = models['len'].predict([[b_tk, env_enc]])[0]
    l_min_geo = (b_tk / np.sin(np.radians(goc))) + 2.0
    l_f_ai = max(l_ai, l_min_geo)
    std_lengths = [15, 18, 21, 24, 25, 30, 33, 38.2, 40]
    l_f_ai = min(std_lengths, key=lambda x: abs(x - l_f_ai))

    analysis_note = ""
    n_nhip_final = 1
    t_f_final = t_f_str
    
    if L_cau_tong and L_cau_tong > 0:
        n_ai = int(np.ceil(L_cau_tong / l_f_ai))
        l_thuc_ai = round(L_cau_tong / n_ai, 2)
        l_spt_max = 38.2
        n_spt = int(np.floor(L_cau_tong / l_spt_max))
        if n_spt < 1: n_spt = 1
        l_thuc_spt = round(L_cau_tong / n_spt, 2)
        if n_ai >= 4 and n_spt < n_ai and l_thuc_spt <= 40.0:
            l_f = l_thuc_spt
            t_f_final = "Super-T"
            n_nhip_final = n_spt
            analysis_note = f"Tối ưu (Cầu dài >= 4 nhịp): Dùng {n_spt} nhịp SPT để giảm {n_ai - n_spt} trụ."
        else:
            l_f = l_thuc_ai
            n_nhip_final = n_ai
            analysis_note = f"Phương án chọn theo AI: {n_nhip_final} nhịp dầm {t_f_final}."
    else:
        l_f = l_f_ai
        analysis_note = "Dự báo thông số cho 1 nhịp đơn."

    le_type = models['le_type']
    t_enc = le_type.transform([t_f_final])[0] if t_f_final in le_type.classes_ else 0
    h_f = models['h'].predict([[t_enc, l_f]])[0]
    s_f = models['dist'].predict([[t_enc, b_cau]])[0]
    n_dam = int(np.floor(b_cau / s_f)) + 1
    oh = round((b_cau - (n_dam - 1) * s_f) / 2, 2)
    if oh >= 0.8 * s_f:
        n_dam += 1
        oh = round((b_cau - (n_dam - 1) * s_f) / 2, 2)

    return {
        "loai_dam": t_f_final,
        "chieu_dai": round(l_f, 2),
        "tong_so_nhip": n_nhip_final,
        "chieu_cao": round(h_f, 2),
        "so_luong_dam_mcn": n_dam,
        "khoang_cach_dam": round(s_f, 2),
        "overhang": oh,
        "ghi_chu_ai": analysis_note
    }

# =========================================================
# MODULE 3: TỐI ƯU HOÁ TỔ HỢP (AUTO)
# =========================================================
def optimize_girder_selection(b_tk, goc, b_cau, env, models, L_cau_tong=None):
    try:
        env_enc = models['le_env'].transform([env])[0]
    except:
        env_enc = 0
    le_type = models['le_type']
    
    # Xác định loại dầm khả thi
    candidate_types = set()
    ai_type_idx = models['type'].predict([[b_tk, env_enc]])[0]
    ai_type = le_type.inverse_transform([ai_type_idx])[0].strip()
    candidate_types.add(ai_type)
    if env == "Đô thị" and b_tk <= 20:
        candidate_types.add("T ngược")
    else:
        candidate_types.update(["Super-T", "I", "T"])
    
    std_lengths = [15, 18, 21, 24, 25, 30, 33, 38.2, 40]
    ai_len = models['len'].predict([[b_tk, env_enc]])[0]
    ai_len_rounded = min(std_lengths, key=lambda x: abs(x - ai_len))
    possible_lengths = sorted(set(std_lengths + [ai_len_rounded]))
    
    candidates = []
    for dam_type in candidate_types:
        if dam_type not in le_type.classes_:
            continue
        t_enc = le_type.transform([dam_type])[0]
        for L in possible_lengths:
            h = models['h'].predict([[t_enc, L]])[0]
            s = models['dist'].predict([[t_enc, b_cau]])[0]
            n_dam = int(np.floor(b_cau / s)) + 1
            oh = round((b_cau - (n_dam - 1) * s) / 2, 2)
            if oh >= 0.8 * s:
                n_dam += 1
                oh = round((b_cau - (n_dam - 1) * s) / 2, 2)
            if L_cau_tong and L_cau_tong > 0:
                n_nhip = int(np.ceil(L_cau_tong / L))
                L_thuc = L_cau_tong / n_nhip
                if L_thuc > 45:
                    continue
            else:
                n_nhip = 1
                L_thuc = L
            score = 0
            if L_cau_tong:
                score += (50 / n_nhip)
            else:
                score += 50
            if 30 <= L_thuc <= 40:
                score += 30
            elif 25 <= L_thuc < 30 or 40 < L_thuc <= 45:
                score += 15
            type_score = {"Super-T": 40, "I": 30, "T": 20, "T ngược": 10}
            score += type_score.get(dam_type, 0)
            if 17 <= L / h <= 22:
                score += 10
            elif 15 <= L / h <= 25:
                score += 5
            candidates.append({
                "loai_dam": dam_type,
                "chieu_dai": round(L_thuc, 2),
                "tong_so_nhip": n_nhip,
                "chieu_cao": round(h, 2),
                "so_luong_dam_mcn": n_dam,
                "khoang_cach_dam": round(s, 2),
                "overhang": oh,
                "score": score
            })
    if not candidates:
        return predict_main_span_legacy(b_tk, goc, b_cau, env, models, L_cau_tong)
    best = max(candidates, key=lambda x: x["score"])
    best.pop("score")
    best["ghi_chu_ai"] = f"Tối ưu từ {len(candidates)} phương án: {best['loai_dam']} - {best['chieu_dai']}m, {best['tong_so_nhip']} nhịp"
    return best

# =========================================================
# MODULE 4: HÀM CHÍNH (HỖ TRỢ METHOD)
# =========================================================
def predict_main_span(b_tk, goc, b_cau, env, models, L_cau_tong=None, method='auto'):
    if method == 'auto':
        return optimize_girder_selection(b_tk, goc, b_cau, env, models, L_cau_tong)
    elif method == 'ai':
        return predict_main_span_legacy(b_tk, goc, b_cau, env, models, L_cau_tong)
    else:  # 'rb'
        l_min_geo = (b_tk / np.sin(np.radians(goc))) + 2.0
        l_rb = max(15, min(40, l_min_geo))
        std_lengths = [15, 18, 21, 24, 25, 30, 33, 38.2, 40]
        l_final = min(std_lengths, key=lambda x: abs(x - l_rb))
        if L_cau_tong and L_cau_tong > 0:
            n_nhip = int(np.ceil(L_cau_tong / l_final))
            l_final = L_cau_tong / n_nhip
        else:
            n_nhip = 1
        return {
            "loai_dam": "Super-T" if n_nhip >= 3 else "I",
            "chieu_dai": round(l_final, 2),
            "tong_so_nhip": n_nhip,
            "chieu_cao": round(l_final / 18, 2),
            "so_luong_dam_mcn": int(b_cau / 2.2) + 1,
            "khoang_cach_dam": 2.2,
            "overhang": 0.5,
            "ghi_chu_ai": "Quy tắc RB (kinh nghiệm)"
        }

# =========================================================
# CHẠY THỬ (NẾU CHẠY ĐỘC LẬP)
# =========================================================
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    xlsx_path = os.path.join(current_dir, 'Girder.xlsx')
    models = train_bridge_ai_system(xlsx_path)
    if not models:
        print("Không thể huấn luyện AI.")
    else:
        print(f"Đã huấn luyện từ {models['count']} mẫu.")
        b_tk = float(input("B (m): "))
        goc = float(input("Góc (độ): "))
        b_cau = float(input("Bc (m): "))
        env = input("Môi trường (Vượt sông/Đô thị): ")
        L_cau_tong = input("L_cau (bỏ qua nếu không): ")
        L_cau_tong = float(L_cau_tong) if L_cau_tong else None
        method = input("Phương pháp (auto/ai/rb): ").strip() or 'auto'
        res = predict_main_span(b_tk, goc, b_cau, env, models, L_cau_tong, method)
        print(res)