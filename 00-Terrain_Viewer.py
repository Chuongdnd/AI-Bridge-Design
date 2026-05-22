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
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D LƯỚI KHÔNG GIAN PHẲNG PHIU (ANTI-CORRUGATED)
    - Giữ nguyên cấu trúc pivot_table, nội suy và mài mịn rolling gốc của bạn.
    - Cập nhật: Ép hiển thị đường đồng mức tĩnh màu đen rõ nét ngay từ đầu trên khối 3D.
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        # Giữ nguyên bước tạo ma trận lưới địa hình của bạn
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # Vuốt nối nội suy hình học liên tục phương trắc ngang Y rồi đến trắc dọc X
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        
        # ✨ Thuật toán khử sọc "múi tôn" bằng rolling + xoay ma trận .T gốc của bạn
        grid_df = grid_df.rolling(window=5, min_periods=1, center=True).mean()
        grid_df = grid_df.T.rolling(window=5, min_periods=1, center=True).mean().T
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_real = grid_df.values
        
        # Kích hoạt hệ số tỉ lệ he_so_z vào ma trận cao độ hiển thị
        z_scaled = z_real * he_so_z
        
        z_min_real = np.min(z_real)
        z_max_real = np.max(z_real)
        
        # BỔ SUNG: Cấu hình lưới đường đồng mức cố định hiện tĩnh ngay từ đầu
        if hien_dong_muc:
            contour_config = dict(
                show=True,                           # Ép buộc vẽ đường đồng mức lên mô hình
                start=np.floor(z_min_real) * he_so_z, # Điểm mét chẵn bắt đầu
                end=np.ceil(z_max_real) * he_so_z,   # Điểm mét chẵn kết thúc
                size=buoc_nhay_cao_do * he_so_z,     # Khoảng cao đều (Ví dụ: 1 mét vẽ 1 đường)
                usecolormap=False,                   # Tách màu đường nét khỏi dải màu nền
                color="rgb(0, 0, 0)",                # Đường nét màu ĐEN TUYỀN nét mực sắc sảo
                width=4,                             # Nét vẽ dày đậm 4 pixel để nhìn thấy luôn
                highlight=False,                     # TẮT CHẾ ĐỘ HOVER: Hiện cố định từ đầu, không đợi chỉ chuột
                project=dict(z=False)                # Chỉ hiện trên khối 3D, không chiếu xuống đáy
            )
        else:
            contour_config = dict(show=False)
        
        # Khởi tạo khối bề mặt Surface (Có bổ sung contours và làm sáng bề mặt)
        fig = go.Figure(data=[go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_scaled,
            customdata=z_real,
            hovertemplate="X: %{x:.1f} m<br>Y: %{y:.2f} m<br>Z thực: %{customdata:.2f} m<extra></extra>",
            colorscale='Earth',    # Hệ màu chuẩn địa hình tự nhiên gốc của bạn
            opacity=0.95,
            contours=dict(z=contour_config), # NẠP LƯỚI ĐƯỜNG ĐỒNG MỨC ĐÃ CẤU HÌNH BIẾN ĐỔI KHỐI TRỤC Z
            
            # Cải tiến ánh sáng phẳng để nét mực đen không bị bóng mờ camera che khuất
            lighting=dict(
                ambient=1.0, 
                diffuse=0.0,
                specular=0.0,
                roughness=1.0
            ),
            colorbar=dict(
                title=dict(text="Cao độ Z (m)", side="right"),
                thickness=15
            )
        )])
        
        fig.update_layout(
            title=dict(
                text="🏔️ MÔ HÌNH BỀ MẶT ĐỊA HÌNH TỰ NHIÊN TỶ LỆ THỰC ĐỊA 1:1:1",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                # Giữ nguyên ép tuyệt đối về tỷ lệ kích thước thật thực địa 1:1:1 của bạn
                aspectmode='data' 
            ),
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        # Đoạn bẫy lỗi hiển thị trên Streamlit gốc của bạn
        import streamlit as st
        st.error(f"Lỗi dựng mô hình địa hình 3D: {e}")
        return None