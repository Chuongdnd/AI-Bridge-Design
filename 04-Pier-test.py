# 04-Pier-test.py
import numpy as np
import trimesh
import plotly.graph_objects as go

def create_pier(H, W, L, top_W, top_H, base_W, base_H, base_L):
    """
    Tạo mô hình trụ cầu dạng khối hộp ghép.
    Tham số (m):
        H: chiều cao thân trụ
        W: chiều rộng thân trụ (dọc cầu)
        L: chiều dài thân trụ (ngang cầu)
        top_W: chiều rộng đỉnh trụ (nếu có)
        top_H: chiều cao đỉnh trụ
        base_W: chiều rộng bệ trụ
        base_H: chiều cao bệ trụ
        base_L: chiều dài bệ trụ
    Trả về: trimesh.Trimesh object
    """
    meshes = []
    # Thân trụ chính
    body = trimesh.primitives.Box(extents=(L, W, H))
    body.apply_translation([0, 0, H/2])
    meshes.append(body)
    
    # Đỉnh trụ (mở rộng)
    if top_H > 0 and top_W > 0:
        top = trimesh.primitives.Box(extents=(L, top_W, top_H))
        top.apply_translation([0, 0, H + top_H/2])
        meshes.append(top)
    
    # Bệ trụ (móng)
    if base_H > 0 and base_W > 0 and base_L > 0:
        base = trimesh.primitives.Box(extents=(base_L, base_W, base_H))
        base.apply_translation([0, 0, -base_H/2])
        meshes.append(base)
    
    # Hợp nhất
    combined = trimesh.util.concatenate(meshes)
    return combined

def trimesh_to_plotly_mesh(mesh):
    """Chuyển trimesh object thành vertices và faces cho Plotly."""
    vertices = mesh.vertices
    faces = mesh.faces
    return vertices, faces

# Hàm vẽ trực tiếp ra figure Plotly (tiện lợi)
def ve_tru_cau_3d(H, W, L, top_W, top_H, base_W, base_H, base_L):
    pier = create_pier(H, W, L, top_W, top_H, base_W, base_H, base_L)
    vertices, faces = trimesh_to_plotly_mesh(pier)
    fig = go.Figure(data=[go.Mesh3d(
        x=vertices[:,0], y=vertices[:,1], z=vertices[:,2],
        i=faces[:,0], j=faces[:,1], k=faces[:,2],
        color='lightgray', opacity=0.9, flatshading=True,
        lighting=dict(ambient=0.5, diffuse=0.8, specular=0.5)
    )])
    fig.update_layout(
        scene=dict(
            xaxis_title="X (m)", yaxis_title="Y (m)", zaxis_title="Z (m)",
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        height=600,
        title="Mô hình trụ cầu 3D"
    )
    return fig