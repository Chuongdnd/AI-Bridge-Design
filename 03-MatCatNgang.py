import matplotlib.pyplot as plt

def thiet_ke_mcn_cau_web(data):
    """Xử lý logic tính toán mặt cắt ngang từ giao diện"""
    n_lan = data.get("n_lan", 2)
    w_lan = data.get("w_lan", 3.5)
    w_le = data.get("w_le", 0.5)
    loai = data.get("loai", "O to")
    
    # Các thông số mặc định khác
    w_lc = 0.5 # Lan can mỗi bên
    w_dpc = 0.75 if loai == "Cao tốc" else 0.0 # Dải phân cách
    
    w_mat_tong = n_lan * w_lan
    bc_cau = w_mat_tong + (2 * w_le) + w_dpc + (2 * w_lc)
    
    return {
        "n_lan": n_lan,
        "w_lan": w_lan,
        "w_mat_tong": w_mat_tong,
        "w_le": w_le,
        "tong_w_le": 2 * w_le,
        "w_dpc": w_dpc,
        "w_lc": w_lc,
        "bc_cau": round(bc_cau, 2),
        "mo_phong": f"LC {w_lc}m | LỀ {w_le}m | {n_lan} Làn | LỀ {w_le}m | LC {w_lc}m"
    }

def ve_so_do_mcn_bridge(res_mcn):
    """Hàm vẽ sơ đồ Matplotlib"""
    fig, ax = plt.subplots(figsize=(10, 2))
    # Logic vẽ các khối (Làn xe, lề, dải phân cách...)
    widths = [res_mcn['w_lc'], res_mcn['w_le'], res_mcn['w_mat_tong'], res_mcn['w_le'], res_mcn['w_lc']]
    labels = ['LC', 'Lề', 'Làn xe', 'Lề', 'LC']
    colors = ['#7f8c8d', '#95a5a6', '#34495e', '#95a5a6', '#7f8c8d']
    
    curr_x = 0
    for w, label, color in zip(widths, labels, colors):
        if w > 0:
            ax.add_patch(plt.Rectangle((curr_x, 0), w, 1, color=color, ec='white'))
            ax.text(curr_x + w/2, 0.5, f"{label}\n{w}m", ha='center', va='center', color='white', fontsize=8)
            curr_x += w
    ax.set_xlim(0, res_mcn['bc_cau'])
    ax.axis('off')
    return fig