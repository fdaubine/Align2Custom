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
Align2Custom package entry point 
"""


from . import align2custom as a2c


bl_info = {
    "name": "Align view to custom orientation or 3D cursor",
    "description": "Set of commands to align the 3D view to the axes of "
                   "the active custom transform orientation or the 3D cursor.",
    "author": "Francois Daubine",
    "version": (2, 1, 0),
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
    a2c.register()


def unregister():
    """ Main unregister function """
    a2c.unregister()


# ## MAIN test section ########################################################
if __name__ == "__main__":
    register()
