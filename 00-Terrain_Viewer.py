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
    - buoc_nhay_cao_do: Khoảng cao đều giữa 2 đường đồng mức kế tiếp (ví dụ: mỗi 1m, 2m hoặc 5m).
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        # 1. Tạo ma trận lưới địa hình
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # Nội suy làm đầy các điểm thiếu dữ liệu
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        
        # Mài mịn bề mặt (Khử sọc múi tôn)
        grid_df = grid_df.rolling(window=5, min_periods=1, center=True).mean()
        grid_df = grid_df.T.rolling(window=5, min_periods=1, center=True).mean().T
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_real = grid_df.values
        
        # Áp dụng hệ số scale trục Z cho giao diện trực quan
        z_scaled = z_real * he_so_z 
        
        # Tính toán cao độ thấp nhất để làm mặt phẳng chiếu đáy
        z_min_scaled = np.min(z_scaled) if len(z_scaled) > 0 else 0
        
        # 2. CẤU HÌNH CHI TIẾT ĐƯỜNG ĐỒNG MỨC (CONTOURS)
        if hien_dong_muc:
            contour_config = dict(
                show=True,
                start=np.min(z_scaled),         # Cao độ bắt đầu vẽ
                end=np.max(z_scaled),           # Cao độ kết thúc
                size=buoc_nhay_cao_do * he_so_z,# Khoảng cao đều (phải nhân với scale Z để khớp mô hình)
                usecolormap=False,              # Không dùng chung màu bề mặt để dễ phân biệt
                color="white",                  # Đổi đường đồng mức sang màu trắng (hoặc màu nổi bật)
                width=2,                        # Độ dày đường đồng mức
                project=dict(
                    z=True                      # KÍCH HOẠT: Chiếu bản đồ đường đồng mức 2D xuống đáy 3D
                )
            )
        else:
            contour_config = dict(show=False)
        
        # 3. Tạo đối tượng bề mặt địa hình
        surface = go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_scaled,
            customdata=z_real,
            hovertemplate="Lý trình X: %{x:.2f} m<br>Trắc ngang Y: %{y:.2f} m<br>Cao độ Z gốc: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth',
            opacity=0.85,                       # Hơi trong suốt một chút để thấy lưới chiếu ở đáy
            contours=dict(z=contour_config),    # Nạp cấu hình đường đồng mức vào trục Z
            colorbar=dict(
                title=dict(text="Cao độ Z (m)", side="right"),
                thickness=15
            )
        )
        
        fig = go.Figure(data=[surface])
        
        # 4. Thiết lập cấu hình Layout không gian 3D
        fig.update_layout(
            title=dict(
                text=f"🏔️ BÌNH ĐỒ ĐỊA HÌNH 3D & ĐƯỜNG ĐỒNG MỨC (Khoảng cao đều = {buoc_nhay_cao_do}m)",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z hiển thị (m)",
                aspectmode='data',
                # Cấu hình mặt phẳng chiếu đáy z
                zaxis=dict(
                    showexponent="none",
                    range=[z_min_scaled - 5, np.max(z_scaled) + 5] # Tạo không gian trống dưới đáy để chứa bản đồ chiếu
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