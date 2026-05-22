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

def ve_dia_hinh_3d(df, he_so_z=1.0, hien_dong_muc=True):
    """
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D LƯỚI KHÔNG GIAN PHẲNG PHIU (ANTI-CORRUGATED)
    Cập nhật: Cho phép cấu hình biến scale Z và ẩn/hiện đường đồng mức (contours).
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        # Tạo bảng ma trận lưới (Grid) từ dữ liệu khảo sát X, Y, Z
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # Vuốt nối nội suy hình học liên tục phương trắc ngang Y rồi đến trắc dọc X
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        
        # ✨ THUẬT TOÁN KHỬ SỌC "MÚI TÔN": Mài mịn bằng rolling trung bình trượt
        grid_df = grid_df.rolling(window=5, min_periods=1, center=True).mean()
        grid_df = grid_df.T.rolling(window=5, min_periods=1, center=True).mean().T
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_real = grid_df.values  # Giữ lại giá trị cao độ thực tế để hiển thị khi di chuột (Hover text)
        
        # Áp dụng hệ số scale Z cho mô hình trực quan
        # Nếu he_so_z > 1: Địa hình sẽ dốc và nhấp nhô rõ hơn để dễ quan sát
        z_scaled = z_real * he_so_z 
        
        # Cấu hình đường đồng mức dựa trên biến điều khiển hien_dong_muc
        contour_config = dict(
            show=True,
            usecolormap=True,  # Đường đồng mức đổ màu theo hệ màu địa hình
            highlightcolor="limegreen",
            project=dict(z=False) # Không chiếu đường đồng mức xuống đáy (để thẳng trên bề mặt 3D)
        ) if hien_dong_muc else dict(show=False)
        
        # Khởi tạo đối tượng đồ họa Surface
        surface = go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_scaled,          # Trục Z hiển thị theo tỷ lệ đã biến đổi
            customdata=z_real,   # Gắn cao độ gốc vào dữ liệu ngầm để làm hover text
            hovertemplate="Lý trình X: %{x:.2f} m<br>Trắc ngang Y: %{y:.2f} m<br>Cao độ Z gốc: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth',   # Hệ màu chuẩn địa hình tự nhiên
            opacity=0.95,
            contours=dict(z=contour_config), # Áp dụng ẩn/hiện đường đồng mức
            colorbar=dict(
                title=dict(text="Cao độ Z (m)", side="right"),
                thickness=15
            )
        )
        
        fig = go.Figure(data=[surface])
        
        fig.update_layout(
            title=dict(
                text=f"🏔️ MÔ HÌNH BỀ MẶT ĐỊA HÌNH TỰ NHIÊN (Scale Z = {he_so_z})",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z hiển thị (m)",
                # Thiết lập aspectmode='data' để tỷ lệ X và Y luôn chuẩn thực địa 1:1, riêng Z biến thiên tự do theo he_so_z
                aspectmode='data' 
            ),
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        # Nếu chạy trong môi trường Streamlit, dòng dưới sẽ hiển thị lên UI, hoặc có thể dùng print() thông thường
        import streamlit as st
        st.error(f"Lỗi dựng mô hình địa hình 3D: {e}")
        return None