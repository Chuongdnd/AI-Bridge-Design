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

def ve_dia_hinh_3d(df, he_so_z=1.0, hien_dong_muc=True, buoc_nhay_cao_do=0.2):
    """
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D - ÉP HIỂN THỊ ĐƯỜNG ĐỒNG MỨC CHO ĐỊA HÌNH PHẲNG/DỐC THẤP
    - buoc_nhay_cao_do: Đặt mặc định nhỏ xuống (0.2m hoặc 0.1m) để ép sinh đường đồng mức
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
        
        # Tính toán biên độ cao độ THỰC TẾ
        z_min_real = np.min(z_real)
        z_max_real = np.max(z_real)
        delta_z = z_max_real - z_min_real
        
        # Áp dụng hệ số scale trục Z
        z_scaled = z_real * he_so_z 
        
        # 2. GIẢI PHÁP MỚI: TỰ ĐỘNG ÉP PHÂN LỚP ĐỒNG MỨC THEO BIẾN THIÊN THỰC TẾ
        # Nếu địa hình quá phẳng (lệch nhau < 2m), ta ép bước nhảy nhỏ mịn (0.1m - 0.2m)
        if delta_z <= 2.0:
            step = 0.1 * he_so_z
        else:
            step = buoc_nhay_cao_do * he_so_z

        if hien_dong_muc:
            # Tạo một danh sách các mốc cao độ chính xác để ép Plotly phải vẽ
            cac_moc_cao_do = np.arange(np.min(z_scaled), np.max(z_scaled) + step, step)
            
            contour_config = dict(
                show=True,
                type='constraint',              # ÉP BUỘC toán học vẽ theo mốc
                coloring='lines',               # Hiển thị rõ ràng dạng đường nét
                start=np.min(z_scaled),
                end=np.max(z_scaled),
                size=step,
                usecolormap=False,
                color="black",                  # Đổi thành màu ĐEN đậm để nổi bần bật trên nền dải cát vàng/trắng hiện tại
                width=4                         # Độ dày nét vẽ cực đậm
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
            opacity=1.0,
            contours=dict(z=contour_config),    # Nạp cấu hình contours ép buộc vào trục Z
            
            # Khử toàn bộ bóng mờ che khuất nét vẽ
            lighting=dict(
                ambient=1.0,                    # Ánh sáng phủ đều 100%, biến mô hình thành dạng bản đồ phẳng dễ nhìn
                diffuse=0.0,
                specular=0.0,
                roughness=1.0
            ),
            colorbar=dict(
                title=dict(text="Cao độ Z (m)", side="right"),
                thickness=15
            )
        )
        
        fig = go.Figure(data=[surface])
        
        # 4. THAY ĐỔI TOÀN BỘ TỶ LỆ KHUNG NHÌN (BẮT BUỘC)
        fig.update_layout(
            title=dict(
                text="🏔️ BÌNH ĐỒ ĐỊA HÌNH TỰ NHIÊN & ĐƯỜNG ĐỒNG MỨC ÉP NÉT",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                
                # SỬA LỖI QUAN TRỌNG: Chuyển từ 'data' sang 'manual'
                # Nếu để 'data', trục X dài 600m sẽ ép trục Y và Z nhỏ tí ti không thể thấy nét vẽ
                aspectmode='manual',
                aspectratio=dict(x=1, y=0.5, z=0.3), # Ép hộp không gian rộng rãi theo phương trắc ngang Y
                
                camera=dict(
                    eye=dict(x=0.0, y=0.0, z=2.0) # ĐẶT CAMERA NHÌN THẲNG TỪ TRÊN TRỜI XUỐNG (Orthographic-like) giống hệt Bản đồ Bình đồ phẳng
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