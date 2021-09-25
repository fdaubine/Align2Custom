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


bl_info = {
    "name": "Align view to custom orientation",
    "description": "Set of commands to align the 3D view to the axes of "
                   "the active custom orientation",
    "author": "Francois Daubine",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > View > Align View",
    "warning": "",
    "doc_url": "https://www.github.com/fdaubine/Align2Custom",
    "tracker_url": "https://www.github.com/fdaubine/Align2Custom",
    "support": "COMMUNITY",
    "category": "3D View",
}


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


# ## Operators section ########################################################
class VIEW3D_OT_align_2_custom(bpy.types.Operator):
    """
    Align 3D View to active custom orientation - Operator base class
    """

    bl_idname = "view3d.align_2_custom"
    bl_label = "Align to custom orientation base class"
    bl_options = {'REGISTER', 'UNDO'}

    def set_orientation(self, context, rot_matrix=mu.Matrix.Identity(3)):
        """
        Set the orientation of the 3D View in which the operator is called,
        as a combination of the active custom orientation matrix and the
        rotation matrix passed in argument
        """

        scene = context.window.scene
        space = context.space_data
        co = scene.transform_orientation_slots[0].custom_orientation
        if co and (space.type == 'VIEW_3D'):
            view_orientation = co.matrix @ rot_matrix

            space.region_3d.view_perspective = 'ORTHO'
            space.region_3d.view_rotation = view_orientation.to_quaternion()


class VIEW3D_OT_a2c_top(VIEW3D_OT_align_2_custom):
    """
    Align View to the top point of view of the custom orientation
    """

    bl_idname = "view3d.a2c_top"
    bl_label = "Align to custom orientation top view"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.set_orientation(context)
        return {'FINISHED'}


class VIEW3D_OT_a2c_bottom(VIEW3D_OT_align_2_custom):
    """
    Align View to the bottom point of view of the custom orientation
    """

    bl_idname = "view3d.a2c_bottom"
    bl_label = "Align to custom orientation bottom view"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rotation_matrix = mu.Matrix.Rotation(math.radians(180.0), 3, 'X')
        self.set_orientation(context, rotation_matrix)
        return {'FINISHED'}


class VIEW3D_OT_a2c_front(VIEW3D_OT_align_2_custom):
    """
    Align View to the front point of view of the custom orientation
    """

    bl_idname = "view3d.a2c_front"
    bl_label = "Align to custom orientation front view"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rotation_matrix = mu.Matrix.Rotation(math.radians(90.0), 3, 'X')
        self.set_orientation(context, rotation_matrix)
        return {'FINISHED'}


class VIEW3D_OT_a2c_back(VIEW3D_OT_align_2_custom):
    """
    Align View to the back point of view of the custom orientation
    """

    bl_idname = "view3d.a2c_back"
    bl_label = "Align to custom orientation back view"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rotation_matrix = mu.Matrix.Rotation(math.radians(90.0), 3, 'X')\
                        @ mu.Matrix.Rotation(math.radians(180.0), 3, 'Y')
        self.set_orientation(context, rotation_matrix)
        return {'FINISHED'}


class VIEW3D_OT_a2c_right(VIEW3D_OT_align_2_custom):
    """
    Align View to the right point of view of the custom orientation
    """

    bl_idname = "view3d.a2c_right"
    bl_label = "Align to custom orientation right view"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rotation_matrix = mu.Matrix.Rotation(math.radians(90.0), 3, 'X')\
                        @ mu.Matrix.Rotation(math.radians(90.0), 3, 'Y')
        self.set_orientation(context, rotation_matrix)
        return {'FINISHED'}


class VIEW3D_OT_a2c_left(VIEW3D_OT_align_2_custom):
    """
    Align View to the left point of view of the custom orientation
    """

    bl_idname = "view3d.a2c_left"
    bl_label = "Align to custom orientation left view"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rotation_matrix = mu.Matrix.Rotation(math.radians(90.0), 3, 'X')\
                        @ mu.Matrix.Rotation(math.radians(-90.0), 3, 'Y')
        self.set_orientation(context, rotation_matrix)
        return {'FINISHED'}


