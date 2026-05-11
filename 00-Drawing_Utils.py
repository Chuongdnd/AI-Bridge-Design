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
    
    # 1. Lấy dữ liệu
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h_dam = res.get('day_dam', 0)
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    label_res = res.get('label', "")

    # Kiểm tra loại cầu
    is_duong_bo = ("Cầu vượt" in label_res) or (res.get('MNCN') == res.get('MNTN'))
    
    # 2. THIẾT LẬP KHUNG NHÌN (ZOOM) THEO B
    if is_duong_bo:
        padding = B * 0.3 if B > 0 else 10 # Lề 30% bề rộng B
        x_min, x_max = 60 - B/2 - padding, 60 + B/2 + padding
    else:
        x_min, x_max = -5, 125 # Vượt sông giữ nguyên 120m

    x = np.linspace(x_min, x_max, 200)

    # 3. VẼ ĐỊA HÌNH
    if is_duong_bo:
        y_nen = np.full_like(x, h1)
        ax.plot(x, y_nen, color='#7f8c8d', ls='-', lw=2.5)
        ax.fill_between(x, h1 - 5, h1, color='#ecf0f1', alpha=0.6)
        ax.text(x_min + 1, h1 + 0.2, f"CAO ĐỘ MẶT ĐƯỜNG: {h1:.3f}m", color='#34495e', fontsize=10, fontweight='bold')
    else:
        # Vẽ lòng sông (giữ nguyên logic cũ của bạn)
        h98 = res.get('MNTN', 0)
        y_tn = h98 - 1.5 + 2.5 * (1 - np.exp(-((x - 60)**2) / 1000))
        ax.plot(x, y_tn, color='#27ae60', ls='--', lw=1.5)
        ax.fill_between(x, y_tn.min() - 5, y_tn, color='#f1e7d0', alpha=0.5)

    # 4. VẼ THỦY VĂN (Chỉ khi vượt sông)
    if not is_duong_bo:
        ve_ky_hieu_muc_nuoc(ax, 15, h1, "MNCN", "red")
        ve_ky_hieu_muc_nuoc(ax, 45, h5, "MNTT", "blue")

    # 5. VẼ KẾT CẤU CẦU (ĐƯỜNG ĐỎ & ĐÁY DẦM)
    h_mat_cau = h_dam + 2.0
    ax.plot([x_min, x_max], [h_mat_cau, h_mat_cau], color='red', lw=3)
    ax.plot([x_min, x_max], [h_dam, h_dam], color='#34495e', ls='-.', lw=1.5)
    ax.text(x_min + 1, h_mat_cau + 0.3, "ĐƯỜNG ĐỎ (MẶT CẦU)", color='red', fontweight='bold')

    # 6. KHUNG TĨNH KHÔNG & DIM (CHUẨN TỶ LỆ)
    if B > 0:
        x_s, x_e = 60 - B/2, 60 + B/2
        # Vẽ khung
        rect = patches.Rectangle((x_s, h5), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2.5, zorder=10)
        ax.add_patch(rect)
        
        # DIM B (Nằm trên nóc khung)
        y_dim_b = h5 + H_tk + 0.5
        ax.annotate('', xy=(x_e, y_dim_b), xytext=(x_s, y_dim_b),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.5, mutation_scale=15))
        ax.text(60, y_dim_b + 0.1, f"B = {B}m", ha='center', va='bottom', fontweight='bold', fontsize=12)

        # DIM H (Nằm sát lề phải khung)
        x_dim_h = x_e + (padding * 0.2)
        ax.annotate('', xy=(x_dim_h, h5 + H_tk), xytext=(x_dim_h, h5),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.5, mutation_scale=15))
        ax.text(x_dim_h + 0.2, h5 + H_tk/2, f"H = {H_tk}m", rotation=90, va='center', fontweight='bold', fontsize=11)

    # Cấu hình trục và hiển thị
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(h1 - 3, h_mat_cau + 4)
    ax.axis('off')
    ax.set_title(label_res.upper(), fontsize=16, fontweight='bold', pad=20)
    
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