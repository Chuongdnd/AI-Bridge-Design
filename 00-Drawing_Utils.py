import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def ve_ky_hieu_muc_nuoc(ax, x_pos, y_val, label, color):
    """Vẽ tam giác ngược và các nét gạch sóng nước chuẩn kỹ thuật"""
    d_x, d_y = 1.2, 0.8
    triangle = patches.Polygon([
        (x_pos - d_x, y_val + d_y), 
        (x_pos + d_x, y_val + d_y), 
        (x_pos, y_val)], 
        facecolor='none', edgecolor=color, lw=1.2, zorder=5)
    ax.add_patch(triangle)
    ax.plot([x_pos - 3, x_pos + 3], [y_val, y_val], color=color, lw=1.2, zorder=4)
    dash_widths = [2.0, 1.2, 0.5] 
    for i, w in enumerate(dash_widths):
        y_dash = y_val - (i + 1) * 0.25  
        ax.plot([x_pos - w/2, x_pos + w/2], [y_dash, y_dash], color=color, lw=0.8)
    ax.text(x_pos, y_val + d_y + 0.3, f"{label}\n{y_val:.3f}m", 
            ha='center', va='bottom', color=color, fontsize=9, fontweight='bold',
            bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=0))

def ve_trac_doc_cau(res):
    fig, ax = plt.subplots(figsize=(16, 7))
    h_tn_tb = res.get('H_TN_TB', 0)
    B = res.get('B', 0)
    H_tk = res.get('H', 0)
    label_res = res.get('label', "")
    is_duong_bo = "Vượt đường" in label_res

    # --- THIẾT LẬP KHUNG NHÌN THEO KÍCH THƯỚC THẬT ---
    if is_duong_bo:
        # Zoom sát vào B để thấy kích thước thật
        padding = B * 0.2 if B > 0 else 5
        x_min, x_max = 60 - B/2 - padding, 60 + B/2 + padding
    else:
        # Vượt sông giữ khung nhìn rộng 120m
        x_min, x_max = -5, 125

    x_draw = np.linspace(x_min, x_max, 200)

    # --- VẼ ĐỊA HÌNH ---
    if is_duong_bo:
        # Đường bộ: Nét liền xám
        y_nen = np.full_like(x_draw, res.get('MNCN', 0))
        ax.plot(x_draw, y_nen, color='#7f8c8d', ls='-', lw=2.5)
    else:
        # Vượt sông: NÉT ĐỨT XANH LÁ cho ĐTNTB
        y_tn = np.full_like(x_draw, h_tn_tb)
        ax.plot(x_draw, y_tn, color='#27ae60', ls='--', lw=2.0) # ls='--' là nét đứt
        ax.text(x_min + 2, h_tn_tb - 0.5, "ĐƯỜNG TỰ NHIÊN TRUNG BÌNH", color='#27ae60', fontsize=9, fontweight='bold')

    # --- KHUNG TĨNH KHÔNG (Vẽ theo B và H thật) ---
    if B > 0:
        x_s, x_e = 60 - B/2, 60 + B/2
        # Khung màu tím
        rect = patches.Rectangle((x_s, res.get('MNTT', 0)), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2)
        ax.add_patch(rect)
        
        # DIM B (Kích thước thật)
        ax.annotate('', xy=(x_e, res.get('MNTT', 0) + H_tk + 0.5), xytext=(x_s, res.get('MNTT', 0) + H_tk + 0.5),
                    arrowprops=dict(arrowstyle='<->', color='black'))
        ax.text(60, res.get('MNTT', 0) + H_tk + 0.7, f"B = {B}m", ha='center', fontweight='bold')

    ax.set_xlim(x_min, x_max)
    ax.axis('off')
    return fig

def ve_mat_cat_ngang(res_mcn):
    fig, ax = plt.subplots(figsize=(10, 5))
    bc = res_mcn.get('bc_cau', 0)
    w_lan = res_mcn.get('w_lan', 3.5)
    # Vẽ bản mặt cầu đơn giản
    ax.add_patch(patches.Rectangle((-bc/2, 0), bc, 0.5, color='#bdc3c7', ec='black'))
    # Vẽ vạch sơn phân làn (minh họa)
    ax.plot([0, 0], [0.5, 0.7], color='black', lw=2) 
    
    ax.set_xlim(-bc/2 - 2, bc/2 + 2)
    ax.set_ylim(-1, 2)
    ax.set_title(f"MẶT CẮT NGANG CẦU (Bc = {bc}m)")
    ax.axis('off')
    return fig