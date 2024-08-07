# -*- coding: utf-8 -*-

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# Contributed to by fdaubine


"""
Align2Custom module implementation
"""


import math
import mathutils as mu
import threading as thd
import time
import bpy


# ## Global data ##############################################################
GL_ADDON_KEYMAPS = []       # Keymap collection
GL_TOKEN_LOCK = False       # Locking token while rotating 3D View


# ## Math functions section ###################################################
def s_curve(x):
    """
    Function that returns the transformation of a linear value by a s-curve
    function.

    Parameter :
     - x [in] : float value [0.0, 1.0]

    Return value : float value
    """

    assert (0.0 <= x <= 1.0), ("Overflow error : argument 'x' should "
                               "be in the range [0, 1]")

    return (1.0 + math.sin((x - 0.5) * math.pi))/2.0


# ## Preferences section ######################################################
class A2C_Preferences(bpy.types.AddonPreferences):
    """
    Addon panel of the 'Preferences...' interface
    """

    bl_idname = __package__

    pref_smooth: bpy.props.BoolProperty(name="Smooth rotation",
                                        default=True,
                                        )

    def draw(self, context):
        """ Display 'smooth' option in panel """
        self.layout.prop(self, "pref_smooth")


# ## Operator section #########################################################
class VIEW3D_OT_a2c(bpy.types.Operator):
    """
    Align 3D View to 3D cursor or active custom transform orientation
    """

    bl_idname = "view3d.a2c"
    bl_label = "Align to 3D cursor or custom transform orientation"
    bl_options = {'REGISTER', 'UNDO'}

    ALIGN_MODE_ITEMS = [
        ("CUSTOM", "Align to custom orientation", "", 1),
        ("CURSOR", "Align to cursor orientation", "", 2),
    ]

    VIEWPOINT_ITEMS = [
        ("TOP", "Top view", "", 1),
        ("BOTTOM", "Bottom view", "", 2),
        ("FRONT", "Front view", "", 3),
        ("BACK", "Back view", "", 4),
        ("RIGHT", "Right view", "", 5),
        ("LEFT", "Left view", "", 6),
    ]

    prop_align_mode: bpy.props.EnumProperty(items=ALIGN_MODE_ITEMS,
                                            name="Align mode",
                                            default="CUSTOM")
    prop_viewpoint: bpy.props.EnumProperty(items=VIEWPOINT_ITEMS,
                                           name="Point of view",
                                           default="TOP")

    SMOOTH_ROT_STEP = 0.02
    SMOOTH_ROT_DURATION = 0.24

    @staticmethod
    def smooth_rotate(space, quat_begin, quat_end):
        """
        Rotate the 3D view smoothly between the quaternions 'quat_begin' and
        'quat_end'
        """

        global GL_TOKEN_LOCK

        if space:
            # Calculation of the rotation angle which is used to compute the
            # smooth rotation duration
            diff_quat = quat_end.rotation_difference(quat_begin)
            _, angle = diff_quat.to_axis_angle()
            duration = abs(VIEW3D_OT_a2c.SMOOTH_ROT_DURATION * angle / math.pi)

            start_time = time.time()
            current_time = start_time

            while current_time <= start_time + duration:
                if duration == 0.0:
                    factor = 1.0
                else:
                    factor = s_curve((current_time - start_time) / duration)
                orientation = quat_begin.slerp(quat_end, factor)
                space.region_3d.view_rotation = orientation

                time.sleep(VIEW3D_OT_a2c.SMOOTH_ROT_STEP)
                current_time = time.time()

            space.region_3d.view_rotation = quat_end

        GL_TOKEN_LOCK = False

    def execute(self, context):
        """
        Set the orientation of the 3D View in which the operator is called,
        as a combination of the 3D cursor matrix or the active custom transform
        orientation matrix, and the rotation matrix passed in argument.

        The rotation transition depends on the parameter selected in the addon
        preferences UI. The transition can be instantaneous or smooth.
        """

        global GL_TOKEN_LOCK

        # Get the addon preferences
        prefs = context.preferences.addons[__package__].preferences

        scene = context.window.scene
        space = context.space_data

        co = scene.transform_orientation_slots[0].custom_orientation
        if (not GL_TOKEN_LOCK) and \
           (space.type == 'VIEW_3D') and \
           ((self.prop_align_mode == 'CURSOR') or co):

            # Compute the rotation matrix according to the desired viewpoint
            if self.prop_viewpoint == "BOTTOM":
                rot_matrix = mu.Matrix.Rotation(math.radians(180.0), 3, 'X')
            elif self.prop_viewpoint == "FRONT":
                rot_matrix = mu.Matrix.Rotation(math.radians(90.0), 3, 'X')
            elif self.prop_viewpoint == "BACK":
                rot_matrix = mu.Matrix.Rotation(math.radians(90.0), 3, 'X')\
                           @ mu.Matrix.Rotation(math.radians(180.0), 3, 'Y')
            elif self.prop_viewpoint == "RIGHT":
                rot_matrix = mu.Matrix.Rotation(math.radians(90.0), 3, 'X')\
                           @ mu.Matrix.Rotation(math.radians(90.0), 3, 'Y')
            elif self.prop_viewpoint == "LEFT":
                rot_matrix = mu.Matrix.Rotation(math.radians(90.0), 3, 'X')\
                           @ mu.Matrix.Rotation(math.radians(-90.0), 3, 'Y')
            else:   # TOP (DEFAULT)
                rot_matrix = mu.Matrix.Identity(3)

            if self.prop_align_mode == 'CURSOR':
                new_orientation = scene.cursor.matrix.to_3x3() @ rot_matrix
            else:
                new_orientation = co.matrix @ rot_matrix

            final_quat = new_orientation.to_quaternion()

            space.region_3d.view_perspective = 'ORTHO'

            if prefs.pref_smooth:
                initial_quat = space.region_3d.view_rotation
                rotation_job = thd.Thread(
                                    target=VIEW3D_OT_a2c.smooth_rotate,
                                    args=(space, initial_quat, final_quat))

                GL_TOKEN_LOCK = True
                rotation_job.start()
            else:
                space.region_3d.view_rotation = final_quat

        return {'FINISHED'}


