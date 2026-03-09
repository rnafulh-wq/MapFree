"""Scene — scene graph and drawable objects for the 3D viewer."""


class Scene:
    """Holds drawable objects (meshes, point clouds) and optional lights."""

    def __init__(self):
        pass

    def add_mesh(self, name, vertices, indices, normals=None, uvs=None):
        pass

    def add_point_cloud(self, name, points, colors=None):
        pass

    def remove(self, name):
        pass

    def clear(self):
        pass

    def draw(self, shader_manager, camera):
        pass

    def get_bounds(self):
        pass
