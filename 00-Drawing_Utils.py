import numpy as np
import plotly.graph_objects as go

def ve_ky_hieu_muc_nuoc_plotly(fig, x_pos, y_val, label, color):
    """Vẽ ký hiệu mực nước tương tác bằng nét vẽ của Plotly"""
    fig.add_trace(go.Scatter(
        x=[x_pos - 6, x_pos + 6], y=[y_val, y_val],
        mode="lines", line=dict(color=color, width=1.5),
        showlegend=False, hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=[x_pos], y=[y_val + 0.3],
        mode="text", text=[f"{label}<br>{y_val:.3f}m"],
        textposition="top center", textfont=dict(color=color, size=9),
        showlegend=False, hoverinfo="skip"
    ))

def ve_trac_doc_cau(res, df_tim_line=None):
    """Vẽ sơ họa trắc dọc cầu, có thể chèn đường địa hình từ dữ liệu khảo sát"""
    geo = res.get('geo_logic')
    if not geo:
        return None

    y_base_goc = geo.get('y_base_goc', 0)
    l_cau_thuc = geo.get('L_cau', 120)
    x_t1, x_t2 = geo['x_t1'], geo['x_t2']

    h1 = res.get('MNCN', 0) - y_base_goc
    h5 = res.get('MNTT', 0) - y_base_goc
    h10 = res.get('MNTC', 0) - y_base_goc
    h98 = res.get('MNTN', 0) - y_base_goc
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    label_res = res.get('label', "")
    is_duong_bo = "vượt đường bộ" in label_res.lower()

    x_start_view = geo['x_mo_trai'] - 60
    x_limit_view = geo['x_mo_phai'] + 60

    h_dam_ai = res.get('ai_result', {}).get('chieu_cao', 1.65)
    h_tong_ket_cau = 0.18 + h_dam_ai

    # Đường cong đứng và dốc
    x_doc_trai = np.linspace(x_start_view, x_t1, 400)
    x_cong_dung = np.linspace(x_t1, x_t2, 600)
    x_doc_phai = np.linspace(x_t2, x_limit_view, 400)

    def y_duong_do(xi):
        if xi < x_t1:
            return geo['y_t'] - geo['i_val'] * (x_t1 - xi)
        elif xi > x_t2:
            return geo['y_t'] - geo['i_val'] * (xi - x_t2)
        else:
            return geo['y_dinh'] - xi**2 / (2 * geo['R'])

    y_doc_trai = np.array([y_duong_do(x) for x in x_doc_trai])
    y_cong_dung = np.array([y_duong_do(x) for x in x_cong_dung])
    y_doc_phai = np.array([y_duong_do(x) for x in x_doc_phai])
    x_full = np.concatenate([x_doc_trai, x_cong_dung, x_doc_phai])
    y_full = np.concatenate([y_doc_trai, y_cong_dung, y_doc_phai])

    fig = go.Figure()

    # --- ĐƯỜNG ĐỊA HÌNH TỰ NHIÊN ---
    if df_tim_line is not None and not df_tim_line.empty:
        mask = (df_tim_line['Lý trình'] >= x_start_view) & (df_tim_line['Lý trình'] <= x_limit_view)
        df_view = df_tim_line[mask].copy()
        if not df_view.empty:
            y_tn = df_view['Z'] - y_base_goc
            fig.add_trace(go.Scatter(
                x=df_view['Lý trình'], y=y_tn,
                name="Địa hình tự nhiên (tim tuyến)",
                line=dict(color='#27ae60', width=2),
                mode='lines'
            ))
        else:
            h_tb = geo['h_tn_tb'] - y_base_goc
            fig.add_trace(go.Scatter(
                x=[x_start_view, x_limit_view], y=[h_tb, h_tb],
                name="Đường TN trung bình (ước lượng)",
                line=dict(color='#27ae60', width=1.5, dash='dash')
            ))
    else:
        h_tb = geo['h_tn_tb'] - y_base_goc
        fig.add_trace(go.Scatter(
            x=[x_start_view, x_limit_view], y=[h_tb, h_tb],
            name="Đường TN trung bình (ước lượng)",
            line=dict(color='#27ae60', width=1.5, dash='dash')
        ))

    # Các đường khác
    fig.add_trace(go.Scatter(x=x_doc_trai, y=y_doc_trai, name=f"Đoạn dốc trái (i={geo['i_val']*100:.1f}%)", line=dict(color='#e67e22', width=3.5)))
    fig.add_trace(go.Scatter(x=x_cong_dung, y=y_cong_dung, name=f"Đường cong đứng (R={geo['R']}m)", line=dict(color='#e74c3c', width=4.5)))
    fig.add_trace(go.Scatter(x=x_doc_phai, y=y_doc_phai, name=f"Đoạn dốc phải (i={geo['i_val']*100:.1f}%)", line=dict(color='#e67e22', width=3.5)))
    fig.add_trace(go.Scatter(x=x_full, y=y_full - h_tong_ket_cau, name="Đáy dầm thiết kế", line=dict(color='darkblue', width=2, dash='dashdot')))

    # Đường gióng
    fig.add_shape(type="line", x0=x_t1, y0=y_doc_trai.min()-2, x1=x_t1, y1=y_duong_do(x_t1), line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t1, y=y_duong_do(x_t1)-3, text=f"T1<br>{x_t1:.1f}m", showarrow=False, font=dict(size=9))
    fig.add_shape(type="line", x0=x_t2, y0=y_doc_phai.min()-2, x1=x_t2, y1=y_duong_do(x_t2), line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t2, y=y_duong_do(x_t2)-3, text=f"T2<br>{x_t2:.1f}m", showarrow=False, font=dict(size=9))

    # Mố
    y_mo = geo['y_mo'] - y_base_goc
    fig.add_trace(go.Scatter(x=[geo['x_mo_trai'], geo['x_mo_trai']], y=[-10, y_mo], name="Mố Trái", line=dict(color='brown', width=3, dash='dash')))
    fig.add_trace(go.Scatter(x=[geo['x_mo_phai'], geo['x_mo_phai']], y=[-10, y_mo], name="Mố Phải", line=dict(color='brown', width=3, dash='dash')))

    # Mực nước / mặt đường
    if is_duong_bo:
        fig.add_trace(go.Scatter(x=[x_start_view, x_limit_view], y=[0, 0], name="Mặt đường bị vượt", line=dict(color='#7f8c8d', width=2.5)))
    else:
        # Gọi trực tiếp hàm ve_ky_hieu_muc_nuoc_plotly (đã định nghĩa trong file)
        ve_ky_hieu_muc_nuoc_plotly(fig, -45, h1, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc_plotly(fig, -15, h5, "MNTT H5% (Y=0)", "blue")
        ve_ky_hieu_muc_nuoc_plotly(fig, 15, h10, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc_plotly(fig, 45, h98, "MNTN H98%", "orange")

    # Khung tĩnh không
    if B > 0 and H_tk > 0:
        fig.add_shape(type="rect", x0=-B/2, y0=0, x1=B/2, y1=H_tk, line=dict(color="magenta", width=2), fillcolor="rgba(255,0,255,0.08)")
        fig.add_annotation(x=0, y=H_tk/2, text=f"TĨNH KHÔNG<br>B x H = {B}m x {H_tk}m", showarrow=False, font=dict(color="magenta", size=10))

    fig.update_layout(
        title=dict(text=f"TRẮC DỌC CẦU (L_cầu = {l_cau_thuc:.2f}m)", x=0.5),
        xaxis=dict(title="Khoảng cách từ tim cầu (m)", range=[x_start_view, x_limit_view], showgrid=True),
        yaxis=dict(title="Cao độ tương đối (m)", scaleanchor="x", scaleratio=1, showgrid=True, zeroline=True),
        height=550, template="plotly_white", dragmode='pan', hovermode="x unified"
    )
    return fig
    
    # Hàm vẽ toán học chuẩn hóa theo hệ trục gốc 0
    def tinh_y_do_hoa(xi):
        if xi < x_t1:   return geo['y_t'] - geo['i_val'] * (x_t1 - xi)
        elif xi > x_t2: return geo['y_t'] - geo['i_val'] * (xi - x_t2)
        else:           return geo['y_dinh'] - xi**2 / (2 * geo['R'])

    y_doc_trai = np.array([tinh_y_do_hoa(xi) for xi in x_doc_trai])
    y_cong_dung = np.array([tinh_y_do_hoa(xi) for xi in x_cong_dung])
    y_doc_phai = np.array([tinh_y_do_hoa(xi) for xi in x_doc_phai])
    
    x_full = np.concatenate([x_doc_trai, x_cong_dung, x_doc_phai])
    y_full = np.concatenate([y_doc_trai, y_cong_dung, y_doc_phai])

    # --- FIX LỖI: TÍNH TOÁN BIẾN CHÊNH CAO TRƯỚC KHI KHỞI TẠO BIỂU ĐỒ ---
    h_tn_tb_tuong_doi = geo['h_tn_tb'] - y_base_goc
    chenh_cao = y_full - h_tn_tb_tuong_doi

    # --- 3. KHỞI TẠO ĐỒ HỌA PLOTLY ---
    fig = go.Figure()

    # 3.1 Đường tự nhiên trung bình tương đối
    fig.add_trace(go.Scatter(x=x_full, y=np.full_like(x_full, h_tn_tb_tuong_doi), name="Đường TN trung bình", line=dict(color='#27ae60', width=1.5, dash='dash')))

    # 3.2 Vẽ 3 phân đoạn màu sắc đường đỏ
    fig.add_trace(go.Scatter(x=x_doc_trai, y=y_doc_trai, name=f"Đoạn dốc thẳng trái (i={geo['i_val']*100:.1f}%)", line=dict(color='#e67e22', width=3.5)))
    fig.add_trace(go.Scatter(x=x_cong_dung, y=y_cong_dung, name=f"Đoạn đường cong đứng (R={geo['R']}m)", line=dict(color='#e74c3c', width=4.5)))
    fig.add_trace(go.Scatter(x=x_doc_phai, y=y_doc_phai, name=f"Đoạn dốc thẳng phải (i={geo['i_val']*100:.1f}%)", line=dict(color='#e67e22', width=3.5)))

    # 3.3 Đường đáy dầm thiết kế
    fig.add_trace(go.Scatter(
        x=x_full, y=y_full - h_tong_ket_cau, 
        name="Đường đáy dầm thiết kế", 
        line=dict(color='darkblue', width=2, dash='dashdot')
    ))

    # 3.4 ĐƯỜNG ẨN HỖ TRỢ HIỂN THỊ THÔNG SỐ CHÊNH CAO ĐỘ (ĐÃ CÓ BIẾN CHÊNH_CAO CHUẨN)
    fig.add_trace(go.Scatter(
        x=x_full, 
        y=y_full, 
        name="Chênh cao (Đỏ - TN)",
        mode="lines",
        line=dict(color="rgba(0,0,0,0)", width=0), 
        customdata=chenh_cao,
        hovertemplate="%{customdata:.3f} m",       
        showlegend=False,                          
        legendgroup="chenh_cao"
    ))

    # 3.5 Đường gióng ranh giới phân tách hình học
    fig.add_shape(type="line", x0=x_t1, y0=h_tn_tb_tuong_doi, x1=x_t1, y1=tinh_y_do_hoa(x_t1), line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t1, y=h_tn_tb_tuong_doi - 1.5, text=f"Tiếp điểm T1<br>{x_t1:.1f}m", showarrow=False, font=dict(size=9, color="#7f8c8d"))

    fig.add_shape(type="line", x0=x_t2, y0=h_tn_tb_tuong_doi, x1=x_t2, y1=tinh_y_do_hoa(x_t2), line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t2, y=h_tn_tb_tuong_doi - 1.5, text=f"Tiếp điểm T2<br>{x_t2:.1f}m", showarrow=False, font=dict(size=9, color="#7f8c8d"))

    # 3.6 Bố trí các mực nước thủy văn hoặc mặt đường bị vượt tương đối
    if is_duong_bo:
        fig.add_trace(go.Scatter(x=x_full, y=np.full_like(x_full, 0), name="Mặt đường bị vượt (Y=0)", line=dict(color='#7f8c8d', width=2.5)))
    else:
        ve_ky_hieu_muc_nuoc_plotly(fig, -45, h1, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc_plotly(fig, -15, h5, "MNTT H5% (Y=0)", "blue")
        ve_ky_hieu_muc_nuoc_plotly(fig, 15, h10, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc_plotly(fig, 45, h98, "MNTN H98%", "orange")

    # 3.7 Khung khổ tĩnh không đặt ngay chính giữa gốc (0,0)
    if B > 0 and H_tk > 0:
        fig.add_shape(type="rect", x0=-B/2, y0=0, x1=B/2, y1=H_tk, line=dict(color="magenta", width=2), fillcolor="rgba(255, 0, 255, 0.08)")
        fig.add_trace(go.Scatter(x=[0], y=[H_tk / 2], mode="text", text=[f"TĨNH KHÔNG KỸ THUẬT<br>B x H = {B}m x {H_tk}m"], textposition="middle center", textfont=dict(color="magenta", size=10, family="Arial Black"), showlegend=False, hoverinfo="skip"))

    # 3.8 Vẽ mố cầu đối xứng
    y_mo_tuong_doi = geo['y_mo'] - y_base_goc
    fig.add_trace(go.Scatter(x=[geo['x_mo_trai'], geo['x_mo_trai']], y=[h_tn_tb_tuong_doi, y_mo_tuong_doi], name="Mố Trái", line=dict(color='brown', width=3, dash='dash')))
    fig.add_trace(go.Scatter(x=[geo['x_mo_phai'], geo['x_mo_phai']], y=[h_tn_tb_tuong_doi, y_mo_tuong_doi], name="Mố Phải", line=dict(color='brown', width=3, dash='dash')))

    # --- 4. THIẾT LẬP LAYOUT ---
    fig.update_layout(
        title=dict(text=f"TRẮC DỌC CẦU ĐỐI XỨNG HỌA TIẾT (L_cầu = {l_cau_thuc:.2f}m)", x=0.5),
        xaxis=dict(title="Khoảng cách tính từ Tim cầu (m)", range=[x_start_view, x_limit_view], showgrid=True),
        yaxis=dict(title="Cao độ tương đối (m)", scaleanchor="x", scaleratio=1, showgrid=True, zeroline=True, zerolinecolor="black", zerolinewidth=1.5),
        height=550, 
        template="plotly_white", 
        dragmode='pan', 
        hovermode="x unified",
        
        hoverlabel=dict(
            bgcolor="rgba(30, 30, 30, 0.85)", 
            font_size=12,
            font_family="Arial",
            font_color="white"
        )
    )
    return fig

def ve_mat_cat_ngang(res_mcn):
    bc = res_mcn.get('bc_cau', 12.0)
    w_lc = res_mcn.get('w_lc', 0.5)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[-bc/2, bc/2, bc/2, -bc/2, -bc/2], y=[0, 0, -0.25, -0.25, 0], fill="toself", fillcolor="#bdc3c7", line=dict(color="black", width=2), name="Bản mặt cầu", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[-bc/2, -bc/2 + w_lc, -bc/2 + w_lc, -bc/2, -bc/2], y=[0, 0, 0.4, 0.4, 0], fill="toself", fillcolor="#7f8c8d", line=dict(color="black", width=1.5), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[bc/2 - w_lc, bc/2, bc/2, bc/2 - w_lc, bc/2 - w_lc], y=[0, 0, 0.4, 0.4, 0], fill="toself", fillcolor="#7f8c8d", line=dict(color="black", width=1.5), showlegend=False, hoverinfo="skip"))

    fig.update_layout(
        title=dict(text=f"MẶT CẮT NGANG CẦU ĐIỂN HÌNH (B_cầu = {bc}m)", x=0.5),
        xaxis=dict(title="Bề rộng cầu (m)", range=[-bc/2 - 2, bc/2 + 2], showgrid=False, zeroline=True),
        yaxis=dict(title="Chiều cao cấu tạo (m)", scaleanchor="x", scaleratio=1, range=[-1, 2], showgrid=False),
        height=380, template="plotly_white", dragmode='pan'
    )
    return fig