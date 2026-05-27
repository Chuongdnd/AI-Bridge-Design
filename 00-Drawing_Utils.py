import numpy as np
import plotly.graph_objects as go
import streamlit as st
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
    geo = res.get('geo_logic')
    if not geo:
        return None
    
    if df_tim_line is None or df_tim_line.empty:
        st.warning("Không có dữ liệu tim tuyến")
        return None
    
    # Lấy thông tin từ geo
    x_tim = geo.get('x_tim_clearance', 0)
    x_mo_trai = geo['x_mo_trai']
    x_mo_phai = geo['x_mo_phai']
    x_t1 = geo['x_t1']
    x_t2 = geo['x_t2']
    y_dinh = geo['y_dinh']
    y_t = geo['y_t']
    R = geo['R']
    i_val = geo['i_val']
    y_base_goc = geo['y_base_goc']
    
    # Xác định phạm vi vẽ
    margin = 50
    x_start = x_mo_trai - margin
    x_end = x_mo_phai + margin
    df_view = df_tim_line[(df_tim_line['Lý trình'] >= x_start) & (df_tim_line['Lý trình'] <= x_end)].copy()
    
    if df_view.empty:
        st.warning("Không có dữ liệu tim tuyến trong phạm vi vẽ")
        return None
    
    fig = go.Figure()
    
    # 1. Đường địa hình tự nhiên
    fig.add_trace(go.Scatter(
        x=df_view['Lý trình'], y=df_view['Z'],
        mode='lines', name='Địa hình tự nhiên (tim tuyến)',
        line=dict(color='#27ae60', width=2)
    ))
    
    # 2. Đường đỏ thiết kế
    x_smooth = np.linspace(x_start, x_end, 500)
    y_red = []
    for x in x_smooth:
        if x < x_t1:
            y = y_t - i_val * (x_t1 - x)
        elif x > x_t2:
            y = y_t - i_val * (x - x_t2)
        else:
            y = y_dinh - (x - x_tim)**2 / (2 * R)
        y_red.append(y)
    fig.add_trace(go.Scatter(
        x=x_smooth, y=y_red, name='Đường đỏ thiết kế',
        line=dict(color='#e74c3c', width=3)
    ))
    
    # 3. Đáy dầm
    h_dam = res.get('ai_result', {}).get('chieu_cao', 1.65)
    h_ban = 0.18
    h_tong = h_ban + h_dam
    y_bottom = [y - h_tong for y in y_red]
    fig.add_trace(go.Scatter(
        x=x_smooth, y=y_bottom, name='Đáy dầm',
        line=dict(color='darkblue', width=2, dash='dashdot')
    ))
    
    # 4. Mố
    y_min = df_view['Z'].min()
    y_mo = geo.get('y_mo', y_min)
    fig.add_trace(go.Scatter(
        x=[x_mo_trai, x_mo_trai], y=[y_min, y_mo],
        mode='lines', name='Mố trái', line=dict(color='brown', width=3, dash='dash')
    ))
    fig.add_trace(go.Scatter(
        x=[x_mo_phai, x_mo_phai], y=[y_min, y_mo],
        mode='lines', name='Mố phải', line=dict(color='brown', width=3, dash='dash')
    ))
    
    # 5. Khung tĩnh không
    B = res.get('B', 0)
    H_tk = res.get('H', 0)
    if B > 0 and H_tk > 0:
        idx_tim = np.argmin(np.abs(x_smooth - x_tim))
        y_tim = y_red[idx_tim]
        fig.add_shape(type="rect",
                      x0=x_tim - B/2, x1=x_tim + B/2,
                      y0=y_tim - H_tk, y1=y_tim,
                      line=dict(color="magenta", width=2),
                      fillcolor="rgba(255,0,255,0.1)")
        fig.add_annotation(x=x_tim, y=y_tim - H_tk/2,
                           text=f"TĨNH KHÔNG<br>B={B}m, H={H_tk}m",
                           showarrow=False, font=dict(color="magenta", size=9))
    
    # 6. Mực nước / mặt đường bị vượt
    label_res = res.get('label', "")
    is_duong_bo = "vượt đường bộ" in label_res.lower()
    if is_duong_bo:
        fig.add_trace(go.Scatter(
            x=[x_start, x_end], y=[0, 0],
            mode='lines',
            name='Mặt đường bị vượt',
            line=dict(color='#7f8c8d', width=2, dash='dash')
        ))
    else:
        h1 = res.get('MNCN', 0) - y_base_goc
        h5 = res.get('MNTT', 0) - y_base_goc
        h10 = res.get('MNTC', 0) - y_base_goc
        h98 = res.get('MNTN', 0) - y_base_goc
        # Dùng hàm ve_ky_hieu_muc_nuoc_plotly đã có
        ve_ky_hieu_muc_nuoc_plotly(fig, x_mo_trai + 20, h1, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc_plotly(fig, x_mo_trai + 40, h5, "MNTT H5%", "blue")
        ve_ky_hieu_muc_nuoc_plotly(fig, x_mo_phai - 40, h10, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc_plotly(fig, x_mo_phai - 20, h98, "MNTN H98%", "orange")
    
    # 7. Đường gióng T1, T2
    fig.add_shape(type="line", x0=x_t1, y0=y_min-5, x1=x_t1, y1=y_t,
                  line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t1, y=y_t-3, text=f"T1<br>{x_t1:.1f}m",
                       showarrow=False, font=dict(size=9))
    fig.add_shape(type="line", x0=x_t2, y0=y_min-5, x1=x_t2, y1=y_t,
                  line=dict(color="#95a5a6", width=1.5, dash="dot"))
    fig.add_annotation(x=x_t2, y=y_t-3, text=f"T2<br>{x_t2:.1f}m",
                       showarrow=False, font=dict(size=9))
    
    # Layout với tỷ lệ 1:1 (scaleratio=1)
    fig.update_layout(
        title=f"TRẮC DỌC THEO TIM TUYẾN - Tim tĩnh không tại LT = {x_tim:.2f}m",
        xaxis_title="Lý trình (m)",
        yaxis_title="Cao độ (m)",
        xaxis=dict(scaleanchor="y", scaleratio=1),
        height=550, template="plotly_white"
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