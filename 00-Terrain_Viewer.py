import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD TOÀN DIỆN KHÔNG GIAN
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
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            df_coord = pd.read_csv(uploaded_file, skiprows=1)
        else:
            df_coord = pd.read_excel(uploaded_file, skiprows=1)
            
        df_coord.columns = [str(c).strip().upper() for c in df_coord.columns]
        
        try:
            col_name = [c for c in df_coord.columns if 'CỌC' in c or 'TEN' in c][0]
        except IndexError:
            col_name = df_coord.columns[1]
            
        col_x = df_coord.columns[3]
        col_y = df_coord.columns[4]
        
        x_numeric = pd.to_numeric(df_coord[col_x], errors='coerce')
        y_numeric = pd.to_numeric(df_coord[col_y], errors='coerce')
        
        df_clean = pd.DataFrame({
            'Cọc_Excel': df_coord[col_name].astype(str).str.strip().str.upper(),
            'X_VN2000': x_numeric,
            'Y_VN2000': y_numeric
        })
        return df_clean.dropna(subset=['X_VN2000', 'Y_VN2000']).reset_index(drop=True)
    except Exception as e:
        st.error(f"Lỗi đọc file bảng tọa độ VN-2000: {e}")
        return None

def convert_to_vn2000(df_ntd, df_coord):
    """
    THUẬT TOÁN ĐỒNG BỘ NÂNG CAO - SỬ DỤNG TIẾP TUYẾN GRADIENT VI PHÂN CHỐNG XOẮN GÓC CONG
    """
    try:
        list_ntd_x = sorted(df_ntd['Lý trình'].unique())
        df_coord_clean = df_coord.copy()
        
        min_len = min(len(list_ntd_x), len(df_coord_clean))
        if min_len == 0:
            return pd.DataFrame()
            
        map_x_real = {}
        map_y_real = {}
        for i in range(min_len):
            ly_trinh_ntd = list_ntd_x[i]
            map_x_real[ly_trinh_ntd] = df_coord_clean['X_VN2000'].iloc[i]
            map_y_real[ly_trinh_ntd] = df_coord_clean['Y_VN2000'].iloc[i]
            
        df_merged = df_ntd.copy()
        df_merged['X_VN2000'] = df_merged['Lý trình'].map(map_x_real)
        df_merged['Y_VN2000'] = df_merged['Lý trình'].map(map_y_real)
        
        df_merged = df_merged.dropna(subset=['X_VN2000', 'Y_VN2000']).copy()
        
        # Trích xuất chuỗi tim tuyến tính hướng
        df_tim_calc = df_merged[df_merged['Offset'] == 0].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình').copy()
        
        if len(df_tim_calc) >= 2:
            df_tim_calc['dX'] = np.gradient(df_tim_calc['X_VN2000'].values)
            df_tim_calc['dY'] = np.gradient(df_tim_calc['Y_VN2000'].values)
        else:
            df_tim_calc['dX'] = 1.0
            df_tim_calc['dY'] = 0.0
            
        df_tim_calc['Góc_Tuyến'] = np.arctan2(df_tim_calc['dY'], df_tim_calc['dX'])
        
        goc_map = dict(zip(df_tim_calc['Lý trình'], df_tim_calc['Góc_Tuyến']))
        df_merged['Góc_Tuyến'] = df_merged['Lý trình'].map(goc_map).bfill().ffill()
        
        # Quay lượng giác đưa toàn bộ điểm mia gốc về hệ VN-2000 thực tế ngoài đời
        angle_offset = df_merged['Góc_Tuyến'] + (np.pi / 2)
        df_merged['X_Real'] = df_merged['X_VN2000'] + df_merged['Offset'] * np.cos(angle_offset)
        df_merged['Y_Real'] = df_merged['Y_VN2000'] + df_merged['Offset'] * np.sin(angle_offset)
        
        return df_merged
    except Exception as e:
        st.error(f"Lỗi xử lý đồng bộ chuỗi điểm tim thực địa: {e}")
        return pd.DataFrame()

