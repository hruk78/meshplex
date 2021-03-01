import math

import numpy as np

import meshplex


def test_heights_tri():
    # two triangles in 5D
    points = [
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0, 0.0],
    ]
    cells = [[0, 1, 2], [0, 3, 2]]
    mesh = meshplex.MeshTri(points, cells)

    ref = np.array(
        [
            [1.0, math.sqrt(0.5), 1.0],
            [1.0, math.sqrt(0.5), 1.0],
        ]
    ).T
    assert np.all(np.abs(mesh.heights - ref) < np.abs(ref) * 1.0e-13)


def test_heights_tetra():
    # two triangles in 5D
    points = [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    cells = [[0, 1, 2, 3]]
    mesh = meshplex.MeshTri(points, cells)

    ref = np.array(
        [
            [math.sqrt(1 / 3), 1.0, 1.0, 1.0],
        ]
    ).T
    assert np.all(np.abs(mesh.heights - ref) < np.abs(ref) * 1.0e-13)


if __name__ == "__main__":
    # test_heights_tri()
    test_heights_tetra()