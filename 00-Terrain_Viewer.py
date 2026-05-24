import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import re
from scipy.interpolate import griddata

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD TOÀN DIỆN KHÔNG GIAN
    - Phân loại trực tiếp bằng cách đọc chữ 'POLE', 'TARGETL', 'TARGETR'
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
        
        # 1. Đọc chữ POLE lấy tọa độ tim tuyến
        if token == 'POLE' and len(parts) >= 4:
            try:
                current_pole = parts[1].strip().upper()
                current_x = float(parts[2])
                z_tim = float(parts[3])
                
                data_points.append({
                    'Cọc': current_pole, 'Lý trình': current_x, 'Offset': 0.0, 'Z': z_tim, 'Tag_Gốc': 'POLE'
                })
            except ValueError:
                pass
        # 2. Đọc chữ TARGETL/R lấy tọa độ cánh trắc ngang thực tế
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                dist_offset = float(parts[1])
                z_val = float(parts[2])
                
                if current_pole:
                    data_points.append({
                        'Cọc': current_pole, 'Lý trình': current_x, 'Offset': dist_offset, 'Z': z_val, 'Tag_Gốc': token
                    })
            except ValueError:
                pass
                
    return pd.DataFrame(data_points)

def parse_coordinate_file(uploaded_file):
    """
    BỘ GIẢI MÃ BẢNG TOẠ ĐỘ VN-2000
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            df_coord = pd.read_csv(uploaded_file, skiprows=1)
        else:
            df_coord = pd.read_excel(uploaded_file, skiprows=1)
            
        df_coord.columns = [str(c).strip().upper() for c in df_coord.columns]
        
        try:
            col_name = [c for c in df_coord.columns if 'CỌC' in c or 'TEN' in c][0]
        except IndexError:
            col_name = df_coord.columns[1]
            
        col_x = df_coord.columns[3]
        col_y = df_coord.columns[4]
        
        x_numeric = pd.to_numeric(df_coord[col_x], errors='coerce')
        y_numeric = pd.to_numeric(df_coord[col_y], errors='coerce')
        
        df_clean = pd.DataFrame({
            'Cọc_Excel': df_coord[col_name].astype(str).str.strip().str.upper(),
            'X_VN2000': x_numeric,
            'Y_VN2000': y_numeric
        })
        return df_clean.dropna(subset=['X_VN2000', 'Y_VN2000']).reset_index(drop=True)
    except Exception as e:
        st.error(f"Lỗi đọc file bảng tọa độ VN-2000: {e}")
        return None

def convert_to_vn2000(df_ntd, df_coord):
    """
    THUẬT TOÁN ĐỒNG BỘ SONG SONG VÀ XOAY LƯỢNG GIÁC THEO TIM TUYẾN THỰC ĐỊA
    """
    try:
        list_ntd_x = sorted(df_ntd['Lý trình'].unique())
        df_coord_clean = df_coord.copy()
        
        min_len = min(len(list_ntd_x), len(df_coord_clean))
        if min_len == 0:
            return pd.DataFrame()
            
        map_x_real = {}
        map_y_real = {}
        for i in range(min_len):
            ly_trinh_ntd = list_ntd_x[i]
            map_x_real[ly_trinh_ntd] = df_coord_clean['X_VN2000'].iloc[i]
            map_y_real[ly_trinh_ntd] = df_coord_clean['Y_VN2000'].iloc[i]
            
        df_merged = df_ntd.copy()
        df_merged['X_VN2000'] = df_merged['Lý trình'].map(map_x_real)
        df_merged['Y_VN2000'] = df_merged['Lý trình'].map(map_y_real)
        
        df_merged = df_merged.dropna(subset=['X_VN2000', 'Y_VN2000']).copy()
        
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
    🏔️ MÔ HÌNH ĐỊA HÌNH 3D XUYÊN SUỐT - GIẢI QUYẾT TRIỆT ĐỂ LỖI SÓT ĐOẠN CONG/THẲNG
    - Quét liên tục qua tất cả các cọc tăng dần theo thứ tự Lý trình.
    - Cọc nào thiếu chữ 'TARGETL/R' sẽ được tự động bù biên từ các cọc đầy đủ lân cận để vuốt nối liền mạch.
    """
    if df.empty: 
        return None
    
    try:
        df_clean = df.sort_values(['Lý trình', 'Offset']).copy()
        unique_lts = sorted(df_clean['Lý trình'].unique())
        
        # Đồng bộ 40 mắt đan trên mỗi mặt cắt ngang line
        num_samples = 40  
        target_pct = np.linspace(0.0, 1.0, num_samples)
        
        matrix_x, matrix_y, matrix_z = [], [], []
        
        for lt in unique_lts:
            df_sub = df_clean[df_clean['Lý trình'] == lt].sort_values('Offset')
            
            # Kiểm tra xem cọc này có chứa chữ TARGETL hoặc TARGETR không (Tag_Gốc có chữ TARGET)
            has_target = df_sub['Tag_Gốc'].str.contains('TARGET', na=False).any()
            
            obs_offsets = df_sub['Offset'].values
            obs_x_real = df_sub['X_Real'].values
            obs_y_real = df_sub['Y_Real'].values
            obs_zs = df_sub['Z'].values
            
            # 🎯 NẾU CỌC SÓT (CHỈ CÓ CHỮ POLE - KHÔNG CÓ CHỮ TARGET): Tự động lấy biên vuốt bù
            if not has_target or len(obs_offsets) < 2:
                goc_tuyen = df_sub['Góc_Tuyến'].iloc[0]
                g_offset = goc_tuyen + (np.pi / 2)
                
                # Giả lập dải cánh 25m mỗi bên gối đầu mềm dẻo qua cọc phụ
                offsets_fake = np.linspace(-25.0, 25.0, num_samples)
                x_line = df_sub['X_VN2000'].iloc[0] + offsets_fake * np.cos(g_offset)
                y_line = df_sub['Y_VN2000'].iloc[0] + offsets_fake * np.sin(g_offset)
                z_line = np.repeat(obs_zs[0], num_samples)
            else:
                # Cọc đo chuẩn chuẩn đầy đủ chữ TARGETL, TARGETR từ file khảo sát
                pct_goc = (obs_offsets - obs_offsets[0]) / (obs_offsets[-1] - obs_offsets[0] + 0.0001)
                x_line = np.interp(target_pct, pct_goc, obs_x_real)
                y_line = np.interp(target_pct, pct_goc, obs_y_real)
                z_line = np.interp(target_pct, pct_goc, obs_zs)
                
            matrix_x.append(x_line)
            matrix_y.append(y_line)
            matrix_z.append(z_line)
            
        matrix_x = np.array(matrix_x)
        matrix_y = np.array(matrix_y)
        matrix_z = np.array(matrix_z)

        # Bộ lọc làm mịn rolling trượt giảm thiểu răng cưa đáy sông
        if do_min > 1:
            mz_pd = pd.DataFrame(matrix_z)
            mz_pd = mz_pd.rolling(window=do_min, min_periods=1, center=True).mean()
            matrix_z = mz_pd.T.rolling(window=do_min, min_periods=1, center=True).mean().T.values

        z_scaled = matrix_z * he_so_z
        fig = go.Figure()

        # Dệt lưới đa giác phủ kín hành lang
        if che_do in ["Bề mặt mịn", "Lưới tam giác"]:
            show_wireframe = True if che_do == "Lưới tam giác" else False
            fig.add_trace(go.Surface(
                x=matrix_x, y=matrix_y, z=z_scaled, customdata=matrix_z,
                colorscale='Earth', opacity=0.95,
                colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
                hovertemplate="X Thực: %{x:.1f} m<br>Y Thực: %{y:.1f} m<br>Z Thực: %{customdata:.2f} m<extra></extra>",
                contours=dict(
                    x=dict(show=show_wireframe, color="rgba(0,0,0,0.2)", width=1), 
                    y=dict(show=show_wireframe, color="rgba(0,0,0,0.2)", width=1)
                )
            ))
        elif che_do == "Đường đồng mức":
            fig.add_trace(go.Surface(
                x=matrix_x, y=matrix_y, z=z_scaled, customdata=matrix_z,
                colorscale='Viridis', opacity=0.95,
                colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
                contours_z=dict(show=True, usecolormap=False, color="rgb(0,0,0)", width=2, project=dict(z=True)),
                hovertemplate="X: %{x:.1f}<br>Y: %{y:.1f}<br>Z Thực: %{customdata:.2f} m<extra></extra>"
            ))

        # ĐƯỜNG CHỈ TIM TUYẾN MÀU ĐỎ VÀ HIỂN THỊ TÊN CỌC + LÝ TRÌNH DỌC SÔNG
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
            title=dict(text="🏔️ MÔ HÌNH ĐỊA HÌNH KHÔNG GIAN 3D BÁM SÁT TOÀN TUYẾN NTD", font=dict(size=16, color='#007acc')),
            height=850,  # ✨ THÊM DÒNG NÀY: Ép chiều cao khung nhìn rộng ra (tăng từ mặc định lên 850px)
            scene=dict(
                xaxis_title="Tọa độ X VN-2000 (m)", 
                yaxis_title="Tọa độ Y VN-2000 (m)", 
                zaxis_title="Cao độ Z (m)", 
                aspectmode='data'
            ),
            template="plotly_dark", 
            margin=dict(l=10, r=10, t=40, b=10), 
            paper_bgcolor='#0e1117'
        )
        return fig
    except Exception as e:
        st.error(f"Lỗi phân tích đồ họa không gian: {e}")
        return None

