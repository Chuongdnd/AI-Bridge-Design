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
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D - CỐ ĐỊNH KHOẢNG CAO ĐỀU ĐƯỜNG ĐỒNG MỨC THEO MÉT
    - buoc_nhay_cao_do: Mặc định cố định là 1.0 (1 mét một đường đồng mức)
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
        
        # Áp dụng hệ số scale trục Z lên ma trận cao độ hiển thị
        z_scaled = z_real * he_so_z 
        
        z_min_scaled = np.min(z_scaled)
        z_max_scaled = np.max(z_scaled)
        
        # Lấy giá trị cao độ thực tế nhỏ nhất và lớn nhất để tính toán mốc chẵn
        z_min_real = np.min(z_real)
        z_max_real = np.max(z_real)

        # 2. CẤU HÌNH ĐƯỜNG ĐỒNG MỨC CỐ ĐỊNH 1M VÀ NỔI BẬT
        if hien_dong_muc:
            # Ép bước nhảy trên đồ thị bằng cách nhân Khoảng cao đều gốc (1m) với hệ số phóng đại Z
            buoc_ve_scaled = buoc_nhay_cao_do * he_so_z
            
            contour_config = dict(
                show=True,
                # Làm tròn xuống mốc mét chẵn dưới cùng và nhân scale Z
                start=np.floor(z_min_real) * he_so_z, 
                # Làm tròn lên mốc mét chẵn trên cùng và nhân scale Z
                end=np.ceil(z_max_real) * he_so_z,   
                size=buoc_ve_scaled,                 # Cố định khoảng cao đều 1m (sau khi scale)
                usecolormap=False,                   # Không dùng chung màu bề mặt để tránh bị chìm nét
                color="rgb(255, 0, 0)",              # ĐỔI THÀNH MÀU ĐỎ RỰC RỠ hiển thị rõ nét ngay từ đầu
                width=4,                             # Độ dày nét vẽ đậm 4 pixel chống nuốt nét
                project=dict(z=True)                 # In bóng bản đồ đường đồng mức phẳng xuống đáy bình đồ
            )
        else:
            contour_config = dict(show=False)
        
        # 3. Khởi tạo bề mặt địa hình với ánh sáng cân bằng
        surface = go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_scaled,
            customdata=z_real,
            hovertemplate="X (Lý trình): %{x:.2f} m<br>Y (Trắc ngang): %{y:.2f} m<br>Z (Cao độ gốc): %{customdata:.2f} m<extra></extra>",
            colorscale='Earth',
            opacity=0.85,                        # Hơi trong suốt để nhìn thấy bản đồ đỏ dưới đáy
            contours=dict(z=contour_config),     # Nạp cấu hình contours vào trục Z
            
            # Điều chỉnh ánh sáng để làm nổi bật nét vẽ cơ học
            lighting=dict(
                ambient=0.7,
                diffuse=0.8,
                specular=0.1,
                roughness=0.5
            ),
            colorbar=dict(
                title=dict(text="Cao độ Z (m)", side="right"),
                thickness=15
            )
        )
        
        fig = go.Figure(data=[surface])
        
        # 4. Thiết lập tỷ lệ khung nhìn cân đối (Tránh lỗi co cụm dải hẹp)
        fig.update_layout(
            title=dict(
                text=f"🏔️ BÌNH ĐỒ ĐỊA HÌNH 3D - ĐƯỜNG ĐỒNG MỨC CỐ ĐỊNH {buoc_nhay_cao_do}M",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                
                # Khắc phục lỗi hình ảnh bị kéo dài như sợi dây ở các lượt trước
                aspectmode='manual',
                aspectratio=dict(x=1, y=0.6, z=0.35), # Ép giãn rộng trục ngang Y cho cân đối
                
                zaxis=dict(
                    range=[z_min_scaled - 3, z_max_scaled + 2] # Tạo khoảng trống dưới đáy để chứa bản đồ chiếu
                ),
                camera=dict(
                    eye=dict(x=1.3, y=1.3, z=0.9) # Góc nhìn tối ưu nhất để thấy cả khối 3D và bản đồ đáy
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