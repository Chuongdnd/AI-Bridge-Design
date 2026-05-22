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
    THUẬT TOÁN ĐỒNG BỘ SONG SONG TUẦN TỰ VÀ BẮN TOẠ ĐỘ THỰC PHẲNG
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
        
        # Tính toán vector hướng tuyến mượt bằng trung bình trượt rolling nhẹ để hướng tuyến không giật cục
        df_tim_calc['X_Smooth'] = df_tim_calc['X_VN2000'].rolling(window=3, min_periods=1, center=True).mean()
        df_tim_calc['Y_Smooth'] = df_tim_calc['Y_VN2000'].rolling(window=3, min_periods=1, center=True).mean()
        
        df_tim_calc['dX'] = np.gradient(df_tim_calc['X_Smooth'].values)
        df_tim_calc['dY'] = np.gradient(df_tim_calc['Y_Smooth'].values)
        
        df_tim_calc['Góc_Tuyến'] = np.arctan2(df_tim_calc['dY'], df_tim_calc['dX'])
        
        goc_map = dict(zip(df_tim_calc['Lý trình'], df_tim_calc['Góc_Tuyến']))
        df_merged['Góc_Tuyến'] = df_merged['Lý trình'].map(goc_map).bfill().ffill()
        
        # Bắn tọa độ thực VN-2000
        angle_offset = df_merged['Góc_Tuyến'] + (np.pi / 2)
        df_merged['X_Real'] = df_merged['X_VN2000'] + df_merged['Offset'] * np.cos(angle_offset)
        df_merged['Y_Real'] = df_merged['Y_VN2000'] + df_merged['Offset'] * np.sin(angle_offset)
        
        return df_merged
    except Exception as e:
        st.error(f"Lỗi xử lý đồng bộ chuỗi điểm tim thực địa: {e}")
        return pd.DataFrame()

def ve_dia_hinh_3d(df, he_so_z=1.0):
    """
    🎯 GIẢI PHÁP KHÓA CHẾT LỖI RÁCH/ĐỨT TUYẾN:
    - Sử dụng go.Mesh3d với giải thuật Delaunay tự động của Plotly.
    - Không gán chỉ số thủ công bằng ma trận để loại bỏ hoàn toàn hiện tượng bậc thang đứt gãy.
    """
    if df.empty:
        return None
    try:
        # Sắp xếp dữ liệu theo trắc dọc tiến trình tăng dần
        df_render = df.sort_values('Lý trình').copy()
        
        x_vals = df_render['X_Real'].values
        y_vals = df_render['Y_Real'].values
        z_scaled = df_render['Z'].values * he_so_z
        z_real = df_render['Z'].values
        
        # Dựng mô hình 3D Mesh tự do
        # Plotly sẽ tự động dệt các điểm kề sát địa lý với nhau thành bề mặt đặc xuyên suốt
        fig = go.Figure(data=[go.Mesh3d(
            x=x_vals,
            y=y_vals,
            z=z_scaled,
            intensity=z_real, 
            colorscale='Earth', 
            opacity=0.95,
            showscale=True,
            # Bật tính năng tự động đan lưới Delaunay trên lưới tọa độ phẳng X-Y
            # Bẻ gãy hoàn toàn lỗi đứt khúc, lỗi sợi chỉ hay lỗi quăn đầu đuôi!
            alphahull=15, 
            colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
            hovertemplate="X Thực: %{x:.1f} m<br>Y Thực: %{y:.1f} m<br>Z Thực: %{intensity:.2f} m<extra></extra>"
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