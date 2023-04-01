# -*- coding: utf-8 -*-

"""
Sphere Surface Edge module. Contains the SphereSurfaceEdge class.
Edges are drawn between sockets over the surface of a sphere_base.

"""

# Do not remove these!!!
# -------------- these will be dynamically read! -----------------------

from sphere_base.shader.sphere_edge_shader import SphereEdgeShader

# -----------------------------------------------------------------------

from pyrr import quaternion
from sphere_base.sphere.graphic_edge import GraphicEdge
from sphere_base.serializable import Serializable
from collections import OrderedDict
from sphere_base.utils import dump_exception
import numpy as np
from sphere_base.constants import *
from OpenGL.GL import *


DEBUG = False


class SurfaceEdge(Serializable):
    """
    Class representing an ``Edge`` on a ``Sphere``. ``Edges`` are drawn between ``Sphere Sockets``.

    This class represents the edge between two sockets. The edges follow the surface of an sphere_base.
    We are using SLERP to determine the angle of each of the points between start and end
    with the center of the sphere_base.

    .. note::

    There is no difference between start and end socket. It is not relevant in the current deployment. In
    future iterations this is likely to change as the direction of the edge may have significance.


    .. warning::

        Currently all lines are drawn using OpenGL begin..end methods,
        instead of modern opengl methods with VBO, VBA.
        This needs to be corrected in a future iteration as 'apparently' this method is very slow.

        How it should work:
        The edge starts at the start socket and ends at the end socket. It takes the shortest distance over the
        surface of the sphere.

        All the variables needed are known:

            - Start_socket angle with origin sphere
            - end socket angle with origin sphere
            - radius of the sphere

        We then can decide how many points we need to plot between start and end based on the distance
        over the sphere.

        When creating or dragging a node with an edge, the vertices change and need to replace the existing
        vertices before drawing the new ones.


    """
    GraphicsEdge_class = GraphicEdge

    def __init__(self, target_sphere: 'sphere_base', socket_start: 'socket' = None, socket_end: 'socket' = None):
        """
        Constructor of the edge class. Creates an edge between a start and an end socket.

        :param target_sphere: The sphere_base on which the edge is drawn
        :type target_sphere: :class:`~sphere_iot.uv_sphere.Sphere`
        :param socket_start: start socket from where is drawn.
        :type socket_start: :class:`~sphere_iot.uv_socket.Socket`
        :param socket_end: end socket where the edge is drawn to.
        :type socket_end: :class:`~sphere_iot.uv_socket.Socket`

        :Instance Attributes:

            - **uv** - Instance of :class:`~sphere_iot.uv_universe.Universe`
            - **sphere_base** - Instance of :class:`~sphere_iot.uv_sphere.Sphere`
            - **calc** - Instance of :class:`~sphere_iot.uv_calc.UvCalc`
            - **model** - Instance of :class:`~sphere_iot.uv_models.Model`
            - **gr_edge** - Instance of :class:`~sphere_iot.uv_graphic_edge.GraphicEdge`
            - **shader** - Instance of :class:`~sphere_iot.shader.uv_base_shader.BaseShader`

        """

        super().__init__("edge")
        self.sphere = target_sphere
        self.calc = self.sphere.calc
        self.config = self.sphere.config

        self._start_socket, self._end_socket = None, None
        self.start_socket = socket_start if socket_start else None
        self.end_socket = socket_end if socket_end else None

        self.gr_edge = self.__class__.GraphicsEdge_class(self)
        self.uv = self.sphere.uv

        self.shader1 = None
        self.shader1 = self.set_up_shader()
        self.shader = self.sphere.shader
        self.model = self.uv.models.get_model('edge1')


        # ------------------------------------------------------------
        self.mesh_id = self.uv.config.get_mesh_id()
        self.vertices = self.vertices = np.array([], dtype=np.float32)  # vertex coordinates
        self.buffer = np.array([], dtype=np.float32)

        self.prepare_open_gl()

        # ------------------------------------------------------------

        self.radius = self.sphere.radius
        self.pos_array = []
        self.collision_object_id = None
        self.color = self.gr_edge.color
        self.edge_type = 0
        self.serialized_detail_scene = None
        self._edge_moved = False

        # register the edge to the sphere_base for rendering
        self.sphere.add_item(self)
        self.update_position()


    def set_up_shader(self):

        for _name in MODELS.keys():
            if _name == "edge1":
                shader = MODELS[_name]["shader"]
                vertex_shader = MODELS[_name]["vertex_shader"]
                fragment_shader = MODELS[_name]["fragment_shader"]
                geometry_shader = MODELS[_name]["geometry_shader"]
                geometry_shader = None if geometry_shader == "none" else geometry_shader

                # setup and return the found shader
                shader = eval(shader)(self, vertex_shader, fragment_shader, geometry_shader)
                return shader

    def prepare_open_gl(self):
        self.mesh_id = glGenVertexArrays(1)
        self.buffer_id = glGenBuffers(1)

    def load_mesh_into_opengl(self):
        try:

            glBindVertexArray(self.mesh_id)

            # vertex Buffer Object
            glBindBuffer(GL_ARRAY_BUFFER, self.buffer_id)
            glBufferData(GL_ARRAY_BUFFER, self.buffer.nbytes, self.buffer, GL_STATIC_DRAW)
            #
            # # # element Buffer Object
            # # glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.config.EBO[mesh_id])
            # # glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
            #
            # # vertex positions
            # Enable the Vertex Attribute so that OpenGL knows to use it
            glEnableVertexAttribArray(0)
            # Configure the Vertex Attribute so that OpenGL knows how to read the VBO
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, self.buffer.itemsize * 8, ctypes.c_void_p(0))
            #
            # # # textures
            # # # Enable the Vertex Attribute so that OpenGL knows to use it
            # # glEnableVertexAttribArray(1)
            # # # Configure the Vertex Attribute so that OpenGL knows how to read the VBO
            # # glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, buffer.itemsize * 8, ctypes.c_void_p(12))
            #
            # # # normals
            # # # Enable the Vertex Attribute so that OpenGL knows to use it
            # # glEnableVertexAttribArray(2)
            # # # Configure the Vertex Attribute so that OpenGL knows how to read the VBO
            # # glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, self.buffer.itemsize * 8, ctypes.c_void_p(20))
            #
            # #  Bind the VBO, VAO to 0 so that we don't accidentally modify the VAO and VBO we created
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindVertexArray(0)
            # # Bind the EBO to 0 so that we don't accidentally modify it
            # # MAKE SURE TO UNBIND IT AFTER UNBINDING THE VAO, as the EBO is linked in the VAO
            # # This does not apply to the VBO because the VBO is already linked to the VAO during glVertexAttribPointer
            # glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
            #
            self.shader.set_environment()

        except Exception as e:
            dump_exception(e)

    @property
    def start_socket(self):
        """
        Start socket

        :getter: Returns start :class:`~sphere_iot.uv_socket.Socket`
        :setter: Sets start :class:`~sphere_iot.uv_socket.Socket` safely
        :type: :class:`~sphere_iot.uv_socket.Socket`
        """
        return self._start_socket

    @start_socket.setter
    def start_socket(self, start_socket):

        # if already connected, delete  from  socket
        if self._start_socket is not None:
            self._start_socket.remove_edge(self)

        # assign new start socket
        self._start_socket = start_socket

        # add edge to the new socket class
        if self.start_socket is not None:
            self.start_socket.add_edge(self)

    @property
    def end_socket(self):
        """
        End socket

        :getter: Returns end :class:`~sphere_iot.uv_socket.Socket`
        :setter: Sets end :class:`~sphere_iot.uv_socket.Socket` safely
        :type: :class:`~sphere_iot.uv_socket.Socket`
        """
        return self._end_socket

    @end_socket.setter
    def end_socket(self, end_socket):

        # if already connected, delete  from  socket
        if self._end_socket is not None:
            self._end_socket.remove_edge(self)

        # assign new end socket
        self._end_socket = end_socket

        # add edge to the Socket class
        if self.end_socket is not None:
            self.end_socket.add_edge(self)

    def update_position(self):
        """
        Updates the position of the edge. First calculates the number of vertices to use.
        Then calls 'update_line_points_position' for the calculation of the position of each of the vertices.
        """
        # get number of vertices on the edge
        if self.start_socket and self.end_socket:
            n = self.gr_edge.get_number_of_points(self.start_socket.xyz, self.end_socket.xyz,
                                                  self.radius, self.gr_edge.unit_length)
            step = 1 / n if n > 1 else 1
            if n > 0:
                self.update_line_points_position(n, step)

            self.load_mesh_into_opengl()

    def update_line_points_position(self, number_of_vertices: int, step: float):
        """
        Creates an array of point locations. SLERP is used to find angles with the center of the sphere_base for
        each of the points.

        :param number_of_vertices: Number of points on the edge
        :type number_of_vertices: ``int``
        :param step: percentage of increase for each point on the edge
        :type step: ``float``
        """

        start, end = self.get_edge_start_end()
        self.pos_array = []

        for i in range(number_of_vertices):
            pos_orientation_offset = quaternion.slerp(start, end, step * i)
            pos = self.gr_edge.get_position(pos_orientation_offset)
            self.pos_array.append([pos[0], pos[1], pos[2]])

        # creating a collision object for mouse picking
        self.collision_object_id = self.sphere.uv.mouse_ray.create_collision_object(self, self.pos_array)

        self.xyz = self.start_socket.xyz
        self.update_buffers(self.pos_array)

    def update_buffers(self, pos_array):
        # takes the list with points and puts them in one list
        vertices = []
        for point in pos_array:
            vertices.append(point[0])
            vertices.append(point[1])
            vertices.append(point[2])

        self.vertices = np.array(vertices, dtype=np.float32)
        self.buffer = np.array(self.vertices, dtype=np.float32)

        # self.uv.models.load_mesh_into_opengl(self.model.meshes[0].mesh_id, self.model.meshes[0].buffer, self.model.meshes[0].indices,
        #                                      self.model.shader)

    def update_content(self, value, item_id):
        """
        This is called on all sphere_base items but is currently not used on edges.
        Updates the content like icons and images

        """
        # needs to be overridden
        pass

    def get_edge_start_end(self):
        # get clearance from start socket
        r = self.start_socket.node.gr_node.node_disc_radius
        ln = self.calc.get_distance_on_sphere(self.end_socket, self.start_socket, self.radius)
        t = r / ln

        s_angle = self.start_socket.pos_orientation_offset
        end = self.end_socket.pos_orientation_offset

        start = quaternion.slerp(s_angle, end, t)

        return start, end

    def is_dragging(self, value=False):
        if self._edge_moved == value:
            return value
        elif self._edge_moved and not value:
            # end dragging
            self._edge_moved = False
            self.sphere.history.store_history("edge moved", True)
        elif not self._edge_moved and value:
            # start dragging
            self._edge_moved = True
        return self._edge_moved

    def on_selected_event(self, event: bool):
        """
        Sets all flags and colors to match the new state.

        :param event: ``True`` sets the state to '_selected'
        :type event: ``bool``
        """
        self.color = self.gr_edge.on_selected_event(event)

    def set_hovered(self, event: bool):
        """
        Sets all flags and colors to match the new state.

        :param event: ``True`` sets the state to 'hovered'
        :type event: ``bool``
        """
        self.color = self.gr_edge.on_hover_event(event)

    def remove(self):
        """
        Removes the edge and the collision object
        """

        # make sure that the edge gets removed from both sockets
        self.start_socket.remove_edge(self)
        self.end_socket.remove_edge(self)
        self.sphere.remove_item(self)

        if self.collision_object_id:
            self.sphere.uv.mouse_ray.delete_collision_object(self)

    def draw(self):
        """
        Renders the edge.
        """
        # in some cases color turns to none. The reason is not known. The following line patches this problem
        self.color = [0.0, 0.0, 0.0, 0.5] if not self.color else self.color
        self.shader.draw_edge(self.pos_array, width=1.5, color=self.color, dotted=False)
        self.model.shader.draw_edge(self.pos_array, width=4, color=self.color, dotted=False)
        try:
            pass
            if len(self.vertices) == 0: return
            # print("buffer", self.buffer)
            # print("vertices", self.vertices)
            glBindVertexArray(self.mesh_id)

            glBindBuffer(GL_ARRAY_BUFFER, self.buffer_id)
            glBufferData(GL_ARRAY_BUFFER, len(self.vertices), self.vertices, GL_STATIC_DRAW)

            # print(mesh_index, self.vertices)

            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, self.buffer.itemsize * 3, ctypes.c_void_p(0))
            # print("mesh_index", mesh_index, self.config.EBO[mesh_index])
            # ------------------------------


            # enable blending
            # glEnable(GL_BLEND)
            # glUniform4f(self.color, *self.color)
            glDrawArrays(GL_LINES, 0, 2)

            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindVertexArray(0)

        except Exception as e:
            dump_exception(e)

    def serialize(self):
        return OrderedDict([
            ('id', self.id),
            ('type', self.type),
            ('edge_type', self.edge_type),
            ('start_socket_id', self.start_socket.id),
            ('end_socket_id', self.end_socket.id),
            ('scene', self.serialized_detail_scene)
        ])

    def deserialize(self, data: dict, hashmap: dict = None, restore_id: bool = True) -> bool:
        if restore_id:
            self.id = data['id']
        self.edge_type = data['edge_type']
        self.start_socket = self.sphere.get_item_by_id(data['start_socket_id'])
        self.end_socket = self.sphere.get_item_by_id(data['end_socket_id'])
        self.serialized_detail_scene = data['scene']
        self.update_position()
        return True
