import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD KHẢO SÁT VIỆT NAM (Nova-TDN, ADS Civil, Topo)
    Chuyển đổi dữ liệu text khảo sát sang DataFrame tọa độ thực tế X, Y, Z
    """
    data_points = []
    
    # Đọc dữ liệu từ file upload và chuyển đổi sang dạng text
    raw_content = uploaded_file.read()
    try:
        lines = raw_content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        # Dự phòng trường hợp file mã hóa font TCVN3 hoặc Windows-1258 phổ biến trong ngành cầu đường
        lines = raw_content.decode("latin1").splitlines()
        
    current_x = 0.0  # Lý trình trắc dọc (Trục X tổng thể)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        parts = line.split()
        first_token = parts[0].upper()
        
        # 1. NHẬN DIỆN DÒNG CHỨA TÊN CỌC (Cọc Trắc dọc / Tim tuyến)
        # Các file .NTD thường bắt đầu bằng tên cọc như: C1, H1, P1, K1, T1... hoặc chữ "TIM"
        if first_token.startswith(('C', 'H', 'P', 'M', 'T', 'K', 'V')) or "TIM" in first_token:
            try:
                # Cấu trúc chuẩn: Tên_Cọc  Lý_Trình_Tổng  Cao_Độ_Z_Tại_Tim
                current_x = float(parts[1])
                z_tim = float(parts[2])
                
                # Lưu điểm tại Tim đường/sông (X = Lý trình, Y = 0, Z = Cao độ tim)
                data_points.append({
                    'X': current_x, 
                    'Y': 0.0, 
                    'Z': z_tim, 
                    'Type': 'Tim tuyến'
                })
            except (ValueError, IndexError):
                pass
                
        # 2. NHẬN DIỆN DÒNG CHỨA ĐIỂM MIA TRẮC NGANG LẺ
        # Nếu dòng bắt đầu bằng một số thực (khoảng cách lẻ), đó là điểm mia địa hình sang 2 bên cánh
        elif len(parts) >= 2 and parts[0].replace('-', '').replace('.', '', 1).isdigit():
            try:
                # Cấu trúc chuẩn: Khoảng_Cách_Lẻ  Cao_Độ_Địa_Hình_Z
                dist_offset = float(parts[0])  # Bên trái tim là âm (-), bên phải là dương (+)
                z_val = float(parts[1])         # Cao độ thực tế mặt đất tại điểm mia
                
                # Tọa độ Bình đồ duỗi thẳng: X là Lý trình cọc, Y là khoảng cách biên cách tim
                point_x = current_x
                point_y = dist_offset
                
                data_points.append({
                    'X': point_x, 
                    'Y': point_y, 
                    'Z': z_val, 
                    'Type': 'Mia địa hình'
                })
            except ValueError:
                pass
                
    return pd.DataFrame(data_points)

def ve_binh_do_goc_2d(df):
    """
    HÀM DỰNG BÌNH ĐỒ GỐC 2D ĐƯỜNG ĐỒNG MỨC (PLAN VIEW)
    Đã xử lý nội suy Ma trận 2D chống lỗi không khớp mảng của Plotly
    """
    if df.empty or len(df.index) < 3:
        st.warning("⚠️ Dữ liệu địa hình quá ít, không đủ điều kiện dựng Bình đồ đồng mức.")
        return None
        
    try:
        # 🧠 MẸO KỸ THUẬT: Chuyển đổi bảng điểm mia 1D rời rạc thành Ma trận lưới 2D (Grid Matrix)
        # index='Y' (hàng là trắc ngang), columns='X' (cột là lý trình), values='Z' (cao độ)
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # Nội suy mịn các vùng trống (nếu có cọc thiếu điểm mia cánh) để biểu đồ không bị rách
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        
        # Trích xuất các mảng chuẩn cấu trúc cấu hình Plotly Contour
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_grid = grid_df.values
        
        fig = go.Figure(data=go.Contour(
            x=x_grid,
            y=y_grid,
            z=z_grid,
            colorscale='Viridis',  
            colorbar=dict(
                title="Cao độ Z (m)",
                titleside="right",
                thickness=15
            ),
            contours=dict(
                start=float(df['Z'].min()),
                end=float(df['Z'].max()),
                size=0.5,           # Cách 0.5m vẽ một đường đồng mức
                showlabels=True,    # Hiện số cao độ trên đường
                labelfont=dict(size=10, color='white')
            ),
            line=dict(width=0.8, color='rgba(255,255,255,0.3)'),
            connectgaps=True        
        ))
        
        fig.update_layout(
            title=dict(
                text="🗺️ BÌNH ĐỒ ĐỊA HÌNH TỰ NHIÊN GỐC (ĐƯỜNG ĐỒNG MỨC SỐ)",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            xaxis_title="Lý trình Tuyến khảo sát (m)",
            yaxis_title="Khoảng cách trắc ngang sang 2 bên cánh tim (m)",
            # Khóa tỉ lệ 1:1 bảo toàn hình học thực địa không bị méo tuyến
            yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='#222c3c'),
            xaxis=dict(gridcolor='#222c3c'),
            template="plotly_dark",  
            margin=dict(l=40, r=40, t=50, b=40),
            plot_bgcolor='#0e1117',
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        st.error(f"Lỗi cấu trúc ma trận bình đồ: {e}")
        return None

def ve_dia_hinh_3d(df):
    if df.empty or len(df.index) < 3:
        return None
        
    # Sử dụng cấu trúc Mesh3d dựa trên mạng lưới các tam giác nội suy không gian Delaunay
    fig = go.Figure(data=[go.Mesh3d(
        x=df['X'],
        y=df['Y'],
        z=df['Z'],
        intensity=df['Z'],     # Đổ tông màu đậm nhạt biến thiên theo cao độ thực tế
        colorscale='Earth',    # Hệ màu chuẩn địa chất (Nâu đất - Xanh lá - Sông ngòi)
        opacity=0.85,
        showscale=True,
        colorbar=dict(title="Cao độ Z (m)", thickness=15),
        flatshading=True       # Ép phẳng các bề mặt mảnh để tạo hiệu ứng khối 3D rõ nét
    )])
    
    # Cấu hình không gian camera và hiển thị 3D trục tọa độ
    fig.update_layout(
        title=dict(
            text="🏔️ MÔ HÌNH KHÔNG GIAN ĐỊA HÌNH TỰ NHIÊN ĐA CHIỀU 3D",
            font=dict(size=16, color='#007acc', family='Arial')
        ),
        scene=dict(
            xaxis=dict(title="Lý trình X (m)", backgroundcolor="#1e1e1e", gridcolor="#333333", textcolor="white"),
            yaxis=dict(title="Trắc ngang Y (m)", backgroundcolor="#1e1e1e", gridcolor="#333333", textcolor="white"),
            zaxis=dict(title="Cao độ Z (m)", backgroundcolor="#1e1e1e", gridcolor="#333333", textcolor="white"),
            # Thiết lập góc nghiêng phóng đại trục đứng Z để tránh địa hình phẳng lì khó nhìn taluy bờ sông
            aspectratio=dict(x=2, y=1, z=0.6) 
        ),
        template="plotly_dark",
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor='#0e1117',
        paper_bgcolor='#0e1117'
    )
    return fig