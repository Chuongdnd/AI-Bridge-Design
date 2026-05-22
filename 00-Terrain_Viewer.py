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

def ve_dia_hinh_3d(df, he_so_z=1.0, hien_dong_muc=True, buoc_nhay_cao_do=1.0):
    """
    HÀM DỰNG ĐỊA HÌNH 3D CHỐNG PHẲNG VÀ ÉP HIỂN THỊ ĐƯỜNG ĐỒNG MỨC
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        # 1. Tạo ma trận lưới địa hình
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        
        # SỬA LỖI 2: Bảo vệ dữ liệu không bị san phẳng phẳng lỳ bởi rolling
        win_y = max(2, min(5, grid_df.shape[0] // 2))
        win_x = max(2, min(5, grid_df.shape[1] // 2))
        
        if grid_df.shape[0] >= win_y:
            grid_df = grid_df.rolling(window=win_y, min_periods=1, center=True).mean()
        if grid_df.shape[1] >= win_x:
            grid_df = grid_df.T.rolling(window=win_x, min_periods=1, center=True).mean().T
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_real = grid_df.values
        
        z_min_real = np.min(z_real)
        z_max_real = np.max(z_real)
        delta_z = z_max_real - z_min_real
        
        # SỬA LỖI 3: Nếu toàn bộ địa hình lệch nhau chưa đầy 1 mét, ta phải dùng bước nhảy nhỏ hơn
        if delta_z < 1.0:
            buoc_tinh = 0.1  # Vẽ đường đồng mức mỗi 10cm để chắc chắn có đường xuất hiện
            title_text = f"ĐƯỜNG ĐỒNG MỨC MỊN 0.1M (Do địa hình phẳng, biên độ Z = {delta_z:.2f}m)"
        else:
            buoc_tinh = buoc_nhay_cao_do
            title_text = f"ĐƯỜNG ĐỒNG MỨC CỐ ĐỊNH {buoc_nhay_cao_do}M"
            
        # Áp dụng hệ số scale trục Z hiển thị
        z_scaled = z_real * he_so_z 
        buoc_ve_scaled = buoc_tinh * he_so_z

        # 2. CẤU HÌNH ĐƯỜNG ĐỒNG MỨC ÉP HIỂN THỊ ĐẬM ĐẶC
        if hien_dong_muc:
            contour_config = dict(
                show=True,
                start=np.floor(z_min_real) * he_so_z,
                end=np.ceil(z_max_real) * he_so_z,
                size=buoc_ve_scaled,
                usecolormap=False,
                color="black",                  # Đổi thành đường nét màu ĐEN để nổi bật trên nền cát vàng
                width=4,                        # Nét vẽ siêu đậm (4px) chống mất nét
                project=dict(z=True)            # Ép in bóng bản đồ 2D xuống đáy
            )
        else:
            contour_config = dict(show=False)
        
        # 3. Khởi tạo bề mặt địa hình
        surface = go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_scaled,
            customdata=z_real,
            hovertemplate="X: %{x:.2f} m<br>Y: %{y:.2f} m<br>Z thực tế: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth',
            opacity=0.85,
            contours=dict(z=contour_config),
            lighting=dict(ambient=0.9, diffuse=0.3, specular=0.0, roughness=1.0), # Khử bóng mờ camera
            colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15)
        )
        
        fig = go.Figure(data=[surface])
        
        # 4. SỬA LỖI 1: HỦY BỎ TUYỆT ĐỐI ASPECTMODE='DATA'
        fig.update_layout(
            title=dict(
                text=f"🏔️ {title_text}",
                font=dict(size=14, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                
                # Ép hộp không gian hiển thị cân đối hình hộp chữ nhật, kéo giãn trục Y và trục Z ra
                aspectmode='manual',
                aspectratio=dict(x=1, y=0.5, z=0.3), 
                
                zaxis=dict(range=[np.min(z_scaled) - 2, np.max(z_scaled) + 1]),
                camera=dict(
                    eye=dict(x=0.0, y=0.0, z=1.8) # Đưa camera lên đỉnh đầu nhìn vuông góc xuống dạng Bình đồ
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