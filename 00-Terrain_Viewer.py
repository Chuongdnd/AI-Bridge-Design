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

def ve_dia_hinh_3d(df, he_so_z=5.0, hien_dong_muc=True, buoc_nhay_cao_do=1.0):
    """
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D - HIỂN THỊ ĐƯỜNG ĐỒNG MỨC CỐ ĐỊNH 1M TRÊN BỀ MẶT
    - Chỉ hiển thị trên khối 3D, không chiếu đáy.
    - Hiển thị tĩnh ngay từ đầu, không phụ thuộc vào con trỏ chuột.
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        # 1. Tạo ma trận lưới địa hình từ dữ liệu X, Y, Z của file NTD
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_real = grid_df.values
        
        z_min_real = np.min(z_real)
        z_max_real = np.max(z_real)
        
        # Áp dụng hệ số scale trục Z hiển thị
        z_scaled = z_real * he_so_z 
        buoc_ve_scaled = buoc_nhay_cao_do * he_so_z

        # 2. CẤU HÌNH ĐƯỜNG ĐỒNG MỨC HIỂN THỊ TĨNH 100% TRÊN BỀ MẶT 3D
        if hien_dong_muc:
            contour_config = dict(
                show=True,                          # ÉP BUỘC HIỂN THỊ NGAY TỪ ĐẦU
                start=np.ceil(z_min_real) * he_so_z, # Mốc mét chẵn bắt đầu
                end=np.floor(z_max_real) * he_so_z, # Mốc mét chẵn kết thúc
                size=buoc_ve_scaled,                # Khoảng cao đều cố định đúng 1m (đã tỷ lệ theo Z)
                usecolormap=False,                  # Không dùng màu nền để đường nét không bị chìm
                color="rgb(0, 0, 0)",               # Đường đồng mức màu ĐEN TUYỀN sắc nét
                width=5,                            # Độ dày nét vẽ cực đậm (5px) để nhìn thấy ngay
                highlight=False,                    # TẮT CHẾ ĐỘ HOVER: Không đợi con trỏ chỉ vào mới hiện
                project=dict(z=False)               # TẮT CHIẾU ĐÁY: Chỉ hiển thị duy nhất ở phần 3D theo yêu cầu
            )
        else:
            contour_config = dict(show=False)
        
        # 3. Khởi tạo bề mặt địa hình
        surface = go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_scaled,
            customdata=z_real,
            hovertemplate="X: %{x:.1f} m<br>Y: %{y:.2f} m<br>Z gốc: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth',
            opacity=1.0,
            contours=dict(z=contour_config),    # Nạp cấu hình đường đồng mức tĩnh
            
            # Khử toàn bộ bóng mờ của Camera để lộ rõ nét vẽ mực đen
            lighting=dict(
                ambient=1.0, 
                diffuse=0.0,
                specular=0.0,
                roughness=1.0
            ),
            colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15)
        )
        
        fig = go.Figure(data=[surface])
        
        # 4. THIẾT LẬP KÉO GIÃN KHUNG NHÌN CHỐNG CO CỤM DẢI MẢNH
        fig.update_layout(
            title=dict(
                text=f"🏔️ BÌNH ĐỒ ĐỊA HÌNH 3D - ĐƯỜNG ĐỒNG MỨC CỐ ĐỊNH {buoc_nhay_cao_do}M",
                font=dict(size=14, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                
                # BẮT BUỘC: Thay đổi sang 'manual' để bẻ gãy tỷ lệ kéo dài của file gốc
                aspectmode='manual',
                # Tỷ lệ hộp hiển thị: X dài 1 phần, Y rộng hẳn ra 0.7 phần, Z cao 0.4 phần
                aspectratio=dict(x=1.0, y=0.7, z=0.4), 
                
                zaxis=dict(range=[np.min(z_scaled) - 1, np.max(z_scaled) + 1]),
                camera=dict(
                    eye=dict(x=1.2, y=1.2, z=1.2) # Góc nhìn xéo từ trên xuống bao quát toàn bộ mặt đường 3D
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