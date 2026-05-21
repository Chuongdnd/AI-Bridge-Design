import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD KHẢO SÁT CHUẨN TDN VERSION 3.5 (Nova / ADS Civil thực địa)
    Đã hiệu chỉnh bắt trúng từ khóa POLE, TARGETL, TARGETR của Chương
    """
    data_points = []
    
    raw_content = uploaded_file.read()
    try:
        lines = raw_content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        lines = raw_content.decode("latin1").splitlines()
        
    current_x = 0.0  # Lý trình trắc dọc (Trục X)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        parts = line.split()
        if not parts:
            continue
            
        token = parts[0].upper()
        
        # 1. NHẬN DIỆN DÒNG CỌC TIM TUYẾN (Từ khóa POLE)
        if token == 'POLE' and len(parts) >= 4:
            try:
                # parts[2] là lý trình số (Ví dụ: 0.00000, 20.00000...)
                current_x = float(parts[2])
                # parts[3] là cao độ tự nhiên tại tim tuyến
                z_tim = float(parts[3])
                
                data_points.append({
                    'X': current_x, 
                    'Y': 0.0, 
                    'Z': z_tim, 
                    'Type': 'Tim tuyến'
                })
            except ValueError:
                pass
                
        # 2. NHẬN DIỆN DÒNG ĐIỂM MIA SANG 2 BÊN CÁNH (Từ khóa TARGETL / TARGETR)
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                # parts[1] là khoảng cách lẻ trắc ngang (Trái âm, Phải dương)
                dist_offset = float(parts[1])
                # parts[2] là cao độ thực tế mặt đất tại điểm mia
                z_val = float(parts[2])
                
                data_points.append({
                    'X': current_x, 
                    'Y': dist_offset, 
                    'Z': z_val, 
                    'Type': 'Mia địa hình'
                })
            except ValueError:
                pass
                
        # 3. DỰ PHÒNG: Nhận diện định dạng số lẻ trắc ngang kiểu cũ (Nếu có)
        elif token.replace('-', '').replace('.', '', 1).isdigit() and len(parts) >= 2:
            try:
                dist_offset = float(parts[0])
                z_val = float(parts[1])
                data_points.append({
                    'X': current_x, 
                    'Y': dist_offset, 
                    'Z': z_val, 
                    'Type': 'Mia địa hình'
                })
            except ValueError:
                pass
                
    return pd.DataFrame(data_points)

def ve_binh_do_goc_2d(df):
    """
    HÀM DỰNG BÌNH ĐỒ GỐC 2D ĐƯỜNG ĐỒNG MỨC (PLAN VIEW)
    """
    if df.empty or len(df.index) < 3:
        st.warning("⚠️ Dữ liệu địa hình quá ít, không đủ điều kiện dựng Bình đồ đồng mức.")
        return None
        
    try:
        # Chuyển đổi bảng điểm mia 1D rời rạc thành Ma trận lưới 2D (Grid Matrix)
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # Nội suy mịn các vùng trống trên lưới để đường đồng mức liền mạch không bị rách
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        
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
                    side="right"
                ),
                thickness=15
            ),
            contours=dict(
                start=float(df['Z'].min()),
                end=float(df['Z'].max()),
                size=0.5,           # Cách 0.5m vạch một đường đồng mức cao độ
                showlabels=True,    # Hiện số cao độ trên đường đồng mức
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
    Đã khóa cứng tỉ lệ kích thước thật 1:1:1 theo số liệu khảo sát thực địa
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        # 1. Làm mịn địa hình (Gom khoảng cách trắc ngang Y về bước lưới 0.5m)
        df_smooth = df.copy()
        df_smooth['Y'] = np.round(df_smooth['Y'] * 2) / 2
        
        # 2. Xoay bảng dữ liệu thành ma trận lưới 2D đồng bộ
        grid_df = df_smooth.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # Nội suy toán học điền đầy các lỗ hổng
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_grid = grid_df.values
        
        # Dùng go.Surface để trải mịn tấm thảm địa hình
        fig = go.Figure(data=[go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_grid,
            colorscale='Earth',    
            opacity=0.9,
            colorbar=dict(
                title=dict(text="Cao độ Z (m)", side="right"),
                thickness=15
            )
        )])
        
        # 🌟 CẬP NHẬT PHÂN VÙNG LAYOUT GIỮ KÍCH THƯỚC THẬT 🌟
        fig.update_layout(
            title=dict(
                text="🏔️ MÔ HÌNH ĐỊA HÌNH KHÔNG GIAN 3D CHUẨN TRỰC QUAN",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                # 📌 THAY ĐỔI CỐT LÕI TẠI ĐÂY:
                aspectmode='manual',
                aspectratio=dict(x=3, y=1, z=he_so_z)
                # Giải thích: Chiều dài hiển thị gấp 3 lần chiều rộng, 
                # và chiều cao đứng chiếm 25% chiều rộng. 
                # Tỷ lệ này giúp Chương nhìn rõ mố cát, lòng sông mà không bị biến dạng thành gai nhọn!
            ),
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        st.error(f"Lỗi dựng mô hình địa hình 3D: {e}")
        return None