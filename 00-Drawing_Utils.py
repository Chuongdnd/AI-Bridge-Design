import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def ve_ky_hieu_muc_nuoc(ax, x_pos, y_val, label, color):
    d_x, d_y = 1.2, 0.8
    triangle = patches.Polygon([
        (x_pos - d_x, y_val + d_y), 
        (x_pos + d_x, y_val + d_y), 
        (x_pos, y_val)], color=color, alpha=0.8)
    ax.add_patch(triangle)
    ax.text(x_pos, y_val + d_y + 0.2, f"{label}\n{y_val:.3f}m", 
            ha='center', va='bottom', color=color, fontsize=9, fontweight='bold')

def ve_trac_doc_cau(res):
    fig, ax = plt.subplots(figsize=(16, 7))
    
    # 1. Lấy dữ liệu từ dictionary res
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h10 = res.get('MNTC', 0)
    h98 = res.get('MNTN', 0)
    h_dam = res.get('day_dam', 0)
    H_tk = res.get('H', 0)
    
    # FIX LỖI Ở ĐÂY: Lấy biến B và xử lý nếu nó không phải là số
    B = res.get('B', 0)
    if isinstance(B, str): 
        B = 0  # Nếu B là "N/A" hoặc chuỗi, gán bằng 0 để tránh lỗi vẽ
    
    # 2. Vẽ địa hình
    x = np.linspace(0, 120, 200)
    y_tn = h98 - 1.5 + 2.5 * (1 - np.exp(-((x - 60)**2) / 1000))
    ax.plot(x, y_tn, color='#27ae60', ls='--', lw=1.5)
    ax.fill_between(x, h98 - 5, y_tn, color='#f1e7d0', alpha=0.5)

    # 3. Vẽ Thủy văn
    ve_ky_hieu_muc_nuoc(ax, 15, h1, "MNCN H1%", "red")
    ve_ky_hieu_muc_nuoc(ax, 45, h5, "MNTT H5%", "blue") # Đổi x_pos để tránh chồng lấn
    ve_ky_hieu_muc_nuoc(ax, 75, h10, "MNTC H10%", "green")
    ve_ky_hieu_muc_nuoc(ax, 105, h98, "MNTN H98%", "orange")

    # 4. Vẽ Kết cấu
    h_mat_cau = h_dam + 2.0
    ax.plot([0, 120], [h_mat_cau, h_mat_cau], color='red', lw=3, label="Mặt cầu")
    ax.plot([0, 120], [h_dam, h_dam], color='#34495e', ls='-.', lw=1.5, label="Đáy dầm")
    ax.text(2, h_mat_cau + 0.3, "ĐƯỜNG ĐỎ", color='red', fontweight='bold')
    ax.text(2, h_dam - 0.8, f"ĐÁY DẦM: {h_dam:.3f}m", color='#34495e', fontsize=9)

    # 5. Tĩnh không (Chỉ vẽ nếu B > 0)
    if B > 0:
        rect = patches.Rectangle((60 - B/2, h5), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2)
        ax.add_patch(rect)
    
    ax.set_xlim(-5, 125)
    ax.set_ylim(min(h98, h5) - 4, h_mat_cau + 5)
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