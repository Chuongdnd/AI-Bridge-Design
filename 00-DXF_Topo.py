"""
00-DXF_Topo.py — Nguồn ĐỊA HÌNH thay thế: BÌNH ĐỒ KHẢO SÁT DXF duy nhất
(khi không có .NTD + file tọa độ tim).

Quy ước bản vẽ (thống nhất với đơn vị khảo sát):
  • 3 tim đặt tên layer rõ: `timluong` (tim luồng/sông), `timtuyenKS` (tim tuyến
    khảo sát), `timtuyenTK` (tim tuyến thiết kế — TUYẾN ĐẶT CẦU).
  • MỐC LÝ TRÌNH 0-0 = giao điểm timluong × timtuyenTK (âm/dương về 2 phía)
    → tim tĩnh không (x_tim_clearance) = 0.
  • CAO ĐỘ = từng TEXT số trong bản vẽ (điểm chèn text = vị trí điểm đo) +
    POINT/INSERT có Z ≠ 0 — dùng TRỰC TIẾP làm điểm địa hình, không bịa thêm.
  • Tọa độ bản vẽ là VN-2000 THẬT (CAD x = Đông/Easting, y = Bắc/Northing).

Đầu ra = BẢNG CHUẨN app đang dùng (như .NTD):
  df_geology : Lý trình · Offset · X_VN2000(=Bắc) · Y_VN2000(=Đông) ·
               Góc_Tuyến · Z   (trạm ~5m dọc timtuyenTK, offset ±40m @2.5m,
               Z nội suy TIN từ đám điểm đo thật)
  df_tim_line: Lý trình · Z (Offset=0)
  features   : cảnh quan sơ họa 3D (nhà, mương ao, lúa, đường, rào, cột điện…)
               tọa độ đã đổi về TRỤC CỘT (Xc=Bắc, Yc=Đông) + Z bám mặt địa hình.

BẪY TRỤC: cột X_VN2000 = BẮC (~1.19M), Y_VN2000 = ĐÔNG (~584k) — NGƯỢC với
CAD (x=Đông). Mọi phép dựng ở đây làm trong "hệ cột" (Xc=Bắc, Yc=Đông) để
_vn/Góc_Tuyến của 11-BanVe dùng được y như nguồn .NTD.
"""
import io
import numpy as np
import pandas as pd

try:
    import ezdxf
except ImportError:                                    # pragma: no cover
    ezdxf = None

# ── Bảng nhận diện layer (khớp chữ thường, dạng CHỨA chuỗi) ─────────────────
TIM_LAYERS = {"tk": "timtuyentk", "ks": "timtuyenks", "luong": "timluong"}

Z_TEXT_LAYERS = ["caodotn", "cao do binh do", "docao"]   # TEXT số = cao độ

BANK_LAYERS = ["ta ly duoi", "ta ly", "taluy", "mep nuoc"]   # mép bờ sông


FEATURE_LAYERS = [   # (category, [mẫu tên layer, chứa-chuỗi, chữ thường])
    # "dien" phải ĐỨNG TRƯỚC "nha": layer `dienhathe` CHỨA chuỗi "nha"
    # (die-NHA-the) — nếu xét "nha" trước, cột điện bị xếp nhầm thành nhà.
    ("dien",       ["dienhathe", "dien ha the"]),
    ("nha",        ["ks.nha", "nha"]),
    ("muong_ao",   ["muong ao", "ks_muong"]),
    ("lua",        ["lua-khks", "lua"]),
    ("duong_dat",  ["leduongdat"]),
    ("duong_nhua", ["leduongnhua"]),
    ("rao",        ["raoxay", "raokem", "rao"]),
    ("cay",        ["caytram", "ks.cay", "cayxanh"]),
    ("cau_cong",   ["cau cong"]),
]
_FEAT_EXCLUDE = ["text nha"]        # layer nhãn chữ — không phải hình


def _lay(e):
    return str(e.dxf.layer or "").strip().lower()


def _match(lay, patterns):
    return any(p in lay for p in patterns)


def _segments_of(e):
    """LINE/LWPOLYLINE/POLYLINE → list [((xE, yN), (xE, yN)), …] (hệ CAD)."""
    t = e.dxftype()
    try:
        if t == "LINE":
            return [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))]
        if t == "LWPOLYLINE":
            vs = [(p[0], p[1]) for p in e.get_points()]
        elif t == "POLYLINE":
            vs = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        else:
            return []
        segs = [(vs[i], vs[i + 1]) for i in range(len(vs) - 1)]
        if getattr(e, "closed", False) or getattr(e, "is_closed", False):
            segs.append((vs[-1], vs[0]))
        return segs
    except Exception:
        return []


