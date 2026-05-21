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
        if len(parts) < 2:
            continue
            
        token = parts[0].upper()
        
        is_trac_ngang = False
        dist_offset = 0.0
        z_val = 0.0
        
        if token == 'T' and len(parts) >= 3:
            try:
                dist_offset = float(parts[1])
                z_val = float(parts[2])
                is_trac_ngang = True
            except ValueError:
                pass
        elif token.replace('-', '').replace('.', '', 1).isdigit():
            try:
                dist_offset = float(parts[0])
                z_val = float(parts[1])
                is_trac_ngang = True
            except ValueError:
                pass
                
        if is_trac_ngang:
            data_points.append({
                'X': current_x, 
                'Y': dist_offset, 
                'Z': z_val, 
                'Type': 'Mia địa hình'
            })
        else:
            if token.startswith(('C', 'H', 'P', 'M', 'T', 'K', 'V', 'P')) or "TIM" in token:
                try:
                    if token == 'POLE' and len(parts) >= 4:
                        current_x = float(parts[2])
                        z_tim = float(parts[3])
                    elif len(parts) >= 3:
                        current_x = float(parts[1])
                        z_tim = float(parts[2])
                    else:
                        continue
                    
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
    Đã chuẩn hóa thứ tự nội suy: Khôi phục mặt phẳng thực tế
    """
    if df.empty or len(df.index) < 3:
        st.warning("⚠️ Dữ liệu địa hình quá ít, không đủ điều kiện dựng Bình đồ đồng mức.")
        return None
        
    try:
        df_smooth = df.copy()
        df_smooth['Y'] = np.round(df_smooth['Y'] * 2) / 2
        
        grid_df = df_smooth.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # 🌟 THUẬT TOÁN MỚI: Nội suy trắc ngang phương Y (axis=0) trước để tạo mặt phẳng cắt phẳng phiu
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        # Sau đó mới nối các mặt cắt lại với nhau dọc theo tuyến X (axis=1)
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
    Đã triệt tiêu hoàn toàn lỗi răng cưa phương Y, giữ nguyên tỷ lệ thực địa 1:1:1
    """
    if df.empty or len(df.index) < 3:
        return None
        
    try:
        df_smooth = df.copy()
        df_smooth['Y'] = np.round(df_smooth['Y'] * 2) / 2
        
        grid_df = df_smooth.pivot_table(index='Y', columns='X', values='Z', aggfunc='mean')
        
        # 🌟 THUẬT TOÁN MỚI: Ép nội suy phương đứng trắc ngang Y (axis=0) lên thảm phẳng trước
        grid_df = grid_df.interpolate(method='linear', axis=0).ffill(axis=0).bfill(axis=0)
        # Nối mượt các thảm phẳng dọc theo lý trình X (axis=1) sau
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
                text="🏔️ MÔ HÌNH ĐỊA HÌNH KHÔNG GIAN TỶ LỆ THỰC ĐỊA 1:1:1",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Lý trình X (m)",
                yaxis_title="Trắc ngang Y (m)",
                zaxis_title="Cao độ Z (m)",
                aspectmode='data'  # Giữ nguyên kích thước thật 1:1:1 tuyệt đối của Chương
            ),
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        st.error(f"Lỗi dựng mô hình địa hình 3D: {e}")
        return None