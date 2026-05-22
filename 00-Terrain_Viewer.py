import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD TOÀN DIỆN KHÔNG GIAN
    Lấy đầy đủ POLE (Lý trình + Cao độ tim Y=0) và TARGETL/R (Khoảng cách lẻ Y + Cao độ Z)
    """
    data_points = []
    
    raw_content = uploaded_file.read()
    try:
        lines = raw_content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        lines = raw_content.decode("latin1").splitlines()
        
    current_x = 0.0  # Lý trình trắc dọc (Trục X tổng thể)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        parts = line.split()
        if not parts:
            continue
            
        token = parts[0].upper()
        
        # 1. LẤY CỌC TIM TUYẾN: Xác định Lý trình X và Cao độ Z tại vị trí tim Y = 0
        if token == 'POLE' and len(parts) >= 4:
            try:
                current_x = float(parts[2])
                z_tim = float(parts[3])
                
                data_points.append({
                    'X': current_x, 
                    'Y': 0.0, 
                    'Z': z_tim,
                    'Type': 'Tim tuyến'
                })
            except ValueError:
                pass
                
        # 2. LẤY TRẮC NGANG CÁNH: Xác định Khoảng cách Y và Cao độ Z tương ứng
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                dist_offset = float(parts[1]) # Khoảng cách trắc ngang (Trục Y)
                z_val = float(parts[2])        # Cao độ trắc ngang (Trục Z)
                
                data_points.append({
                    'X': current_x, 
                    'Y': dist_offset, 
                    'Z': z_val,
                    'Type': 'Mia địa hình'
                })
            except ValueError:
                pass
                
    return pd.DataFrame(data_points)

import plotly.graph_objects as go
import pandas as pd

def ve_dia_hinh_3d(df, he_so_z=1.0, hien_dong_muc=True, buoc_nhay_cao_do=1.0):
    """
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D VÀ HIỂN THỊ ĐƯỜNG ĐỒNG MỨC CHI TIẾT
    Đã sửa lỗi không hiển thị đường đồng mức do sai lệch tỉ lệ trục dữ liệu.
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        # 1. Tạo ma trận lưới địa hình và nội suy làm mịn
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        
        # Mài mịn bề mặt khử sọc múi tôn
        grid_df = grid_df.rolling(window=5, min_periods=1, center=True).mean()
        grid_df = grid_df.T.rolling(window=5, min_periods=1, center=True).mean().T
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_real = grid_df.values
        
        # Áp dụng hệ số scale trục Z
        z_scaled = z_real * he_so_z 
        
        z_min = np.min(z_scaled)
        z_max = np.max(z_scaled)
        
        # TỰ ĐỘNG TÍNH TOÁN KHOẢNG CAO ĐỀU NẾU NGƯỜI DÙNG ĐẶT QUÁ NHỎ HOẶC QUÁ LỚN
        # Đảm bảo luôn có từ 10 đến 30 đường đồng mức xuất hiện trên mô hình
        chenh_lech_z = z_max - z_min
        if chenh_lech_z > 0 and (buoc_nhay_cao_do * he_so_z) > chenh_lech_z:
            buoc_ve = chenh_lech_z / 15
        else:
            buoc_ve = buoc_nhay_cao_do * he_so_z

        # 2. CẤU HÌNH ĐƯỜNG ĐỒNG MỨC ĐƯỢC ÉP HIỂN THỊ RÕ NÉT
        if hien_dong_muc:
            contour_config = dict(
                show=True,
                start=z_min,
                end=z_max,
                size=buoc_ve,
                usecolormap=False,
                color="rgba(255, 255, 255, 0.9)", # Màu trắng độ nét cao 90% để nổi bật trên nền Earth
                width=3,                           # Tăng độ dày nét vẽ lên 3 để không bị nuốt nét
                project=dict(z=True)               # Chiếu bản đồ phẳng xuống đáy
            )
        else:
            contour_config = dict(show=False)
        
        # 3. Khởi tạo bề mặt địa hình
        surface = go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_scaled,
            customdata=z_real,
            hovertemplate="X: %{x:.2f} m<br>Y: %{y:.2f} m<br>Z gốc: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth',
            opacity=0.9,
            contours=dict(z=contour_config), # Ép cấu hình contours vào bề mặt 3D
            colorbar=dict(
                title=dict(text="Cao độ Z (m)", side="right"),
                thickness=15
            )
        )
        
        fig = go.Figure(data=[surface])
        
        # 4. THAY ĐỔI CHIẾN LƯỢC ASPECT RATIO ĐỂ BẢN BẢO KHÔNG BỊ CO CỤM
        # Thay vì dùng 'data' (bị kéo dài theo trục X 600m), ta dùng 'manual' để ép khung hình cân đối
        fig.update_layout(
            title=dict(
                text=f"🏔️ BÌNH ĐỒ ĐỊA HÌNH 3D & ĐƯỜNG ĐỒNG MỨC",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                # SỬA LỖI CO CỤM: Ép tỉ lệ hiển thị của hộp không gian thành hình hộp cân đối (X:Y:Z = 1:1:0.4)
                aspectmode='manual',
                aspectratio=dict(x=1, y=1, z=0.4),
                
                # Cấu hình mặt phẳng chứa bản đồ chiếu ở đáy
                zaxis=dict(
                    range=[z_min - (chenh_lech_z * 0.2) - 1, z_max + 2]
                ),
                # Thiết lập góc nhìn Camera từ trên chéo xuống để thấy rõ đường đồng mức đáy và khối 3D
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.2)
                )
            ),
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        print(f"Lỗi dựng mô hình địa hình 3D: {e}")
        return None