# ## Menus section ############################################################
class VIEW3D_MT_a2c(bpy.types.Menu):
    """
    Submenu 'Align View ...' base class
    """

    bl_idname = "VIEW3D_MT_a2c"
    bl_label = "Align View base class"

    def draw(self, context):
        """ Display menu items """
        self.create_items(context)

    def create_items(self, context, align_mode='CUSTOM'):
        """ Create menu items """
        operator_prop = self.layout.operator(VIEW3D_OT_a2c.bl_idname,
                                             text="Top")
        operator_prop.prop_viewpoint = 'TOP'
        operator_prop.prop_align_mode = align_mode
        operator_prop = self.layout.operator(VIEW3D_OT_a2c.bl_idname,
                                             text="Bottom")
        operator_prop.prop_viewpoint = 'BOTTOM'
        operator_prop.prop_align_mode = align_mode

        self.layout.separator()

        operator_prop = self.layout.operator(VIEW3D_OT_a2c.bl_idname,
                                             text="Front")
        operator_prop.prop_viewpoint = 'FRONT'
        operator_prop.prop_align_mode = align_mode
        operator_prop = self.layout.operator(VIEW3D_OT_a2c.bl_idname,
                                             text="Back")
        operator_prop.prop_viewpoint = 'BACK'
        operator_prop.prop_align_mode = align_mode

        self.layout.separator()

        operator_prop = self.layout.operator(VIEW3D_OT_a2c.bl_idname,
                                             text="Right")
        operator_prop.prop_viewpoint = 'RIGHT'
        operator_prop.prop_align_mode = align_mode
        operator_prop = self.layout.operator(VIEW3D_OT_a2c.bl_idname,
                                             text="Left")
        operator_prop.prop_viewpoint = 'LEFT'
        operator_prop.prop_align_mode = align_mode


class VIEW3D_MT_align2custom(VIEW3D_MT_a2c):
    """
    Submenu 'Align View to Custom' : offers to select one of the 6 possible
    orientations (Top, Bottom, Front, Back, Right, Left) according to the
    selected custom transform orientation axes
    """

    bl_idname = "VIEW3D_MT_align2custom"
    bl_label = "Align View to Custom"

    def draw(self, context):
        """ Display menu items """
        self.create_items(context, 'CUSTOM')


