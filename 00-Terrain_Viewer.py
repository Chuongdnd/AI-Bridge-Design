import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import re
from scipy.interpolate import griddata

def parse_ntd_file(uploaded_file):
    """
    🏔️ BỘ GIẢI MÃ FILE .NTD NGUYÊN BẢN CỦA CHƯƠNG:
    - Trích xuất dữ liệu trắc ngang trắc dọc từ file khảo sát địa hình sông.
    """
    data_points = []
    raw_content = uploaded_file.read()
    try:
        lines = raw_content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        lines = raw_content.decode("latin1").splitlines()
        
    current_x = 0.0
    current_pole = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
            
        token = parts[0].upper()
        
        if token == 'POLE' and len(parts) >= 4:
            try:
                current_pole = parts[1].strip()
                current_x = float(parts[2])
                z_tim = float(parts[3])
                
                data_points.append({
                    'Cọc': current_pole, 'Lý trình': current_x, 'Offset': 0.0, 'Z': z_tim,
                    'Tag_Gốc': 'POLE'
                })
            except:
                continue
                
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                offset = float(parts[1])
                z_val = float(parts[2])
                
                data_points.append({
                    'Cọc': current_pole, 'Lý trình': current_x, 'Offset': offset, 'Z': z_val,
                    'Tag_Gốc': 'TARGET'
                })
            except:
                continue
                
    return pd.DataFrame(data_points)

def parse_coordinate_file(uploaded_file):
    """
    📍 BỘ GIẢI MÃ TOẠ ĐỘ MỐC TIM TUYẾN PHẲNG (ĐÃ NÂNG CẤP THÔNG MINH):
    - Tự động viết hoa, xóa dấu tiếng Việt cơ bản để nhận diện mọi kiểu đặt tên cột X, Y, Tên Cọc.
    - Khắc phục triệt để lỗi chặn file "thiếu cột tên cọc hoặc toạ độ X, Y".
    """
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        c_name = [c for c in df.columns if any(k in c for k in ['TÊN', 'TEN', 'CỌC', 'COC', 'POLE', 'MÃ', 'MA', 'HO_KHOAN', 'HỐ KHOAN'])]
        c_x = [c for c in df.columns if 'X' in c]
        c_y = [c for c in df.columns if 'Y' in c]
        
        if not c_name or not c_x or not c_y:
            if df.shape[1] >= 3:
                df_clean = pd.DataFrame({
                    'Cọc_Excel': df.iloc[:, 0].astype(str).str.strip().str.upper(),
                    'X_VN2000': pd.to_numeric(df.iloc[:, 1], errors='coerce'),
                    'Y_VN2000': pd.to_numeric(df.iloc[:, 2], errors='coerce')
                }).dropna()
                return df_clean
            else:
                st.error("❌ File toạ độ cọc không đủ 3 cột dữ liệu tối thiểu (Tên cọc, X, Y)!")
                return None
            
        df_clean = pd.DataFrame({
            'Cọc_Excel': df[c_name[0]].astype(str).str.strip().str.upper(),
            'X_VN2000': pd.to_numeric(df[c_x[0]], errors='coerce'),
            'Y_VN2000': pd.to_numeric(df[c_y[0]], errors='coerce')
        }).dropna()
        
        return df_clean
    except Exception as e:
        st.error(f"Lỗi đọc file toạ độ mốc: {e}")
        return None