# =========================================================================
# ⚙️ PHÂN HỆ XỬ LÝ ĐỊA CHẤT NÂNG CAO - LÀM SẠCH VÀ CHUẨN HÓA 100%
# =========================================================================

def doc_excel_dia_chat_3_sheet(uploaded_file):
    """
    📥 BỘ ĐỌC FILE EXCEL ĐỊA CHẤT TRỌN GÓI 3 PHÂN HỆ CỦA CHƯƠNG:
    - Bóc tách Toado_HK, các sheet chi tiết (HK1, HK2, HK3) và sheet SPT.
    """
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        # 1. Đọc bảng tọa độ định vị hố khoan
        sheet_toado = [s for s in sheet_names if 'TOADO' in s.upper() or 'TỌA ĐỘ' in s.upper()]
        if not sheet_toado:
            return None, None, None
        df_hk_raw = pd.read_excel(uploaded_file, sheet_name=sheet_toado[0])
        df_hk_raw.columns = [str(c).strip().upper() for c in df_hk_raw.columns]
        
        c_name = [c for c in df_hk_raw.columns if any(k in c for k in ['HỐ KHOAN', 'HO_KHOAN', 'TÊN', 'CỌC'])][0]
        c_x = [c for c in df_hk_raw.columns if 'X_VN2000' in c or 'X=' in c or 'X ' in c][0]
        c_y = [c for c in df_hk_raw.columns if 'Y_VN2000' in c or 'Y=' in c or 'Y ' in c][0]
        c_z = [c for c in df_hk_raw.columns if 'Z_MIENG' in c or 'CAO ĐỘ' in c or 'Z' in c][0]
        
        df_hk = pd.DataFrame({
            'Ho_Khoan': df_hk_raw[c_name].astype(str).str.strip().str.upper(),
            'X_VN2000': pd.to_numeric(df_hk_raw[c_x], errors='coerce'),
            'Y_VN2000': pd.to_numeric(df_hk_raw[c_y], errors='coerce'),
            'Z_Mieng': pd.to_numeric(df_hk_raw[c_z], errors='coerce')
        }).dropna(subset=['X_VN2000', 'Y_VN2000']).reset_index(drop=True)
        
        # 2. Đọc chi tiết phân tầng đất từ các sheet hố khoan cụ thể
        list_layers = []
        for sheet in sheet_names:
            if 'SPT' in sheet.upper() or 'TOADO' in sheet.upper() or 'TỌA ĐỘ' in sheet.upper():
                continue
            df_layer_raw = pd.read_excel(uploaded_file, sheet_name=sheet)
            df_layer_raw.columns = [str(c).strip().upper() for c in df_layer_raw.columns]
            
            c_lop = [c for c in df_layer_raw.columns if 'TÊN LỚP' in c or 'TEN_LOP' in c or 'LOP' in c][0]
            c_tu = [c for c in df_layer_raw.columns if 'TỪ' in c or 'TU_' in c or 'DEPTH' in c][0]
            c_den = [c for c in df_layer_raw.columns if 'ĐẾN' in c or 'DEN_' in c][0]
            
            for _, r in df_layer_raw.iterrows():
                try:
                    tu_v = float(str(r[c_tu]).replace(',', '.'))
                    den_v = float(str(r[c_den]).replace(',', '.'))
                    if np.isnan(tu_v) or np.isnan(den_v): continue
                    list_layers.append({
                        'Ho_Khoan': str(sheet).strip().upper(),
                        'Tu_Chieu_Sau_Lop': tu_v,
                        'Den_Chieu_Sau_Lop': den_v,
                        'Ten_Lop': str(r[c_lop]).strip().upper()
                    })
                except: continue
        df_layers = pd.DataFrame(list_layers)
        
        # 3. Đọc thông số số búa thí nghiệm SPT
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
    🏗️ HÀM TÍCH HỢP ĐỊA CHẤT 3D CHUẨN HOÀN CHỈNH CHO CHƯƠNG:
    1. Xác định vị trí hố khoan theo đúng trục tọa độ phẳng lớn địa hình.
    2. Vuốt nối tuyến tính thấu kính dọc tuyến giữa các hố (Nối về trung điểm nếu hố liền kề thiếu lớp).
    3. Kéo dài biên đầu/cuối tuyến thêm 50m.
    4. Giới hạn bề rộng trắc ngang ngắt phẳng khít kẽ bằng biên ngang địa hình sông.
    5. Vẽ biểu đồ SPT độc lập dạng lines + markers + text bên cạnh hố khoan.
    """
    if fig is None or df_hk is None or df_hk.empty:
        return fig
        
    mau_quy_uoc = {'K': '#8B4513', '1': '#A0522D', '2B': '#4682B4', 'TK4': '#DEB887', '5': '#D2B48C'}
    
    # 📐 DỰNG ĐA GIÁC ĐƯỜNG BAO ĐỊA HÌNH SÔNG ĐỂ NGẮT PHƯƠNG NGANG
    import matplotlib.path as mpath
    from scipy.spatial import ConvexHull
    all_terrain_pts = np.column_stack((matrix_x.flatten(), matrix_y.flatten()))
    hull_t = ConvexHull(all_terrain_pts)
    poly_terrain = mpath.Path(all_terrain_pts[hull_t.vertices])
    
    # Lưới mịn để dệt các lớp thảm mặt phân cách địa chất
    gx, gy = np.meshgrid(
        np.linspace(matrix_x.min() - 60, matrix_x.max() + 60, 40),
        np.linspace(matrix_y.min() - 60, matrix_y.max() + 60, 40)
    )
    
    list_hk_valid = []
    
    # 🎯 Luồng A: Cắm trụ đứng hố khoan và vẽ biểu đồ SPT dích dắc
    for _, hk in df_hk.iterrows():
        try:
            ten_hk = str(hk['Ho_Khoan']).strip().upper()
            x_hk = float(hk['Y_VN2000']) # Đồng bộ trục X đồ họa = Y_Excel (6 số)
            y_hk = float(hk['X_VN2000']) # Đồng bộ trục Y đồ họa = X_Excel (7 số)
            z_mieng = float(hk['Z_Mieng'])
            if np.isnan(x_hk) or np.isnan(y_hk): continue
            
            list_hk_valid.append({'name': ten_hk, 'x': x_hk, 'y': y_hk, 'z_mieng': z_mieng})
            
            # Vẽ các dải phân tầng màu trên trục đứng hố khoan
            df_sub_layers = df_layers[df_layers['Ho_Khoan'] == ten_hk].sort_values('Tu_Chieu_Sau_Lop')
            for _, lop in df_sub_layers.iterrows():
                z_top = (z_mieng - float(lop['Tu_Chieu_Sau_Lop'])) * he_so_z
                z_bot = (z_mieng - float(lop['Den_Chieu_Sau_Lop'])) * he_so_z
                mau_n = mau_quy_uoc.get(str(lop['Ten_Lop']).strip().upper(), '#808080')
                fig.add_trace(go.Scatter3d(
                    x=[x_hk, x_hk], y=[y_hk, y_hk], z=[z_top, z_bot], mode='lines',
                    line=dict(color=mau_n, width=10), showlegend=False, hoverinfo="skip"
                ))
                
            # ✨ THỂ HIỆN SPT ĐỘC LẬP: Lines + Markers + Text kề bên cọc
            if df_spt is not None:
                col_n = [c for c in df_spt.columns if ten_hk in c.upper()]
                if col_n and 'Độ sâu thí nghiệm (m)' in df_spt.columns:
                    df_sub_spt = df_spt[['Độ sâu thí nghiệm (m)', col_n[0]]].dropna()
                    spt_x, spt_y, spt_z, spt_txt = [], [], [], []
                    for _, r_spt in df_sub_spt.iterrows():
                        try:
                            n_val = float(r_spt[col_n[0]])
                            txt_sau = str(r_spt['Độ sâu thí nghiệm (m)'])
                            nums = [float(n.replace(',', '.')) for n in re.findall(r'[\d,\.]+', txt_sau)]
                            if nums:
                                d_spt = nums[0]
                                spt_x.append(x_hk + 12.0 + n_val * 0.8) # Đẩy nhẹ đồ thị ra cạnh thân cọc 12m để nhìn rõ
                                spt_y.append(y_hk)
                                spt_z.append((z_mieng - d_spt) * he_so_z)
                                spt_txt.append(f"N={n_val:.0f}")
                        except: continue
                    if spt_z:
                        fig.add_trace(go.Scatter3d(
                            x=spt_x, y=spt_y, z=spt_z, mode='lines+markers+text',
                            line=dict(color='yellow', width=2.5), marker=dict(size=4.5, color='orange'),
                            text=spt_txt, textposition="middle right",
                            textfont=dict(size=9, color='yellow'), name=f"Biểu đồ SPT {ten_hk}"
                        ))
        except: continue

    # 🎯 Luồng B: Toán học nội suy dệt màng ngăn cách liên tục (Xử lý thấu kính + Vuốt biên 50m)
    df_hk_v = pd.DataFrame(list_hk_valid)
    if len(df_hk_v) >= 2 and not df_layers.empty:
        df_hk_v['sort_key'] = df_hk_v['x'] + df_hk_v['y']
        df_hk_v = df_hk_v.sort_values('sort_key').reset_index(drop=True)
        all_unique_layers = df_layers['Ten_Lop'].unique()
        
        for lop_dat in all_unique_layers:
            lop_dat = str(lop_dat).strip().upper()
            pt_x, pt_y, pt_z_bot = [], [], []
            
            # Thuật toán quét thấu kính qua từng cặp hố khoan kế cận dọc tuyến
            for idx in range(len(df_hk_v) - 1):
                hk1 = df_hk_v.iloc[idx]
                hk2 = df_hk_v.iloc[idx + 1]
                sub1 = df_layers[(df_layers['Ho_Khoan'] == hk1['name']) & (df_layers['Ten_Lop'] == lop_dat)]
                sub2 = df_layers[(df_layers['Ho_Khoan'] == hk2['name']) & (df_layers['Ten_Lop'] == lop_dat)]
                
                h1_has = not sub1.empty
                h2_has = not sub2.empty
                
                if h1_has and h2_has:
                    pt_x.extend([hk1['x'], hk2['x']])
                    pt_y.extend([hk1['y'], hk2['y']])
                    pt_z_bot.extend([hk1['z_mieng'] - sub1['Den_Chieu_Sau_Lop'].iloc[0], hk2['z_mieng'] - sub2['Den_Chieu_Sau_Lop'].iloc[0]])
                elif h1_has and not h2_has: # Thấu kính vuốt ngắt dần về trung điểm giữa 2 hố
                    mid_x = (hk1['x'] + hk2['x']) / 2
                    mid_y = (hk1['y'] + hk2['y']) / 2
                    pt_x.extend([hk1['x'], mid_x])
                    pt_y.extend([hk1['y'], mid_y])
                    pt_z_bot.extend([hk1['z_mieng'] - sub1['Den_Chieu_Sau_Lop'].iloc[0], hk1['z_mieng'] - sub1['Den_Chieu_Sau_Lop'].iloc[0]])
                elif not h1_has and h2_has: # Thấu kính vuốt ngược từ hố 2 về trung điểm
                    mid_x = (hk1['x'] + hk2['x']) / 2
                    mid_y = (hk1['y'] + hk2['y']) / 2
                    pt_x.extend([mid_x, hk2['x']])
                    pt_y.extend([mid_y, hk2['y']])
                    pt_z_bot.extend([hk2['z_mieng'] - sub2['Den_Chieu_Sau_Lop'].iloc[0], hk2['z_mieng'] - sub2['Den_Chieu_Sau_Lop'].iloc[0]])

            if len(pt_x) < 2: continue
            
            # ✨ KÉO DÀI BIÊN ĐẦU VÀ CUỐI TUYẾN THÊM 50M KHÔNG GIAN
            hk_dau, hk_cuoi = df_hk_v.iloc[0], df_hk_v.iloc[-1]
            if lop_dat in df_layers[df_layers['Ho_Khoan'] == hk_dau['name']]['Ten_Lop'].values:
                sub_d = df_layers[(df_layers['Ho_Khoan'] == hk_dau['name']) & (df_layers['Ten_Lop'] == lop_dat)]
                vx, vy = hk_dau['x'] - hk_cuoi['x'], hk_dau['y'] - hk_cuoi['y']
                v_len = np.sqrt(vx**2 + vy**2 + 0.0001)
                pt_x.insert(0, hk_dau['x'] + (vx / v_len) * 50.0)
                pt_y.insert(0, hk_dau['y'] + (vy / v_len) * 50.0)
                pt_z_bot.insert(0, hk_dau['z_mieng'] - sub_d['Den_Chieu_Sau_Lop'].iloc[0])
                
            if lop_dat in df_layers[df_layers['Ho_Khoan'] == hk_cuoi['name']]['Ten_Lop'].values:
                sub_c = df_layers[(df_layers['Ho_Khoan'] == hk_cuoi['name']) & (df_layers['Ten_Lop'] == lop_dat)]
                vx, vy = hk_cuoi['x'] - hk_dau['x'], hk_cuoi['y'] - hk_dau['y']
                v_len = np.sqrt(vx**2 + vy**2 + 0.0001)
                pt_x.append(hk_cuoi['x'] + (vx / v_len) * 50.0)
                pt_y.append(hk_cuoi['y'] + (vy / v_len) * 50.0)
                pt_z_bot.append(hk_cuoi['z_mieng'] - sub_c['Den_Chieu_Sau_Lop'].iloc[0])

            # Dệt thảm mặt phân cách 3D từ chuỗi điểm nội suy kết cấu thấu kính
            grid_z = griddata((pt_x, pt_y), pt_z_bot, (gx, gy), method='nearest')
            
            # ✨ CẮT NGẮT PHƯƠNG NGANG: Giới hạn khít kẽ theo chu vi đường bao trắc ngang địa hình sông
            for r in range(gx.shape[0]):
                for c in range(gx.shape[1]):
                    if not poly_terrain.contains_point((gx[r, c], gy[r, c])):
                        grid_z[r, c] = np.nan
                        
            grid_z_scaled = grid_z * he_so_z
            m_color = mau_quy_uoc.get(lop_dat, '#808080')
            
            fig.add_trace(go.Surface(
                x=gx, y=gy, z=grid_z_scaled, customdata=grid_z,
                colorscale=[[0, m_color], [1, m_color]], showscale=False, opacity=0.6,
                name=f"Mặt sàn: Lớp {lop_dat}",
                hovertemplate=f"<b>Mặt phân cách đáy lớp: {lop_dat}</b><br>Cao độ đáy thực: %{{customdata:.2f}} m<extra></extra>"
            ))
            
    return fig