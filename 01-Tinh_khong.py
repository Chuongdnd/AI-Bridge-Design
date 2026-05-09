import matplotlib.pyplot as plt
import matplotlib.patches as patches

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

def ve_so_do_dam_gian_don_dong(res):
    """Vẽ sơ đồ trắc dọc dầm giản đơn thay thế hình con chó"""
    fig, ax = plt.subplots(figsize=(12, 7))
    h1, h5, h98 = res.get('H1', 0), res.get('H5', 0), res.get('H98', 0)
    h_dam, H_tk, B = res.get('day_dam', 0), res.get('H', 0), res.get('B', 0)
    
    # Vẽ nước và trụ cầu
    ax.fill_between([-10, 80], h98 - 1, h1, color='#E3F2FD', alpha=0.6)
    ax.add_patch(patches.Rectangle((5, h98 - 2), 4, h_dam - h98 + 3, color='#BDBDBD', ec='black'))
    ax.add_patch(patches.Rectangle((61, h98 - 2), 4, h_dam - h98 + 3, color='#BDBDBD', ec='black'))
    # Vẽ dầm giản đơn (chiều cao h=2m không đổi)
    ax.add_patch(patches.Rectangle((-5, h_dam), 80, 2.0, color='#546E7A', ec='black', lw=2))
    
    # Thêm các đường mực nước và DIM
    levels = [(h1, 'MNCN H1%', 'red'), (h5, 'MNTT H5%', 'blue'), (h98, 'MNTN H98%', 'orange')]
    for val, label, col in levels:
        ax.axhline(y=val, color=col, linestyle='--', alpha=0.7)
        ax.text(72, val + 0.1, f"{label}: {val:.3f}m", color=col, fontweight='bold', fontsize=9)
    
    ax.set_xlim(-5, 90); ax.set_ylim(h98 - 3, h_dam + 5); ax.axis('off')
    ax.set_title("SƠ ĐỒ TRẮC DỌC TĨNH KHÔNG (DẦM GIẢN ĐƠN)", fontsize=14, fontweight='bold')
    return fig