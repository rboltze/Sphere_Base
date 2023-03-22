# -*- coding: utf-8 -*-

"""
camera module. Contains the camera class. Is used to create a camera object for the implementation. In the
current implementation there is only need for a single camera object.

"""

from pyrr import Vector3, Vector4, vector, matrix44
from sphere_base.sphere_universe_base.suv_cam_movement import CameraMovement
from sphere_base.constants import *

MOUSE_SENSITIVITY = .1
TARGET = Vector3([0.0, 0.0, 0.0])
DEFAULT_POS = Vector3([0.0, 0.0, 3.0])


class Camera:
    CameraMovement_class = CameraMovement
    """
    Class representing the camera. 

    """

    def __init__(self, parent):
        """
        Constructor of the camera class.  Creates a single camera object for the program.


        :param parent: This class is instantiated from the :class:`~sphere_iot.uv_universe.Universe`
        :type parent: :class:`~sphere_iot.uv_universe.Universe`


        :Instance Attributes:

        - **cm** - Instance of :class:`~sphere_iot.uv_cam_movement.CameraMovement`
        - **shader** - Instance of :class:`~sphere_iot.shader.uv_default_shader.DefaultShader` from universe
        - **config** - Instance of :class:`~sphere_iot.uv_config.UvConfig` from universe


        :Instance Variables:

        - **target** - ``Vector`` xyz position of the target sphere_base.
        - **distance_to_target** - distance between camera and center of the target sphere_base. (``Vector3``).
        - **camera_direction** - normalized ``vector3`` pointing away from the center of the target sphere_base through the center of the camera.
        - **camera_up** - ``Vector3`` with the ``up`` position of the camera.
        - **xyz** - position of the camera (``Vector3``).
        - **mouse_sensitivity** - ``float`` modifier to adjust the sensitivity of the mouse when moving the camera.

        """

        self._init_variables()

        self.shader = parent.shader
        self.config = parent.config

        self._set_view()

        # has the calculations for camera movement
        self.cm = self.__class__.CameraMovement_class(self)
        self.set_movement_values()

        view = self.get_view_matrix()
        self.config.set_view_loc(view)

    def _init_variables(self):
        # camera target pointing at origin
        self.target = TARGET
        self.set_position()
        self.distance_to_target = None
        self.camera_direction = None
        self.camera_up = None

        self.mouse_sensitivity = MOUSE_SENSITIVITY
        self.movement_stack = []
        self.target_stack = []

    def _set_view(self):
        # distance to target
        self.distance_to_target = self.get_distance_to_target()

        # direction vector, points away from target
        self.camera_direction = vector.normalize(Vector3(self.xyz) - Vector3(self.target))

        # right vector that represents the positive x-axis of the camera space
        up = Vector3([0.0, 1.0, 0.0])
        camera_right = vector.normalize(Vector3.cross(up, self.camera_direction))
        self.camera_up = Vector3.cross(Vector3(self.camera_direction), Vector3(camera_right))

    def set_position(self):
        self.xyz = DEFAULT_POS

    def set_movement_values(self, min_radius=MIN_RADIUS, cam_movement_steps=CAM_MOVEMENT_STEPS):
        self.cm.set_minimum_values(min_radius, cam_movement_steps)

    def reset_to_default_view(self, target_sphere, default_pos= DEFAULT_POS):
        """
        Resetting the camera view to the default view on the sphere_base, without any rotation.

        :param target_sphere: The target :class:`~sphere_iot.uv_sphere.Sphere` the camera is looking at
        :type target_sphere:  :class:`~sphere_iot.uv_sphere.Sphere`

        """

        # used when de-serializing
        self.target = target_sphere.xyz
        self.xyz = self.target + default_pos

        self.move_to_new_target_sphere(target_sphere)
        self.cm.reset()
        self._set_view()

    def get_view_matrix(self) -> 'matrix44':
        """
        Set view and get the look at matrix

        """

        self._set_view()
        m = matrix44.create_look_at(self.xyz, self.target, self.camera_up)
        self.config.set_view_loc(m)
        return m

    def process_mouse_movement(self, target_sphere: 'sphere_base', x_offset: int, y_offset: int):
        """
        :param target_sphere: The :class:`~sphere_iot.uv_sphere.Sphere` the camera is looking at
        :type target_sphere: :class:`~sphere_iot.uv_sphere.Sphere`
        :param x_offset: used for rotation
        :type x_offset: ``int``
        :param y_offset: used for up and down (yaw) movement
        :type y_offset: ``int``

        """
        x_offset *= self.mouse_sensitivity
        y_offset *= self.mouse_sensitivity

        self.process_movement(target_sphere, rotation=x_offset, angle_up=y_offset)

    def process_movement(self, target_sphere: 'sphere_base' = None, rotation: int = 0, angle_up: int = 0, radius: int = 0):
        """
        Moves the camera around the target sphere_base based on received angles.

        :param target_sphere: The :class:`~sphere_iot.uv_sphere.Sphere` the camera is looking at
        :type target_sphere: :class:`~sphere_iot.uv_sphere.Sphere`
        :param rotation: rotation angle
        :type rotation: ``int``
        :param angle_up: yaw or angle up or down
        :type angle_up: ``int``
        :param radius: distance to the center of the target sphere_base
        :type radius: ``float``

        """
        xyzw = self.cm.orbit_around_target(target_sphere, rotation, angle_up, radius)
        self.xyz = Vector3(Vector4(xyzw).xyz)
        view = self.get_view_matrix()
        self.config.set_view_loc(view)

    def move_to_new_target_sphere(self, target_sphere: 'Sphere'):
        """
        Moves the camera from its current location to the new target sphere_base.

        :param target_sphere: The new :class:`~sphere_iot.uv_sphere.Sphere` to move to.
        :type target_sphere: :class:`~sphere_iot.uv_sphere.Sphere`

        """
        self.cm.move_to_new_target(target_sphere)

    def get_angles(self) -> (int, int):
        """
        Returns current camera rotation and yaw angles

        """

        return self.cm.rotation, self.cm.yaw

    def get_distance_to_target(self):
        return vector.length(Vector3(self.target) - Vector3(self.xyz))

    def draw(self):
        """
        Sets the camera view for use with all shaders. If a new sphere_base target is _selected move the camera
        to the new position.

        """

        # if a sphere_base has been on_current_row_changed (_selected) then move the camera to the new sphere_base
        if len(self.movement_stack) > 0:
            self.xyz = Vector3(self.movement_stack[0])
            self.target = Vector3(self.target_stack[0])
            del self.movement_stack[0]
            del self.target_stack[0]

        # The view needs to be updated before drawing. This is because OpenGL is a state machine that listens to
        # changes program wide spanning instances!
        self.get_view_matrix()








