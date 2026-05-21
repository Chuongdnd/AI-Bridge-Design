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

def ve_dia_hinh_3d(df, he_so_z=0.25):
    """
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D LƯỚI KHÔNG GIAN PHẲNG PHIU (ANTI-CORRUGATED)
    Đã sửa cú pháp rolling() tương thích hoàn toàn với Pandas mới nhất, tỷ lệ thực tế 1:1:1
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        grid_df = df.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # Vuốt nối nội suy hình học liên tục phương trắc ngang Y rồi đến trắc dọc X
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        grid_df = grid_df.interpolate(method='linear', axis=1).ffill(axis=1).bfill(axis=1)
        
        # ✨ THUẬT TOÁN MỚI: Khử sạch sọc "múi tôn" bằng rolling + xoay ma trận .T
        # Mài mịn phương trắc ngang Y
        grid_df = grid_df.rolling(window=5, min_periods=1, center=True).mean()
        # Mài mịn phương lý trình X bằng kỹ thuật Transpose xoay trục an toàn
        grid_df = grid_df.T.rolling(window=5, min_periods=1, center=True).mean().T
        
        x_grid = grid_df.columns.values
        y_grid = grid_df.index.values
        z_grid = grid_df.values
        
        fig = go.Figure(data=[go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_grid,
            colorscale='Earth',    # Hệ màu chuẩn địa hình tự nhiên
            opacity=0.95,
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
                # ÉP TUYỆT ĐỐI VỀ TỶ LỆ KÍCH THƯỚC THẬT THỰC ĐỊA 1:1:1
                aspectmode='data' 
            ),
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        st.error(f"Lỗi dựng mô hình địa hình 3D: {e}")
        return None