# ## Menus section ############################################################
class VIEW3D_MT_align2custom(bpy.types.Menu):
    """
    Submenu 'Align View to Custom' : offers to select one of the 6 possible
    orientations (Top, Bottom, Front, Back, Right, Left) according to the
    selected custom axes
    """

    bl_idname = "VIEW3D_MT_align2custom"
    bl_label = "Align View to Custom"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        self.layout.operator(VIEW3D_OT_a2c_top.bl_idname, text="Top")
        self.layout.operator(VIEW3D_OT_a2c_bottom.bl_idname, text="Bottom")
        self.layout.separator()
        self.layout.operator(VIEW3D_OT_a2c_front.bl_idname, text="Front")
        self.layout.operator(VIEW3D_OT_a2c_back.bl_idname, text="Back")
        self.layout.separator()
        self.layout.operator(VIEW3D_OT_a2c_right.bl_idname, text="Right")
        self.layout.operator(VIEW3D_OT_a2c_left.bl_idname, text="Left")


def a2c_menu_func(self, context):
    """
    Append the submenu 'Align to custom orientation' to the menu
    'View3D > View > Align View'
    """

    self.layout.separator()
    self.layout.menu(VIEW3D_MT_align2custom.bl_idname)


# ## Keymap collection ########################################################
addon_keymaps = []


# ## Blender registration section #############################################
def register():
    bpy.utils.register_class(VIEW3D_MT_align2custom)
    bpy.utils.register_class(VIEW3D_OT_align_2_custom)
    bpy.utils.register_class(VIEW3D_OT_a2c_top)
    bpy.utils.register_class(VIEW3D_OT_a2c_bottom)
    bpy.utils.register_class(VIEW3D_OT_a2c_front)
    bpy.utils.register_class(VIEW3D_OT_a2c_back)
    bpy.utils.register_class(VIEW3D_OT_a2c_right)
    bpy.utils.register_class(VIEW3D_OT_a2c_left)

    bpy.types.VIEW3D_MT_view_align.append(a2c_menu_func)

    if bpy.context.window_manager.keyconfigs.addon:
        km = bpy.context.window_manager.keyconfigs.addon.keymaps.new(
            name='3D View',
            space_type='VIEW_3D')

        kmi = km.keymap_items.new(VIEW3D_OT_a2c_top.bl_idname,
                                  'NUMPAD_7', 'PRESS',
                                  alt=True, ctrl=False)
        addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new(VIEW3D_OT_a2c_bottom.bl_idname,
                                  'NUMPAD_7', 'PRESS',
                                  alt=True, ctrl=True)
        addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new(VIEW3D_OT_a2c_front.bl_idname,
                                  'NUMPAD_1', 'PRESS',
                                  alt=True, ctrl=False)
        addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new(VIEW3D_OT_a2c_back.bl_idname,
                                  'NUMPAD_1', 'PRESS',
                                  alt=True, ctrl=True)
        addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new(VIEW3D_OT_a2c_right.bl_idname,
                                  'NUMPAD_3', 'PRESS',
                                  alt=True, ctrl=False)
        addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new(VIEW3D_OT_a2c_left.bl_idname,
                                  'NUMPAD_3', 'PRESS',
                                  alt=True, ctrl=True)
        addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    bpy.types.VIEW3D_MT_view_align.remove(a2c_menu_func)

    bpy.utils.unregister_class(VIEW3D_OT_a2c_left)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_right)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_back)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_front)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_bottom)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_top)
    bpy.utils.unregister_class(VIEW3D_OT_align_2_custom)
    bpy.utils.unregister_class(VIEW3D_MT_align2custom)


# ## MAIN test section ########################################################
if __name__ == "__main__":
    register()