def convert_to_vn2000(df_ntd, df_coord):
    """
    🎯 THUẬT TOÁN ĐỒNG BỘ ĐỊA HÌNH THEO QUY ƯỚC TOÁN HỌC ĐỒ HỌA 3D:
    - Trục X đồ họa nhận dải 6 số (Y_VN2000 Đông của Excel mốc)
    - Trục Y đồ họa nhận dải 7 số (X_VN2000 Bắc của Excel mốc)
    """
    try:
        if df_ntd is None or df_ntd.empty or df_coord is None or df_coord.empty:
            return pd.DataFrame()
            
        df_ntd_clean = df_ntd.copy()
        df_coord_clean = df_coord.copy()
        
        df_ntd_clean['Cọc'] = df_ntd_clean['Cọc'].astype(str).str.strip().str.upper()
        df_coord_clean['Cọc_Excel'] = df_coord_clean['Cọc_Excel'].astype(str).str.strip().str.upper()
        
        # ĐỒNG BỘ ĐẢO TRỤC ĐỒ HỌA CHUẨN: X_Toán = Y_Excel (6 số), Y_Toán = X_Excel (7 số)
        map_x = dict(zip(df_coord_clean['Cọc_Excel'], df_coord_clean['Y_VN2000'])) 
        map_y = dict(zip(df_coord_clean['Cọc_Excel'], df_coord_clean['X_VN2000'])) 
        
        df_merged = df_ntd_clean.copy()
        df_merged['X_VN2000'] = df_merged['Cọc'].map(map_x)
        df_merged['Y_VN2000'] = df_merged['Cọc'].map(map_y)
        
        if df_merged['X_VN2000'].isna().all():
            list_ntd_x = sorted(df_merged['Lý trình'].unique())
            min_len = min(len(list_ntd_x), len(df_coord_clean))
            map_x_lt, map_y_lt = {}, {}
            for i in range(min_len):
                ly_trinh_ntd = list_ntd_x[i]
                map_x_lt[ly_trinh_ntd] = df_coord_clean['Y_VN2000'].iloc[i]
                map_y_lt[ly_trinh_ntd] = df_coord_clean['X_VN2000'].iloc[i]
            df_merged['X_VN2000'] = df_merged['Lý trình'].map(map_x_lt)
            df_merged['Y_VN2000'] = df_merged['Lý trình'].map(map_y_lt)

        df_merged = df_merged.dropna(subset=['X_VN2000', 'Y_VN2000']).copy()
        if df_merged.empty:
            return pd.DataFrame()
            
        df_tim_calc = df_merged[df_merged['Offset'] == 0].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình').copy()
        if len(df_tim_calc) >= 2:
            df_tim_calc['dX'] = np.gradient(df_tim_calc['X_VN2000'].values)
            df_tim_calc['dY'] = np.gradient(df_tim_calc['Y_VN2000'].values)
        else:
            df_tim_calc['dX'] = 1.0
            df_tim_calc['dY'] = 0.0
            
        df_tim_calc['Góc_Tuyến'] = np.arctan2(df_tim_calc['dY'], df_tim_calc['dX'])
        goc_map = dict(zip(df_tim_calc['Lý trình'], df_tim_calc['Góc_Tuyến']))
        df_merged['Góc_Tuyến'] = df_merged['Lý trình'].map(goc_map).bfill().ffill()
        
        angle_offset = df_merged['Góc_Tuyến'] + (np.pi / 2)
        df_merged['X_Real'] = df_merged['X_VN2000'] + df_merged['Offset'] * np.cos(angle_offset)
        df_merged['Y_Real'] = df_merged['Y_VN2000'] + df_merged['Offset'] * np.sin(angle_offset)
        
        return df_merged
    except Exception as e:
        st.error(f"Lỗi xử lý đồng bộ chuỗi điểm tim thực địa: {e}")
        return pd.DataFrame()

