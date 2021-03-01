import numpy as np

from ._helpers import compute_tri_areas, compute_triangle_circumcenters
from ._mesh import Mesh

__all__ = ["MeshTetra"]


class MeshTetra(Mesh):
    """Class for handling tetrahedral meshes."""

    def __init__(self, points, cells, sort_cells=False):
        super().__init__(points, cells, sort_cells=sort_cells)

        self.subdomains = {}

        self.ce_ratios = self._compute_ce_ratios_geometric()
        # self.ce_ratios = self._compute_ce_ratios_algebraic()

        self._inv_faces = None
        self.edges = None
        self.faces = None

    def _create_face_edge_relationships(self):
        a = np.vstack(
            [
                self.faces["points"][:, [1, 2]],
                self.faces["points"][:, [2, 0]],
                self.faces["points"][:, [0, 1]],
            ]
        )

        # Find the unique edges
        b = np.ascontiguousarray(a).view(
            np.dtype((np.void, a.dtype.itemsize * a.shape[1]))
        )
        _, idx, inv = np.unique(b, return_index=True, return_inverse=True)
        edge_points = a[idx]

        self.edges = {"points": edge_points}

        # face->edge relationship
        num_faces = len(self.faces["points"])
        face_edges = inv.reshape([3, num_faces]).T
        self.faces["edges"] = face_edges

    # Question:
    # We're looking for an explicit expression for the algebraic c/e ratios. Might it be
    # that, analogous to the triangle dot product, the "triple product" has something to
    # do with it?
    # "triple product": Project one edge onto the plane spanned by the two others.
    #
    # def _compute_ce_ratios_algebraic(self):
    #     # Precompute edges.
    #     half_edges = (
    #         self.points[self.idx_hierarchy[1]]
    #         - self.points[self.idx_hierarchy[0]]
    #     )

    #     # Build the equation system:
    #     # The equation
    #     #
    #     # |simplex| ||u||^2 = \sum_i \alpha_i <u,e_i> <e_i,u>
    #     #
    #     # has to hold for all vectors u in the plane spanned by the edges,
    #     # particularly by the edges themselves.
    #     # A = np.empty(3, 4, half_edges.shape[2], 3, 3)
    #     A = np.einsum("j...k,l...k->jl...", half_edges, half_edges)
    #     A = A ** 2

    #     # Compute the RHS  cell_volume * <edge, edge>.
    #     # The dot product <edge, edge> is also on the diagonals of A (before squaring),
    #     # but simply computing it again is cheaper than extracting it from A.
    #     edge_dot_edge = np.einsum("...i,...j->...", half_edges, half_edges)
    #     # TODO cell_volumes
    #     self.cell_volumes = np.random.rand(2951)
    #     rhs = edge_dot_edge * self.cell_volumes
    #     exit(1)

    #     # Solve all k-by-k systems at once ("broadcast"). (`k` is the number of edges
    #     # per simplex here.)
    #     # If the matrix A is (close to) singular if and only if the cell is (close to
    #     # being) degenerate. Hence, it has volume 0, and so all the edge coefficients
    #     # are 0, too. Hence, do nothing.
    #     ce_ratios = np.linalg.solve(A, rhs)

    #     return ce_ratios

    def _compute_ce_ratios_geometric(self):
        # For triangles, the covolume/edgelength ratios are
        #
        #   [1]   ce_ratios = -<ei, ej> / cell_volume / 4;
        #
        # for tetrahedra, is somewhat more tricky. This is the reference expression:
        #
        # ce_ratios = (
        #     2 * _my_dot(x0_cross_x1, x2)**2 -
        #     _my_dot(
        #         x0_cross_x1 + x1_cross_x2 + x2_cross_x0,
        #         x0_cross_x1 * x2_dot_x2[..., None] +
        #         x1_cross_x2 * x0_dot_x0[..., None] +
        #         x2_cross_x0 * x1_dot_x1[..., None]
        #     )) / (12.0 * face_areas)
        #
        # Tedious simplification steps (with the help of
        # <https://github.com/nschloe/brute_simplify>) lead to
        #
        #   zeta = (
        #       + ei_dot_ej[0, 2] * ei_dot_ej[3, 5] * ei_dot_ej[5, 4]
        #       + ei_dot_ej[0, 1] * ei_dot_ej[3, 5] * ei_dot_ej[3, 4]
        #       + ei_dot_ej[1, 2] * ei_dot_ej[3, 4] * ei_dot_ej[4, 5]
        #       + self.ei_dot_ej[0] * self.ei_dot_ej[1] * self.ei_dot_ej[2]
        #       ).
        #
        # for the face [1, 2, 3] (with edges [3, 4, 5]), where points and edges are
        # ordered like
        #
        #                        3
        #                        ^
        #                       /|\
        #                      / | \
        #                     /  \  \
        #                    /    \  \
        #                   /      |  \
        #                  /       |   \
        #                 /        \    \
        #                /         4\    \
        #               /            |    \
        #              /2            |     \5
        #             /              \      \
        #            /                \      \
        #           /            _____|       \
        #          /        ____/     2\_      \
        #         /    ____/1            \_     \
        #        /____/                    \_    \
        #       /________                   3\_   \
        #      0         \__________           \___\
        #                        0  \______________\\
        #                                            1
        #
        # This is not a too obvious extension of -<ei, ej> in [1]. However, consider the
        # fact that this contains all pairwise dot-products of edges not part of the
        # respective face (<e0, e1>, <e1, e2>, <e2, e0>), each of them weighted with
        # dot-products of edges in the respective face.
        #
        # Note that, to retrieve the covolume-edge ratio, one divides by
        #
        #       alpha = (
        #           + ei_dot_ej[3, 5] * ei_dot_ej[5, 4]
        #           + ei_dot_ej[3, 5] * ei_dot_ej[3, 4]
        #           + ei_dot_ej[3, 4] * ei_dot_ej[4, 5]
        #           )
        #
        # (which is the square of the face area). It's funny that there should be no
        # further simplification in zeta/alpha, but nothing has been found here yet.
        #

        # From base.py, but spelled out here since we can avoid one sqrt when computing
        # the c/e ratios for the faces.
        alpha = (
            +self.ei_dot_ej[2] * self.ei_dot_ej[0]
            + self.ei_dot_ej[0] * self.ei_dot_ej[1]
            + self.ei_dot_ej[1] * self.ei_dot_ej[2]
        )
        # face_ce_ratios = -self.ei_dot_ej * 0.25 / face_areas[None]
        face_ce_ratios_div_face_areas = -self.ei_dot_ej / alpha

        #
        # self.circumcenter_face_distances =
        #    zeta / (24.0 * face_areas) / self.cell_volumes[None]
        # ce_ratios = \
        #     0.5 * face_ce_ratios * self.circumcenter_face_distances[None],
        #
        # so
        ce_ratios = (
            self.zeta / 48.0 * face_ce_ratios_div_face_areas / self.cell_volumes[None]
        )

        # Distances of the cell circumcenter to the faces.
        face_areas = 0.5 * np.sqrt(alpha)
        self.circumcenter_face_distances = (
            self.zeta / (24.0 * face_areas) / self.cell_volumes[None]
        )

        return ce_ratios

    @property
    def q_min_sin_dihedral_angles(self):
        """Get the smallest of the sines of the 6 angles between the faces of each
        tetrahedron, times a scaling factor that makes sure the value is 1 for the
        equilateral tetrahedron.
        """
        # https://math.stackexchange.com/a/49340/36678
        fa = compute_tri_areas(self.ei_dot_ej)

        el2 = self.ei_dot_ei
        a = el2[0][0]
        b = el2[1][0]
        c = el2[2][0]
        d = el2[0][2]
        e = el2[1][1]
        f = el2[0][1]

        cos_alpha = []

        H2 = (4 * a * d - ((b + e) - (c + f)) ** 2) / 16
        J2 = (4 * b * e - ((a + d) - (c + f)) ** 2) / 16
        K2 = (4 * c * f - ((a + d) - (b + e)) ** 2) / 16

        # Angle between face 0 and face 1.
        # The faces share (face 0, edge 0), (face 1, edge 2).
        cos_alpha += [(fa[0] ** 2 + fa[1] ** 2 - H2) / (2 * fa[0] * fa[1])]
        # Angle between face 0 and face 2.
        # The faces share (face 0, edge 1), (face 2, edge 1).
        cos_alpha += [(fa[0] ** 2 + fa[2] ** 2 - J2) / (2 * fa[0] * fa[2])]
        # Angle between face 0 and face 3.
        # The faces share (face 0, edge 2), (face 3, edge 0).
        cos_alpha += [(fa[0] ** 2 + fa[3] ** 2 - K2) / (2 * fa[0] * fa[3])]
        # Angle between face 1 and face 2.
        # The faces share (face 1, edge 0), (face 2, edge 2).
        cos_alpha += [(fa[1] ** 2 + fa[2] ** 2 - K2) / (2 * fa[1] * fa[2])]
        # Angle between face 1 and face 3.
        # The faces share (face 1, edge 1), (face 3, edge 1).
        cos_alpha += [(fa[1] ** 2 + fa[3] ** 2 - J2) / (2 * fa[1] * fa[3])]
        # Angle between face 2 and face 3.
        # The faces share (face 2, edge 0), (face 3, edge 2).
        cos_alpha += [(fa[2] ** 2 + fa[3] ** 2 - H2) / (2 * fa[2] * fa[3])]

        cos_alpha = np.array(cos_alpha).T
        sin_alpha = np.sqrt(1 - cos_alpha ** 2)

        m = np.min(sin_alpha, axis=1) / (np.sqrt(2) * 2 / 3)
        return m

    @property
    def q_vol_rms_edgelength3(self):
        """For each cell, return the ratio of the volume and the cube of the
        root-mean-square edge length. (This is cell quality measure used by Stellar
        <https://people.eecs.berkeley.edu/~jrs/stellar>.)
        """
        el2 = self.ei_dot_ei
        rms = np.sqrt(
            (el2[0][0] + el2[1][0] + el2[2][0] + el2[0][2] + el2[1][1] + el2[0][1]) / 6
        )
        alpha = np.sqrt(2) / 12  # normalization factor
        return self.cell_volumes / rms ** 3 / alpha

    def num_delaunay_violations(self):
        # Delaunay violations are present exactly on the interior faces where the sum of
        # the signed distances between face circumcenter and tetrahedron circumcenter is
        # negative.
        if self.circumcenter_face_distances is None:
            self._compute_ce_ratios_geometric()
            # self._compute_ce_ratios_algebraic()

        if "faces" not in self.cells:
            self.create_facets()

        sums = np.bincount(
            self.cells["faces"].T.reshape(-1),
            self.circumcenter_face_distances.reshape(-1),
        )

        return np.sum(sums < 0.0)

    def show(self):
        from matplotlib import pyplot as plt

        self.plot()
        plt.show()
        plt.close()

    def plot(self):
        from matplotlib import pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D

        fig = plt.figure()
        ax = fig.gca(projection=Axes3D.name)
        # "It is not currently possible to manually set the aspect on 3D axes"
        # plt.axis("equal")

        X = self.points
        for cell_id in range(len(self.cells["points"])):
            cc = self.cell_circumcenters[cell_id]
            #
            x = X[self.point_face_cells[..., [cell_id]]]
            # TODO replace `self.ei_dot_ei * self.ei_dot_ej` with cell_partitions
            face_ccs = compute_triangle_circumcenters(
                x, self.ei_dot_ei * self.ei_dot_ej
            )
            # draw the face circumcenters
            ax.plot(
                face_ccs[..., 0].flatten(),
                face_ccs[..., 1].flatten(),
                face_ccs[..., 2].flatten(),
                "go",
            )
            # draw the connections
            #   tet circumcenter---face circumcenter
            for face_cc in face_ccs:
                ax.plot(
                    [cc[0], face_cc[cell_id, 0]],
                    [cc[1], face_cc[cell_id, 1]],
                    [cc[2], face_cc[cell_id, 2]],
                    "b-",
                )

    def show_edge(self, edge_id):
        from matplotlib import pyplot as plt

        self.plot_edge(edge_id)
        plt.show()
        plt.close()

    def plot_edge(self, edge_id):
        """Displays edge with ce_ratio.

        :param edge_id: Edge ID for which to show the ce_ratio.
        :type edge_id: int
        """
        # pylint: disable=unused-variable,relative-import
        from matplotlib import pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D

        if "faces" not in self.cells:
            self.create_facets()
        if "edges" not in self.faces:
            self._create_face_edge_relationships()

        fig = plt.figure()
        ax = fig.gca(projection=Axes3D.name)
        # "It is not currently possible to manually set the aspect on 3D axes"
        # plt.axis("equal")

        # find all faces with this edge
        adj_face_ids = np.where((self.faces["edges"] == edge_id).any(axis=1))[0]
        # find all cells with the faces
        # https://stackoverflow.com/a/38481969/353337
        adj_cell_ids = np.where(
            np.in1d(self.cells["faces"], adj_face_ids)
            .reshape(self.cells["faces"].shape)
            .any(axis=1)
        )[0]

        # plot all those adjacent cells; first collect all edges
        adj_edge_ids = np.unique(
            [
                adj_edge_id
                for adj_cell_id in adj_cell_ids
                for face_id in self.cells["faces"][adj_cell_id]
                for adj_edge_id in self.faces["edges"][face_id]
            ]
        )
        col = "k"
        for adj_edge_id in adj_edge_ids:
            x = self.points[self.edges["points"][adj_edge_id]]
            ax.plot(x[:, 0], x[:, 1], x[:, 2], col)

        # make clear which is edge_id
        x = self.points[self.edges["points"][edge_id]]
        ax.plot(x[:, 0], x[:, 1], x[:, 2], color=col, linewidth=3.0)

        # connect the face circumcenters with the corresponding cell
        # circumcenters
        X = self.points
        for cell_id in adj_cell_ids:
            cc = self.cell_circumcenters[cell_id]
            #
            x = X[self.point_face_cells[..., [cell_id]]]
            # TODO replace `self.ei_dot_ei * self.ei_dot_ej` with cell_partitions
            face_ccs = compute_triangle_circumcenters(
                x, self.ei_dot_ei * self.ei_dot_ej
            )
            # draw the face circumcenters
            ax.plot(
                face_ccs[..., 0].flatten(),
                face_ccs[..., 1].flatten(),
                face_ccs[..., 2].flatten(),
                "go",
            )
            # draw the connections
            #   tet circumcenter---face circumcenter
            for face_cc in face_ccs:
                ax.plot(
                    [cc[0], face_cc[cell_id, 0]],
                    [cc[1], face_cc[cell_id, 1]],
                    [cc[2], face_cc[cell_id, 2]],
                    "b-",
                )

        # draw the cell circumcenters
        cc = self.cell_circumcenters[adj_cell_ids]
        ax.plot(cc[:, 0], cc[:, 1], cc[:, 2], "ro")
        return

    def show_cell(
        self,
        cell_id,
        control_volume_boundaries_rgba=None,
        barycenter_rgba=None,
        circumcenter_rgba=None,
        incenter_rgba=None,
        face_circumcenter_rgba=None,
        insphere_rgba=None,
        circumsphere_rgba=None,
        line_width=1.0,
        close=False,
        render=True,
    ):
        import vtk

        def get_line_actor(x0, x1, line_width=1.0):
            source = vtk.vtkLineSource()
            source.SetPoint1(x0)
            source.SetPoint2(x1)
            # mapper
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(source.GetOutputPort())
            # actor
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            # color actor
            actor.GetProperty().SetColor(0, 0, 0)
            actor.GetProperty().SetLineWidth(line_width)
            return actor

        def get_sphere_actor(x0, r, rgba):
            # Generate polygon data for a sphere
            sphere = vtk.vtkSphereSource()

            sphere.SetCenter(x0)
            sphere.SetRadius(r)

            sphere.SetPhiResolution(100)
            sphere.SetThetaResolution(100)

            # Create a mapper for the sphere data
            sphere_mapper = vtk.vtkPolyDataMapper()
            # sphere_mapper.SetInput(sphere.GetOutput())
            sphere_mapper.SetInputConnection(sphere.GetOutputPort())

            # Connect the mapper to an actor
            sphere_actor = vtk.vtkActor()
            sphere_actor.SetMapper(sphere_mapper)
            sphere_actor.GetProperty().SetColor(rgba[:3])
            sphere_actor.GetProperty().SetOpacity(rgba[3])
            return sphere_actor

        # Visualize
        renderer = vtk.vtkRenderer()
        render_window = vtk.vtkRenderWindow()
        render_window.AddRenderer(renderer)
        render_window_interactor = vtk.vtkRenderWindowInteractor()
        render_window_interactor.SetRenderWindow(render_window)

        for ij in [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]]:
            x0, x1 = self.points[self.cells["points"][cell_id][ij]]
            renderer.AddActor(get_line_actor(x0, x1, line_width))
        renderer.SetBackground(1.0, 1.0, 1.0)

        r = 0.02

        if circumcenter_rgba is not None:
            renderer.AddActor(
                get_sphere_actor(self.cell_circumcenters[cell_id], r, circumcenter_rgba)
            )

        if circumsphere_rgba is not None:
            renderer.AddActor(
                get_sphere_actor(
                    self.cell_circumcenters[cell_id],
                    self.cell_circumradius[cell_id],
                    circumsphere_rgba,
                )
            )

        if incenter_rgba is not None:
            renderer.AddActor(
                get_sphere_actor(self.cell_incenters[cell_id], r, incenter_rgba)
            )

        if insphere_rgba is not None:
            renderer.AddActor(
                get_sphere_actor(
                    self.cell_incenters[cell_id],
                    self.cell_inradius[cell_id],
                    insphere_rgba,
                )
            )

        if barycenter_rgba is not None:
            renderer.AddActor(
                get_sphere_actor(self.cell_barycenters[cell_id], r, barycenter_rgba)
            )

        if face_circumcenter_rgba is not None:
            x = self.points[self.point_face_cells[..., [cell_id]]]
            # TODO replace `self.ei_dot_ei * self.ei_dot_ej` with cell_partitions
            face_ccs = compute_triangle_circumcenters(
                x, self.ei_dot_ei * self.ei_dot_ej
            )[:, 0, :]
            for f in face_ccs:
                renderer.AddActor(get_sphere_actor(f, r, face_circumcenter_rgba))

        if control_volume_boundaries_rgba:
            cell_cc = self.cell_circumcenters[cell_id]
            x = self.points[self.point_face_cells[..., [cell_id]]]
            # TODO replace `self.ei_dot_ei * self.ei_dot_ej` with cell_partitions
            face_ccs = compute_triangle_circumcenters(
                x, self.ei_dot_ei * self.ei_dot_ej
            )[:, 0, :]
            for face, face_cc in zip(range(4), face_ccs):
                for edge in range(3):
                    k0, k1 = self.idx_hierarchy[:, edge, face, cell_id]
                    edge_midpoint = 0.5 * (self.points[k0] + self.points[k1])

                    points = vtk.vtkPoints()
                    points.InsertNextPoint(*edge_midpoint)
                    points.InsertNextPoint(*cell_cc)
                    points.InsertNextPoint(*face_cc)

                    triangle = vtk.vtkTriangle()
                    triangle.GetPointIds().SetId(0, 0)
                    triangle.GetPointIds().SetId(1, 1)
                    triangle.GetPointIds().SetId(2, 2)

                    triangles = vtk.vtkCellArray()
                    triangles.InsertNextCell(triangle)

                    trianglePolyData = vtk.vtkPolyData()
                    trianglePolyData.SetPoints(points)
                    trianglePolyData.SetPolys(triangles)

                    # mapper
                    mapper = vtk.vtkPolyDataMapper()
                    mapper.SetInputData(trianglePolyData)

                    # actor
                    actor = vtk.vtkActor()
                    actor.SetMapper(mapper)

                    actor.GetProperty().SetColor(*control_volume_boundaries_rgba[:3])
                    actor.GetProperty().SetOpacity(control_volume_boundaries_rgba[3])
                    renderer.AddActor(actor)

        if render:
            render_window.Render()

        if close:
            render_window.Finalize()
            del render_window, render_window_interactor
        else:
            render_window_interactor.Start()