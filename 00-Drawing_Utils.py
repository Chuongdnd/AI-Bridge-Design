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
    """Vẽ sơ họa trắc dọc cầu - Tự động nhận diện Vượt sông hoặc Vượt đường"""
    fig, ax = plt.subplots(figsize=(16, 7))
    
    # --- 1. LẤY DỮ LIỆU ---
    h1 = res.get('MNCN', 0)
    h5 = res.get('MNTT', 0)
    h10 = res.get('MNTC', 0)
    h98 = res.get('MNTN', 0)
    h_dam = res.get('day_dam', 0)
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    label_res = res.get('label', "")

    # Kiểm tra loại cầu: Nếu là vượt đường bộ, các mực nước thường bằng nhau hoặc label chứa chữ 'Vượt'
    is_duong_bo = "vượt đường bộ" in label_res.lower()
    
    if isinstance(B, str): B = 0
    x = np.linspace(0, 120, 200)

    # --- 2. VẼ ĐỊA HÌNH ---
    h_tn_tb = res.get('H_TN_TB', res.get('MNTN', 0))

    if is_duong_bo:
        # Nếu VƯỢT ĐƯỜNG: Vẽ mặt đường bằng phẳng màu xám
        y_nen = np.full_like(x, h1)
        ax.plot(x, y_nen, color='#7f8c8d', ls='-', lw=2.5, label="Mặt đường bị vượt")
        ax.fill_between(x, h1 - 5, h1, color='#ecf0f1', alpha=0.6)
        ax.text(2, h1 + 0.2, f"CAO ĐỘ MẶT ĐƯỜNG: {h1:.3f}m", color='#34495e', fontsize=9, fontweight='bold')
    else:
        # Nếu VƯỢT SÔNG: Đổi đường cong thành ĐƯỜNG THẲNG xanh lá
        y_tn_flat = np.full_like(x, h_tn_tb)
        
        # Vẽ đường thẳng nét đứt màu xanh lá
        ax.plot(x, y_tn_flat, color='#27ae60', ls='--', lw=2.0)
        
        # Tô màu đất bên dưới đường thẳng
        ax.fill_between(x, h_tn_tb - 5, h_tn_tb, color='#f1e7d0', alpha=0.5)
        
        # Hiển thị nhãn Cao độ tự nhiên trung bình
        ax.text(2, h_tn_tb - 0.8, f"ĐƯỜNG TỰ NHIÊN TRUNG BÌNH: {h_tn_tb:.3f}m", 
                color='#27ae60', fontsize=9, fontweight='bold')
    # --- 3. VẼ KÝ HIỆU MỰC NƯỚC (Chỉ vẽ khi vượt sông) ---
    if not is_duong_bo:
        ve_ky_hieu_muc_nuoc(ax, 15, h1, "MNCN H1%", "red")
        ve_ky_hieu_muc_nuoc(ax, 45, h5, "MNTT H5%", "blue")
        ve_ky_hieu_muc_nuoc(ax, 75, h10, "MNTC H10%", "green")
        ve_ky_hieu_muc_nuoc(ax, 105, h98, "MNTN H98%", "orange")

    # --- 4. VẼ KẾT CẤU CẦU (ĐƯỜNG ĐỎ: TIẾP TUYẾN + ĐƯỜNG CONG + XÁC ĐỊNH CHIỀU DÀI CẦU) ---
    R_curve = res.get('R_hinh_hoc', 5000)
    # Lấy i_max (giả sử i_max là số thực 4, 5, 6... chuyển về thập phân)
    i_val = res.get('i_max_hinh_hoc', 4.0) / 100 
    # Lấy cao độ tự nhiên trung bình để tính toán chiều dài cầu
    h_tn_tb = res.get('H_TN_TB', res.get('MNTN', 0))
    
    x_dinh = 60
    y_dinh_mat_cau = h_dam + 2.0
    
    # --- Bổ sung: Xác định vị trí mố và Tổng chiều dài cầu ---
    # Giả định chiều cao đắp tại mố lý tưởng là 7m (trong khoảng 6-8m)
    h_dap_yc = 7.0 
    y_mo_cau = h_tn_tb + h_dap_yc
    
    # Chiều dài tiếp tuyến đường cong đứng: T = R * i
    T = R_curve * i_val
    x_tiep_1 = x_dinh - T
    x_tiep_2 = x_dinh + T
    y_tiep_mat_cau = y_dinh_mat_cau - (T**2) / (2 * R_curve)

    # Vị trí mố trái (nằm trên đường dốc): x_mo = x_tiep - (y_tiep - y_mo)/i
    x_mo_trai = x_tiep_1 - (y_tiep_mat_cau - y_mo_cau) / i_val
    x_mo_phai = x_dinh + (x_dinh - x_mo_trai)
    L_cau = x_mo_phai - x_mo_trai
    
    # Tạo mảng Y cho toàn bộ trắc dọc
    y_mat_cau = []
    y_day_dam = []
    
    for xi in x:
        if xi < x_tiep_1:
            # Đoạn tiếp tuyến trái
            yi_mat = y_tiep_mat_cau - i_val * (x_tiep_1 - xi)
        elif xi > x_tiep_2:
            # Đoạn tiếp tuyến phải
            yi_mat = y_tiep_mat_cau - i_val * (xi - x_tiep_2)
        else:
            # Đoạn đường cong đứng Parabol
            yi_mat = y_dinh_mat_cau - (xi - x_dinh)**2 / (2 * R_curve)
        
        y_mat_cau.append(yi_mat)
        y_day_dam.append(yi_mat - 2.0) # Đáy dầm song song cách mặt cầu 2m

    # Chuyển về mảng numpy để vẽ
    y_mat_cau = np.array(y_mat_cau)
    y_day_dam = np.array(y_day_dam)

    # Vẽ Đường đỏ và Đáy dầm
    ax.plot(x, y_mat_cau, color='red', lw=3, label="Đường đỏ")
    ax.plot(x, y_day_dam, color='#34495e', ls='-.', lw=1.5)
    
    # Vẽ ký hiệu vị trí mố cầu
    ax.vlines([x_mo_trai, x_mo_phai], h_tn_tb, y_mo_cau, colors='brown', ls='--', lw=2)

    # Ghi chú thông số hình học và Tổng chiều dài cầu
    ax.text(x_dinh, y_dinh_mat_cau + 1.2, f"TỔNG CHIỀU DÀI CẦU DỰ KIẾN: L = {L_cau:.2f}m", 
            color='brown', fontweight='bold', fontsize=11, ha='center', bbox=dict(facecolor='white', alpha=0.8))
    
    ax.text(x_dinh, y_dinh_mat_cau + 0.5, f"ĐƯỜNG ĐỎ: i_max={i_val*100}% | R={R_curve}m", 
            color='red', fontweight='bold', fontsize=10, ha='center')
    
    # Khôi phục ghi chú cao độ đáy dầm tại tim (đỉnh cầu)
    y_day_dam_tai_tim = y_dinh_mat_cau - 2.0
    ax.text(x_dinh, y_day_dam_tai_tim - 0.8, f"CAO ĐỘ ĐÁY DẦM TẠI TIM: {y_day_dam_tai_tim:.3f}m", 
            color='#34495e', fontsize=9, ha='center', fontweight='bold')

    # --- 5. KHUNG TĨNH KHÔNG VÀ NÉT DIM ---
    if B > 0:
        # Khung tĩnh không Magenta
        rect = patches.Rectangle((60 - B/2, h5), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2.5, zorder=3)
        ax.add_patch(rect)
        
        # DIM Bề rộng B (Dời lên cao h5 + 3.0)
        y_dim_b = h5 + H_tk/2
        ax.annotate('', xy=(60 + B/2, y_dim_b), xytext=(60 - B/2, y_dim_b),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        ax.text(60, y_dim_b + 0.2, f"B = {B}m", ha='center', va='bottom', fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        # DIM Chiều cao H
        ax.annotate('', xy=(60 + B/2 + 3, h5 + H_tk), xytext=(60 + B/2 + 3, h5),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.2, mutation_scale=15))
        ax.text(60 + B/2 + 3.5, h5 + H_tk/2, f"H = {H_tk}m", ha='left', va='center', rotation=90, fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # Cấu hình trục
    ax.set_xlim(-5, 125)
    # Tính toán cao độ mặt cầu cao nhất để đặt giới hạn trục Y
    h_mat_cau_max = h_dam + 2.0 
    
    # Thiết lập giới hạn trục Y an toàn
    y_min = min(h98, h1, h5) - 5
    y_max = h_mat_cau_max + 5
    ax.set_ylim(y_min, y_max)
    ax.axis('off')
    ax.set_title(label_res.upper() if label_res else "SƠ HỌA TRẮC DỌC CẦU", fontsize=16, fontweight='bold', pad=20)
    
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