def ve_dia_hinh_3d(df, he_so_z=1.0, che_do="Bề mặt mịn", do_min=3):
    """
    🏔️ MÔ HÌNH ĐỊA HÌNH BỀ MẶT LÒNG SÔNG NGUYÊN BẢN CỦA CHƯƠNG
    """
    if df is None or df.empty: 
        return None
    
    try:
        df_clean = df.sort_values(['Lý trình', 'Offset']).copy()
        unique_lts = sorted(df_clean['Lý trình'].unique())
        
        num_samples = 40  
        target_pct = np.linspace(0.0, 1.0, num_samples)
        
        matrix_x, matrix_y, matrix_z = [], [], []
        
        for lt in unique_lts:
            df_sub = df_clean[df_clean['Lý trình'] == lt].sort_values('Offset')
            obs_offsets = df_sub['Offset'].values
            obs_x_real = df_sub['X_Real'].values  
            obs_y_real = df_sub['Y_Real'].values  
            obs_zs = df_sub['Z'].values
            
            if len(obs_offsets) < 2:
                continue
                
            pct_goc = (obs_offsets - obs_offsets[0]) / (obs_offsets[-1] - obs_offsets[0] + 0.0001)
            
            matrix_x.append(np.interp(target_pct, pct_goc, obs_x_real))
            matrix_y.append(np.interp(target_pct, pct_goc, obs_y_real))
            matrix_z.append(np.interp(target_pct, pct_goc, obs_zs))
            
        matrix_x = np.array(matrix_x)
        matrix_y = np.array(matrix_y)
        matrix_z = np.array(matrix_z)

        if do_min > 1:
            mz_pd = pd.DataFrame(matrix_z)
            mz_pd = mz_pd.rolling(window=do_min, min_periods=1, center=True).mean()
            matrix_z = mz_pd.T.rolling(window=do_min, min_periods=1, center=True).mean().T.values

        z_scaled = matrix_z * he_so_z
        fig = go.Figure()

        if che_do in ["Bề mặt mịn", "Lưới tam giác"]:
            show_wireframe = True if che_do == "Lưới tam giác" else False
            fig.add_trace(go.Surface(
                x=matrix_x, y=matrix_y, z=z_scaled, customdata=matrix_z,
                colorscale='Earth', opacity=0.85, name="Bề mặt đáy sông",
                colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
                hovertemplate="X VN2000: %{x:.2f} m<br>Y VN2000: %{y:.2f} m<br>Z Đáy: %{customdata:.2f} m<extra></extra>",
                contours=dict(
                    x=dict(show=show_wireframe, color="rgba(0,0,0,0.2)", width=1), 
                    y=dict(show=show_wireframe, color="rgba(0,0,0,0.2)", width=1)
                )
            ))
        elif che_do == "Đường đồng mức":
            fig.add_trace(go.Surface(
                x=matrix_x, y=matrix_y, z=z_scaled, customdata=matrix_z,
                colorscale='Viridis', opacity=0.85, name="Đường đồng mức đáy sông",
                colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
                contours_z=dict(show=True, usecolormap=False, color="rgb(0,0,0)", width=2, project=dict(z=True)),
                hovertemplate="X VN2000: %{x:.2f}<br>Y VN2000: %{y:.2f}<br>Z Đáy: %{customdata:.2f} m<extra></extra>"
            ))

        df_tim_all = df_clean[df_clean['Offset'] == 0].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình')
        if not df_tim_all.empty:
            nhan_hien_thi = df_tim_all.apply(lambda r: f"{r['Cọc']} (LT: {r['Lý trình']:.1f}m)", axis=1).values
            fig.add_trace(go.Scatter3d(
                x=df_tim_all['X_Real'].values, y=df_tim_all['Y_Real'].values, z=df_tim_all['Z'].values * he_so_z,
                mode='lines+markers+text',
                line=dict(color='red', width=4), marker=dict(size=4, color='yellow'),
                text=nhan_hien_thi, textposition="top center",
                textfont=dict(family="Arial, sans-serif", size=11, color="lightblue"),
                name='Đường tim tuyến dọc sông'
            ))

        fig.update_layout(
            title=dict(text="🏔️ MÔ HÌNH KHÔNG GIAN 3D TOÀN TUYẾN DỰ ÁN", font=dict(size=16, color='#007acc')),
            height=850,
            scene=dict(
                xaxis=dict(title="Tọa độ X (Y VN-2000 Đông - 6 số)", tickformat=".0f"), 
                yaxis=dict(title="Tọa độ Y (X VN-2000 Bắc - 7 số)", tickformat=".0f"), 
                zaxis=dict(title="Cao độ Z (m)"), 
                aspectmode='data'
            ),
            template="plotly_dark", 
            margin=dict(l=10, r=10, t=40, b=10), 
            paper_bgcolor='#0e1117'
        )
        return fig, matrix_x, matrix_y
    except Exception as e:
        st.error(f"Lỗi phân tích đồ họa không gian địa hình: {e}")
        return None, None, None

# =========================================================================
# ⚙️ PHÂN HỆ XỬ LÝ ĐỊA CHẤT NÂNG CAO - ĐỒNG BỘ TOÀN DIỆN VÀ FIX LỆCH TRỤC
# =========================================================================

