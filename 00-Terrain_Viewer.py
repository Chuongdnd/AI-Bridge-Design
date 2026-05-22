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
    current_pole = ""
    
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
                current_pole = parts[1].strip().upper() # Lưu tên cọc chuẩn hóa để so khớp VN-2000
                current_x = float(parts[2])
                z_tim = float(parts[3])
                
                data_points.append({
                    'Cọc': current_pole,
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
                
                if current_pole:
                    data_points.append({
                        'Cọc': current_pole,
                        'X': current_x, 
                        'Y': dist_offset, 
                        'Z': z_val,
                        'Type': 'Mia địa hình'
                    })
            except ValueError:
                pass
                
    return pd.DataFrame(data_points)

def parse_coordinate_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE BẢNG TOẠ ĐỘ THỰC VN-2000 (.CSV HOẶC .XLSX)
    Tự động xử lý bỏ qua các dòng tiêu đề giới thiệu để lấy chính xác dữ liệu số
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            # File CSV thực tế thường có 1-2 dòng tiêu đề lớn ở đỉnh -> nhảy dòng lấy header
            df_coord = pd.read_csv(uploaded_file, skiprows=1)
        else:
            df_coord = pd.read_excel(uploaded_file, skiprows=1)
            
        # Chuẩn hóa toàn bộ tên tiêu đề cột viết hoa và cắt khoảng trắng
        df_coord.columns = [str(c).strip().upper() for c in df_coord.columns]
        
        # Nhận diện cột tự động bằng từ khóa trắc đạc
        col_name = [c for c in df_coord.columns if 'CỌC' in c or 'TEN' in c][0]
        col_x = [c for c in df_coord.columns if 'X(M)' in c or 'X' in c][0]
        col_y = [c for c in df_coord.columns if 'Y(M)' in c or 'Y' in c][0]
        
        df_clean = pd.DataFrame({
            'Cọc': df_coord[col_name].astype(str).str.strip().str.upper(),
            'X_VN2000': df_coord[col_x].astype(float),
            'Y_VN2000': df_coord[col_y].astype(float)
        })
        return df_clean.drop_duplicates(subset=['Cọc'])
    except Exception as e:
        st.error(f"Lỗi đọc file bảng tọa độ VN-2000: {e}")
        return None

def convert_to_vn2000(df_ntd, df_coord):
    """
    THUẬT TOÁN PHÉP QUAY HÌNH HỌC KHÔNG GIAN TRẮC ĐẠC
    Bắn tọa độ các điểm mia vuông góc sang 2 bên cánh mố cầu theo hệ VN-2000 thực tế
    """
    # Đồng bộ liên kết tên cọc giữa dữ liệu hình học tuyến và tọa độ trắc địa thực tế
    df_merged = pd.merge(df_ntd, df_coord, on='Cọc', how='inner')
    
    if df_merged.empty:
        return pd.DataFrame()
        
    # Tính toán véc-tơ hướng tuyến dựa trên các mốc cọc tim thực (Y == 0)
    df_tim = df_merged[df_merged['Y'] == 0].drop_duplicates(subset=['X']).sort_values('X').copy()
    
    df_tim['dX'] = df_tim['X_VN2000'].diff().shift(-1)
    df_tim['dY'] = df_tim['Y_VN2000'].diff().shift(-1)
    
    # Điền bù dữ liệu cọc cuối cùng bám sát cọc kề trước nó
    df_tim['dX'] = df_tim['dX'].bfill().ffill()
    df_tim['dY'] = df_tim['dY'].bfill().ffill()
    
    # Tính góc phương vị chỉ phương của con đường ngoài thực tế bằng hàm lượng giác arctan2
    df_tim['Góc_Tuyến'] = np.arctan2(df_tim['dY'], df_tim['dX'])
    
    goc_map = dict(zip(df_tim['X'], df_tim['Góc_Tuyến']))
    df_merged['Góc_Tuyến'] = df_merged['X'].map(goc_map).bfill().ffill()
    
    # 🎯 BẮN TOẠ ĐỘ LƯỢNG GIÁC SANG 2 CÁNH VUÔNG GÓC TIM ĐƯỜNG (X_Real, Y_Real)
    angle_offset = df_merged['Góc_Tuyến'] + (np.pi / 2)
    df_merged['X_Real'] = df_merged['X_VN2000'] + df_merged['Y'] * np.cos(angle_offset)
    df_merged['Y_Real'] = df_merged['Y_VN2000'] + df_merged['Y'] * np.sin(angle_offset)
    
    return df_merged

def ve_binh_do_goc_2d(df):
    """
    DỰNG BÌNH ĐỒ SỐ ĐỊA HÌNH KHÔNG GIAN 2D TRÊN TOẠ ĐỘ THỰC VN-2000
    """
    if df.empty: 
        return None
    try:
        fig = go.Figure(data=go.Mesh3d(
            x=df['X_Real'], y=df['Y_Real'], z=df['Z'],
            intensity=df['Z'], colorscale='Viridis',
            opacity=0.90, showscale=True,
            colorbar=dict(title="Cao độ Z (m)", thickness=15)
        ))
        
        fig.update_layout(
            title=dict(text="🗺️ BÌNH ĐỒ SỐ ĐỊA HÌNH KHÔNG GIAN ĐỊNH VỊ THỰC TẾ VN-2000", font=dict(size=15, color='#007acc')),
            xaxis_title="Tọa độ thực X (m)", yaxis_title="Tọa độ thực Y (m)",
            yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='#222c3c'),
            xaxis=dict(gridcolor='#222c3c'),
            template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20), plot_bgcolor='#0e1117', paper_bgcolor='#0e1117'
        )
        return fig
    except Exception as e:
        st.error(f"Lỗi dựng bình đồ phẳng VN-2000: {e}")
        return None