def _poly_pts(e):
    t = e.dxftype()
    try:
        if t == "LWPOLYLINE":
            return [(p[0], p[1]) for p in e.get_points()]
        if t == "POLYLINE":
            return [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        if t == "LINE":
            return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    except Exception:
        pass
    return []


def _num(s):
    try:
        return float(str(s).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _chain_loops(segs, tol=0.2):
    """Nối các đoạn LINE rời thành CHUỖI liên tục; chuỗi khép kín → 'loop'
    (đa giác — nhà, ao). Trả (loops, opens): loops = [[(x,y)…]] KHÔNG lặp điểm
    cuối; opens = các đoạn còn lại (chuỗi hở tách về từng đoạn)."""
    from collections import defaultdict

    def _key(p):
        return (round(p[0] / tol), round(p[1] / tol))

    adj = defaultdict(list)                    # đầu-mút → [(idx đoạn, đầu 0/1)]
    for i, (a, b) in enumerate(segs):
        adj[_key(a)].append((i, 0))
        adj[_key(b)].append((i, 1))
    used = [False] * len(segs)
    loops, opens = [], []
    for i0 in range(len(segs)):
        if used[i0]:
            continue
        used[i0] = True
        chain = [segs[i0][0], segs[i0][1]]
        for _fwd in (True, False):             # nối dài về 2 phía
            while True:
                p = chain[-1] if _fwd else chain[0]
                cand = [(j, e) for (j, e) in adj[_key(p)] if not used[j]]
                if not cand:
                    break
                j, e = cand[0]
                used[j] = True
                s_, t_ = segs[j]
                nxt = t_ if e == 0 else s_
                chain.append(nxt) if _fwd else chain.insert(0, nxt)
        if len(chain) >= 4 and _key(chain[0]) == _key(chain[-1]):
            loops.append(chain[:-1])
        else:
            opens.extend((chain[k], chain[k + 1])
                         for k in range(len(chain) - 1))
    return loops, opens


def parse_topo_dxf(data):
    """Đọc DXF (bytes | đường dẫn) → dict thô:
    {z_points (E,N,Z), tims {tk|ks|luong: [(E,N)…]}, features, warnings, stats}."""
    if ezdxf is None:
        raise RuntimeError("Thiếu thư viện ezdxf")
    if isinstance(data, (bytes, bytearray)):
        # DXF thật ngoài công trường thường KHÔNG phải UTF-8 thuần (codepage
        # tiếng Việt cp1258, khối preview nhị phân…) — decode utf-8 rồi đọc
        # text sẽ vỡ ("Invalid binary data near line…"). ezdxf.recover nhận
        # BYTES trực tiếp, tự dò codepage/binary + chịu lỗi → dùng làm chuẩn.
        from ezdxf import recover as _recover
        doc, _audit = _recover.read(io.BytesIO(bytes(data)))
    else:
        doc = ezdxf.readfile(str(data))
    msp = doc.modelspace()

    z_points, warnings, banks = [], [], []
    tims_raw = {k: [] for k in TIM_LAYERS}
    feats = {cat: {"segs": [], "pts": []} for cat, _ in FEATURE_LAYERS}

    for e in msp:
        lay = _lay(e)
        t = e.dxftype()
        # ── 3 TIM đặt tên rõ ────────────────────────────────────────────
        hit_tim = next((k for k, p in TIM_LAYERS.items() if p in lay), None)
        if hit_tim and t in ("LINE", "LWPOLYLINE", "POLYLINE"):
            pts = _poly_pts(e)
            if len(pts) >= 2:
                tims_raw[hit_tim].append(pts)
            continue
        # ── MÉP BỜ SÔNG (ta luy dưới) — đường bao mặt nước thật ─────────
        if _match(lay, BANK_LAYERS) and t in ("LINE", "LWPOLYLINE", "POLYLINE"):
            pts_b = _poly_pts(e)
            if len(pts_b) >= 2:
                banks.append(pts_b)
            continue
        # ── ĐIỂM CAO ĐỘ ─────────────────────────────────────────────────
        if t in ("TEXT", "MTEXT") and _match(lay, Z_TEXT_LAYERS):
            v = _num(e.dxf.text if t == "TEXT" else e.text)
            if v is not None and -100.0 < v < 1000.0:
                ins = e.dxf.insert
                z_points.append((ins.x, ins.y, v))
            continue
        if t == "POINT" and abs(e.dxf.location.z) > 1e-6:
            z_points.append((e.dxf.location.x, e.dxf.location.y,
                             e.dxf.location.z))
            continue
        # ── CẢNH QUAN sơ họa ────────────────────────────────────────────
        if any(p in lay for p in _FEAT_EXCLUDE):
            continue
        cat = next((c for c, ps in FEATURE_LAYERS if _match(lay, ps)), None)
        if cat:
            if t == "INSERT":
                feats[cat]["pts"].append((e.dxf.insert.x, e.dxf.insert.y))
            else:
                feats[cat]["segs"].extend(_segments_of(e))

    # Mỗi tim lấy polyline DÀI NHẤT trên layer đó
    tims = {}
    for k, plist in tims_raw.items():
        if not plist:
            tims[k] = None
            continue
        def _len(pts):
            return sum(np.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
                       for i in range(len(pts)-1))
        tims[k] = max(plist, key=_len)

    if tims.get("tk") is None:
        warnings.append("Không tìm thấy layer `timtuyenTK` — cần polyline tim "
                        "tuyến thiết kế đặt đúng tên layer.")
    if tims.get("luong") is None:
        warnings.append("Không tìm thấy layer `timluong` — không xác định được "
                        "mốc lý trình 0-0 (sẽ lấy 0 tại đầu tuyến).")
    if len(z_points) < 20:
        warnings.append(f"Chỉ đọc được {len(z_points)} điểm cao độ — địa hình "
                        "có thể không tin cậy (cần TEXT số trên layer cao độ).")

    stats = {"n_z": len(z_points),
             "n_z_text": sum(1 for *_xy, _z in z_points),
             "feat_counts": {c: len(d_["segs"]) + len(d_["pts"])
                             for c, d_ in feats.items() if d_["segs"] or d_["pts"]}}
    return {"z_points": z_points, "tims": tims, "features": feats,
            "banks": banks, "warnings": warnings, "stats": stats}


# ── Hình học tim tuyến ───────────────────────────────────────────────────────
def _densify(pts, step=1.0):
    """Polyline → mảng điểm dày (E,N) + lý trình cộng dồn s."""
    P = np.asarray(pts, float)
    seg = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
    s_v = np.concatenate([[0.0], np.cumsum(seg)])
    L = float(s_v[-1])
    n = max(2, int(L / step) + 1)
    ss = np.linspace(0.0, L, n)
    return (np.interp(ss, s_v, P[:, 0]), np.interp(ss, s_v, P[:, 1]), ss, L)


def _seg_intersect(p1, p2, p3, p4):
    """Giao 2 đoạn thẳng (mỗi đoạn 2 điểm) → (x, y) hoặc None."""
    x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
    den = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(den) < 1e-12:
        return None
    t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / den
    u = ((x1-x3)*(y1-y2) - (y1-y3)*(x1-x2)) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return (x1 + t*(x2-x1), y1 + t*(y2-y1))
    return None


def chainage_zero(tim_tk, tim_luong):
    """Lý trình s0 (m, dọc tim TK) của GIAO ĐIỂM tim luồng × tim TK — mốc 0-0.
    Không giao → None."""
    if not tim_tk or not tim_luong:
        return None
    s_acc = 0.0
    for i in range(len(tim_tk) - 1):
        a, b = tim_tk[i], tim_tk[i + 1]
        for j in range(len(tim_luong) - 1):
            hit = _seg_intersect(a, b, tim_luong[j], tim_luong[j + 1])
            if hit is not None:
                return s_acc + float(np.hypot(hit[0]-a[0], hit[1]-a[1]))
        s_acc += float(np.hypot(b[0]-a[0], b[1]-a[1]))
    return None


def _coc_name(ly, moc=20.0):
    """Tên CỌC hiển thị: '0-0' tại giao tim luồng, mỗi 20m một cọc ('0+020',
    '-0+540'…); trạm trung gian (5m) để RỖNG — không dán nhãn."""
    a = abs(float(ly))
    if a < 1e-6:
        return "0-0"
    if abs(a % moc) > 1e-6:
        return ""
    km, m = int(a // 1000), a % 1000
    return f"{'-' if ly < 0 else ''}{km}+{m:03.0f}"


# ── Dựng bảng chuẩn ─────────────────────────────────────────────────────────
def build_geology(parsed, step=5.0, off_max=None, off_step=2.5):
    """Sinh (df_geology, df_tim_line, tin_fn, info) từ kết quả parse.

    Trạm mỗi `step` m dọc timtuyenTK; tại mỗi trạm cắt ngang ±off_max bước
    off_step; Z nội suy TIN (LinearND) từ đám điểm đo thật, ngoài biên dùng
    điểm gần nhất. Lý trình = s − s0 (0-0 tại giao tim luồng).

    off_max=None (mặc định): TỰ LẤY THEO BỀ RỘNG dải điểm đo của file CAD
    (bách phân vị 98 khoảng cách vuông góc điểm→tim, kẹp 40–300m) — địa hình
    phủ hết phạm vi khảo sát chứ không bó ±40m quanh tim."""
    from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

    zp = np.asarray(parsed["z_points"], float)
    if len(zp) < 4:
        raise ValueError("Quá ít điểm cao độ để dựng địa hình.")
    tim = parsed["tims"].get("tk") or parsed["tims"].get("ks")
    if not tim:
        raise ValueError("Thiếu tim tuyến TK/KS trong bản vẽ.")

    lin = LinearNDInterpolator(zp[:, :2], zp[:, 2])
    near = NearestNDInterpolator(zp[:, :2], zp[:, 2])

    def tin_fn(E, N):
        z = lin(E, N)
        z = np.where(np.isnan(z), near(E, N), z)
        return z

    Ee, Nn, ss, L = _densify(tim, step=1.0)
    if off_max is None:
        # Bề rộng dải = phạm vi ĐÁM MÂY ĐIỂM ĐO thật (khoảng cách vuông góc
        # từng điểm → tim, p98 chống điểm lạc), kẹp 40–300m; dải rộng thì bước
        # offset thô hơn (5m) để số điểm lưới không phình.
        from scipy.spatial import cKDTree
        _tree = cKDTree(np.column_stack([Ee[::3], Nn[::3]]))
        _dist, _ = _tree.query(zp[:, :2], k=1)
        off_max = float(np.clip(np.ceil(np.percentile(_dist, 98.0) / 10) * 10,
                                40.0, 300.0))
        if off_max > 60.0:
            off_step = max(float(off_step), 5.0)
    s0 = chainage_zero(tim, parsed["tims"].get("luong"))
    if s0 is None:
        s0 = 0.0
    # Lưới trạm NEO THEO LÝ TRÌNH (bội số step, ly=0 ĐÚNG giao tim luồng) —
    # nếu neo theo s tuyệt đối thì mọi ly lệch s0 → không có cọc chẵn 20m.
    ly0 = float(np.ceil((-s0) / step) * step)
    stations_ly = np.arange(ly0, (L - s0) + 1e-6, step)
    offs = np.arange(-off_max, off_max + 1e-6, off_step)

    rows = []
    for ly_g in stations_ly:
        s = float(ly_g) + s0
        cE = float(np.interp(s, ss, Ee)); cN = float(np.interp(s, ss, Nn))
        s2 = min(s + 1.0, L)
        tE = float(np.interp(s2, ss, Ee)) - float(np.interp(max(s2-1, 0), ss, Ee))
        tN = float(np.interp(s2, ss, Nn)) - float(np.interp(max(s2-1, 0), ss, Nn))
        # HỆ CỘT: Xc = Bắc(N), Yc = Đông(E) — Góc_Tuyến trong hệ cột để 11-BanVe
        # (_vn: x = Xc + off·cos(goc+90°)) dùng y như nguồn .NTD.
        goc = float(np.arctan2(tE, tN))         # atan2(dYc, dXc)
        per = goc + np.pi / 2.0
        ly = round(float(ly_g), 3)
        for off in offs:
            Xc = cN + off * np.cos(per)         # điểm thật — Bắc
            Yc = cE + off * np.sin(per)         # điểm thật — Đông
            z = float(tin_fn(Yc, Xc))           # tin nhận (E, N)
            # SCHEMA .NTD: X/Y_VN2000 = TIM (lặp mọi offset của trạm);
            # X/Y_Real = ĐIỂM THẬT (= tim + off·(cos,sin)(góc+90°)); 'Cọc' tên
            # cọc 20m; 'Tag_Gốc'='TARGET' — TV dựng lưới TỪ các điểm TARGET
            # (mỗi trạm cần ≥2), mọi offset ở đây đều là mẫu địa hình thật.
            rows.append((ly, round(float(off), 2), cN, cE, goc,
                         round(z, 3), Xc, Yc, _coc_name(ly), "TARGET"))

    df = pd.DataFrame(rows, columns=["Lý trình", "Offset", "X_VN2000",
                                     "Y_VN2000", "Góc_Tuyến", "Z",
                                     "X_Real", "Y_Real", "Cọc", "Tag_Gốc"])
    df_tim = (df[df["Offset"] == 0][["Lý trình", "Z"]]
              .drop_duplicates("Lý trình").sort_values("Lý trình")
              .reset_index(drop=True))
    info = {"L_tuyen": round(L, 1), "s0": round(s0, 2),
            "off_max": round(float(off_max), 1),
            "n_tram": len(stations_ly), "n_diem": len(df),
            "z_min": float(df["Z"].min()), "z_max": float(df["Z"].max())}
    return df, df_tim, tin_fn, info


def bake_features(parsed, tin_fn, max_seg_per_cat=1500):
    """Cảnh quan sơ họa → HỆ CỘT (Xc=Bắc, Yc=Đông) + Z bám mặt địa hình:
    {cat: {"segs": [((Xc,Yc,Z),(Xc,Yc,Z))…], "pts": [(Xc,Yc,Z)…],
           "loops": [[(Xc,Yc,Z)…]…]}}.
    'loops' = chuỗi đoạn KHÉP KÍN đã nối lại (nhà → khối nhà, ao → mặt nước)."""
    out = {}
    for cat, dd in parsed["features"].items():
        segs, pts = dd["segs"], dd["pts"]
        if not segs and not pts:
            continue
        o = {"segs": [], "pts": [], "loops": []}
        if cat in ("nha", "muong_ao") and segs:
            loops, segs = _chain_loops(segs)
            for lp in loops[:800]:
                o["loops"].append([(p[1], p[0], float(tin_fn(p[0], p[1])))
                                   for p in lp])
        if cat == "cay" and pts:
            # 1 ký hiệu cây khảo sát đại diện 1 KHÓM — rải thành cụm 5 cây
            # (offset cố định, không random) trong phạm vi ký hiệu thể hiện.
            _CLUST = ((0.0, 0.0), (5.5, 2.5), (-4.5, 4.0),
                      (3.0, -5.0), (-5.0, -3.5))
            pts = [(p[0] + dx, p[1] + dy) for p in pts for dx, dy in _CLUST]
        for (a, b) in segs[:max_seg_per_cat]:
            za = float(tin_fn(a[0], a[1])); zb = float(tin_fn(b[0], b[1]))
            o["segs"].append(((a[1], a[0], za), (b[1], b[0], zb)))
        for p in pts[:max_seg_per_cat]:
            o["pts"].append((p[1], p[0], float(tin_fn(p[0], p[1]))))
        out[cat] = o
    return out


def bake_timluong(parsed, tin_fn, half=80.0, off_step=2.0, step=5.0):
    """MẶT NƯỚC dọc TIM LUỒNG: nướng sẵn MẶT CẮT NGANG ĐỊA HÌNH tại từng trạm
    dọc polyline timluong (offset ±half). Mực nước (MNCN/MNTT/MNTN) chỉ biết
    lúc vẽ → khi render mới lan nước từ tim ra 2 phía tới khi CHẠM BỜ, nên bề
    rộng dải nước bám đúng lòng sông từng vị trí.
    Hệ CỘT: c=(Xc=Bắc,Yc=Đông), per=vector vuông góc đơn vị (hệ cột)."""
    tl = parsed["tims"].get("luong")
    if not tl:
        return None
    # KÉO DÀI tim luồng 2 đầu: polyline khảo sát thường chỉ vẽ đoạn quanh cầu,
    # trong khi mặt nước phải phủ HẾT bề rộng địa hình theo phương ngang cầu.
    # Phần thừa bị cắt lại đúng biên địa hình lúc dựng mesh (clip_poly).
    P0 = np.asarray(tl, float)
    if len(P0) >= 2:
        d_a = P0[0] - P0[1]; d_a = d_a / (float(np.hypot(*d_a)) or 1.0)
        d_b = P0[-1] - P0[-2]; d_b = d_b / (float(np.hypot(*d_b)) or 1.0)
        EXT = 500.0
        tl = ([tuple(P0[0] + d_a * EXT)] + [tuple(p) for p in P0]
              + [tuple(P0[-1] + d_b * EXT)])
    Ee, Nn, ss, L = _densify(tl, step=step)
    offs = np.arange(-half, half + 1e-6, off_step)
    sts = []
    for i in range(len(ss)):
        cE, cN = float(Ee[i]), float(Nn[i])
        i1, i2 = max(i - 1, 0), min(i + 1, len(ss) - 1)
        tE, tN = float(Ee[i2] - Ee[i1]), float(Nn[i2] - Nn[i1])
        nrm = float(np.hypot(tE, tN)) or 1.0
        pE, pN = -tN / nrm, tE / nrm            # vuông góc (hệ CAD E,N)
        zs = np.asarray(tin_fn(cE + offs * pE, cN + offs * pN), float)
        sts.append({"c": (cN, cE), "per": (pN, pE),
                    "zs": [round(float(z), 2) for z in zs]})
    out = {"offs": [round(float(o), 2) for o in offs], "st": sts,
           "L": round(float(L), 1)}

    # ── 2 MÉP BỜ SÔNG thật (layer `ta ly duoi`) → đường bao mặt nước ────────
    # Có bờ thì mặt nước vẽ ĐÚNG THEO ĐƯỜNG BAO SÔNG trong hồ sơ khảo sát,
    # không dò bờ từ TIN. LỌC KỸ: nhiều bản vẽ có đối tượng rác trên layer này
    # (đoạn dài 0m, nằm cách sông hàng trăm mét) — nhận nhầm thì dải nước suy
    # biến/lệch hẳn khỏi sông. Chỉ nhận polyline dài ≥20m và bám sát tim luồng.
    def _plen(pts_):
        P = np.asarray(pts_, float)
        return float(np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1])).sum())

    banks = []
    for b in (parsed.get("banks") or []):
        if len(b) < 2 or _plen(b) < 20.0:
            continue
        P = np.asarray(b, float)
        d_ = np.min(np.hypot(P[:, None, 0] - Ee[None, ::5],
                             P[:, None, 1] - Nn[None, ::5]), axis=1)
        if float(np.median(d_)) <= max(2.0 * half, 60.0):
            banks.append(b)
    if len(banks) >= 2:
        def _resamp(pts_, n=100):
            P = np.asarray(pts_, float)
            seg = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
            sv = np.concatenate([[0.0], np.cumsum(seg)])
            sn = np.linspace(0.0, sv[-1], n)
            return np.column_stack([np.interp(sn, sv, P[:, 0]),
                                    np.interp(sn, sv, P[:, 1])])

        b1, b2 = sorted(banks, key=_plen)[-2:]
        A, B = _resamp(b1), _resamp(b2)
        # Xoay chiều bờ 2 nếu 2 bờ chạy ngược nhau (ghép cặp chéo → mesh xoắn)
        d_thuan = (float(np.hypot(*(A[0] - B[0])))
                   + float(np.hypot(*(A[-1] - B[-1]))))
        d_nguoc = (float(np.hypot(*(A[0] - B[-1])))
                   + float(np.hypot(*(A[-1] - B[0]))))
        if d_thuan > d_nguoc:
            B = B[::-1]
        # CAD (E,N) → hệ cột (Xc=Bắc, Yc=Đông)
        out["bankL"] = [(float(p[1]), float(p[0])) for p in A]
        out["bankR"] = [(float(p[1]), float(p[0])) for p in B]
    return out


def build_from_dxf(data, step=5.0, off_max=None, off_step=2.5):
    """MỘT PHÁT ĂN NGAY: DXF → (df_geology, df_tim_line, features, info).
    info gồm stats/warnings để UI hiển thị. features có thêm khóa đặc biệt
    `__timluong` (profile mặt nước dọc tim luồng — không phải hạng mục vẽ)."""
    parsed = parse_topo_dxf(data)
    df, df_tim, tin_fn, info = build_geology(parsed, step, off_max, off_step)
    feats = bake_features(parsed, tin_fn)
    tl = bake_timluong(parsed, tin_fn)
    if tl:
        feats["__timluong"] = tl
    info.update(parsed["stats"])
    info["warnings"] = parsed["warnings"]
    return df, df_tim, feats, info
