import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.interpolate import griddata
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

def ve_dia_hinh_3d(df, he_so_z=5.0, hien_dong_muc=True, buoc_nhay_cao_do=1.0):
    """
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D - TRẢ VỀ TỶ LỆ THỰC ĐỊA 1:1 GIỮA X VÀ Y
    - Tự động tính toán tỉ lệ thực của tuyến để chống biến dạng bề mặt.
    - Ép hiển thị đường đồng mức tĩnh rực rỡ trực tiếp trên khối 3D.
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        # 1. Lấy giá trị cực trị thực tế từ file dữ liệu (.ntd)
        x_min, x_max = df['X'].min(), df['X'].max()
        y_min, y_max = df['Y'].min(), df['Y'].max()
        z_min_real, z_max_real = df['Z'].min(), df['Z'].max()
        
        # Tính toán khoảng kích thước thực tế của các trục
        range_x = x_max - x_min
        range_y = y_max - y_min
        
        # ✨ THUẬT TOÁN TÍNH TỶ LỆ THỰC ĐỊA TUYẾN CHUẨN X : Y
        # Ví dụ: Nếu X = 3000m, Y = 60m -> ty_le_y = 60 / 3000 = 0.02
        ty_le_y_thuc = range_y / range_x
        
        # Đan lưới ô cờ mịn theo cấu trúc tuyến dài
        xi = np.linspace(x_min, x_max, 300)
        yi = np.linspace(y_min, y_max, 60)
        X_grid, Y_grid = np.meshgrid(xi, yi)
        
        # Nội suy không gian trắc đạc 2D
        z_grid_linear = griddata((df['X'], df['Y']), df['Z'], (X_grid, Y_grid), method='linear')
        z_grid_nearest = griddata((df['X'], df['Y']), df['Z'], (X_grid, Y_grid), method='nearest')
        z_real = np.where(np.isnan(z_grid_linear), z_grid_nearest, z_grid_linear)
        
        # Áp dụng hệ số scale trục Z hiển thị
        z_scaled = z_real * he_so_z 
        buoc_ve_scaled = buoc_nhay_cao_do * he_so_z

        # 2. CẤU HÌNH ĐƯỜNG ĐỒNG MỨC HIỂN THỊ TĨNH 100%
        if hien_dong_muc:
            contour_config = dict(
                show=True,                          # Hiện ngay từ đầu không đợi chuột
                start=np.floor(z_min_real) * he_so_z,
                end=np.ceil(z_max_real) * he_so_z,
                size=buoc_ve_scaled,                # Cố định đúng bước nhảy 1m
                usecolormap=False,
                color="rgb(255, 0, 0)",              # Đổi sang màu ĐỎ RỰC RỠ để nổi bật trên dải màu thuôn dài
                width=4,                            # Nét vẽ siêu dày (4px)
                highlight=False,                    # Tắt chế độ chờ chuột hover
                project=dict(z=False)               # Chỉ hiển thị duy nhất ở phần khối 3D
            )
        else:
            contour_config = dict(show=False)
        
        # 3. Khởi tạo bề mặt địa hình 3D Surface
        surface = go.Surface(
            x=X_grid,
            y=Y_grid,
            z=z_scaled,
            customdata=z_real,
            hovertemplate="X: %{x:.1f} m<br>Y: %{y:.2f} m<br>Z gốc: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth',
            opacity=1.0,
            contours=dict(z=contour_config),
            lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0, roughness=1.0),
            colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15)
        )
        
        fig = go.Figure(data=[surface])
        
        # 4. THIẾT LẬP CẤU HÌNH TỶ LỆ HÌNH HỘP THỰC ĐỊA TUYẾN
        fig.update_layout(
            title=dict(
                text=f"🏔️ BÌNH ĐỒ ĐỊA HÌNH 3D - TỶ LỆ THỰC ĐỊA TUYẾN X VÀ Y",
                font=dict(size=14, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                
                aspectmode='manual',
                
                # ✨ ĐÂY LÀ DÒNG CHỈNH SỬA MẤU CHỐT:
                # Trục X chiếm trọn chiều dài 1.0, trục Y tự động co nhỏ đúng tỷ lệ thật (ví dụ 0.02)
                # Trục Z đặt tầm 0.15 đến 0.2 để khối hình học nhô lên vừa vặn dễ nhìn đường đồng mức
                aspectratio=dict(x=1.0, y=ty_le_y_thuc, z=0.2), 
                
                zaxis=dict(range=[np.min(z_scaled) - 1, np.max(z_scaled) + 1]),
                camera=dict(
                    eye=dict(x=0.8, y=0.8, z=0.8) # Góc nhìn tối ưu cho mô hình tuyến thuôn dài
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