def ve_dia_hinh_3d(df, he_so_z=1.0, hien_dong_muc=True, buoc_nhay_cao_do=1.0):
    """
    HÀM DỰNG KHỐI BỀ MẶT ĐỊA HÌNH 3D TRÊN HỆ TOẠ ĐỘ THỰC VN-2000
    Sử dụng Mesh3d (Delaunay Triangulation) để tự động nối lưới uốn cong tự do mượt mà, chống đơ máy.
    """
    if df.empty:
        return None
        
    try:
        # Nếu số lượng điểm mia quá dày đặc, tự động lọc trích mẫu để tăng tốc đồ họa trình duyệt
        df_render = df.iloc[::2].copy() if len(df.index) > 2000 else df.copy()
        
        # Áp dụng hệ số tỉ lệ trục đứng he_so_z trực tiếp vào cao độ Z hiển thị
        z_scaled = df_render['Z'] * he_so_z
        
        # Dựng mô hình lưới tam giác không gian đa hướng chuẩn trắc địa VN-2000
        fig = go.Figure(data=[go.Mesh3d(
            x=df_render['X_Real'],
            y=df_render['Y_Real'],
            z=z_scaled,
            intensity=df_render['Z'], # Đổ màu dải màu theo cao độ thực tự nhiên
            colorscale='Earth',
            opacity=0.95,
            showscale=False,
            hovertemplate="X Thực: %{x:.1f} m<br>Y Thực: %{y:.1f} m<br>Z Cao độ: %{intensity:.2f} m<extra></extra>"
        )])
        
        fig.update_layout(
            title=dict(
                text="🏔️ MÔ HÌNH KHÔNG GIAN ĐỊA HÌNH 3D ĐỊNH VỊ TOÀN CẦU VN-2000",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Tọa độ X VN-2000 (m)",
                yaxis_title="Tọa độ Y VN-2000 (m)",
                zaxis_title="Cao độ Z (m)",
                # Khóa tỷ lệ hệ mét đồng dạng, Chương kéo slider he_so_z để tăng giảm độ nhô lòng sông trực quan
                aspectmode='data' 
            ),
            template="plotly_dark",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor='#0e1117'
        )
        return fig
        
    except Exception as e:
        st.error(f"Lỗi dựng mô hình địa hình 3D VN-2000: {e}")
        return None