import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD CHUẨN KHẢO SÁT CHẶT CHẼ
    Đã xóa bỏ bộ lọc số thô dự phòng để triệt tiêu hoàn toàn các điểm ma cao độ 1m
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
        
        # 🌟 KHÓA CHẶT CHẼ: CHỈ ĐỌC 3 TỪ KHÓA ĐỊA HÌNH CHÍNH - BỎ QUA TOÀN BỘ MÃ HIỆU SỐ RÁC 🌟
        
        # 1. Nhận diện dòng cọc tim tuyến (Từ khóa POLE)
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
                
        # 2. Nhận diện dòng trắc ngang trái / phải (Từ khóa TARGETL / TARGETR)
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                dist_offset = float(parts[1])
                z_val = float(parts[2])
                
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
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # Nội suy chuẩn phẳng: phương Y trắc ngang trước, phương X trắc dọc sau
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_grid = grid_df.values
        
        fig = go.Figure(data=go.Contour(
            x=x_grid,
            y=y_grid,
            z=z_grid,
            colorscale='Viridis',  
            colorbar=dict(
                title=dict(text="Cao độ Z (m)", side="right"),
                thickness=15
            ),
            contours=dict(
                start=float(df['Z'].min()),
                end=float(df['Z'].max()),
                size=0.5,           
                showlabels=True,    
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

def ve_dia_hinh_3d(df, he_so_z=0.25):
    """
    HÀM DỰNG KHỐI MÔ HÌNH ĐỊA HÌNH KHÔNG GIAN 3D (TERRAIN DIGITAL MODEL)
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # Nội suy chuẩn phẳng: phương Y trắc ngang trước, phương X trắc dọc sau
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_grid = grid_df.values
        
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
        
        fig.update_layout(
            title=dict(
                text="🏔️ MÔ HÌNH KHÔNG GIAN ĐỊA HÌNH TUYẾN 3D MƯỢT MÀ",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                aspectmode='manual',
                aspectratio=dict(x=6, y=1, z=he_so_z) # Nhận trực tiếp he_so_z mềm dẻo từ slider
            ),
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        st.error(f"Lỗi dựng mô hình địa hình 3D: {e}")
        return None