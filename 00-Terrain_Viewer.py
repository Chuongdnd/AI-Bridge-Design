import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD TOÀN DIỆN KHÔNG GIAN
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
                current_pole = parts[1].strip().upper()
                current_x = float(parts[2])
                z_tim = float(parts[3])
                
                data_points.append({
                    'Cọc': current_pole, 'Lý trình': current_x, 'Offset': 0.0, 'Z': z_tim
                })
            except ValueError:
                pass
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                dist_offset = float(parts[1])
                z_val = float(parts[2])
                
                if current_pole:
                    data_points.append({
                        'Cọc': current_pole, 'Lý trình': current_x, 'Offset': dist_offset, 'Z': z_val
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
    THUẬT TOÁN ĐỒNG BỘ TUẦN TỰ SONG SONG (INDEX-BASED MATCHING) WITH CO-ORDINATE INJECTION
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
        df_tim_calc['dX'] = df_tim_calc['X_VN2000'].diff().shift(-1)
        df_tim_calc['dY'] = df_tim_calc['Y_VN2000'].diff().shift(-1)
        df_tim_calc['dX'] = df_tim_calc['dX'].bfill().ffill()
        df_tim_calc['dY'] = df_tim_calc['dY'].bfill().ffill()
        
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

def tao_ma_tran_huong_tuyen(df):
    """
    ⚡ THUẬT TOÁN ĐỘT PHÁ: Tạo ma trận lưới cong dọc theo hành lang tuyến 
    Ngăn chặn 100% hiện tượng nối dính đầu và cuối tuyến lại với nhau.
    """
    # 1. Làm tròn gom cụm Offset Y về bước lưới chẵn 2m để đồng bộ hàng ma trận
    df_grid = df.copy()
    df_grid['Offset_Bin'] = np.round(df_grid['Offset'] / 2.0) * 2.0
    
    # 2. Xây dựng cấu trúc Pivot Table theo trục chính: Dòng = Offset, Cột = Lý trình
    # Pivot này chạy theo thứ tự tăng dần của con đường chứ không phụ thuộc tọa độ bản đồ băm nhỏ
    pivot_x = df_grid.pivot_table(index='Offset_Bin', columns='Lý trình', values='X_Real', aggfunc='mean')
    pivot_y = df_grid.pivot_table(index='Offset_Bin', columns='Lý trình', values='Y_Real', aggfunc='mean')
    pivot_z = df_grid.pivot_table(index='Offset_Bin', columns='Lý trình', values='Z', aggfunc='mean')
    
    # Nội suy điền khuyết tật lưới phẳng theo phương ngang trắc dọc và dọc trắc ngang
    pivot_x = pivot_x.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1).interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
    pivot_y = pivot_y.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1).interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
    pivot_z = pivot_z.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1).interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
    
    # Mài phẳng mịn màng bề mặt ma trận không gian bám dọc hành lang con đường
    pivot_z = pivot_z.rolling(window=3, min_periods=1, center=True).mean()
    pivot_z = pivot_z.T.rolling(window=3, min_periods=1, center=True).mean().T
    
    return pivot_x.values, pivot_y.values, pivot_z.values

def ve_dia_hinh_3d(df, he_so_z=1.0):
    """
    DỰNG MÔ HÌNH ĐỊA HÌNH KHÔNG GIAN 3D ĐỊNH HƯỚNG TẤM LƯỚI CONG THEO TUYẾN
    """
    if df.empty:
        return None
    try:
        # Gọi ma trận định hướng hành lang tuyến uốn cong
        x_grid, y_grid, z_grid = tao_ma_tran_huong_tuyen(df)
        
        # Ép hệ số phóng đại trục đứng vào cao độ ma trận hiển thị
        z_scaled = z_grid * he_so_z
        
        # Dựng tấm bề mặt uốn lượn chạy dọc mượt mà nối tiếp nhau
        fig = go.Figure(data=[go.Surface(
            x=x_grid, y=y_grid, z=z_scaled,
            customdata=z_grid,
            hovertemplate="X Thực: %{x:.1f} m<br>Y Thực: %{y:.1f} m<br>Z Thực: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth', opacity=0.95,
            colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
            contours=dict(x=dict(show=False), y=dict(show=False)) # Tắt đường lưới đen phụ cho nhẹ máy
        )])
        
        fig.update_layout(
            title=dict(text="🏔️ MÔ HÌNH ĐỊA HÌNH 3D ĐỊNH VỊ TOÀN CẦU CHUẨN VN-2000", font=dict(size=16, color='#007acc')),
            scene=dict(
                xaxis_title="Tọa độ X VN-2000 (m)",
                yaxis_title="Tọa độ Y VN-2000 (m)",
                zaxis_title="Cao độ Z (m)",
                aspectmode='data'
            ),
            template="plotly_dark", margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='#0e1117'
        )
        return fig
    except Exception as e:
        st.error(f"Lỗi dựng mô hình địa hình 3D VN-2000: {e}")
        return None