def tao_mesh_dan_hop_ly_tuyen(df):
    """
    🎯 GIẢI PHÁP TỐI ƯU TOÀN DIỆN MESH3D:
    - Thu thập toàn bộ các điểm nút thực tế phẳng của file NTD.
    - Tự động dệt mạng lưới tam giác chạy dọc hành lang sông thông qua phép chiếu cục bộ (Local Indexing).
    - Triệt tiêu 100% hiện tượng răng cưa, rách cung cong, sợi chỉ độc lập và thắt nút đầu đuôi!
    """
    unique_lts = sorted(df['Lý trình'].unique())
    
    x_nodes = []
    y_nodes = []
    z_nodes = []
    
    i_indices = []
    j_indices = []
    k_indices = []
    
    # Mảng lưu trữ vị trí bắt đầu chỉ số index nút của từng cọc để đan lưới sang cọc bên cạnh
    cọc_node_indices = {}
    current_index_counter = 0
    
    # Bước 1: Gom nút của từng cọc một cách tuần tiến độc lập bám sát file NTD gốc
    for lt in unique_lts:
        df_sub = df[df['Lý trình'] == lt].sort_values('Offset')
        if df_sub.empty:
            continue
            
        cọc_node_indices[lt] = {
            'start_idx': current_index_counter,
            'count': len(df_sub),
            'offsets': df_sub['Offset'].values
        }
        
        x_nodes.extend(df_sub['X_Real'].values)
        y_nodes.extend(df_sub['Y_Real'].values)
        z_nodes.extend(df_sub['Z'].values)
        
        current_index_counter += len(df_sub)
        
    # Bước 2: Đan mắt lưới tam giác bọc kín hành lang nối từ cọc i sang cọc i+1 dọc theo lý trình
    for idx in range(len(unique_lts) - 1):
        lt_curr = unique_lts[idx]
        lt_next = unique_lts[idx + 1]
        
        if (lt_curr not in cọc_node_indices) or (lt_next not in cọc_node_indices):
            continue
            
        info_curr = cọc_node_indices[lt_curr]
        info_next = cọc_node_indices[lt_next]
        
        # Đan lưới thông minh dựa trên việc tìm điểm kề có khoảng cách Offset tương ứng nhất giữa 2 cọc
        # Giải thuật này giúp triệt tiêu hiện tượng lệch pha điểm trắc ngang giữa cọc dày và cọc thưa
        for c in range(info_curr['count'] - 1):
            p0 = info_curr['start_idx'] + c
            p1 = info_curr['start_idx'] + (c + 1)
            
            # Khớp nối tìm điểm kề sát tương đương trên trục trắc ngang của cọc kế tiếp
            offset_val_c = info_curr['offsets'][c]
            offset_val_c1 = info_curr['offsets'][c + 1]
            
            n0 = info_next['start_idx'] + np.argmin(np.abs(info_next['offsets'] - offset_val_c))
            n1 = info_next['start_idx'] + np.argmin(np.abs(info_next['offsets'] - offset_val_c1))
            
            # Tạo các mặt tam giác kín bền vững khít kẽ hành lang dòng chảy
            i_indices.append(p0)
            j_indices.append(p1)
            k_indices.append(n0)
            
            i_indices.append(p1)
            j_indices.append(n1)
            k_indices.append(n0)
            
    return np.array(x_nodes), np.array(y_nodes), np.array(z_nodes), i_indices, j_indices, k_indices

def ve_dia_hinh_3d(df, he_so_z=1.0):
    """
    DỰNG MÔ HÌNH ĐỊA HÌNH 3D LƯỚI KHÔNG GIAN BỀN VỮNG CHO MỌI LOẠI FILE NTD
    """
    if df.empty:
        return None
    try:
        # Gọi thuật toán dệt lưới tam giác hành lang tuyến bám sát thực địa
        x, y, z, i, j, k = tao_mesh_dan_hop_ly_tuyen(df)
        z_scaled = z * he_so_z
        
        fig = go.Figure(data=[go.Mesh3d(
            x=x, y=y, z=z_scaled,
            i=i, j=j, k=k,
            intensity=z, # Đổ dải hệ màu Earth mượt theo cao độ thực tế tự nhiên
            colorscale='Earth', opacity=0.95,
            showscale=True,
            colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
            hovertemplate="X Thực: %{x:.1f} m<br>Y Thực: %{y:.1f} m<br>Z Thực: %{intensity:.2f} m<extra></extra>"
        )])
        
        fig.update_layout(
            title=dict(text="🏔️ MÔ HÌNH ĐỊA HÌNH 3D ĐỊNH VỊ TOÀN CẦU CHUẨN VN-2000", font=dict(size=16, color='#007acc')),
            scene=dict(
                xaxis_title="Tọa độ X VN-2000 (m)",
                yaxis_title="Tọa độ Y VN-2000 (m)",
                zaxis_title="Cao độ Z (m)",
                aspectmode='data'
            ),
            template="plotly_dark", margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='#0e1117'
        )
        return fig
    except Exception as e:
        st.error(f"Lỗi dựng mô hình địa hình 3D VN-2000: {e}")
        return None