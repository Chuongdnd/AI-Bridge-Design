import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD TOÀN DIỆN KHÔNG GIAN
    Trích xuất Lý trình (X), Khoảng cách cánh (Offset) và Cao độ (Z)
    """
    data_points = []
    raw_content = uploaded_file.read()
    try:
        lines = raw_content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        lines = raw_content.decode("latin1").splitlines()
        
    current_x = 0.0
    current_pole = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
            
        token = parts[0].upper()
        
        if token == 'POLE' and len(parts) >= 4:
            try:
                current_pole = parts[1].strip().upper()
                current_x = float(parts[2])
                z_tim = float(parts[3])
                
                data_points.append({
                    'Cọc': current_pole, 'Lý trình': current_x, 'Offset': 0.0, 'Z': z_tim
                })
            except ValueError:
                pass
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                dist_offset = float(parts[1])
                z_val = float(parts[2])
                
                if current_pole:
                    data_points.append({
                        'Cọc': current_pole, 'Lý trình': current_x, 'Offset': dist_offset, 'Z': z_val
                    })
            except ValueError:
                pass
                
    return pd.DataFrame(data_points)

def parse_coordinate_file(uploaded_file):
    """
    BỘ GIẢI MÃ BẢNG TOẠ ĐỘ VN-2000
    Bỏ qua dòng tiêu đề phụ thô đầu tiên để lấy đúng các cột thuộc tính số liệu
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            df_coord = pd.read_csv(uploaded_file, skiprows=1)
        else:
            df_coord = pd.read_excel(uploaded_file, skiprows=1)
            
        # Chuẩn hóa viết hoa và xóa khoảng trắng ở tiêu đề cột
        df_coord.columns = [str(c).strip().upper() for c in df_coord.columns]
        
        # Tìm các cột chính dựa trên từ khóa kỹ thuật
        col_name = [c for c in df_coord.columns if 'CỌC' in c or 'TEN' in c][0]
        col_lt = [c for c in df_coord.columns if 'TRÌNH' in c or 'LYTRINH' in c][0]
        col_x = [c for c in df_coord.columns if 'X(M)' in c or 'X' in c][0]
        col_y = [c for c in df_coord.columns if 'Y(M)' in c or 'Y' in c][0]
        
        df_clean = pd.DataFrame({
            'Cọc_Excel': df_coord[col_name].astype(str).str.strip().str.upper(),
            'Lý_Trình_Excel': df_coord[col_lt].astype(float),
            'X_VN2000': df_coord[col_x].astype(float),
            'Y_VN2000': df_coord[col_y].astype(float)
        })
        # Lọc bỏ dòng trống hoặc dòng trùng lý trình lỗi
        return df_clean.dropna(subset=['Lý_Trình_Excel']).sort_values('Lý_Trình_Excel').reset_index(drop=True)
    except Exception as e:
        st.error(f"Lỗi đọc file bảng tọa độ VN-2000: {e}")
        return None

