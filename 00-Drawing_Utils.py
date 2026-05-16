import numpy as np
import plotly.graph_objects as go

def ve_ky_hieu_muc_nuoc_plotly(fig, x_pos, y_val, label, color):
    """Vẽ ký hiệu mực nước tương tác bằng nét vẽ của Plotly"""
    # Vẽ đường ngang mực nước (Dài 8m vây quanh vị trí đặt)
    fig.add_trace(go.Scatter(
        x=[x_pos - 4, x_pos + 4],
        y=[y_val, y_val],
        mode="lines",
        line=dict(color=color, width=1.5),
        showlegend=False,
        hoverinfo="skip"
    ))
    # Tạo nhãn chữ hiển thị thông số cao độ ngay phía trên nét gạch
    fig.add_trace(go.Scatter(
        x=[x_pos],
        y=[y_val + 0.3],
        mode="text",
        text=[f"{label}<br>{y_val:.3f}m"],
        textposition="top center",
        textfont=dict(color=color, size=9, family="Arial Black"),
        showlegend=False,
        hoverinfo="skip"
    ))

def ve_trac_doc_cau(res):
    """Vẽ sơ họa trắc dọc cầu bằng Plotly - Phân tách màu sắc đoạn Dốc thẳng và Đường cong đứng"""
    geo = res.get('geo_logic')
    if not geo:
        return None
        
    # --- 1. LẤY DỮ LIỆU ĐẦU VÀO VÀ ĐỔI GỐC TỌA ĐỘ VỀ (0,0) ---
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h10 = res.get('MNTC', 0)
    h98 = res.get('MNTN', 0)
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    label_res = res.get('label', "")
    is_duong_bo = "vượt đường bộ" in label_res.lower()
    
    y_base_goc = h1 if is_duong_bo else h5
    x_dinh_cu = geo.get('x_dinh', 150)
    l_cau_thuc = geo.get('L_cau', 120)
    
    # Chuyển đổi tọa độ các điểm gãy hình học sang hệ tọa độ mới (Tim = 0)
    x_t1_moi = geo['x_t1'] - x_dinh_cu
    x_t2_moi = geo['x_t2'] - x_dinh_cu
    x_mo_trai_moi = -l_cau_thuc / 2
    x_mo_phai_moi = l_cau_thuc / 2
    
    x_start_view = x_mo_trai_moi - 50
    x_limit_view = x_mo_phai_moi + 50
    
    h_dam_ai = res.get('ai_result', {}).get('chieu_cao', 1.65)
    h_ban_mat_cau = 0.18
    h_tong_ket_cau = h_ban_mat_cau + h_dam_ai

    # --- 2. TẠO MẢNG RIÊNG BIỆT CHO TỪNG PHÂN ĐOẠN HÌNH HỌC ---
    # Việc chia nhỏ dải điểm giúp Plotly tô màu độc lập từng đoạn mà không bị dính nét
    x_doc_trai = np.linspace(x_start_view, x_t1_moi, 300)
    x_cong_dung = np.linspace(x_t1_moi, x_t2_moi, 500)
    x_doc_phai = np.linspace(x_t2_moi, x_limit_view, 300)
    
    # Hàm tính cao độ phụ thuộc hệ trục mới (Y đã trừ y_base_goc)
    def tinh_y_moi(xi_moi):
        xi_cu = xi_moi + x_dinh_cu
        if xi_cu < geo['x_t1']:
            return (geo['y_t'] - geo['i_val'] * (geo['x_t1'] - xi_cu)) - y_base_goc
        elif xi_cu > geo['x_t2']:
            return (geo['y_t'] - geo['i_val'] * (xi_cu - geo['x_t2'])) - y_base_goc
        else:
            return (geo['y_dinh'] - (xi_cu - x_dinh_cu)**2 / (2 * geo['R'])) - y_base_goc

    y_doc_trai = np.array([tinh_y_moi(xi) for xi in x_doc_trai])
    y_cong_dung = np.array([tinh_y_moi(xi) for xi in x_cong_dung])
    y_doc_phai = np.array([tinh_y_moi(xi) for xi in x_doc_phai])

    # --- 3. KHỞI TẠO BIỂU ĐỒ PLOTLY ---
    fig = go.Figure()

    # 3.1 Vẽ Đường tự nhiên trung bình nền
    h_tn_tb_moi = geo.get('h_tn_tb', 3.0) - y_base_goc
    x_full = np.concatenate([x_doc_trai, x_cong_dung, x_doc_phai])
    fig.add_trace(go.Scatter(x=x_full, y=np.full_like(x_full, h_tn_tb_moi), name="Đường TN trung bình", line=dict(color='#27ae60', width=1.5, dash='dash')))

    # 3.2 THỂ HIỆN TRỰC QUAN ĐƯỜNG ĐỎ THEO PHÂN ĐOẠN (ĐỔI MÀU NÉT VẼ)
    # Đoạn dốc dọc bên trái (Nét liền màu Cam đậm)
    fig.add_trace(go.Scatter(
        x=x_doc_trai, y=y_doc_trai,
        name=f"Đoạn dốc dọc trái (i={geo['i_val']*100:.1f}%)",
        line=dict(color='#e67e22', width=3.5)
    ))
    
    # Đoạn đường cong đứng Parabol (Nét liền màu Đỏ rực)
    fig.add_trace(go.Scatter(
        x=x_cong_dung, y=y_cong_dung,
        name=f"Đoạn đường cong đứng (R={geo['R']}m)",
        line=dict(color='#e74c3c', width=4.5)
    ))
    
    # Đoạn dốc dọc bên phải (Nét liền màu Cam đậm)
    fig.add_trace(go.Scatter(
        x=x_doc_phai, y=y_doc_phai,
        name=f"Đoạn dốc dọc phải (i={geo['i_val']*100:.1f}%)",
        line=dict(color='#e67e22', width=3.5)
    ))

    # 3.3 Vẽ đường Đáy dầm thiết kế tương ứng (Dùng nét đứt màu xanh biển)
    fig.add_trace(go.Scatter(x=x_full, y=np.concatenate([y_doc_trai, y_cong_dung, y_doc_phai]) - h_tong_ket_cau, 
                             name="Đường đáy dầm", line=dict(color='darkblue', width=2, dash='dashdot')))

    # 3.4 THÊM ĐƯỜNG GIÓNG RÀNH GIỚI VÀO BIỂU ĐỒ (MÉP ĐƯỜNG CONG ĐỨNG)
    # Đường gióng Tiếp điểm 1 (Bắt đầu vào đường cong)
    fig.add_shape(type="line", x0=x_t1_moi, y0=h_tn_tb_moi, x1=x_t1_moi, y1=tinh_y_moi(x_t1_moi),
                  line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t1_moi, y=h_tn_tb_moi - 1, text="Tiếp điểm T1<br>(Vào đường cong)", showarrow=False, font=dict(size=9, color="#7f8c8d"))

    # Đường gióng Tiếp điểm 2 (Hết đường cong, vào dốc thẳng)
    fig.add_shape(type="line", x0=x_t2_moi, y0=h_tn_tb_moi, x1=x_t2_moi, y1=tinh_y_moi(x_t2_moi),
                  line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t2_moi, y=h_tn_tb_moi - 1, text="Tiếp điểm T2<br>(Hết đường cong)", showarrow=False, font=dict(size=9, color="#7f8c8d"))

    # 3.5 Bố trí Khung tĩnh không kỹ thuật và các yếu tố phụ trợ khác
    if B > 0 and H_tk > 0:
        fig.add_shape(type="rect", x0=-B/2, y0=0, x1=B/2, y1=H_tk, line=dict(color="magenta", width=2), fillcolor="rgba(255, 0, 255, 0.08)")
    if not is_duong_bo:
        ve_ky_hieu_muc_nuoc_plotly(fig, -15, h5 - y_base_goc, "MNTT H5% (Y=0)", "blue")

    # Vẽ vị trí mố cầu
    y_mo_moi = geo['y_mo'] - y_base_goc
    fig.add_trace(go.Scatter(x=[x_mo_trai_moi, x_mo_trai_moi], y=[h_tn_tb_moi, y_mo_moi], name="Mố Trái", line=dict(color='brown', width=3, dash='dash')))
    fig.add_trace(go.Scatter(x=[x_mo_phai_moi, x_mo_phai_moi], y=[h_tn_tb_moi, y_mo_moi], name="Mố Phải", line=dict(color='brown', width=3, dash='dash')))

    # --- 4. THIẾT LẬP GIAO DIỆN ---
    fig.update_layout(
        title=dict(text=f"TRẮC DỌC CẦU - PHÂN TÁCH ĐOẠN CONG ĐỨNG VÀ ĐOẠN DỐC THẲNG (1-1)", x=0.5),
        xaxis=dict(title="Khoảng cách tính từ Tim cầu (m)", range=[x_start_view, x_limit_view], showgrid=True),
        yaxis=dict(title="Cao độ tương đối (m)", scaleanchor="x", scaleratio=1, showgrid=True, zeroline=True, zerolinecolor="black"),
        height=550,
        template="plotly_white",
        dragmode='pan',
        hovermode="x unified"
    )
    
    return fig

