import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    🏔️ BỘ GIẢI MÃ FILE .NTD CHUẨN TRẮC ĐẠC PHẲNG VN-2000:
    - Ép trục X_Real và Y_Real nhận giá trị tịnh tiến lượng giác từ Tọa độ Mốc VN-2000 thực.
    - Đồng nhất quy mô không gian với hố khoan địa chất Excel.
    """
    data_points = []
    raw_content = uploaded_file.read()
    try:
        lines = raw_content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        lines = raw_content.decode("latin1").splitlines()
        
    current_x = 0.0
    current_pole = ""
    current_x_vn2000 = 0.0
    current_y_vn2000 = 0.0
    current_goc_tuyen = 0.0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
            
        token = parts[0].upper()
        
        # 1. Đọc cọc POLE lấy mốc tọa độ tim thực địa VN-2000 gốc
        if token == 'POLE' and len(parts) >= 4:
            try:
                current_pole = parts[1].strip().upper()
                current_x = float(parts[2])  # Lý trình
                z_tim = float(parts[3])      # Cao độ tim
                
                # Phương án dự phòng: Nếu dòng POLE có sẵn tọa độ thực địa lớn ở cột sau
                current_x_vn2000 = float(parts[4]) if len(parts) >= 6 else 0.0
                current_y_vn2000 = float(parts[5]) if len(parts) >= 6 else 0.0
                
                data_points.append({
                    'Cọc': current_pole, 'Lý trình': current_x, 'Offset': 0.0, 'Z': z_tim,
                    'X_VN2000': current_x_vn2000, 'Y_VN2000': current_y_vn2000, 'Góc_Tuyến': 0.0,
                    'X_Real': current_x_vn2000, 'Y_Real': current_y_vn2000, 'Tag_Gốc': 'POLE'
                })
            except:
                continue
                
        # 2. Đọc các điểm mia trắc ngang bên Trái / Bên Phải
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                offset = float(parts[1])
                z_val = float(parts[2])
                
                data_points.append({
                    'Cọc': current_pole, 'Lý trình': current_x, 'Offset': offset, 'Z': z_val,
                    'X_VN2000': current_x_vn2000, 'Y_VN2000': current_y_vn2000, 'Góc_Tuyến': 0.0,
                    'X_Real': 0.0, 'Y_Real': 0.0, 'Tag_Gốc': 'TARGET'
                })
            except:
                continue
                
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
    🎯 THUẬT TOÁN ĐỒNG BỘ ĐỊA HÌNH HỆ VN-2000 CHUẨN ĐỒ HỌA TOÁN HỌC:
    - Trục X_Real nhận giá trị dải 6 số (Y_VN2000 trong Excel mốc)
    - Trục Y_Real nhận giá trị dải 7 số (X_VN2000 trong Excel mốc)
    """
    try:
        if df_ntd is None or df_ntd.empty or df_coord is None or df_coord.empty:
            return pd.DataFrame()
            
        df_ntd_clean = df_ntd.copy()
        df_coord_clean = df_coord.copy()
        
        # Chuẩn hóa chuỗi tên cọc để khớp nối chính xác
        df_ntd_clean['Cọc'] = df_ntd_clean['Cọc'].astype(str).str.strip().str.upper()
        df_coord_clean['Cọc_Excel'] = df_coord_clean['Cọc_Excel'].astype(str).str.strip().str.upper()
        
        # Đổi trục đồ họa toán học 3D ngay từ khâu ánh xạ mốc:
        # X_Toán = Y_Excel (6 số), Y_Toán = X_Excel (7 số)
        map_x = dict(zip(df_coord_clean['Cọc_Excel'], df_coord_clean['Y_VN2000']))
        map_y = dict(zip(df_coord_clean['Cọc_Excel'], df_coord_clean['X_VN2000']))
        
        df_merged = df_ntd_clean.copy()
        df_merged['X_VN2000'] = df_merged['Cọc'].map(map_x)
        df_merged['Y_VN2000'] = df_merged['Cọc'].map(map_y)
        
        # Dự phòng: Nếu không khớp được tên cọc, nội suy tuần tự theo thứ tự Lý trình
        if df_merged['X_VN2000'].isna().all():
            list_ntd_x = sorted(df_merged['Lý trình'].unique())
            min_len = min(len(list_ntd_x), len(df_coord_clean))
            map_x_lt, map_y_lt = {}, {}
            for i in range(min_len):
                ly_trinh_ntd = list_ntd_x[i]
                map_x_lt[ly_trinh_ntd] = df_coord_clean['Y_VN2000'].iloc[i] # Ép 6 số về X_Toán
                map_y_lt[ly_trinh_ntd] = df_coord_clean['X_VN2000'].iloc[i] # Ép 7 số về Y_Toán
            df_merged['X_VN2000'] = df_merged['Lý trình'].map(map_x_lt)
            df_merged['Y_VN2000'] = df_merged['Lý trình'].map(map_y_lt)

        # Loại bỏ các hàng bị thiếu tọa độ mốc
        df_merged = df_merged.dropna(subset=['X_VN2000', 'Y_VN2000']).copy()
        if df_merged.empty:
            return pd.DataFrame()
            
        # Tính toán hướng đi của tuyến để tịnh tiến lượng giác các điểm cánh trắc ngang
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
        
        # Dịch chuyển pháp tuyến trắc ngang theo đúng tọa độ mặt bằng thực tế
        angle_offset = df_merged['Góc_Tuyến'] + (np.pi / 2)
        df_merged['X_Real'] = df_merged['X_VN2000'] + df_merged['Offset'] * np.cos(angle_offset)
        df_merged['Y_Real'] = df_merged['Y_VN2000'] + df_merged['Offset'] * np.sin(angle_offset)
        
        return df_merged
    except Exception as e:
        st.error(f"Lỗi xử lý đồng bộ chuỗi điểm tim thực địa: {e}")
        return pd.DataFrame()