def doc_excel_dia_chat_3_sheet(uploaded_file):
    """
    📥 BỘ ĐỌC FILE EXCEL ĐỊA CHẤT TRỌN GÓI 3 PHÂN HỆ CỦA CHƯƠNG:
    - Bóc tách Toado_HK, các sheet chi tiết (HK1, HK2, HK3) và sheet SPT.
    """
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        sheet_toado = [s for s in sheet_names if 'TOADO' in s.upper() or 'TỌA ĐỘ' in s.upper()]
        if not sheet_toado:
            return None, None, None
        df_hk_raw = pd.read_excel(uploaded_file, sheet_name=sheet_toado[0])
        df_hk_raw.columns = [str(c).strip().upper() for c in df_hk_raw.columns]
        
        c_name_list = [c for c in df_hk_raw.columns if any(k in c for k in ['HỐ KHOAN', 'HO_KHOAN', 'TÊN', 'TEN', 'CỌC', 'COC', 'POLE'])]
        c_x_list = [c for c in df_hk_raw.columns if 'X' in c]
        c_y_list = [c for c in df_hk_raw.columns if 'Y' in c]
        c_z_list = [c for c in df_hk_raw.columns if any(k in c for k in ['Z', 'CAO ĐỘ', 'CAO DO', 'MIỆNG', 'MIENG'])]
        
        col_name = c_name_list[0] if c_name_list else df_hk_raw.columns[0]
        col_x = c_x_list[0] if c_x_list else (df_hk_raw.columns[1] if len(df_hk_raw.columns) > 1 else None)
        col_y = c_y_list[0] if c_y_list else (df_hk_raw.columns[2] if len(df_hk_raw.columns) > 2 else None)
        col_z = c_z_list[0] if c_z_list else (df_hk_raw.columns[3] if len(df_hk_raw.columns) > 3 else df_hk_raw.columns[-1])
        
        if col_x is None or col_y is None:
            return None, None, None
            
        df_hk = pd.DataFrame({
            'Ho_Khoan': df_hk_raw[col_name].astype(str).str.strip().str.upper(),
            'X_VN2000': pd.to_numeric(df_hk_raw[col_x], errors='coerce'),
            'Y_VN2000': pd.to_numeric(df_hk_raw[col_y], errors='coerce'),
            'Z_Mieng': pd.to_numeric(df_hk_raw[col_z], errors='coerce')
        }).dropna(subset=['X_VN2000', 'Y_VN2000']).reset_index(drop=True)
        
        list_layers = []
        for sheet in sheet_names:
            if 'SPT' in sheet.upper() or 'TOADO' in sheet.upper() or 'TỌA ĐỘ' in sheet.upper():
                continue
            df_layer_raw = pd.read_excel(uploaded_file, sheet_name=sheet)
            if df_layer_raw.empty: continue
            df_layer_raw.columns = [str(c).strip().upper() for c in df_layer_raw.columns]
            
            c_lop_list = [c for c in df_layer_raw.columns if any(k in c for k in ['TÊN LỚP', 'TEN_LOP', 'LỚP', 'LOP', 'ĐẤT', 'DAT'])]
            c_tu_list = [c for c in df_layer_raw.columns if any(k in c for k in ['TỪ', 'TU_', 'DEPTH', 'FROM'])]
            c_den_list = [c for c in df_layer_raw.columns if any(k in c for k in ['ĐẾN', 'DEN_', 'TO'])]
            
            col_lop = c_lop_list[0] if c_lop_list else df_layer_raw.columns[0]
            col_tu = c_tu_list[0] if c_tu_list else (df_layer_raw.columns[1] if len(df_layer_raw.columns) > 1 else None)
            col_den = c_den_list[0] if c_den_list else (df_layer_raw.columns[2] if len(df_layer_raw.columns) > 2 else None)
            
            if col_tu is None or col_den is None: continue
            
            for _, r in df_layer_raw.iterrows():
                try:
                    tu_v = float(str(r[col_tu]).replace(',', '.'))
                    den_v = float(str(r[col_den]).replace(',', '.'))
                    if np.isnan(tu_v) or np.isnan(den_v): continue
                    list_layers.append({
                        'Ho_Khoan': str(sheet).strip().upper(),
                        'Tu_Chieu_Sau_Lop': tu_v,
                        'Den_Chieu_Sau_Lop': den_v,
                        'Ten_Lop': str(r[col_lop]).strip().upper()
                    })
                except: continue
        df_layers = pd.DataFrame(list_layers)
        
        sheet_spt = [s for s in sheet_names if 'SPT' in s.upper()]
        df_spt = pd.read_excel(uploaded_file, sheet_name=sheet_spt[0]) if sheet_spt else None
        if df_spt is not None:
            df_spt.columns = [str(c).strip() for c in df_spt.columns]
            
        return df_hk, df_layers, df_spt
    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu cấu trúc Excel địa chất: {e}")
        return None, None, None

