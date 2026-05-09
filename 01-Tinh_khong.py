import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
def tra_cuu_tinh_khong_bridge(loai_cau, mien=None, cap_num=None, loai_hinh=None, 
                               h1=0, h5=0, h10=0, h98=0, 
                               loai_duong_vuot=None, cap_oto=None):
    # Dữ liệu tra cứu chuẩn
    data_thuy = {
        "1": { "1": {"1": 70, "2": 85, "H": 11.0}, "2": {"1": 40, "2": 50, "H": 9.5}, "3": {"1": 30, "2": 40, "H": 7.0}, "4": {"1": 25, "2": 30, "H": 6.0}, "5": {"1": 15, "2": 20, "H": 4.0}, "6": {"1": 10, "2": 10, "H": 3.0} },
        "2": { "1": {"1": 75, "2": 120, "H": 11.0}, "2": {"1": 50, "2": 60, "H": 9.5}, "3": {"1": 30, "2": 50, "H": 7.0}, "4": {"1": 25, "2": 30, "H": 6.0}, "5": {"1": 15, "2": 25, "H": 4.0}, "6": {"1": 10, "2": 13, "H": 3.0} }
    }

    if loai_cau == "Vượt sông":
        if mien in data_thuy and cap_num in data_thuy[mien]:
            target = data_thuy[mien][cap_num]
            B = target.get(loai_hinh, "N/A")
            H = target["H"]
            cao_do_day_dam = max(h5 + H + 0.1, h1 + 0.5)
            return {
                "status": "success", "B": B, "H": H, "H1": h1, "H5": h5, "H10": h10, "H98": h98,
                "day_dam": round(cao_do_day_dam, 3), "label": f"Cầu vượt {('Kênh' if loai_hinh=='1' else 'Sông')} - Cấp {cap_num}"
            }
    elif loai_cau == "Vượt đường bộ":
        H = 5.0 if loai_duong_vuot == "Cao tốc" else (4.75 if cap_oto == "1" else 4.5)
        return {"status": "success", "B": 20.0, "H": H, "day_dam": 0.0, "label": f"Cầu vượt {loai_duong_vuot}"}
    return {"status": "error"}

def ve_so_do_bo_tri_chung(res):
    # Thiết lập khổ ảnh panorama
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # ĐỒNG BỘ BIẾN: Sử dụng đúng key từ res
    h1 = res.get('H1', 0)
    h5 = res.get('H5', 0)
    h10 = res.get('H10', 0)
    h98 = res.get('H98', 0)
    h_dam = res.get('day_dam', 0)
    H_tk = res.get('H', 0)
    B = res.get('B', 0)
    
    # 1. TẠO ĐƯỜNG TỰ NHIÊN (Đường xanh lá nét đứt)
    x = np.linspace(0, 120, 200)
    # Hàm mô phỏng lòng sông trũng ở giữa x=60
    y_tn = h98 - 1.5 + 2.5 * (1 - np.exp(-((x - 60)**2) / 1000)) 
    ax.plot(x, y_tn, color='#27ae60', linestyle='--', lw=1.5, label='Đường tự nhiên')
    ax.fill_between(x, -10, y_tn, color='#f1e7d0', alpha=0.5) # Tô màu đất

    # 2. VẼ ĐƯỜNG ĐỎ (Mặt đường - Màu đỏ)
    h_mat_cau = h_dam + 2.0 # Độ dày dầm + bản mặt cầu
    ax.plot([0, 120], [h_mat_cau, h_mat_cau], color='red', lw=2.5)
    ax.text(5, h_mat_cau + 0.5, "ĐƯỜNG ĐỎ (MẶT CẦU)", color='red', fontweight='bold')

    # 3. VẼ CẤU TẠO CẦU (Mố, Trụ, Dầm)
    # Vẽ Trụ cầu (Pier)
    for x_tru in [40, 80]:
        # Thân trụ
        idx = int(x_tru * 200 / 120)
        ax.add_patch(patches.Rectangle((x_tru-1.5, y_tn[idx]), 3, h_dam - y_tn[idx], color='#7f8c8d'))
        # Bệ trụ/Móng (Min minh họa)
        ax.add_patch(patches.Rectangle((x_tru-3, y_tn[idx]-1.5), 6, 1.5, color='#95a5a6'))

    # Vẽ Mố cầu (Abutment)
    ax.add_patch(patches.Polygon([[0, h_mat_cau], [15, h_mat_cau], [20, y_tn[33]], [0, y_tn[0]]], color='#7f8c8d'))
    ax.add_patch(patches.Polygon([[105, h_mat_cau], [120, h_mat_cau], [120, y_tn[-1]], [100, y_tn[166]]], color='#7f8c8d'))

    # Vẽ Dầm (Girder) giản đơn
    ax.add_patch(patches.Rectangle((15, h_dam), 90, 1.8, color='#bdc3c7', ec='black', lw=1.5))

    # 4. VẼ VÙNG NƯỚC & KHUNG TĨNH KHÔNG
    ax.fill_between(x, y_tn, h1, color='#add8e6', alpha=0.4) # Màu nước xanh nhạt
    
    # Khung tĩnh không (Nét đứt tím)
    ax.add_patch(patches.Rectangle((60 - B/2, h5), B, H_tk, fill=False, edgecolor='magenta', ls='--', lw=2))
    ax.text(60, h5 + H_tk/2, f"TĨNH KHÔNG\nHtk={H_tk}m, B={B}m", ha='center', va='center', color='magenta', fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # 5. GHI CHÚ CAO ĐỘ (MNCN, MNTT...)
    levels = [(h1, 'MNCN H1%', 'red'), (h5, 'MNTT H5%', 'blue'), (h10, 'MNTC H10%', 'green'), (h98, 'MNTN H98%', '#d35400')]
    for val, txt, col in levels:
        ax.axhline(y=val, color=col, ls='-', lw=1, alpha=0.6)
        ax.text(122, val, f"{txt}: {val:.3f}m", color=col, fontweight='bold', va='center')

    # 6. DIM ĐÁY DẦM
    ax.annotate('', xy=(60+B/2+5, h5), xytext=(60+B/2+5, h_dam), arrowprops=dict(arrowstyle='<->', color='black'))
    ax.text(60+B/2+6, (h5+h_dam)/2, f"H_thực = {h_dam-h5:.3f}m", fontweight='bold', rotation=90, va='center')

    ax.set_xlim(-5, 155)
    ax.set_ylim(h98-5, h_mat_cau+5)
    ax.axis('off')
    ax.set_title("BỐ TRÍ CHUNG MẶT CẮT DỌC CẦU (DẦM SPT GIẢN ĐƠN)", fontsize=16, fontweight='bold', pad=20)
    
    return fig