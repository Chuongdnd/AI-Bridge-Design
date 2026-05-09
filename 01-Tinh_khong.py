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
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # Lấy thông số từ res
    h1, h5, h10, h98 = res['MNCN'], res['MNTT'], res['MNTC'], res['MNTN']
    h_dam = res['day_dam']
    H_tk, B = res['H'], res['B']
    
    # 1. TẠO ĐƯỜNG TỰ NHIÊN (N_tn) nhấp nhô
    x = np.linspace(0, 120, 200)
    # Hàm tạo đáy sông dốc ở giữa
    y_tn = h98 - 2 + 3 * (1 - np.exp(-((x - 60)**2) / 800)) 
    ax.plot(x, y_tn, color='#556B2F', linestyle='--', lw=1.5, label='Đường tự nhiên')
    ax.fill_between(x, -5, y_tn, color='#D2B48C', alpha=0.3) # Tô màu đất

    # 2. VẼ ĐƯỜNG ĐỎ (N_đỏ) - Cao độ mặt cầu
    h_mat_cau = h_dam + 2.5 
    ax.plot([0, 120], [h_mat_cau, h_mat_cau], color='red', lw=2.5)
    ax.text(5, h_mat_cau + 0.5, "ĐƯỜNG ĐỎ (MẶT CẦU)", color='red', fontweight='bold')

    # 3. VẼ CẤU TẠO CẦU CHI TIẾT
    # Vẽ Trụ (Pier) - Có thân trụ và bệ trụ
    for x_tru in [40, 80]:
        # Thân trụ
        ax.add_patch(patches.Rectangle((x_tru-1.5, y_tn[int(x_tru*200/120)]), 3, h_dam - y_tn[int(x_tru*200/120)], color='#7F8C8D'))
        # Xà mũ trụ
        ax.add_patch(patches.Rectangle((x_tru-4, h_dam-0.8), 8, 0.8, color='#95A5A6'))

    # Vẽ Mố cầu (Abutment)
    ax.add_patch(patches.Polygon([[0, h_mat_cau], [15, h_mat_cau], [20, y_tn[33]], [0, y_tn[0]]], color='#7F8C8D'))
    ax.add_patch(patches.Polygon([[105, h_mat_cau], [120, h_mat_cau], [120, y_tn[-1]], [100, y_tn[166]]], color='#7F8C8D'))

    # Vẽ Dầm (Girder) - Chia làm các nhịp
    nhip = [ (15, 40), (40, 80), (80, 105) ]
    for start, end in nhip:
        ax.add_patch(patches.Rectangle((start+0.2, h_dam), end-start-0.4, 1.8, color='#BDC3C7', ec='black'))

    # 4. VẼ CÁC MỰC NƯỚC VÀ KHUNG TĨNH KHÔNG
    ax.fill_between(x, y_tn, h1, color='#AED6F1', alpha=0.4) # Màu nước
    
    # Khung tĩnh không tím
    ax.add_patch(patches.Rectangle((60 - B/2, h5), B, H_tk, fill=False, edgecolor='purple', ls='--', lw=2))
    ax.text(60, h5 + H_tk/2, f"KHUNG TĨNH KHÔNG\nB={B}m x H={H_tk}m", ha='center', color='purple', fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    # 5. ĐIỀN THÔNG SỐ MNCN, MNTT... CÓ MŨI TÊN
    levels = [
        (h1, f'MNCN H1%: {h1:.3f}m', 'red'),
        (h5, f'MNTT H5%: {h5:.3f}m', 'blue'),
        (h10, f'MNTC H10%: {h10:.3f}m', 'green'),
        (h98, f'MNTN H98%: {h98:.3f}m', '#E67E22')
    ]
    for val, txt, col in levels:
        ax.axhline(y=val, color=col, ls='-', lw=1, alpha=0.6)
        ax.annotate(txt, xy=(115, val), xytext=(122, val), color=col, fontweight='bold', arrowprops=dict(arrowstyle='->', color=col))

    # 6. DIM ĐÁY DẦM TỐI THIỂU
    ax.annotate('', xy=(60+B/2+2, h5), xytext=(60+B/2+2, h_dam), arrowprops=dict(arrowstyle='<->', color='black'))
    ax.text(60+B/2+3, (h5+h_dam)/2, f"Đáy dầm TT: {h_dam}m", fontweight='bold', rotation=90, va='center')

    ax.set_xlim(0, 150)
    ax.set_ylim(h98-5, h_mat_cau+5)
    ax.axis('off')
    return fig