def dap_them_ket_cau_dia_chat_3d(fig, df_hk, df_layers, df_spt, matrix_x, matrix_y, he_so_z=1.0):
    """
    🏗️ HÀM TÍCH HỢP ĐỊA CHẤT 3D CHUẨN XÁC LOGIC KHÔNG GIAN:
    - SỬA LỖI ĐỒNG BỘ TRỤC PHẲNG: X đồ họa = Y_Excel (6 số), Y đồ họa = X_Excel (7 số).
    - ĐỒNG BỘ SCALE THEO CHIỀU ĐỨNG: Nhân hằng số he_so_z vào toàn bộ các phần tử cao độ địa chất.
    - Tạo thảm màng phân lớp mở rộng tự do, không bị giới hạn cắt xén bởi biên đa giác địa hình.
    """
    if fig is None or df_hk is None or df_hk.empty or df_layers is None or df_layers.empty:
        return fig
        
    mau_quy_uoc = {
        'K': '#8B4513', '1': '#A0522D', '2B': '#4682B4', '2b': '#4682B4',
        'TK4': '#DEB887', '5': '#D2B48C', 'CL': '#4682B4', 'C': '#D2B48C'
    }
    
    # Tạo lưới mịn nền phẳng mở rộng biên ra ngoài ranh giới lòng sông để hứng hố khoan ngoài rìa
    min_x, max_x = float(matrix_x.min()), float(matrix_x.max())
    min_y, max_y = float(matrix_y.min()), float(matrix_y.max())
    gx, gy = np.meshgrid(
        np.linspace(min_x - 40, max_x + 40, 45),
        np.linspace(min_y - 40, max_y + 40, 45)
    )
    
    def lam_sach_ten(text):
        return re.sub(r'[^A-Z0-9]', '', str(text).upper().strip())
        
    df_hk_clean = df_hk.copy()
    df_layers_clean = df_layers.copy()
    df_hk_clean['Key_HK'] = df_hk_clean['Ho_Khoan'].apply(lam_sach_ten)
    df_layers_clean['Key_HK'] = df_layers_clean['Ho_Khoan'].apply(lam_sach_ten)
    
    list_hk_valid = []
    
    # 🎯 LUỒNG A: CẮM TRỤ ĐỨNG HỐ KHOAN VÀ ĐỒ THỊ SPT (ĐÃ ĐỒNG BỘ TOÀN DIỆN TRỤC VÀ SCALE)
    for _, hk in df_hk_clean.iterrows():
        try:
            ten_hk_goc = str(hk['Ho_Khoan']).strip()
            key_hk = hk['Key_HK']
            
            # ✨ ĐỒNG BỘ ĐẢO TRỤC: X_Đồ họa = Y_Excel (6 số Đông), Y_Đồ họa = X_Excel (7 số Bắc)
            x_hk = float(hk['Y_VN2000'])
            y_hk = float(hk['X_VN2000'])
            z_mieng = float(hk['Z_Mieng'])
            
            if np.isnan(x_hk) or np.isnan(y_hk): continue
            list_hk_valid.append({'name': key_hk, 'x': x_hk, 'y': y_hk, 'z_mieng': z_mieng})
            
            df_sub_layers = df_layers_clean[df_layers_clean['Key_HK'] == key_hk].sort_values('Tu_Chieu_Sau_Lop')
            
            # Vẽ các đốt hình trụ đứng phân chia các lớp đất của hố khoan
            for _, lop in df_sub_layers.iterrows():
                # ✨ ĐỒNG BỘ TỶ LỆ SCALE: Áp dụng he_so_z vào cao độ trần và nền của lớp đất
                z_top = (z_mieng - float(lop['Tu_Chieu_Sau_Lop'])) * he_so_z
                z_bot = (z_mieng - float(lop['Den_Chieu_Sau_Lop'])) * he_so_z
                
                t_lop = str(lop['Ten_Lop']).strip().upper()
                mau_n = '#808080'
                for k_mau, v_mau in mau_quy_uoc.items():
                    if k_mau in t_lop: mau_n = v_mau; break
                        
                fig.add_trace(go.Scatter3d(
                    x=[x_hk, x_hk], y=[y_hk, y_hk], z=[z_top, z_bot], mode='lines',
                    line=dict(color=mau_n, width=12), name=f"Hố {ten_hk_goc} - Lớp {t_lop}",
                    hoverinfo="text", text=f"Hố: {ten_hk_goc}<br>Lớp: {t_lop}<br>Sâu: {lop['Tu_Chieu_Sau_Lop']}m - {lop['Den_Chieu_Sau_Lop']}m"
                ))
                
            # Thể hiện biểu đồ dích dắc số búa SPT dạt xiên cạnh hố đứng
            if df_spt is not None:
                col_spt = [c for c in df_spt.columns if lam_sach_ten(c) in key_hk or key_hk in lam_sach_ten(c)]
                if col_spt and 'Độ sâu thí nghiệm (m)' in df_spt.columns:
                    df_sub_spt = df_spt[['Độ sâu thí nghiệm (m)', col_spt[0]]].dropna()
                    spt_x, spt_y, spt_z, spt_txt = [], [], [], []
                    for _, r_spt in df_sub_spt.iterrows():
                        try:
                            n_val = float(r_spt[col_spt[0]])
                            txt_sau = str(r_spt['Độ sâu thí nghiệm (m)'])
                            nums = [float(n.replace(',', '.')) for n in re.findall(r'[\d,\.]+', txt_sau)]
                            if nums:
                                d_spt = nums[0]
                                # Đẩy biểu đồ nghiêng tịnh tiến theo phương X đồ họa mới (Y_Excel)
                                spt_x.append(x_hk + 15.0 + n_val * 0.8) 
                                spt_y.append(y_hk)
                                # ✨ ĐỒNG BỘ TỶ LỆ SCALE CHIỀU Z CHO SPT:
                                spt_z.append((z_mieng - d_spt) * he_so_z)
                                spt_txt.append(f"N={n_val:.0f}")
                        except: continue
                    if spt_z:
                        fig.add_trace(go.Scatter3d(
                            x=spt_x, y=spt_y, z=spt_z, mode='lines+markers+text',
                            line=dict(color='yellow', width=2.5), marker=dict(size=4.5, color='orange'),
                            text=spt_txt, textposition="middle right",
                            textfont=dict(size=9, color='yellow'), name=f"SPT {ten_hk_goc}"
                        ))
        except: continue

    # 🎯 LUỒNG B: NỘI SUY DỆT TẤM THẢM MẶT PHẲNG ĐỊA CHẤT 3D MỞ RỘNG TỰ DO
    df_hk_v = pd.DataFrame(list_hk_valid)
    if len(df_hk_v) >= 2 and not df_layers_clean.empty:
        df_hk_v['sort_key'] = df_hk_v['x'] + df_hk_v['y']
        df_hk_v = df_hk_v.sort_values('sort_key').reset_index(drop=True)
        all_unique_layers = df_layers_clean['Ten_Lop'].unique()
        
        for lop_dat in all_unique_layers:
            lop_dat_str = str(lop_dat).strip().upper()
            pt_x, pt_y, pt_z_bot = [], [], []
            
            for idx in range(len(df_hk_v)):
                hk_curr = df_hk_v.iloc[idx]
                sub = df_layers_clean[(df_layers_clean['Key_HK'] == hk_curr['name']) & (df_layers_clean['Ten_Lop'] == lop_dat)]
                if not sub.empty:
                    pt_x.append(hk_curr['x'])
                    pt_y.append(hk_curr['y'])
                    pt_z_bot.append(hk_curr['z_mieng'] - sub['Den_Chieu_Sau_Lop'].iloc[0])
            
            if len(pt_x) < 2: continue
            
            # Tính toán lưới cao độ nền phẳng từ dữ liệu tọa độ chuẩn
            grid_z = griddata((pt_x, pt_y), pt_z_bot, (gx, gy), method='nearest')
            # ✨ ĐỒNG BỘ TỶ LỆ SCALE CHIỀU Z CHO MẶT PHẲNG NỘI SUY ĐỊA CHẤT:
            grid_z_scaled = grid_z * he_so_z
            
            m_color = '#808080'
            for k_mau, v_mau in mau_quy_uoc.items():
                if k_mau in lop_dat_str: m_color = v_mau; break
            
            # Đẩy thảm địa chất màu mịn lên mô hình không gian phối hợp cùng lòng sông
            fig.add_trace(go.Surface(
                x=gx, y=gy, z=grid_z_scaled, customdata=grid_z,
                colorscale=[[0, m_color], [1, m_color]], showscale=False, opacity=0.55,
                name=f"Mặt phẳng: {lop_dat_str}",
                hovertemplate=f"<b>Mặt đáy lớp: {lop_dat_str}</b><br>Cao độ đáy thực: %{{customdata:.2f}} m<extra></extra>"
            ))
            
    return fig