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

import bpy
import math
import mathutils as mu
import threading as thd
import time


bl_info = {
    "name": "Align view to custom orientation or 3D cursor",
    "description": "Set of commands to align the 3D view to the axes of "
                   "the active custom transform orientation or the 3D cursor.",
    "author": "Francois Daubine",
    "version": (1, 0, 1),
    "blender": (2, 80, 0),
    "location": "View3D > View > Align View",
    "warning": "",
    "doc_url": "https://www.github.com/fdaubine/Align2Custom",
    "tracker_url": "https://www.github.com/fdaubine/Align2Custom",
    "support": "COMMUNITY",
    "category": "3D View",
}


# ## Global data ##############################################################
gl_addon_keymaps = []       # Keymap collection
gl_token_lock = False       # Locking token while rotating 3D View


# ## Math functions section ###################################################
def s_curve_range(nb_samples):
    """
    Function that returns a list of range values (from 0.0 to 1.0) spaced
    according to a S-curve function. Useful for smooth interpolation.

    Parameters :
     - nb_samples [in] : number of range values to generate (greater than 0)
    """

    assert nb_samples > 0

    rng = [elt/nb_samples for elt in range(nb_samples+1)]
    rng = [(1.0 + math.sin((x - 0.5) * math.pi))/2.0 for x in rng]

    return rng


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

    NB_FRAME_MAX = 9
    FRAME_DELAY = 0.03

    @staticmethod
    def rotate_view(space, orient_steps):
        """
        Rotate the 3D view smoothly along the intermediate quaternions of the
        'orient_steps' list parameter
        """

        global gl_token_lock

        if space and len(orient_steps) > 0:
            for quat in orient_steps:
                space.region_3d.view_rotation = quat
                time.sleep(VIEW3D_OT_a2c.FRAME_DELAY)

        gl_token_lock = False

    def execute(self, context):
        """
        Set the orientation of the 3D View in which the operator is called,
        as a combination of the active custom orientation matrix and the
        rotation matrix passed in argument.

        This function computes a set of intermediate orientations between
        the current 3D view orientation and the custom orientation, and
        next gives them to a thread which rotate the 3D view along those
        intermediate orientations (Smooth transition).
        """

        global gl_token_lock

        scene = context.window.scene
        space = context.space_data

        co = scene.transform_orientation_slots[0].custom_orientation
        if (not gl_token_lock) and \
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

            initial_quat = space.region_3d.view_rotation
            final_quat = new_orientation.to_quaternion()
            diff_quat = final_quat.rotation_difference(initial_quat)
            axis, angle = diff_quat.to_axis_angle()

            # Compute the number of intermediate orientations according to
            # the angle difference between starting and ending orientations
            # (the smaller the angle, the fewer samples)
            nb_frames = max(1, int(VIEW3D_OT_a2c.NB_FRAME_MAX *
                            angle / math.pi))

            # Sample the intermediate orientations along a S-curve (smooth
            # transition), and compute the associated quaternions
            frames_range = s_curve_range(nb_frames)
            view_orientations = [initial_quat.slerp(final_quat, factor) for
                                 factor in frames_range]

            space.region_3d.view_perspective = 'ORTHO'

            rotation_job = thd.Thread(
                                target=VIEW3D_OT_a2c.rotate_view,
                                args=(space, view_orientations))

            gl_token_lock = True
            rotation_job.start()

        return {'FINISHED'}


# ## Menus section ############################################################
class VIEW3D_MT_a2c(bpy.types.Menu):
    """
    Submenu 'Align View ...' base class
    """

    bl_idname = "VIEW3D_MT_a2c"
    bl_label = "Align View base class"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        self.create_items(context)

    def create_items(self, context, align_mode='CUSTOM'):
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
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        self.create_items(context, 'CUSTOM')


class VIEW3D_MT_align2cursor(VIEW3D_MT_a2c):
    """
    Submenu 'Align View to Cursor' : offers to select one of the 6 possible
    orientations (Top, Bottom, Front, Back, Right, Left) according to the
    3D cursor axes
    """

    bl_idname = "VIEW3D_MT_align2cursor"
    bl_label = "Align View to Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
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
    global gl_addon_keymaps

    bpy.utils.register_class(VIEW3D_OT_a2c)
    bpy.utils.register_class(VIEW3D_MT_a2c)
    bpy.utils.register_class(VIEW3D_MT_align2custom)
    bpy.utils.register_class(VIEW3D_MT_align2cursor)

    bpy.types.VIEW3D_MT_view_align.append(a2c_menu_func)

    if bpy.context.window_manager.keyconfigs.addon:
        km = bpy.context.window_manager.keyconfigs.addon.keymaps.new(
            name='3D View',
            space_type='VIEW_3D')

        def set_km_item(km, numpad, ctrl, viewpoint, align_mode):
            global gl_addon_keymaps

            if km:
                str_numpad = 'NUMPAD_{}'.format(numpad)
                kmi = km.keymap_items.new(VIEW3D_OT_a2c.bl_idname,
                                          str_numpad, 'PRESS',
                                          alt=True, ctrl=ctrl)
                kmi.properties.prop_viewpoint = viewpoint
                kmi.properties.prop_align_mode = align_mode
                gl_addon_keymaps.append((km, kmi))

        # Shortcuts for align to custom orientation operators
        set_km_item(km, '7', False, 'TOP', 'CUSTOM')
        set_km_item(km, '7', True, 'BOTTOM', 'CUSTOM')
        set_km_item(km, '1', False, 'FRONT', 'CUSTOM')
        set_km_item(km, '1', True, 'BACK', 'CUSTOM')
        set_km_item(km, '3', False, 'RIGHT', 'CUSTOM')
        set_km_item(km, '3', True, 'LEFT', 'CUSTOM')

        # Shortcuts for align to 3D cursor operators
        set_km_item(km, '8', False, 'TOP', 'CURSOR')
        set_km_item(km, '8', True, 'BOTTOM', 'CURSOR')
        set_km_item(km, '5', False, 'FRONT', 'CURSOR')
        set_km_item(km, '5', True, 'BACK', 'CURSOR')
        set_km_item(km, '6', False, 'RIGHT', 'CURSOR')
        set_km_item(km, '6', True, 'LEFT', 'CURSOR')


def unregister():
    global gl_addon_keymaps

    for km, kmi in gl_addon_keymaps:
        km.keymap_items.remove(kmi)
    gl_addon_keymaps.clear()

    bpy.types.VIEW3D_MT_view_align.remove(a2c_menu_func)

    bpy.utils.unregister_class(VIEW3D_MT_align2cursor)
    bpy.utils.unregister_class(VIEW3D_MT_align2custom)
    bpy.utils.unregister_class(VIEW3D_MT_a2c)
    bpy.utils.unregister_class(VIEW3D_OT_a2c)


# ## MAIN test section ########################################################
if __name__ == "__main__":
    register()

