# -*- coding: utf-8 -*-

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation, either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.
#  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# Contributed to by fdaubine and 1P2D


""" 
Align2Custom package entry point 
"""


import bpy

from . import ops as a2c
from . import preferences
from . import ui


# Keymaps registered by the addon (pivot-by-drag, leave aligned view)
_addon_keymaps = []


bl_info = {
    "name": "Align 3D View to selection, custom orientation or cursor",
    "description": "Set of commands to align the 3D view to the axes of "
                   "the active custom transform orientation or the 3D cursor.",
    "author": "Francois Daubine, 1P2D",
    "version": (2, 5, 1),
    "blender": (4, 2, 0),
    "location": "View3D > View > Align View",
    "warning": "",
    "doc_url": "https://www.github.com/fdaubine/Align2Custom",
    "tracker_url": "https://www.github.com/fdaubine/Align2Custom",
    "support": "COMMUNITY",
    "category": "3D View",
}


# ## Blender registration section #############################################
def register():
    """ Main register function """
    preferences.register()
    a2c.register()
    ui.register()

    # Register addon keymaps (user can add align-to-custom/cursor shortcuts themselves)
    wm = bpy.context.window_manager
    if wm.keyconfigs.addon:
        km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(
            "view3d.a2c_pivot_view_drag", 'MIDDLEMOUSE', 'PRESS', alt=True
        )
        _addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new(
            "view3d.a2c_leave_aligned_view", 'LEFTMOUSE', 'DOUBLE_CLICK',
            shift=True, alt=True, ctrl=True
        )
        _addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new(
            "view3d.a2c_snap_orbit", 'LEFT_ALT', 'PRESS'
        )
        _addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new(
            "view3d.view_roll", 'WHEELUPMOUSE', 'PRESS', shift=True, alt=True
        )
        kmi.properties.angle = 0.1
        _addon_keymaps.append((km, kmi))
        kmi = km.keymap_items.new(
            "view3d.view_roll", 'WHEELDOWNMOUSE', 'PRESS', shift=True, alt=True
        )
        kmi.properties.angle = -0.1
        _addon_keymaps.append((km, kmi))


def unregister():
    """ Main unregister function """
    for km, kmi in _addon_keymaps:
        km.keymap_items.remove(kmi)
    _addon_keymaps.clear()

    ui.unregister()
    a2c.unregister()
    preferences.unregister()


# ## MAIN test section ########################################################
if __name__ == "__main__":
    register()
