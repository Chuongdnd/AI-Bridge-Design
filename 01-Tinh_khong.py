import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from ezdxf.enums import TextEntityAlignment
def tra_cuu_tinh_khong_bridge(loai_cau, mien=None, cap_num=None, loai_hinh=None, 
                               h1=0, h5=0, h10=0, h98=0, 
                               loai_duong_vuot=None, cap_oto=None):
    # (Giữ nguyên logic tra cứu dữ liệu của bạn ở đây...)
    # Giả định trả về dictionary res
    return {
        "status": "success", "B": 40, "H": 7.0, 
        "H1": h1, "H5": h5, "H10": h10, "H98": h98, 
        "day_dam": h5 + 7.0 + 0.1
    }

def ve_ky_hieu_muc_nuoc(ax, x_pos, y_val, label, color):
    """
    Vẽ ký hiệu tam giác mức nước và text cao độ
    """
    d_x = 1.2   # Độ rộng tam giác
    d_y = 0.8   # Chiều cao tam giác
    
    # Vẽ tam giác
    triangle = patches.Polygon([
        (x_pos - d_x, y_val + d_y), 
        (x_pos + d_x, y_val + d_y), 
        (x_pos, y_val)
    ], facecolor=color, edgecolor='black', lw=1)
    ax.add_patch(triangle)
    
    # Vẽ 3 gạch nhỏ bên dưới (sóng nước)
    for i in range(1, 4):
        dash_w = d_x * (1 - i*0.2)
        ax.plot([x_pos - dash_w, x_pos + dash_w], [y_val - i*0.3, y_val - i*0.3], color='black', lw=0.8)
    
    # Ghi chú Text
    ax.text(x_pos, y_val + d_y + 0.2, f"{label}\n{y_val:.3f}m", 
            ha='center', va='bottom', color=color, fontweight='bold', fontsize=9)

def ve_so_do_bo_tri_chung(res):
    fig, ax = plt.subplots(figsize=(16, 8))
    
    h1, h5, h10, h98 = res.get('H1', 0), res.get('H5', 0), res.get('H10', 0), res.get('H98', 0)
    h_dam, H_tk, B = res.get('day_dam', 0), res.get('H', 0), res.get('B', 0)
    
    # --- PHẦN 1: ĐƯỜNG TỰ NHIÊN & ĐẤT ---
    x = np.linspace(0, 120, 200)
    y_tn = h98 - 1.5 + 2.5 * (1 - np.exp(-((x - 60)**2) / 1000)) 
    ax.plot(x, y_tn, color='#27ae60', linestyle='--', lw=1.5)
    ax.fill_between(x, h98 - 6, y_tn, color='#f1e7d0', alpha=0.5)

    # --- PHẦN 2: KÝ HIỆU MỰC NƯỚC (TAM GIÁC) ---
    ve_ky_hieu_muc_nuoc(ax, 15, h1, "MNCN H1%", "red")
    ve_ky_hieu_muc_nuoc(ax, 35, h10, "MNTC H10%", "green")
    ve_ky_hieu_muc_nuoc(ax, 85, h5, "MNTT H5%", "blue")
    ve_ky_hieu_muc_nuoc(ax, 105, h98, "MNTN H98%", "#d35400")

    # --- PHẦN 3: ĐƯỜNG ĐỎ VÀ CAO ĐỘ ĐÁY DẦM ---
    h_mat_cau = h_dam + 2.0  # Giả sử chiều cao dầm + mặt đường là 2m
    
    # Vẽ ĐƯỜNG ĐỎ (Mặt cầu)
    ax.plot([0, 120], [h_mat_cau, h_mat_cau], color='red', lw=2.5, label="Đường đỏ")
    ax.text(2, h_mat_cau + 0.5, "ĐƯỜNG ĐỎ (MẶT CẦU)", color='red', fontweight='bold', fontsize=10)
    
    # Vẽ ĐƯỜNG ĐÁY DẦM (Nét đứt màu đen/xám)
    ax.plot([0, 120], [h_dam, h_dam], color='#555555', linestyle='-.', lw=1.5, label="Đáy dầm")
    ax.text(2, h_dam - 1.2, f"CAO ĐỘ ĐÁY DẦM: {h_dam:.3f}m", color='#333333', fontweight='bold', fontsize=10)

    # --- PHẦN 4: KHUNG TĨNH KHÔNG ---
    # Vẽ khung tĩnh không Magenta nét đứt
    rect_tk = patches.Rectangle((60 - B/2, h5), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2)
    ax.add_patch(rect_tk)
    
    # Chú thích kích thước trong khung
    ax.text(60, h5 + H_tk/2, f"KHUNG TĨNH KHÔNG\nB={B}m x H={H_tk}m", 
            ha='center', va='center', color='magenta', fontweight='bold', 
            bbox=dict(facecolor='white', alpha=0.6, edgecolor='none'))

    # Vẽ đường DIM đứng thể hiện tĩnh không thực tế (từ MNTT đến Đáy dầm)
    ax.annotate('', xy=(60 + B/2 + 2, h5), xytext=(60 + B/2 + 2, h_dam),
                arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
    ax.text(60 + B/2 + 3, (h5 + h_dam)/2, f"H_thực = {h_dam - h5:.3f}m", 
            va='center', fontweight='bold', fontsize=10)

    # Cấu hình trục
    ax.set_xlim(-5, 125)
    ax.set_ylim(h98 - 5, h_mat_cau + 5)
    ax.axis('off')
    ax.set_title("SƠ ĐỒ CAO ĐỘ ĐƯỜNG ĐỎ, ĐÁY DẦM VÀ THỦY VĂN", fontsize=15, fontweight='bold', pad=20)
    
    return fig