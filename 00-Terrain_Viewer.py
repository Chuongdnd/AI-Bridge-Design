import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import re
import unicodedata

def parse_ntd_file(uploaded_file):
    """
    BỘ GIẢI MÃ FILE .NTD TOÀN DIỆN KHÔNG GIAN
    - Phân loại trực tiếp bằng cách đọc chữ 'POLE', 'TARGETL', 'TARGETR'
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
        
        # 1. Đọc chữ POLE lấy tọa độ tim tuyến
        if token == 'POLE' and len(parts) >= 4:
            try:
                current_pole = parts[1].strip().upper()
                current_x = float(parts[2])
                z_tim = float(parts[3])
                
                data_points.append({
                    'Cọc': current_pole, 'Lý trình': current_x, 'Offset': 0.0, 'Z': z_tim, 'Tag_Gốc': 'POLE'
                })
            except ValueError:
                pass
        # 2. Đọc chữ TARGETL/R lấy tọa độ cánh trắc ngang thực tế
        elif token in ['TARGETL', 'TARGETR'] and len(parts) >= 3:
            try:
                dist_offset = float(parts[1])
                z_val = float(parts[2])
                
                if current_pole:
                    data_points.append({
                        'Cọc': current_pole, 'Lý trình': current_x, 'Offset': dist_offset, 'Z': z_val, 'Tag_Gốc': token
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
    THUẬT TOÁN ĐỒNG BỘ SONG SONG VÀ XOAY LƯỢNG GIÁC THEO TIM TUYẾN THỰC ĐỊA
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
        
        angle_offset = df_merged['Góc_Tuyến'] + (np.pi / 2)
        df_merged['X_Real'] = df_merged['X_VN2000'] + df_merged['Offset'] * np.cos(angle_offset)
        df_merged['Y_Real'] = df_merged['Y_VN2000'] + df_merged['Offset'] * np.sin(angle_offset)
        
        return df_merged
    except Exception as e:
        st.error(f"Lỗi xử lý đồng bộ chuỗi điểm tim thực địa: {e}")
        return pd.DataFrame()

def ve_dia_hinh_3d(df, he_so_z=1.0, che_do="Bề mặt mịn", do_min=3):
    """
    🏔️ MÔ HÌNH ĐỊA HÌNH 3D XUYÊN SUỐT - GIẢI QUYẾT TRIỆT ĐỂ LỖI SÓT ĐOẠN CONG/THẲNG
    - Quét liên tục qua tất cả các cọc tăng dần theo thứ tự Lý trình.
    - Cọc nào thiếu chữ 'TARGETL/R' sẽ được tự động bù biên từ các cọc đầy đủ lân cận để vuốt nối liền mạch.
    """
    if df.empty: 
        return None, None, None, None
    
    try:
        df_clean = df.sort_values(['Lý trình', 'Offset']).copy()
        unique_lts = sorted(df_clean['Lý trình'].unique())
        
        lt_min = unique_lts[0]
        lt_max = unique_lts[-1]
        lt_left = lt_min - 50.0
        lt_right = lt_max + 50.0

        # Lấy mặt cắt tại đầu và cuối tuyến
        df_first = df_clean[df_clean['Lý trình'] == lt_min].sort_values('Offset')
        df_last = df_clean[df_clean['Lý trình'] == lt_max].sort_values('Offset')

        def create_extended_section(df_template, new_lt, delta_lt):
            """Tạo mặt cắt mới bằng cách dịch chuyển toàn bộ điểm theo hướng tuyến"""
            goc = df_template['Góc_Tuyến'].iloc[0]  # góc radian của tim tuyến tại cọc gốc
            ux = np.cos(goc)
            uy = np.sin(goc)
            new_df = df_template.copy()
            new_df['Lý trình'] = new_lt
            new_df['X_Real'] = new_df['X_Real'] + delta_lt * ux
            new_df['Y_Real'] = new_df['Y_Real'] + delta_lt * uy
            # Thay đổi tên cọc để phân biệt
            new_df['Cọc'] = new_df['Cọc'] + f"_ext{new_lt:.0f}"
            return new_df

        # Tạo mặt cắt trái và phải
        df_left = create_extended_section(df_first, lt_left, lt_left - lt_min)
        df_right = create_extended_section(df_last, lt_right, lt_right - lt_max)

        # Ghép tất cả và sắp xếp theo lý trình
        df_clean = pd.concat([df_left, df_clean, df_right], ignore_index=True)
        df_clean = df_clean.sort_values(['Lý trình', 'Offset']).reset_index(drop=True)
        unique_lts = sorted(df_clean['Lý trình'].unique())
        # -----------------------------------

        # Đồng bộ 40 mắt đan trên mỗi mặt cắt ngang line
        num_samples = 40  
        target_pct = np.linspace(0.0, 1.0, num_samples)
        
        matrix_x, matrix_y, matrix_z = [], [], []
        
        for lt in unique_lts:
            df_sub = df_clean[df_clean['Lý trình'] == lt].sort_values('Offset')
            
            # Kiểm tra xem cọc này có chứa chữ TARGETL hoặc TARGETR không (Tag_Gốc có chữ TARGET)
            has_target = df_sub['Tag_Gốc'].str.contains('TARGET', na=False).any()
            
            obs_offsets = df_sub['Offset'].values
            obs_x_real = df_sub['X_Real'].values
            obs_y_real = df_sub['Y_Real'].values
            obs_zs = df_sub['Z'].values
            
            # 🎯 NẾU CỌC SÓT (CHỈ CÓ CHỮ POLE - KHÔNG CÓ CHỮ TARGET): Tự động lấy biên vuốt bù
            if not has_target or len(obs_offsets) < 2:
                goc_tuyen = df_sub['Góc_Tuyến'].iloc[0]
                g_offset = goc_tuyen + (np.pi / 2)
                
                # Giả lập dải cánh 25m mỗi bên gối đầu mềm dẻo qua cọc phụ
                offsets_fake = np.linspace(-25.0, 25.0, num_samples)
                x_line = df_sub['X_VN2000'].iloc[0] + offsets_fake * np.cos(g_offset)
                y_line = df_sub['Y_VN2000'].iloc[0] + offsets_fake * np.sin(g_offset)
                z_line = np.repeat(obs_zs[0], num_samples)
            else:
                # Cọc đo chuẩn chuẩn đầy đủ chữ TARGETL, TARGETR từ file khảo sát
                pct_goc = (obs_offsets - obs_offsets[0]) / (obs_offsets[-1] - obs_offsets[0] + 0.0001)
                x_line = np.interp(target_pct, pct_goc, obs_x_real)
                y_line = np.interp(target_pct, pct_goc, obs_y_real)
                z_line = np.interp(target_pct, pct_goc, obs_zs)
                
            matrix_x.append(x_line)
            matrix_y.append(y_line)
            matrix_z.append(z_line)
            
        matrix_x = np.array(matrix_x)
        matrix_y = np.array(matrix_y)
        matrix_z = np.array(matrix_z)

        # Bộ lọc làm mịn rolling trượt giảm thiểu răng cưa đáy sông
        if do_min > 1:
            mz_pd = pd.DataFrame(matrix_z)
            mz_pd = mz_pd.rolling(window=do_min, min_periods=1, center=True).mean()
            matrix_z = mz_pd.T.rolling(window=do_min, min_periods=1, center=True).mean().T.values

        z_scaled = matrix_z * he_so_z
        fig = go.Figure()

        # Dệt lưới đa giác phủ kín hành lang
        if che_do in ["Bề mặt mịn", "Lưới tam giác"]:
            show_wireframe = True if che_do == "Lưới tam giác" else False
            fig.add_trace(go.Surface(
                x=matrix_x, y=matrix_y, z=z_scaled, customdata=matrix_z,
                colorscale='Earth', opacity=0.95,
                colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
                hovertemplate="X Thực: %{x:.1f} m<br>Y Thực: %{y:.1f} m<br>Z Thực: %{customdata:.2f} m<extra></extra>",
                contours=dict(
                    x=dict(show=show_wireframe, color="rgba(0,0,0,0.2)", width=1), 
                    y=dict(show=show_wireframe, color="rgba(0,0,0,0.2)", width=1)
                )
            ))
        elif che_do == "Đường đồng mức":
            fig.add_trace(go.Surface(
                x=matrix_x, y=matrix_y, z=z_scaled, customdata=matrix_z,
                colorscale='Viridis', opacity=0.95,
                colorbar=dict(title=dict(text="Cao độ Z (m)", side="right"), thickness=15),
                contours_z=dict(show=True, usecolormap=False, color="rgb(0,0,0)", width=2, project=dict(z=True)),
                hovertemplate="X: %{x:.1f}<br>Y: %{y:.1f}<br>Z Thực: %{customdata:.2f} m<extra></extra>"
            ))

        # ĐƯỜNG CHỈ TIM TUYẾN MÀU ĐỎ VÀ HIỂN THỊ TÊN CỌC + LÝ TRÌNH DỌC SÔNG
        df_tim_all = df_clean[df_clean['Offset'] == 0].drop_duplicates(subset=['Lý trình']).sort_values('Lý trình')
        if not df_tim_all.empty:
            nhan_hien_thi = df_tim_all.apply(lambda r: f"{r['Cọc']} (LT: {r['Lý trình']:.1f}m)", axis=1).values
            fig.add_trace(go.Scatter3d(
                x=df_tim_all['X_Real'].values, y=df_tim_all['Y_Real'].values, z=df_tim_all['Z'].values * he_so_z,
                mode='lines+markers+text',
                line=dict(color='red', width=4), marker=dict(size=4, color='yellow'),
                text=nhan_hien_thi, textposition="top center",
                textfont=dict(family="Arial, sans-serif", size=11, color="lightblue"),
                name='Đường tim tuyến dọc sông'
            ))

        fig.update_layout(
            title=dict(text="🏔️ MÔ HÌNH ĐỊA HÌNH KHÔNG GIAN 3D BÁM SÁT TOÀN TUYẾN NTD", font=dict(size=16, color='#007acc')),
            height=850,  # ✨ THÊM DÒNG NÀY: Ép chiều cao khung nhìn rộng ra (tăng từ mặc định lên 850px)
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
        return fig, matrix_x, matrix_y, matrix_z
    except Exception as e:
        st.error(f"Lỗi phân tích đồ họa không gian: {e}")
        return None, None, None, None

# =========================================================================
# ⚙️ PHÂN HỆ XỬ LÝ ĐỊA CHẤT NÂNG CAO - LÀM SẠCH VÀ CHUẨN HÓA 100%
# =========================================================================

def doc_excel_dia_chat_3_sheet(uploaded_file):
    """
    Đọc file Excel địa chất gồm 3 phần:
    - Sheet tọa độ hố khoan (tên chứa 'Toado' hoặc 'TỌA ĐỘ')
    - Các sheet chi tiết lớp đất (mỗi sheet tên là mã hố khoan)
    - Sheet SPT (tên chứa 'SPT')
    Trả về df_hk, df_layers, df_spt
    """
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        # 1. Tìm sheet tọa độ (không phân biệt hoa thường, bỏ dấu cách, gạch dưới)
        sheet_toado = [s for s in sheet_names if 'toado' in s.lower().replace('_','').replace(' ','')]
        if not sheet_toado:
            st.error("Không tìm thấy sheet tọa độ hố khoan. Hãy đặt tên sheet chứa 'Toado'.")
            return None, None, None
        
        df_hk_raw = pd.read_excel(uploaded_file, sheet_name=sheet_toado[0])
        # Chuẩn hóa tên cột: bỏ khoảng trắng thừa, viết hoa, bỏ dấu ngoặc
        original_columns = list(df_hk_raw.columns)
        df_hk_raw.columns = [re.sub(r'[\(\)\[\]]', '', ' '.join(str(c).split())).upper() for c in original_columns]
        
        # In ra tất cả các cột để debug
        st.write("📋 Các cột trong sheet tọa độ:", list(df_hk_raw.columns))
        
        # Từ khóa tìm kiếm mở rộng cho từng loại cột
        keywords_name = ['HỐ KHOAN','HO KHOAN','TÊN HỐ KHOAN','TEN HO KHOAN','TÊN CỌC','TEN COC','CỌC','COC','HK','NAME','TÊN','TEN','HỐ','HO']
        keywords_x = ['X_VN2000','X VN2000','X=','X =','X_VN','X VN','X_TOA_DO','X TOA DO','TOẠ ĐỘ X','TOA DO X','X_M','X M','X']
        keywords_y = ['Y_VN2000','Y VN2000','Y=','Y =','Y_VN','Y VN','Y_TOA_DO','Y TOA DO','TOẠ ĐỘ Y','TOA DO Y','Y_M','Y M','Y']
        keywords_z = ['Z_MIENG','Z MIỆNG','Z_M','Z M','CAO ĐỘ MIỆNG','CAO DO MIENG','CAO ĐỘ','CAO DO','Z','ELEVATION','ĐỘ CAO','DO CAO']
        
        def find_column(cols, keywords):
            for col in cols:
                col_clean = col.strip().upper()
                # Kiểm tra chính xác hoặc chứa từ khóa
                for kw in keywords:
                    if col_clean == kw or kw in col_clean:
                        return col
            return None
        
        col_name = find_column(df_hk_raw.columns, keywords_name)
        col_x = find_column(df_hk_raw.columns, keywords_x)
        col_y = find_column(df_hk_raw.columns, keywords_y)
        col_z = find_column(df_hk_raw.columns, keywords_z)
        
        if col_name is None or col_x is None or col_y is None:
            missing = []
            if col_name is None: missing.append("Tên hố khoan")
            if col_x is None: missing.append("X")
            if col_y is None: missing.append("Y")
            st.error(f"❌ Thiếu cột: {', '.join(missing)}. Vui lòng đảm bảo file Excel có các cột này. Các cột hiện có: {list(df_hk_raw.columns)}")
            return None, None, None
        
        df_hk = pd.DataFrame({
            'Ho_Khoan': df_hk_raw[col_name].astype(str).str.strip().str.upper(),
            'X_VN2000': pd.to_numeric(df_hk_raw[col_x], errors='coerce'),
            'Y_VN2000': pd.to_numeric(df_hk_raw[col_y], errors='coerce'),
            'Z_Mieng': pd.to_numeric(df_hk_raw[col_z], errors='coerce') if col_z else 0.0
        }).dropna(subset=['X_VN2000', 'Y_VN2000']).reset_index(drop=True)
        
        if df_hk.empty:
            st.error("Không có dữ liệu hố khoan hợp lệ (X,Y bị thiếu).")
            return None, None, None
            
                # 2. Đọc chi tiết lớp đất từ các sheet không phải tọa độ và không phải SPT
        list_layers = []
        skip_sheets = [s.lower() for s in sheet_toado]
        for sheet in sheet_names:
            if sheet.lower() in skip_sheets or 'spt' in sheet.lower():
                continue
            df_layer_raw = pd.read_excel(uploaded_file, sheet_name=sheet)
            if df_layer_raw.empty:
                continue
            # Chuẩn hóa tên cột: bỏ khoảng trắng thừa, viết hoa
            df_layer_raw.columns = ['_'.join(str(c).split()).upper() for c in df_layer_raw.columns]
            
            # --- Tìm cột tên hố khoan trong sheet (ưu tiên 'HO_KHOAN', 'HỐ KHOAN', ...) ---
            col_hk_name = None
            for col in df_layer_raw.columns:
                col_clean = col.strip().upper()
                if 'HO_KHOAN' in col_clean or 'HỐ KHOAN' in col_clean or 'TÊN HỐ' in col_clean or 'TEN HO' in col_clean:
                    col_hk_name = col
                    break
            # Nếu không tìm thấy cột tên hố, thử lấy cột đầu tiên (có thể chứa tên hố lặp lại)
            if col_hk_name is None:
                col_hk_name = df_layer_raw.columns[0]
            
            # Lấy giá trị tên hố khoan duy nhất từ cột đó (bỏ qua NA)
            hk_values = df_layer_raw[col_hk_name].dropna().astype(str).str.strip().str.upper().unique()
            if len(hk_values) == 0:
                st.warning(f"Sheet '{sheet}' không tìm thấy tên hố khoan, bỏ qua.")
                continue
            ten_hk_sheet = hk_values[0]  # ví dụ: 'CVVVD-T4'
            
            # --- Tìm cột tên lớp, độ sâu từ, độ sâu đến ---
            col_lop = find_column(df_layer_raw.columns, ['TÊN LỚP','LỚP','ĐẤT','LOAI','MÔ TẢ','DESCRIPTION','TEN LOP','TEN_LOP'])
            col_tu = find_column(df_layer_raw.columns, ['TỪ','CHIỀU SÂU TỪ','DEPTH FROM','FROM','TOP','ĐỘ SÂU TỪ', 'TU_CHIEU_SAU'])
            col_den = find_column(df_layer_raw.columns, ['ĐẾN','CHIỀU SÂU ĐẾN','DEPTH TO','TO','BOTTOM','ĐỘ SÂU ĐẾN', 'DEN_CHIEU_SAU'])
            
            # Fallback nếu không tìm thấy
            if col_lop is None:
                col_lop = df_layer_raw.columns[0]
            if col_tu is None and len(df_layer_raw.columns) > 1:
                col_tu = df_layer_raw.columns[1]
            if col_den is None and len(df_layer_raw.columns) > 2:
                col_den = df_layer_raw.columns[2]
            
            if col_tu is None or col_den is None:
                st.warning(f"Sheet '{sheet}' không đủ cột độ sâu, bỏ qua.")
                continue
            
            # --- Duyệt từng dòng để lấy lớp đất ---
            for _, r in df_layer_raw.iterrows():
                # Kiểm tra tên hố khoan trong dòng (nếu khác với ten_hk_sheet thì bỏ qua)
                hk_cell = str(r[col_hk_name]).strip().upper() if col_hk_name in r else ten_hk_sheet
                if hk_cell != ten_hk_sheet:
                    continue
                try:
                    tu_v = float(str(r[col_tu]).replace(',', '.'))
                    den_v = float(str(r[col_den]).replace(',', '.'))
                    if pd.isna(tu_v) or pd.isna(den_v):
                        continue
                    list_layers.append({
                        'Ho_Khoan': ten_hk_sheet,
                        'Tu_Chieu_Sau_Lop': tu_v,
                        'Den_Chieu_Sau_Lop': den_v,
                        'Ten_Lop': str(r[col_lop]).strip().upper()
                    })
                except:
                    continue
        
        df_layers = pd.DataFrame(list_layers)
        
        # 3. Đọc SPT
        df_spt = None
        sheet_spt = [s for s in sheet_names if 'spt' in s.lower()]
        if sheet_spt:
            df_spt = pd.read_excel(uploaded_file, sheet_name=sheet_spt[0])
            df_spt.columns = [' '.join(str(c).split()) for c in df_spt.columns]
        
        return df_hk, df_layers, df_spt
    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu địa chất: {e}")
        return None, None, None

def _lam_sach_ten_hk(text):
    """
    Chuẩn hóa tên hố khoan: 
    - Bỏ dấu tiếng Việt (chuyển về không dấu)
    - Giữ lại chữ cái và số, bỏ khoảng trắng và ký tự đặc biệt
    - Viết hoa
    """
    s = str(text).strip()
    # Chuyển về dạng NFD để tách dấu
    s = unicodedata.normalize('NFD', s)
    # Lọc chỉ giữ ký tự chữ, số, dấu cách (sau đó sẽ bỏ dấu cách)
    s = ''.join(c for c in s if not unicodedata.combining(c))  # bỏ dấu
    # Bây giờ chỉ giữ chữ cái, số
    s = re.sub(r'[^A-Za-z0-9]', '', s)
    return s.upper()

def _tinh_tuyen_dia_hinh(matrix_x, matrix_y):
    """
    Xác định tim tuyến địa hình và lý trình tích lũy trên từng mặt cắt ngang.
    Trả về: (chainage_rows, ux, uy, x0, y0) — hướng và gốc chiếu dọc tuyến.
    """
    mid = matrix_x.shape[1] // 2
    cx = matrix_x[:, mid]
    cy = matrix_y[:, mid]
    dx = np.diff(cx)
    dy = np.diff(cy)
    chainage = np.zeros(len(cx))
    chainage[1:] = np.cumsum(np.sqrt(dx ** 2 + dy ** 2))
    x0, y0 = cx[0], cy[0]
    x1, y1 = cx[-1], cy[-1]
    vlen = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2) + 1e-6
    return chainage, (x1 - x0) / vlen, (y1 - y0) / vlen, x0, y0

def _chainage_diem(x, y, ux, uy, x0, y0):
    return (x - x0) * ux + (y - y0) * uy

def _xay_dung_ho_so_lop(df_hk_v, df_layers, lop_dat, ext_m=50.0):
    """
    Dựng profile đáy lớp dọc tuyến:
    - Mỗi hố khoan đóng góp một điểm (chainage, cao độ đáy lớp).
    - Nội suy tuyến tính giữa các hố.
    - Kéo dài thêm ext_m về hai phía.
    """
    pt_c, pt_z = [], []
    for _, hk in df_hk_v.iterrows():
        sub = df_layers[(df_layers['Key_HK'] == hk['Key_HK']) & (df_layers['Ten_Lop'] == lop_dat)]
        if sub.empty:
            continue
        # Lấy độ sâu đáy lớn nhất của lớp này tại hố khoan
        max_bottom = sub['Den_Chieu_Sau_Lop'].max()
        z_bot = hk['Z_Mieng'] - max_bottom
        pt_c.append(hk['Chainage'])
        pt_z.append(z_bot)
    
    if len(pt_c) < 2:
        return None, None
    
    # Sắp xếp theo chainage
    idx = np.argsort(pt_c)
    c_arr = np.array(pt_c)[idx]
    z_arr = np.array(pt_z)[idx]
    
    # Kéo dài hai đầu
    c_arr = np.insert(c_arr, 0, c_arr[0] - ext_m)
    z_arr = np.insert(z_arr, 0, z_arr[0])
    c_arr = np.append(c_arr, c_arr[-1] + ext_m)
    z_arr = np.append(z_arr, z_arr[-1])
    
    return c_arr, z_arr

def _mask_bien_xy_dia_hinh(matrix_x, matrix_y):
    """
    Mặt nạ 2D: ô lưới nằm trong đa giác biên địa hình (viền ngoài lưới khảo sát).
    Chiếu thẳng đứng → phạm vi X,Y mặt phẳng lớp đất trùng phạm vi địa hình.
    """
    nr, nc = matrix_x.shape
    bien_trai = np.column_stack([matrix_x[:, 0], matrix_y[:, 0]])
    bien_phai = np.column_stack([matrix_x[:, -1], matrix_y[:, -1]])[::-1]
    bien_duoi = np.column_stack([matrix_x[-1, :], matrix_y[-1, :]])
    bien_tren = np.column_stack([matrix_x[0, :], matrix_y[0, :]])[::-1]
    polygon = np.vstack([bien_trai, bien_duoi, bien_phai, bien_tren])

    xq = matrix_x.ravel()
    yq = matrix_y.ravel()
    inside = np.zeros(xq.shape, dtype=bool)
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        cond = ((y1 > yq) != (y2 > yq)) & (xq < (x2 - x1) * (yq - y1) / (y2 - y1 + 1e-9) + x1)
        inside ^= cond
    return inside.reshape(matrix_x.shape)

def _dag_luoi_mat_lop(chainage_rows, c_arr, z_arr, shape):
    """Nội suy cao độ mặt phẳng lớp dọc tuyến, trải ngang theo từng mặt cắt địa hình."""
    grid_z = np.full(shape, np.nan)
    for i, c_row in enumerate(chainage_rows):
        grid_z[i, :] = float(np.interp(c_row, c_arr, z_arr))
    return grid_z

def _cat_lop_duoi_dia_hinh(grid_z, matrix_z, eps=0.05):
    """Ép mặt lớp nằm dưới (hoặc sát) bề mặt địa hình tại cùng (X,Y)."""
    out = grid_z.copy()
    valid = ~np.isnan(out) & ~np.isnan(matrix_z)
    out[valid] = np.minimum(out[valid], matrix_z[valid] - eps)
    return out

def _tao_mat_phang_lop_3d(matrix_x, matrix_y, matrix_z, chainage_rows, c_arr, z_arr,
                          he_so_z=1.0, cat_duoi_dia_hinh=True):
    """
    Tạo lưới mặt phẳng 3D đại diện đáy một lớp đất:
    - X,Y bám lưới địa hình (chiếu thẳng đứng).
    - Z nội suy từ hố khoan dọc tuyến, trải ngang full bề rộng mặt cắt.
    """
    grid_z = _dag_luoi_mat_lop(chainage_rows, c_arr, z_arr, matrix_x.shape)
    mask_xy = _mask_bien_xy_dia_hinh(matrix_x, matrix_y)
    grid_z[~mask_xy] = np.nan
    if cat_duoi_dia_hinh:
        grid_z = _cat_lop_duoi_dia_hinh(grid_z, matrix_z)
    return grid_z, grid_z * he_so_z

def _thu_tu_lop_dat(df_layers):
    """Sắp xếp lớp từ nông → sâu dựa trên độ sâu đỉnh trung bình."""
    # Chuẩn hóa tên cột: tìm cột chứa tên lớp (không phân biệt hoa/thường, có thể có space)
    col_ten = None
    for col in df_layers.columns:
        col_clean = col.strip().upper()
        if 'TEN LOP' in col_clean or 'TÊN LỚP' in col_clean or 'TEN_LOP' in col_clean or 'TENLOP' in col_clean:
            col_ten = col
            break
    if col_ten is None:
        st.error("Không tìm thấy cột tên lớp (TEN_LOP) trong dữ liệu địa tầng.")
        return []
    
    # Tính độ sâu đỉnh trung bình cho mỗi lớp
    depth = df_layers.groupby(col_ten)['Tu_Chieu_Sau_Lop'].mean()
    # Sắp xếp theo depth tăng dần (từ nông xuống sâu)
    danh_sach = depth.sort_values().index.tolist()
    return danh_sach

def dap_them_ket_cau_dia_chat_3d(fig, df_hk, df_layers, df_spt, matrix_x, matrix_y, matrix_z, he_so_z=1.0,
                                 hien_mat_phang_lop=True, hien_khoi_lop=False, do_trong_dia_hinh=0.72):
    if fig is None or df_hk is None or df_hk.empty or df_layers is None or df_layers.empty:
        st.warning("Không đủ dữ liệu địa chất để vẽ.")
        return fig
    if matrix_x is None or matrix_y is None or matrix_z is None:
        st.warning("Chưa có lưới địa hình (matrix_x, matrix_y, matrix_z).")
        return fig

    # Chuẩn hóa tên hố khoan
    df_hk_clean = df_hk.copy()
    df_layers_clean = df_layers.copy()
    df_hk_clean['Key_HK'] = df_hk_clean['Ho_Khoan'].apply(_lam_sach_ten_hk)
    df_layers_clean['Key_HK'] = df_layers_clean['Ho_Khoan'].apply(_lam_sach_ten_hk)

    # Debug (có thể tắt sau)
    st.write("🔍 Key hố khoan từ sheet tọa độ:", df_hk_clean['Key_HK'].unique())
    st.write("🔍 Key hố khoan từ sheet lớp đất:", df_layers_clean['Key_HK'].unique())
    chung = set(df_hk_clean['Key_HK']) & set(df_layers_clean['Key_HK'])
    if not chung:
        st.error("❌ Tên hố khoan không khớp!")
        return fig

    # Tạo chainage dọc tuyến từ lưới địa hình
    chainage_rows, ux, uy, x0, y0 = _tinh_tuyen_dia_hinh(matrix_x, matrix_y)
    df_hk_clean['Chainage'] = df_hk_clean.apply(
        lambda r: _chainage_diem(r['X_VN2000'], r['Y_VN2000'], ux, uy, x0, y0), axis=1
    )
    df_hk_v = df_hk_clean.sort_values('Chainage').reset_index(drop=True)
    chainage_min = df_hk_v['Chainage'].min()
    chainage_max = df_hk_v['Chainage'].max()
    chainage_allow_min = chainage_min - 10.0
    chainage_allow_max = chainage_max + 10.0

    # Tạo mặt nạ dọc tuyến: chỉ giữ các hàng có chainage trong khoảng cho phép
    mask_chainage = (chainage_rows >= chainage_allow_min) & (chainage_rows <= chainage_allow_max)
    # Danh sách lớp theo thứ tự nông → sâu
    danh_sach_lop = _thu_tu_lop_dat(df_layers_clean)
    st.write("📋 Các lớp đất (từ trên xuống):", danh_sach_lop)

    # Màu sắc cho các lớp
    mau_sac = ['#d73027', '#f46d43', '#fdae61', '#fee090', '#e0f3f8', '#abd9e9', '#74add1', '#4575b4', '#313695', '#a6d96a']

    for idx, lop in enumerate(danh_sach_lop):
        c_arr, z_arr = _xay_dung_ho_so_lop(df_hk_v, df_layers_clean, lop, ext_m=50.0)
        if c_arr is None:
            st.warning(f"Không đủ điểm cho lớp {lop}, bỏ qua.")
            continue

        # Tạo lưới mặt phẳng đáy lớp
        grid_z = _dag_luoi_mat_lop(chainage_rows, c_arr, z_arr, matrix_x.shape)
        mask_xy = _mask_bien_xy_dia_hinh(matrix_x, matrix_y)
        grid_z[~mask_xy] = np.nan
        # Cắt không cho mặt lớp vượt quá bề mặt địa hình
        grid_z = _cat_lop_duoi_dia_hinh(grid_z, matrix_z, eps=0.05)
        grid_z[~mask_chainage, :] = np.nan
        grid_z_scaled = grid_z * he_so_z

        if np.all(np.isnan(grid_z)):
            continue

        if hien_mat_phang_lop:
            fig.add_trace(go.Surface(
                x=matrix_x, y=matrix_y, z=grid_z_scaled,
                colorscale=[[0, mau_sac[idx % len(mau_sac)]], [1, mau_sac[idx % len(mau_sac)]]],
                opacity=0.65, showscale=False,
                name=f"Đáy lớp {lop}",
                hovertemplate=f"Lớp {lop}<br>X: %{{x:.1f}}<br>Y: %{{y:.1f}}<br>Z đáy: %{{z:.2f}}<extra></extra>"
            ))

        # Nếu muốn vẽ khối (thể tích) thì cần xử lý thêm, tạm thời bỏ qua
        if hien_khoi_lop:
            pass

    return fig