def ve_mat_cat_ngang(res_mcn):
    """Vẽ mặt cắt ngang cầu điển hình bằng Plotly - Khóa tỷ lệ 1-1"""
    bc = res_mcn.get('bc_cau', 12.0)
    w_lc = res_mcn.get('w_lc', 0.5)   # Mặc định bề rộng gờ lan can
    
    fig = go.Figure()

    # Vẽ Khối bản mặt cầu bê tông (Hình hộp chữ nhật dày 25cm)
    fig.add_trace(go.Scatter(
        x=[-bc/2, bc/2, bc/2, -bc/2, -bc/2],
        y=[0, 0, -0.25, -0.25, 0],
        fill="toself",
        fillcolor="#bdc3c7",
        line=dict(color="black", width=2),
        name="Bản mặt cầu",
        hoverinfo="skip"
    ))

    # Vẽ gờ chắn lan can bên trái
    fig.add_trace(go.Scatter(
        x=[-bc/2, -bc/2 + w_lc, -bc/2 + w_lc, -bc/2, -bc/2],
        y=[0, 0, 0.4, 0.4, 0],
        fill="toself", fillcolor="#7f8c8d",
        line=dict(color="black", width=1.5),
        showlegend=False, hoverinfo="skip"
    ))
    
    # Vẽ gờ chắn lan can bên phải
    fig.add_trace(go.Scatter(
        x=[bc/2 - w_lc, bc/2, bc/2, bc/2 - w_lc, bc/2 - w_lc],
        y=[0, 0, 0.4, 0.4, 0],
        fill="toself", fillcolor="#7f8c8d",
        line=dict(color="black", width=1.5),
        showlegend=False, hoverinfo="skip"
    ))

    # Khóa trục tỷ lệ 1-1 cho mặt cắt ngang
    fig.update_layout(
        title=dict(text=f"MẶT CẮT NGANG CẦU ĐIỂN HÌNH (B_cầu = {bc}m)", x=0.5),
        xaxis=dict(title="Bề rộng cầu (m)", range=[-bc/2 - 2, bc/2 + 2], showgrid=False, zeroline=True),
        yaxis=dict(
            title="Chiều cao cấu tạo (m)",
            scaleanchor="x",
            scaleratio=1, # Tỉ lệ 1-1 thực thụ
            range=[-1, 2],
            showgrid=False
        ),
        height=380,
        template="plotly_white",
        dragmode='pan'
    )
    
    return fig