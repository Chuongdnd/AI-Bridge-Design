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
    THUẬT TOÁN ĐỒNG BỘ SONG SONG VÀ XOAY LƯỢNG GIÁC THEO TIM TUYẾN THỰC ĐỊA
    - Sửa lỗi NameError: df_coord
    - Tự động fallback nếu file tọa độ thiếu cột 'Lý trình'
    """
    try:
        if df_coord is None or df_coord.empty or df_ntd.empty:
            return pd.DataFrame()
            
        df_coord_clean = df_coord.copy()
        list_ntd_x = sorted(df_ntd['Lý trình'].unique())
        
        # Tạo bản copy để xử lý dữ liệu trộn
        df_merged = df_ntd.copy()
        
        # Kiểm tra xem file tọa độ đầu vào có cột 'Lý trình' để nội suy hay không
        if 'Lý trình' in df_coord_clean.columns:
            from scipy.interpolate import interp1d
            
            # Loại bỏ dòng trùng lý trình trong file mốc tọa độ để tránh lỗi hàm nội suy
            df_coord_nodup = df_coord_clean.drop_duplicates(subset=['Lý trình']).sort_values('Lý trình')
            
            if len(df_coord_nodup) >= 2:
                interp_x = interp1d(df_coord_nodup['Lý trình'], df_coord_nodup['X_VN2000'], kind='linear', fill_value="extrapolate")
                interp_y = interp1d(df_coord_nodup['Lý trình'], df_coord_nodup['Y_VN2000'], kind='linear', fill_value="extrapolate")
                
                df_merged['X_VN2000'] = interp_x(df_merged['Lý trình'])
                df_merged['Y_VN2000'] = interp_y(df_merged['Lý trình'])
            else:
                # Nếu chỉ có 1 điểm mốc, gán mốc cố định cho toàn tuyến
                df_merged['X_VN2000'] = df_coord_nodup['X_VN2000'].iloc[0]
                df_merged['Y_VN2000'] = df_coord_nodup['Y_VN2000'].iloc[0]
        else:
            # 🔄 FALLBACK BAN ĐẦU CỦA CHƯƠNG (Nếu file tọa độ chỉ có chuỗi điểm xếp tuần tự):
            min_len = min(len(list_ntd_x), len(df_coord_clean))
            if min_len == 0:
                return pd.DataFrame()
                
            map_x_real = {}
            map_y_real = {}
            for i in range(min_len):
                ly_trinh_ntd = list_ntd_x[i]
                map_x_real[ly_trinh_ntd] = df_coord_clean['X_VN2000'].iloc[i]
                map_y_real[ly_trinh_ntd] = df_coord_clean['Y_VN2000'].iloc[i]
                
            df_merged['X_VN2000'] = df_merged['Lý trình'].map(map_x_real)
            df_merged['Y_VN2000'] = df_merged['Lý trình'].map(map_y_real)

        # Loại bỏ các dòng trống không nội suy được tọa độ mốc tim
        df_merged = df_merged.dropna(subset=['X_VN2000', 'Y_VN2000']).copy()
        
        # Trích xuất riêng tim tuyến (Offset == 0) để tính vector chỉ phương
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
        
        # Tính toán tọa độ pháp tuyến trắc ngang thực địa phẳng
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
    🎯 PHIÊN BẢN GIỚI HẠN THEO PHƯƠNG X, Y (BOUNDING BOX / CONVEX HULL CLIPPING):
    - Tự động dựng đường bao biên (Polygon) bao quanh toàn bộ tọa độ X_Real, Y_Real của địa hình sông.
    - Gióng thẳng đứng xuống: Chỉ vẽ những hố khoan nào nằm TRONG phạm vi mặt bằng của lòng sông.
    - Loại bỏ hoàn toàn các hố khoan nằm ngoài rìa biên địa hình.
    """
    if fig is None or df_hk is None or df_hk.empty:
        return fig
        
    mau_quy_uoc = {'K': '#8B4513', '1': '#A0522D', '2B': '#4682B4', 'TK4': '#DEB887', '5': '#D2B48C'}
    
    # 📐 THUẬT TOÁN DỰNG ĐƯỜNG BAO ĐỊA HÌNH (X, Y BOUNDARY)
    points_terrain = []
    
    # Quét qua các trace bề mặt (Surface) và đường tim để bốc toàn bộ các cặp tọa độ X, Y của địa hình
    for data in fig.data:
        if data.type == 'surface' and data.x is not None and data.y is not None:
            xs_flat = np.array(data.x).flatten()
            ys_flat = np.array(data.y).flatten()
            for x, y in zip(xs_flat, ys_flat):
                if not np.isnan(x) and not np.isnan(y):
                    points_terrain.append([x, y])
                    
    if len(points_terrain) < 3:
        # Nếu không bốc được lưới bề mặt, lấy dự phòng từ danh sách dữ liệu đầu vào (nếu có)
        return fig

    # Sử dụng Matplotlib Path để tạo vùng đa giác bao che từ đường bao lòng sông
    from scipy.spatial import ConvexHull
    import matplotlib.path as mpath
    
    points_arr = np.array(points_terrain)
    hull = ConvexHull(points_arr)
    # Lấy các điểm đỉnh sắp xếp tuần tự tạo thành đa giác khép kín
    boundary_polygon = points_arr[hull.vertices]
    terrain_path = mpath.Path(boundary_polygon)

    # Tiến hành lặp qua từng hố khoan để lọc không gian
    for _, hk in df_hk.iterrows():
        try:
            ten_hk = str(hk['Ho_Khoan']).strip()
            x_hk = float(hk['Y_VN2000'])  # Đã đổi trục chuẩn quy ước đồ họa 3D toán học
            y_hk = float(hk['X_VN2000'])  # Đã đổi trục chuẩn quy ước đồ họa 3D toán học
            z_mieng = float(hk['Z_Mieng'])
            
            if np.isnan(x_hk) or np.isnan(y_hk) or np.isnan(z_mieng):
                continue
                
            # ✨ KIỂM TRA ĐIỀU KIỆN BIÊN PHƯƠNG X, Y:
            # Gióng hố khoan xuống mặt bằng, nếu (x_hk, y_hk) nằm ngoài đường bao lòng sông -> LOẠI BỎ
            if not terrain_path.contains_point((x_hk, y_hk)):
                continue # Bỏ qua hố khoan này, không vẽ bất kỳ thành phần nào của nó
                
            # 1. VẼ ĐƯỜNG TRỤ ĐỊA CHẤT (Chỉ dành cho hố hợp lệ nằm trong vùng bao che)
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
                        
                        fig.add_trace(go.Scatter3d(
                            x=[x_hk, x_hk], y=[y_hk, y_hk], z=[z_top, z_bot],
                            mode='lines',
                            line=dict(color=mau_nen, width=14),
                            name=f"{ten_hk}: Lớp {ten_lop}",
                            hovertemplate=f"<b>Hố khoan: {ten_hk}</b><br>Tên lớp: {ten_lop}<br>Độ sâu: {tu_d:.2f}m - {den_d:.2f}m<br>Mô tả: {txt_mo_ta}<extra></extra>"
                        ))
                    except:
                        continue
            
            # 2. VẼ ĐƯỜNG BIỂU ĐỒ SPT MÀU VÀNG CHO HỐ KHẢO SÁT HỢP LỆ
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
                                
                                spt_x.append(x_hk + 20.0 + n_val * 1.5)
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
                            line=dict(color='yellow', width=3), marker=dict(size=4, color='orange'),
                            text=[f"N={n:.0f}" for n in np.array(spt_n)[spt_indices]], textposition="middle right",
                            textfont=dict(size=9, color='yellow'),
                            name=f"Đồ thị SPT {ten_hk}",
                            hovertemplate="Độ sâu SPT tính từ miệng: %{z:.2f}m<extra></extra>"
                        ))
                        
                        max_depth = df_sub_layers['Den_Chieu_Sau_Lop'].max() if not df_sub_layers.empty else 50.0
                        fig.add_trace(go.Scatter3d(
                            x=[x_hk, x_hk], y=[y_hk, y_hk], z=[z_mieng * he_so_z, (z_mieng - max_depth) * he_so_z],
                            mode='lines', line=dict(color='white', width=1.5, dash='dash'), showlegend=False
                        ))
        except:
            continue
            
    return fig