class VIEW3D_MT_align2cursor(VIEW3D_MT_a2c):
    """
    Submenu 'Align View to Cursor' : offers to select one of the 6 possible
    orientations (Top, Bottom, Front, Back, Right, Left) according to the
    3D cursor axes
    """

    bl_idname = "VIEW3D_MT_align2cursor"
    bl_label = "Align View to Cursor"

    def draw(self, context):
        """ Display menu items """
        self.create_items(context, 'CURSOR')


def a2c_menu_func(self, context):
    """
    Append the submenus 'Align View to Custom' and 'Align View to Cursor' to
    the menu 'View3D > View > Align View'
    """

    self.layout.separator()
    self.layout.menu(VIEW3D_MT_align2custom.bl_idname)
    self.layout.menu(VIEW3D_MT_align2cursor.bl_idname)


# ## Blender registration section #############################################
def register():
    """
    Module register function called by the main package register function
    """
    global GL_ADDON_KEYMAPS

    bpy.utils.register_class(A2C_Preferences)
    bpy.utils.register_class(VIEW3D_OT_a2c)
    bpy.utils.register_class(VIEW3D_MT_a2c)
    bpy.utils.register_class(VIEW3D_MT_align2custom)
    bpy.utils.register_class(VIEW3D_MT_align2cursor)

    bpy.types.VIEW3D_MT_view_align.append(a2c_menu_func)

    if bpy.context.window_manager.keyconfigs.addon:
        km = bpy.context.window_manager.keyconfigs.addon.keymaps.new(
            name='3D View',
            space_type='VIEW_3D')

        def set_km_item(km, key, ctrl, viewpoint, align_mode):
            global GL_ADDON_KEYMAPS

            if km:
                kmi = km.keymap_items.new(VIEW3D_OT_a2c.bl_idname,
                                          key, 'PRESS',
                                          alt=True, ctrl=ctrl)
                kmi.properties.prop_viewpoint = viewpoint
                kmi.properties.prop_align_mode = align_mode
                GL_ADDON_KEYMAPS.append((km, kmi))

        # Shortcuts for align to custom orientation operators
        set_km_item(km, 'NUMPAD_7', False, 'TOP', 'CUSTOM')
        set_km_item(km, 'NUMPAD_7', True, 'BOTTOM', 'CUSTOM')
        set_km_item(km, 'NUMPAD_1', False, 'FRONT', 'CUSTOM')
        set_km_item(km, 'NUMPAD_1', True, 'BACK', 'CUSTOM')
        set_km_item(km, 'NUMPAD_3', False, 'RIGHT', 'CUSTOM')
        set_km_item(km, 'NUMPAD_3', True, 'LEFT', 'CUSTOM')

        # Shortcuts for align to 3D cursor operators
        set_km_item(km, 'NUMPAD_8', False, 'TOP', 'CURSOR')
        set_km_item(km, 'NUMPAD_8', True, 'BOTTOM', 'CURSOR')
        set_km_item(km, 'NUMPAD_5', False, 'FRONT', 'CURSOR')
        set_km_item(km, 'NUMPAD_5', True, 'BACK', 'CURSOR')
        set_km_item(km, 'NUMPAD_6', False, 'RIGHT', 'CURSOR')
        set_km_item(km, 'NUMPAD_6', True, 'LEFT', 'CURSOR')


def unregister():
    """
    Module unregister function called by the main package register function
    """
    global GL_ADDON_KEYMAPS

    for km, kmi in GL_ADDON_KEYMAPS:
        km.keymap_items.remove(kmi)
    GL_ADDON_KEYMAPS.clear()

    bpy.types.VIEW3D_MT_view_align.remove(a2c_menu_func)

    bpy.utils.unregister_class(VIEW3D_MT_align2cursor)
    bpy.utils.unregister_class(VIEW3D_MT_align2custom)
    bpy.utils.unregister_class(VIEW3D_MT_a2c)
    bpy.utils.unregister_class(VIEW3D_OT_a2c)
    bpy.utils.unregister_class(A2C_Preferences)


# ## MAIN test section ########################################################
if __name__ == "__main__":
    register()