def ve_dia_hinh_3d(df, he_so_z=1.0, che_do="Bề mặt mịn", do_min=3):
    """
    🏔️ MÔ HÌNH ĐỊA HÌNH 3D HỆ VN-2000 THỰC ĐỊA TUYỆT ĐỐI:
    - Trục X nhận X_Real (Tọa độ phẳng VN-2000)
    - Trục Y nhận Y_Real (Tọa độ phẳng VN-2000)
    - Đồng nhất 100% không gian với vị trí cắm cọc địa chất Excel.
    """
    if df.empty: 
        return None
    
    try:
        # Sắp xếp thứ tự trắc ngang bám dọc theo tuyến
        df_clean = df.sort_values(['Lý trình', 'Offset']).copy()
        unique_lts = sorted(df_clean['Lý trình'].unique())
        
        num_samples = 40  
        target_pct = np.linspace(0.0, 1.0, num_samples)
        
        matrix_x, matrix_y, matrix_z = [], [], []
        
        for lt in unique_lts:
            df_sub = df_clean[df_clean['Lý trình'] == lt].sort_values('Offset')
            
            obs_offsets = df_sub['Offset'].values
            obs_x_real = df_sub['X_Real'].values  # Tọa độ X thực từ convert_to_vn2000
            obs_y_real = df_sub['Y_Real'].values  # Tọa độ Y thực từ convert_to_vn2000
            obs_zs = df_sub['Z'].values
            
            if len(obs_offsets) < 2:
                continue
                
            pct_goc = (obs_offsets - obs_offsets[0]) / (obs_offsets[-1] - obs_offsets[0] + 0.0001)
            
            # ✨ ĐỒNG NHẤT KHÔNG GIAN: Nội suy ma trận 3D theo đúng trục tọa độ thực lớn VN-2000
            x_line = np.interp(target_pct, pct_goc, obs_x_real)
            y_line = np.interp(target_pct, pct_goc, obs_y_real)
            z_line = np.interp(target_pct, pct_goc, obs_zs)
                
            matrix_x.append(x_line)
            matrix_y.append(y_line)
            matrix_z.append(z_line)
            
        matrix_x = np.array(matrix_x)
        matrix_y = np.array(matrix_y)
        matrix_z = np.array(matrix_z)

        # Bộ lọc Rolling Smooth làm mịn khử gồ ghề lòng sông
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
                hovertemplate="X VN2000: %{x:.2f} m<br>Y VN2000: %{y:.2f} m<br>Z Cao độ: %{customdata:.2f} m<extra></extra>",
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
                hovertemplate="X VN2000: %{x:.2f}<br>Y VN2000: %{y:.2f}<br>Z Cao độ: %{customdata:.2f} m<extra></extra>"
            ))

        # Vẽ đường tim cọc màu đỏ bám theo tọa độ VN-2000 thực địa
        df_tim_all = df_clean[df_clean['Offset'] == 0].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình')
        if not df_tim_all.empty:
            nhan_hien_thi = df_tim_all.apply(lambda r: f"{r['Cọc']} (LT: {r['Lý trình']:.1f}m)", axis=1).values
            fig.add_trace(go.Scatter3d(
                x=df_tim_all['X_Real'].values, y=df_tim_all['Y_Real'].values, z=df_tim_all['Z'].values * he_so_z,
                mode='lines+markers+text',
                line=dict(color='red', width=4), marker=dict(size=4, color='yellow'),
                text=nhan_hien_thi, textposition="top center",
                textfont=dict(family="Arial, sans-serif", size=11, color="lightblue"),
                name='Tim tuyến dọc sông thực địa'
            ))

        # ✨ ĐIỀU CHỈNH CAMERA PLOTLY: Ép khung nhìn tập trung vào đúng dải số lớn của VN-2000
        fig.update_layout(
            title=dict(text="🏔️ SA BÀN KHÔNG GIAN BIM 3D - HỆ TOẠ ĐỘ PHẲNG THỰC ĐỊA VN-2000", font=dict(size=16, color='#007acc')),
            height=850,
            scene=dict(
                xaxis=dict(title="Tọa độ X VN-2000 (m)", tickformat=".0f"), 
                yaxis=dict(title="Tọa độ Y VN-2000 (m)", tickformat=".0f"), 
                zaxis=dict(title="Cao độ Z (m)"), 
                aspectmode='data' # Giữ nguyên tỉ lệ hình học thực tế, không méo bảng vẽ
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
    🏗️ THUẬT TOÁN ĐỊA CHẤT KHỚP RẠT HỆ ĐỊA HÌNH VN-2000:
    - Bốc chính xác tọa độ Excel địa chất: Đưa Y_VN2000 (6 số) vào X_Toán, X_VN2000 (7 số) vào Y_Toán.
    - Gióng thẳng đứng và dệt mặt lớp phẳng bám khít biên dạng lòng sông phương X, Y.
    """
    if fig is None or df_hk is None or df_hk.empty:
        return fig
        
    mau_quy_uoc = {'K': '#8B4513', '1': '#A0522D', '2B': '#4682B4', 'TK4': '#DEB887', '5': '#D2B48C'}
    
    # 📐 1. TRÍCH XUẤT MA TRẬN ĐƯỜNG BAO LÒNG SÔNG ĐỂ LÀM KHUNG GIỚI HẠN
    points_terrain = []
    for data in fig.data:
        if data.type == 'surface' and data.x is not None and data.y is not None:
            xs_flat = np.array(data.x).flatten()
            ys_flat = np.array(data.y).flatten()
            for x, y in zip(xs_flat, ys_flat):
                if not np.isnan(x) and not np.isnan(y):
                    points_terrain.append([x, y])
                    
    if len(points_terrain) < 3:
        return fig

    from scipy.spatial import ConvexHull
    from scipy.interpolate import griddata
    import matplotlib.path as mpath
    
    points_arr = np.array(points_terrain)
    hull = ConvexHull(points_arr)
    boundary_polygon = points_arr[hull.vertices]
    terrain_path = mpath.Path(boundary_polygon)

    # Khởi tạo ma trận lưới không gian phục vụ nội suy các tầng địa chất
    grid_x, grid_y = np.meshgrid(
        np.linspace(points_arr[:, 0].min(), points_arr[:, 0].max(), 35),
        np.linspace(points_arr[:, 1].min(), points_arr[:, 1].max(), 35)
    )

    layer_profiles = {}

    # 🗺️ 2. ĐỌC FILE EXCEL ĐỊA CHẤT VÀ CẮM ĐỊNH VỊ TRỤC ĐỨNG HỐ KHOAN
    for _, hk in df_hk.iterrows():
        try:
            ten_hk = str(hk['Ho_Khoan']).strip()
            
            # 🔥 ĐỒNG NHẤT KHÓA TỌA ĐỘ PHẲNG:
            # Bốc đúng cột Excel địa chất và gán theo quy ước đồ họa toán học giống địa hình
            x_hk = float(hk['Y_VN2000'])  # Cột Y_Excel (6 số) -> Đưa vào trục X đồ họa
            y_hk = float(hk['X_VN2000'])  # Cột X_Excel (7 số) -> Đưa vào trục Y đồ họa
            z_mieng = float(hk['Z_Mieng'])
            
            if np.isnan(x_hk) or np.isnan(y_hk) or np.isnan(z_mieng):
                continue
                
            # Lọc không gian phương X, Y: Chỉ xử lý hố khoan nằm lọt trong dải sông
            if not terrain_path.contains_point((x_hk, y_hk)):
                continue 
                
            max_depth_hk = 0.0
            if df_layers is not None and not df_layers.empty:
                df_sub_layers = df_layers[df_layers['Ho_Khoan'] == ten_hk].sort_values('Tu_Chieu_Sau_Lop')
                
                for _, lop in df_sub_layers.iterrows():
                    try:
                        tu_d = float(lop['Tu_Chieu_Sau_Lop'])
                        den_d = float(lop['Den_Chieu_Sau_Lop'])
                        ten_lop = str(lop['Ten_Lop']).strip().upper()
                        
                        if den_d > max_depth_hk:
                            max_depth_hk = den_d
                            
                        z_top = (z_mieng - tu_d) * he_so_z
                        z_bot = (z_mieng - den_d) * he_so_z
                        
                        # Thu thập dữ liệu phục vụ nội suy thảm đáy
                        if ten_lop not in layer_profiles:
                            layer_profiles[ten_lop] = {'x': [], 'y': [], 'z_bot': []}
                        layer_profiles[ten_lop]['x'].append(x_hk)
                        layer_profiles[ten_lop]['y'].append(y_hk)
                        layer_profiles[ten_lop]['z_bot'].append(z_mieng - den_d)
                        
                        # Vẽ cột trụ đứng đại diện vị trí hố khoan công trình
                        mau_nen = mau_quy_uoc.get(ten_lop, '#808080')
                        fig.add_trace(go.Scatter3d(
                            x=[x_hk, x_hk], y=[y_hk, y_hk], z=[z_top, z_bot],
                            mode='lines',
                            line=dict(color=mau_nen, width=12),
                            name=f"Trục {ten_hk}: Lớp {ten_lop}",
                            hoverinfo="skip"
                        ))
                    except:
                        continue
            
            # Vẽ biểu đồ thí nghiệm SPT màu vàng bám dọc trục hố
            if df_spt is not None and not df_spt.empty:
                col_n = [c for c in df_spt.columns if ten_hk in c]
                if col_n and 'Độ sâu thí nghiệm (m)' in df_spt.columns:
                    spt_col_name = col_n[0]
                    df_sub_spt = df_spt[['Độ sâu thí nghiệm (m)', spt_col_name]].dropna()
                    
                    spt_x, spt_y, spt_z = [], [], []
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
                                
                                spt_x.append(x_hk + 8.0 + n_val * 0.8)
                                spt_y.append(y_hk)
                                spt_z.append(z_spt)
                        except:
                            continue
                            
                    if spt_z:
                        spt_indices = np.argsort(spt_z)[::-1]
                        fig.add_trace(go.Scatter3d(
                            x=np.array(spt_x)[spt_indices], y=np.array(spt_y)[spt_indices], z=np.array(spt_z)[spt_indices],
                            mode='lines+markers',
                            line=dict(color='yellow', width=2.5), marker=dict(size=3.5, color='orange'),
                            name=f"SPT {ten_hk}",
                            hoverinfo="skip"
                        ))
                        
                        fig.add_trace(go.Scatter3d(
                            x=[x_hk, x_hk], y=[y_hk, y_hk], z=[z_mieng * he_so_z, (z_mieng - max_depth_hk) * he_so_z],
                            mode='lines', line=dict(color='white', width=1, dash='dash'), showlegend=False
                        ))
        except:
            continue
            
    # 🌊 3. NỐI ĐÁY ĐỊA CHẤT THÀNH BỀ MẶT 3D LIÊN TỤC GIỚI HẠN TRONG ĐƯỜNG BAO SÔNG
    for ten_lop, data in layer_profiles.items():
        try:
            if len(set(zip(data['x'], data['y']))) < 3:
                continue
                
            grid_z = griddata(
                (data['x'], data['y']), data['z_bot'],
                (grid_x, grid_y), method='linear'
            )
            
            # Cắt gọt rìa đa giác theo phương phẳng X, Y
            for r in range(grid_x.shape[0]):
                for c in range(grid_x.shape[1]):
                    if not terrain_path.contains_point((grid_x[r, c], grid_y[r, c])):
                        grid_z[r, c] = np.nan
                        
            grid_z_scaled = grid_z * he_so_z
            mau_lop = mau_quy_uoc.get(ten_lop, '#808080')
            
            fig.add_trace(go.Surface(
                x=grid_x, y=grid_y, z=grid_z_scaled, customdata=grid_z,
                colorscale=[[0, mau_lop], [1, mau_lop]],
                showscale=False, opacity=0.6,
                name=f"Mặt đáy: Lớp {ten_lop}",
                hovertemplate=f"<b>Mặt đáy: Lớp {ten_lop}</b><br>X VN2000: %{{x:.1f}} m<br>Y VN2000: %{{y:.1f}} m<br>Cao độ đáy thực: %{{customdata:.2f}} m<extra></extra>"
            ))
        except:
            continue
            
    return fig