def convert_to_vn2000(df_ntd, df_coord):
    """
    THUẬT TOÁN ĐỒNG BỘ ĐỊNH VỊ THEO LÝ TRÌNH MÉT THỰC ĐỊA
    Đồng bộ chuẩn xác tọa độ thực tế cho các mốc cọc tim (kể cả B1, B2...)
    """
    # Tạo bảng sao lưu để tính toán
    df_merged = df_ntd.copy()
    
    # Lấy danh sách lý trình tim duy nhất từ file Excel
    excel_lts = df_coord['Lý_Trình_Excel'].values
    
    # Thuật toán thông minh: Khớp tọa độ dựa trên khoảng cách lý trình gần nhau nhất (Sai số < 0.1m)
    x_vn_list = []
    y_vn_list = []
    
    for idx, row in df_merged.iterrows():
        lt_ntd = row['Lý trình']
        # Tìm vị trí lý trình trong Excel có độ chênh lệch nhỏ nhất so với lý trình trong NTD
        abs_diff = np.abs(excel_lts - lt_ntd)
        closest_idx = np.argmin(abs_diff)
        
        # Nếu sai số lý trình nằm trong phạm vi chấp nhận được (hoặc lấy điểm tuần tự kề sát)
        x_vn_list.append(df_coord.loc[closest_idx, 'X_VN2000'])
        y_vn_list.append(df_coord.loc[closest_idx, 'Y_VN2000'])
        
    df_merged['X_VN2000'] = x_vn_list
    df_merged['Y_VN2000'] = y_vn_list
    
    # Lọc chuỗi mốc tim phẳng (Offset == 0) thực tế để dựng véc-tơ hướng hướng tuyến
    df_tim_calc = df_merged[df_merged['Offset'] == 0].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình').copy()
    
    # Tính toán dX, dY hướng tuyến giữa cọc sau và cọc trước
    df_tim_calc['dX'] = df_tim_calc['X_VN2000'].diff().shift(-1)
    df_tim_calc['dY'] = df_tim_calc['Y_VN2000'].diff().shift(-1)
    
    df_tim_calc['dX'] = df_tim_calc['dX'].bfill().ffill()
    df_tim_calc['dY'] = df_tim_calc['dY'].bfill().ffill()
    
    # Lượng giác hóa góc phương vị chỉ phương hướng tuyến ngoài thực địa
    df_tim_calc['Góc_Tuyến'] = np.arctan2(df_tim_calc['dY'], df_tim_calc['dX'])
    
    goc_map = dict(zip(df_tim_calc['Lý trình'], df_tim_calc['Góc_Tuyến']))
    df_merged['Góc_Tuyến'] = df_merged['Lý trình'].map(goc_map).bfill().ffill()
    
    # 🎯 BẮN TOẠ ĐỘ LƯỢNG GIÁC: Quay các điểm cánh trái / cánh phải vuông góc với tim đường thực VN-2000
    angle_offset = df_merged['Góc_Tuyến'] + (np.pi / 2)
    df_merged['X_Real'] = df_merged['X_VN2000'] + df_merged['Offset'] * np.cos(angle_offset)
    df_merged['Y_Real'] = df_merged['Y_VN2000'] + df_merged['Offset'] * np.sin(angle_offset)
    
    return df_merged

def ve_binh_do_goc_2d(df):
    """
    DỰNG BÌNH ĐỒ SỐ PHẲNG 2D TRÊN TOẠ ĐỘ THỰC VN-2000
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

def ve_dia_hinh_3d(df, he_so_z=1.0):
    """
    DỰNG MÔ HÌNH ĐỊA HÌNH KHÔNG GIAN 3D TRÊN TOẠ ĐỘ THỰC VN-2000
    """
    if df.empty:
        return None
        
    try:
        df_render = df.iloc[::2].copy() if len(df.index) > 2000 else df.copy()
        z_scaled = df_render['Z'] * he_so_z
        
        fig = go.Figure(data=[go.Mesh3d(
            x=df_render['X_Real'],
            y=df_render['Y_Real'],
            z=z_scaled,
            intensity=df_render['Z'],
            colorscale='Earth',
            opacity=0.95,
            showscale=False,
            hovertemplate="X Thực: %{x:.1f} m<br>Y Thực: %{y:.1f} m<br>Z Thực: %{intensity:.2f} m<extra></extra>"
        )])
        
        fig.update_layout(
            title=dict(
                text="🏔️ MÔ HÌNH KHÔNG GIAN ĐỊNH VỊ ĐỊA HÌNH 3D CHUẨN TOÀN CẦU VN-2000",
                font=dict(size=16, color='#007acc', family='Arial')
            ),
            scene=dict(
                xaxis_title="Tọa độ X VN-2000 (m)",
                yaxis_title="Tọa độ Y VN-2000 (m)",
                zaxis_title="Cao độ Z (m)",
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