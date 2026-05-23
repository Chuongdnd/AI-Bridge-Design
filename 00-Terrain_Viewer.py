import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

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
    🏔️ MÔ HÌNH ĐỊA HÌNH 3D NGUYÊN BẢN - CHỈ VẼ ĐỊA HÌNH SÔNG CỦA CHƯƠNG
    """
    if df.empty: 
        return None
    
    try:
        df_clean = df.sort_values(['Lý trình', 'Offset']).copy()
        unique_lts = sorted(df_clean['Lý trình'].unique())
        
        num_samples = 40  
        target_pct = np.linspace(0.0, 1.0, num_samples)
        
        matrix_x, matrix_y, matrix_z = [], [], []
        
        for lt in unique_lts:
            df_sub = df_clean[df_clean['Lý trình'] == lt].sort_values('Offset')
            has_target = df_sub['Tag_Gốc'].str.contains('TARGET', na=False).any()
            
            obs_offsets = df_sub['Offset'].values
            obs_x_real = df_sub['X_Real'].values
            obs_y_real = df_sub['Y_Real'].values
            obs_zs = df_sub['Z'].values
            
            if not has_target or len(obs_offsets) < 2:
                goc_tuyen = df_sub['Góc_Tuyến'].iloc[0]
                g_offset = goc_tuyen + (np.pi / 2)
                offsets_fake = np.linspace(-25.0, 25.0, num_samples)
                x_line = df_sub['X_VN2000'].iloc[0] + offsets_fake * np.cos(g_offset)
                y_line = df_sub['Y_VN2000'].iloc[0] + offsets_fake * np.sin(g_offset)
                z_line = np.repeat(obs_zs[0], num_samples)
            else:
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
            height=850,
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
        st.error(f"Lỗi phân tích đồ họa không gian địa hình: {e}")
        return None
 
def doc_excel_dia_chat_nguyen_ban(uploaded_file):
    """
    📥 BỘ ĐỌC KHỚP 100% CẤU TRÚC FILE EXCEL CỦA CHƯƠNG:
    - Quét các sheet để lấy X, Y, Z_Mieng và danh sách phân tầng.
    - Đọc riêng sheet 'SPT' để lấy giá trị đóng búa.
    """
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        if 'SPT' not in sheet_names:
            return None, None, None
            
        list_df_hk = []
        list_df_layer = []
        
        # 1. Đọc địa tầng từ các sheet hố khoan (Ví dụ: HK1, HK2, HK3...)
        for sheet in sheet_names:
            if sheet.upper() == 'SPT':
                continue
                
            # Đọc thô để dò tìm metadata tọa độ
            df_raw = pd.read_excel(uploaded_file, sheet_name=sheet, header=None)
            
            ten_hk = sheet.strip()
            x_hk, y_hk, z_mieng = 0.0, 0.0, 0.0
            
            # Quét tìm vị trí hàng tọa độ và cao độ miệng hố
            for idx, row in df_raw.iterrows():
                row_vals = [str(v).strip() for v in row.values if pd.notna(v)]
                for v in row_vals:
                    if 'HO_KHOAN' in v.upper():
                        ten_hk = row_vals[row_vals.index(v)+1] if row_vals.index(v)+1 < len(row_vals) else ten_hk
                    if 'X_VN2000' in v.upper():
                        try: x_hk = float(row_vals[row_vals.index(v)+1])
                        except: pass
                    if 'Y_VN2000' in v.upper():
                        try: y_hk = float(row_vals[row_vals.index(v)+1])
                        except: pass
                    if 'Z_MIENG' in v.upper():
                        try: z_mieng = float(row_vals[row_vals.index(v)+1])
                        except: pass
            
            list_df_hk.append({
                'Ho_Khoan': ten_hk, 'X_VN2000': x_hk, 'Y_VN2000': y_hk, 'Z_Mieng': z_mieng
            })
            
            # ✨ SỬA LỖI DÒ HEADER CHÍNH XÁC:
            header_row_idx = 0
            for idx, row in df_raw.iterrows():
                row_vals_upper = [str(v).upper().strip() for v in row.values if pd.notna(v)]
                # Quét trúng dòng chứa các từ khóa tiêu đề của Chương
                if 'TEN_LOP' in row_vals_upper or 'TU_CHIEU_SAU' in row_vals_upper:
                    header_row_idx = idx
                    break
            
            # Đọc chuẩn xác dòng header_row_idx làm tiêu đề cột (Không dùng + 1 làm mất dòng tiêu đề nữa)
            df_table = pd.read_excel(uploaded_file, sheet_name=sheet, skiprows=header_row_idx)
            
            # ✨ BƯỚC KHÓA LỖI: Ép toàn bộ tiêu đề cột về chữ thường và xóa khoảng trắng dư thừa
            df_table.columns = [str(c).strip().lower() for c in df_table.columns]
            
            # Lọc bỏ dòng trống dựa trên các cột (bằng chữ thường)
            df_table = df_table.dropna(subset=['ten_lop', 'tu_chieu_sau', 'den_chieu_sau'])
            
            for _, row in df_table.iterrows():
                try:
                    tu_depth = float(str(row['tu_chieu_sau']).replace(',', '.'))
                    den_depth = float(str(row['den_chieu_sau']).replace(',', '.'))
                    ten_lop = str(row['ten_lop']).strip()
                    mo_ta = str(row.get('mo_ta', '')) # Nếu không có cột mô tả thì bỏ qua
                except Exception as e:
                    continue
                    
                list_df_layer.append({
                    'Ho_Khoan': ten_hk,
                    'Tu_Chieu_Sau_Lop': tu_depth,
                    'Den_Chieu_Sau_Lop': den_depth,
                    'Ten_Lop': ten_lop,
                    'Mo_Ta': mo_ta
                })  
        # 2. Đọc sheet SPT
        df_spt_raw = pd.read_excel(uploaded_file, sheet_name='SPT')
        df_spt_raw.columns = [str(c).strip() for c in df_spt_raw.columns]
        
        return pd.DataFrame(list_df_hk), pd.DataFrame(list_df_layer), df_spt_raw
    except Exception as e:
        st.error(f"Lỗi phân tích tệp Excel địa chất: {e}")
        return None, None, None

def ve_them_ho_khoan_3d(fig, df_hk, df_layers, df_spt, he_so_z=1.0):
    """
    ⚡ HÀM KHÓA LỖI TỐI HẬU: Đắp thêm hố khoan 3D vào biểu đồ địa hình có sẵn.
    Có lỗi dữ liệu Excel ở hố nào, chỉ bỏ qua hố đó, KHÔNG LÀM SẬP TOÀN BỘ APP.
    """
    if fig is None or df_hk is None or df_hk.empty:
        return fig
        
    mau_quy_uoc = {'K': '#8B4513', '1': '#A0522D', '2B': '#4682B4', 'TK4': '#DEB887', '5': '#D2B48C'}
    
    for _, hk in df_hk.iterrows():
        try:
            ten_hk = str(hk['Ho_Khoan']).strip()
            x_hk = float(hk['X_VN2000'])
            y_hk = float(hk['Y_VN2000'])
            z_mieng = float(hk['Z_Mieng'])
            
            # Kiểm tra xem tọa độ hố khoan có bị rỗng toán học NaN không
            if np.isnan(x_hk) or np.isnan(y_hk) or np.isnan(z_mieng):
                continue
                
            # 1. Vẽ khối trụ địa tầng của riêng hố này
            if df_layers is not None and not df_layers.empty:
                df_sub_layers = df_layers[df_layers['Ho_Khoan'] == ten_hk].sort_values('Tu_Chieu_Sau_Lop')
                
                for _, lop in df_sub_layers.iterrows():
                    try:
                        tu_d = float(lop['Tu_Chieu_Sau_Lop'])
                        den_d = float(lop['Den_Chieu_Sau_Lop'])
                        ten_lop = str(lop['Ten_Lop']).strip().upper()
                        
                        txt_mo_ta = str(lop.get('Mo_Ta', ''))
                        if txt_mo_ta.lower() == 'nan' or pd.isna(lop.get('Mo_Ta')):
                            txt_mo_ta = "Không có mô tả chi tiết"
                            
                        mau_nen = mau_quy_uoc.get(ten_lop, '#808080')
                        z_top = (z_mieng - tu_d) * he_so_z
                        z_bot = (z_mieng - den_d) * he_so_z
                        
                        r_cylinder = 4.0
                        theta = np.linspace(0, 2 * np.pi, 20)
                        xs = x_hk + r_cylinder * np.cos(theta)
                        ys = y_hk + r_cylinder * np.sin(theta)
                        
                        fig.add_trace(go.Surface(
                            x=np.array([xs, xs]), y=np.array([ys, ys]), z=np.array([[z_top] * 20, [z_bot] * 20]),
                            colorscale=[[0, mau_nen], [1, mau_nen]], showscale=False, opacity=0.9,
                            name=f"{ten_hk}: Lớp {ten_lop}",
                            hovertemplate=f"<b>Hố khoan: {ten_hk}</b><br>Tên lớp: {ten_lop}<br>Độ sâu: {tu_d:.2f}m - {den_d:.2f}m<br>Mô tả: {txt_mo_ta}<extra></extra>"
                        ))
                    except:
                        continue
            
            # 2. Vẽ đường dích dắc biểu đồ số búa SPT màu vàng
            if df_spt is not None and not df_spt.empty:
                col_n = [c for c in df_spt.columns if ten_hk in c]
                if col_n and 'Độ sâu thí nghiệm (m)' in df_spt.columns:
                    spt_col_name = col_n[0]
                    df_sub_spt = df_spt[['Độ sâu thí nghiệm (m)', spt_col_name]].dropna()
                    
                    spt_x, spt_y, spt_z, spt_n = [], [], [], []
                    for _, r_spt in df_sub_spt.iterrows():
                        try:
                            text_sau = str(r_spt['Độ sâu thí nghiệm (m)'])
                            n_val = float(r_spt[spt_col_name])
                            
                            if np.isnan(n_val):
                                continue
                                
                            import re
                            numbers = [float(num.replace(',', '.')) for num in re.findall(r'[\d,\.]+', text_sau)]
                            if numbers:
                                depth_spt = numbers[0]
                                z_spt = (z_mieng - depth_spt) * he_so_z
                                
                                spt_x.append(x_hk + 6.0 + n_val * 0.3)
                                spt_y.append(y_hk)
                                spt_z.append(z_spt)
                                spt_n.append(n_val)
                        except:
                            continue
                            
                    if spt_z:
                        spt_indices = np.argsort(spt_z)[::-1]
                        fig.add_trace(go.Scatter3d(
                            x=np.array(spt_x)[spt_indices], y=np.array(spt_y)[spt_indices], z=np.array(spt_z)[spt_indices],
                            mode='lines+markers+text',
                            line=dict(color='yellow', width=3.5), marker=dict(size=5, color='orange'),
                            text=[f"N={n:.0f}" for n in np.array(spt_n)[spt_indices]], textposition="middle right",
                            textfont=dict(size=10, color='yellow'),
                            name=f"Đồ thị SPT {ten_hk}",
                            hovertemplate="Độ sâu SPT tính từ miệng: %{z:.2f}m<extra></extra>"
                        ))
                        
                        max_depth = df_sub_layers['Den_Chieu_Sau_Lop'].max() if not df_sub_layers.empty else 50.0
                        fig.add_trace(go.Scatter3d(
                            x=[x_hk, x_hk], y=[y_hk, y_hk], z=[z_mieng * he_so_z, (z_mieng - max_depth) * he_so_z],
                            mode='lines', line=dict(color='white', width=1.5, dash='dash'), showlegend=False
                        ))
        except Exception as e:
            # Khóa lỗi cục bộ của một hố khoan để bảo vệ biểu đồ chính
            continue
            
    return fig