def thiet_ke_mcn_cau_web(data):
    """
    Hàm xử lý logic thiết kế mặt cắt ngang trả về Dictionary cho Web
    """
    loai = data.get("loai")
    vtk = data.get("vtk")
    
    # Mặc định các thông số
    w_lan = 3.5
    n_lan = 2
    w_le = 0.5
    w_dpc = 0.0
    w_lc = 0.5 # Bề rộng gờ lan can mỗi bên

    if loai == "Cao tốc":
        db_caotoc = {120: 3.75, 100: 3.75, 80: 3.5, 60: 3.5}
        w_lan = db_caotoc.get(vtk, 3.75)
        w_dpc = 0.75 # Dải phân cách mặc định
    elif loai == "Do thi":
        db_dothi = {100: 3.75, 80: 3.5, 60: 3.25, 50: 3.0, 40: 3.0}
        w_lan = db_dothi.get(vtk, 3.5)

    # Tính toán tổng
    w_mat_tong = n_lan * w_lan
    bc_thong_thuy = w_mat_tong + (2 * w_le) + w_dpc
    bc_cau = bc_thong_thuy + (2 * w_lc)

    return {
        "w_lan": w_lan,
        "n_lan": n_lan,
        "w_mat_tong": w_mat_tong,
        "w_le": w_le,
        "w_dpc": w_dpc,
        "w_lc": w_lc,
        "bc_cau": round(bc_cau, 2),
        "mo_phong": f"LC {w_lc}m | LỀ {w_le}m | {n_lan} LÀN x {w_lan}m | LỀ {w_le}m | LC {w_lc}m"
    }