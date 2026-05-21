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
        if len(parts) < 2:
            continue
            
        first_token = parts[0].upper()
        
        # 🧠 THUẬT TOÁN CHUẨN: TÁCH BIỆT TRẮC NGANG "T" VỚI CỌC TUYẾN CHỐNG LỖI MẤT TỌA ĐỘ Y
        is_trac_ngang = False
        dist_offset = 0.0
        z_val = 0.0
        
        # Nhánh 1: Dòng trắc ngang bắt đầu bằng ký hiệu chữ "T" độc lập (Ví dụ: T  -15.00  3.85)
        if first_token == "T" and len(parts) >= 3:
            try:
                dist_offset = float(parts[1])
                z_val = float(parts[2])
                is_trac_ngang = True
            except ValueError:
                pass
        # Nhánh 2: Dòng trắc ngang chỉ có số thực trực tiếp (Ví dụ: -15.00  3.85)
        elif first_token.replace('-', '').replace('.', '', 1).isdigit():
            try:
                dist_offset = float(parts[0])
                z_val = float(parts[1])
                is_trac_ngang = True
            except ValueError:
                pass
                
        # 📊 TIẾN HÀNH PHÂN LOẠI VÀ GHI DỮ LIỆU VÀO ĐÚNG TRỤC HÌNH HỌC
        if is_trac_ngang:
            # Lưu điểm mia địa hình thực tế (Giữ nguyên tọa độ rộng Y sang 2 bên cánh)
            data_points.append({
                'X': current_x, 
                'Y': dist_offset, 
                'Z': z_val, 
                'Type': 'Mia địa hình'
            })
        else:
            # Nhánh 3: Dòng định nghĩa cọc/tim tuyến (Chỉ nhận diện cọc thực sự như C1, H1, T1 hoặc chữ TIM)
            if first_token.startswith(('C', 'H', 'P', 'M', 'T', 'K', 'V')) or "TIM" in first_token:
                try:
                    # Cấu trúc chuẩn: Tên_Cọc  Lý_Trình_Tổng  Cao_Độ_Z_Tại_Tim
                    if first_token == "N" and len(parts) >= 4:
                        current_x = float(parts[2])
                        z_tim = float(parts[3])
                    elif len(parts) >= 3:
                        current_x = float(parts[1])
                        z_tim = float(parts[2])
                    else:
                        continue
                    
                    # Lưu điểm tại Tim đường/sông (Y cố định = 0 tại tim)
                    data_points.append({
                        'X': current_x, 
                        'Y': 0.0, 
                        'Z': z_tim, 
                        'Type': 'Tim tuyến'
                    })
                except (ValueError, IndexError):
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
                title=dict(
                    text="Cao độ Z (m)",
                    side="right" # ✅ Đưa side lọt vào trong title dict theo đúng chuẩn Plotly
                ),
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
    """
    HÀM DỰNG KHỐI MÔ HÌNH ĐỊA HÌNH KHÔNG GIAN 3D (TERRAIN DIGITAL MODEL)
    Đã chuẩn hóa tham số layout chống lỗi nghiêm ngặt của Plotly
    """
    if df.empty or len(df.index) < 3:
        return None
        
    fig = go.Figure(data=[go.Mesh3d(
        x=df['X'],
        y=df['Y'],
        z=df['Z'],
        intensity=df['Z'],     # Đổ tông màu đậm nhạt biến thiên theo cao độ
        colorscale='Earth',    # Hệ màu chuẩn địa chất
        opacity=0.85,
        showscale=True,
        colorbar=dict(
            title=dict(
                text="Cao độ Z (m)",
                side="right" # ✅ Đưa side lọt vào trong title dict theo đúng chuẩn Plotly
            ),
            thickness=15
        ),
        flatshading=True       # Ép phẳng các bề mặt mảnh tạo hiệu ứng khối 3D
    )])
    
    # 🌟 CẬP NHẬT LAYOUT CHUẨN KHÔNG LO XUNG ĐỘT THUỘC TÍNH 🌟
    fig.update_layout(
        title=dict(
            text="🏔️ MÔ HÌNH KHÔNG GIAN ĐỊA HÌNH TỰ NHIÊN ĐA CHIỀU 3D",
            font=dict(size=16, color='#007acc', family='Arial')
        ),
        scene=dict(
            # Sử dụng các khóa macro tiêu chuẩn, an toàn tuyệt đối
            xaxis_title="Lý trình X (m)",
            yaxis_title="Trắc ngang Y (m)",
            zaxis_title="Cao độ Z (m)",
            aspectratio=dict(x=2, y=1, z=0.6) # Tỉ lệ hình học trực quan
        ),
        template="plotly_dark",  # Hệ Darkmode tự động tối ưu màu chữ/lưới thành màu sáng
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor='#0e1117'
    )
    return fig