def doc_excel_dia_chat_nguyen_ban(uploaded_file):
    """
    📥 BỘ ĐỌC KHỚP TIÊU ĐỀ HOA THƯỜNG VÀ ĐỊNH DẠNG FILE EXCEL GỐC CỦA CHƯƠNG:
    - Tự động quét tìm hàng chứa tiêu đề thực tế để tránh lỗi lệch Index.
    - Ép text về dạng chữ thường để khớp tuyệt đối dữ liệu.
    """
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        if 'SPT' not in sheet_names:
            st.error("⚠️ Không tìm thấy sheet mang tên 'SPT' trong file Excel!")
            return None, None, None
            
        list_df_hk = []
        list_df_layer = []
        
        # 1. ĐỌC ĐỊA TẦNG TỪ CÁC SHEET HỐ KHOAN
        for sheet in sheet_names:
            if sheet.upper() == 'SPT':
                continue
                
            df_raw = pd.read_excel(uploaded_file, sheet_name=sheet, header=None)
            
            ten_hk = sheet.strip()
            x_hk, y_hk, z_mieng = 0.0, 0.0, 0.0
            
            # Quét tìm thông tin tọa độ metadata dòng đầu
            for idx, row in df_raw.iterrows():
                row_vals = [str(v).strip() for v in row.values if pd.notna(v)]
                for v in row_vals:
                    if 'HO_KHOAN' in v.upper() or 'HỐ KHOAN' in v.upper() or 'TÊN HỐ KHOAN' in v.upper():
                        try: ten_hk = row_vals[row_vals.index(v)+1].split()[0].replace(':', '').strip()
                        except: pass
                    if 'X_VN2000' in v.upper() or 'X=' in v.upper() or 'X =' in v.upper():
                        try:
                            import re
                            match = re.search(r'([\d\.\,]+)', "".join(row_vals[row_vals.index(v):]))
                            if match: x_hk = float(match.group(1).replace(',', '.'))
                        except: pass
                    if 'Y_VN2000' in v.upper() or 'Y=' in v.upper() or 'Y =' in v.upper():
                        try:
                            import re
                            match = re.search(r'([\d\.\,]+)', "".join(row_vals[row_vals.index(v):]))
                            if match: y_hk = float(match.group(1).replace(',', '.'))
                        except: pass
                    if 'Z_MIENG' in v.upper() or 'CAO ĐỘ MIỆNG' in v.upper():
                        try:
                            import re
                            match = re.search(r'([\d\.\,\+]+)', "".join(row_vals[row_vals.index(v):]))
                            if match: z_mieng = float(match.group(1).replace('+', '').replace(',', '.'))
                        except: pass
            
            if not ten_hk or len(ten_hk) > 20: 
                ten_hk = sheet.strip()
                
            list_df_hk.append({
                'Ho_Khoan': ten_hk, 'X_VN2000': x_hk, 'Y_VN2000': y_hk, 'Z_Mieng': z_mieng
            })
            
            # Dò tìm dòng tiêu đề bảng để bóc tách địa tầng lớp đất
            header_row_idx = 0
            for idx, row in df_raw.iterrows():
                row_vals_upper = [str(v).upper().strip() for v in row.values if pd.notna(v)]
                if 'TEN_LOP' in row_vals_upper or 'TU_CHIEU_SAU' in row_vals_upper:
                    header_row_idx = idx
                    break
                    
            df_table = pd.read_excel(uploaded_file, sheet_name=sheet, skiprows=header_row_idx)
            df_table.columns = [str(c).strip().lower() for c in df_table.columns]
            df_table = df_table.dropna(subset=['ten_lop', 'tu_chieu_sau', 'den_chieu_sau'])
            
            for _, row in df_table.iterrows():
                try:
                    tu_depth = float(str(row['tu_chieu_sau']).replace(',', '.'))
                    den_depth = float(str(row['den_chieu_sau']).replace(',', '.'))
                    ten_lop = str(row['ten_lop']).strip()
                    mo_ta = str(row.get('mo_ta', '')).strip()
                except:
                    continue
                    
                list_df_layer.append({
                    'Ho_Khoan': ten_hk,
                    'Tu_Chieu_Sau_Lop': tu_depth,
                    'Den_Chieu_Sau_Lop': den_depth,
                    'Ten_Lop': ten_lop,
                    'Mo_Ta': mo_ta
                })
                
        # 2. ĐỌC SHEET 'SPT' RIÊNG BIỆT (TỰ ĐỘNG DÒ HÀNG TIÊU ĐỀ THỰC TẾ)
        df_spt_all = pd.read_excel(uploaded_file, sheet_name='SPT', header=None)
        
        spt_header_idx = 0
        for idx, row in df_spt_all.iterrows():
            row_vals_str = [str(v).upper() for v in row.values if pd.notna(v)]
            if any('ĐỘ SÂU' in v or 'DO_SAU' in v or 'THÍ NGHIỆM' in v or 'SPT' in v for v in row_vals_str):
                spt_header_idx = idx
                break
                
        df_spt_raw = pd.read_excel(uploaded_file, sheet_name='SPT', skiprows=spt_header_idx)
        df_spt_raw.columns = [str(c).strip() for c in df_spt_raw.columns]
        
        return pd.DataFrame(list_df_hk), pd.DataFrame(list_df_layer), df_spt_raw
        
    except Exception as e:
        st.error(f"Lỗi phân tích tệp Excel địa chất công trình: {e}")
        return None, None, None