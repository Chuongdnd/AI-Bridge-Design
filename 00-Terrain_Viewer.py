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
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D - ÉP HIỂN THỊ ĐƯỜNG ĐỒNG MỨC CỐ ĐỊNH 1M
    - Sử dụng thuật toán GridData để xử lý dữ liệu tuyến dài 3000m.
    - Cập nhật tỷ lệ hiển thị hình hộp phẳng cân đối x=1, y=1, z=0.4 theo yêu cầu.
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        # 1. Trích xuất biên độ thực tế từ file dữ liệu (.ntd)
        x_min, x_max = df['X'].min(), df['X'].max()
        y_min, y_max = df['Y'].min(), df['Y'].max()
        z_min_real, z_max_real = df['Z'].min(), df['Z'].max()
        
        # Tạo lưới ô cờ đồng đều tuyệt đối để tính toán độ dốc thực tế
        xi = np.linspace(x_min, x_max, 200)
        yi = np.linspace(y_min, y_max, 60)
        X_grid, Y_grid = np.meshgrid(xi, yi)
        
        # Tiến hành nội suy không gian 2D (Khắc phục triệt để lỗi phẳng lỳ của pivot_table)
        z_grid_linear = griddata((df['X'], df['Y']), df['Z'], (X_grid, Y_grid), method='linear')
        z_grid_nearest = griddata((df['X'], df['Y']), df['Z'], (X_grid, Y_grid), method='nearest')
        z_real = np.where(np.isnan(z_grid_linear), z_grid_nearest, z_grid_linear)
        
        # Áp dụng tỷ lệ khuếch đại trục Z để mô hình nhô cao rõ nét
        z_scaled = z_real * he_so_z 
        buoc_ve_scaled = buoc_nhay_cao_do * he_so_z

        # 2. CẤU HÌNH ĐƯỜNG ĐỒNG MỨC HIỂN THỊ TĨNH 100% TRÊN KHỐI 3D
        if hien_dong_muc:
            contour_config = dict(
                show=True,                          # Ép buộc vẽ ngay từ giây đầu tiên khi tải trang
                start=np.floor(z_min_real) * he_so_z,
                end=np.ceil(z_max_real) * he_so_z,
                size=buoc_ve_scaled,                # Khoảng cao đều cố định đúng 1m
                usecolormap=False,                  # Tách biệt màu đường nét khỏi màu nền dải màu
                color="rgb(0, 0, 0)",               # Đường nét màu ĐEN TUYỀN nét mực rõ ràng
                width=5,                            # Nét vẽ siêu dày (5px) để nhìn thấy luôn
                highlight=False,                    # Tắt cơ chế chờ hover (chuột chỉ vào mới hiện)
                project=dict(z=False)               # Tắt tính năng in bóng xuống đáy bản đồ
            )
        else:
            contour_config = dict(show=False)
        
        # 3. Khởi tạo bề mặt địa hình 3D Surface
        surface = go.Surface(
            x=X_grid,
            y=Y_grid,
            z=z_scaled,
            customdata=z_real,
            hovertemplate="Lý trình X: %{x:.1f} m<br>Trắc ngang Y: %{y:.2f} m<br>Cao độ Z gốc: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth',
            opacity=1.0,
            contours=dict(z=contour_config),    # Đưa lưới đường đồng mức tĩnh vào mô hình
            
            # Triệt tiêu bóng mờ đổ bóng của camera để nhìn rõ nét mực đen
            lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0, roughness=1.0),
            colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15)
        )
        
        fig = go.Figure(data=[surface])
        
        # 4. THIẾT LẬP CẤU HÌNH TỶ LỆ HÌNH HỘP 1:1:z THEO YÊU CẦU
        fig.update_layout(
            title=dict(
                text=f"🏔️ BÌNH ĐỒ ĐỊA HÌNH 3D NỘI SUY TỶ LỆ KHUNG NHÌN 1:1:z",
                font=dict(size=14, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                
                # Chế độ manual cho phép ta tự định nghĩa tỷ lệ hiển thị
                aspectmode='manual',
                
                # ✨ ĐÂY LÀ DÒNG CODE CHỈNH TỶ LỆ 1:1:z THEO YÊU CẦU CỦA BẠN
                # X và Y bằng nhau tạo thành hình vuông, trục Z chiếm tỷ lệ 0.4 độ cao của hộp
                aspectratio=dict(x=1.0, y=1.0, z=0.4), 
                
                zaxis=dict(range=[np.min(z_scaled) - 1, np.max(z_scaled) + 1]),
                camera=dict(
                    eye=dict(x=1.3, y=1.3, z=1.1)   # Góc nhìn từ trên cao chếch xuống bao quát rộng rãi
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