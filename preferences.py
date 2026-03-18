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
Align2Custom Addon Preferences
"""


import bpy
import rna_keymap_ui

from . import ui
from . import ops
from .ops import A2C_PIE_MODE_ITEMS


class A2C_Preferences(bpy.types.AddonPreferences):
    """
    Addon panel of the 'Preferences...' interface
    """

    bl_idname = __package__

    pref_smooth: bpy.props.BoolProperty(
        name="Smooth rotation",
        description="Performs smooth rotation between the current view and the target view",
        default=True,
    )

    pref_minimize_roll: bpy.props.BoolProperty(
        name="Minimize viewport roll",
        description="Tries to maintain the current viewport orientation (up/down/left/right) "
                    "by minimizing roll when aligning to specific viewpoints",
        default=True,
    )

    pref_set_orientation_to_view: bpy.props.BoolProperty(
        name="Set Transformation orientation to 'View' in Aligned View",
        description="Automatically sets the transform orientation to 'View' after aligning the viewport",
        default=True,
    )

    pref_set_orientation_to_view_for_custom: bpy.props.BoolProperty(
        name="Set Transformation orientation to 'View' for 'Align to Custom' too",
        description="Also apply 'Set orientation to View' when using Align to Custom. "
                    "Warning: This will make subsequent Align to Custom operations not work "
                    "until you reselect a custom orientation",
        default=False,
    )

    pref_use_view_orientation_in_aligned_view: bpy.props.BoolProperty(
        name="Set align to 'View' for newly added objects in Aligned View",
        description="While in aligned view: set 'New Objects > Align to' to View (Edit preferences) "
                    "so newly added primitives use align='VIEW'. Restored when you leave aligned view. "
                    "Does not change the Transform Orientation dropdown; use the option above for that",
        default=True,
    )

    pref_default_pie_mode: bpy.props.EnumProperty(
        name="Default mode for Primary pie menu",
        description="Which alignment mode is pre-selected when opening the pie menu",
        items=A2C_PIE_MODE_ITEMS,
        default='SELECTION',
        update=lambda self, context: setattr(
            context.window_manager, 'a2c_pie_mode', self.pref_default_pie_mode
        ),
    )

    pref_force_ortho_in_aligned_view: bpy.props.BoolProperty(
        name="Force orthographic view in Aligned View",
        description="While in aligned view, rotation will never leave orthographic projection. "
                    "Any automatic or manual switch to perspective is immediately reverted until "
                    "you leave aligned view. Blender's 'Auto Perspective' setting is temporarily "
                    "disabled for the duration and restored when you leave aligned view",
        default=False,
    )

    pref_force_viewpoint_edge: bpy.props.BoolProperty(
        name="Force Viewpoint (Edge)",
        description="Before aligning to the selected edge, first orient the view to the edge's object "
                    "This makes the edge alignment relative to the object "
                    "rather than the current arbitrary view. Disabled by default because it relies on "
                    "the object's origin being correctly placed",
        default=False,
    )

    pref_ignore_depth_edge: bpy.props.BoolProperty(
        name="Keep object straight in view",
        description="When aligning to the edge, only roll the view so the edge lies flat; do not tilt "
                    "the view to be perpendicular to the edge. The object stays aligned to the view axis, "
                    "so geometry behind the edge does not appear shifted or rotated",
        default=False,
    )

    pref_enable_relative_position_after_align: bpy.props.BoolProperty(
        name="Use secondary Pie Menu when in Aligned View",
        description="When the view is already aligned, the pie menu shows new pivot options "
                    "(rotate view 90° up/down/left/right/roll angles) instead of the original pie menu",
        default=False,
    )

    pref_offer_edge_mode_when_one_edge: bpy.props.BoolProperty(
        name="Suggest Edge Align when one edge selected in Selection mode",
        description="In Edit Mode with exactly one edge selected, if you trigger an align operator "
                    "in Selection mode, show a dialog asking whether to switch to Edge Align mode instead",
        default=True,
    )

    # Aligned View overlay
    pref_show_overlay: bpy.props.BoolProperty(
        name="Show 'Aligned View' label in viewport",
        description="Display a persistent text label in the 3D viewport while in Aligned View",
        default=True,
    )

    pref_overlay_text_size: bpy.props.IntProperty(
        name="Text Size",
        description="Font size of the Aligned View overlay label",
        default=16,
        min=8,
        max=48,
    )

    pref_overlay_text_color: bpy.props.FloatVectorProperty(
        name="Text Color",
        description="Color and opacity of the Aligned View overlay label",
        default=(1.0, 1.0, 1.0, 0.8),
        size=4,
        min=0.0,
        max=1.0,
        subtype='COLOR',
    )

    pref_overlay_vertical_position: bpy.props.FloatProperty(
        name="Vertical Position",
        description="Vertical position of the label (percentage from bottom of viewport)",
        default=90.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE',
    )

    pref_overlay_horizontal_position: bpy.props.FloatProperty(
        name="Horizontal Position",
        description="Horizontal position of the label (percentage from left of viewport)",
        default=50.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE',
    )

    # Active preferences tab
    pref_active_tab: bpy.props.EnumProperty(
        name="Category",
        items=[
            ('GENERAL',   "General",   "General and Aligned View settings", 'SETTINGS',      0),
            ('EDGE_MODE', "Edge Mode", "Edge alignment settings",           'MOD_EDGESPLIT', 1),
            ('UI',        "UI",        "User interface and overlay settings",'COLLAPSEMENU',  2),
            ('KEYMAPS',   "Keymaps",   "Keyboard shortcut settings",        'KEYINGSET',     3),
        ],
        default='GENERAL',
    )

    def draw(self, context):
        """ Display preference options in panel """
        layout = self.layout

        # Category tab bar
        row = layout.row()
        row.prop(self, "pref_active_tab", expand=True)


        tab = self.pref_active_tab

        if tab == 'GENERAL':
            # General
            box = layout.box()
            box.label(text="General", icon='SETTINGS')
            box.prop(self, "pref_smooth")
            box.prop(self, "pref_minimize_roll")

            # Aligned View
            box = layout.box()
            box.label(text="Aligned View", icon='ORIENTATION_VIEW')
            box.prop(self, "pref_set_orientation_to_view")
            row = box.row()
            row.separator(factor=2.0)
            sub = row.row()
            sub.enabled = self.pref_set_orientation_to_view
            sub.prop(self, "pref_set_orientation_to_view_for_custom")
            if self.pref_set_orientation_to_view and self.pref_set_orientation_to_view_for_custom:
                warn_row = box.row()
                warn_row.separator(factor=2.0)
                warn_box = warn_row.box()
                col = warn_box.column(align=True)
                col.alert = True
                col.label(text="Warning: This will select the 'View' orientation,", icon='ERROR')
                col.label(text="making Align to Custom not work until you")
                col.label(text="reselect a Custom Orientation.")
            box.prop(self, "pref_use_view_orientation_in_aligned_view")
            box.prop(self, "pref_force_ortho_in_aligned_view")

        elif tab == 'EDGE_MODE':
            # About
            about_box = layout.box()
            about_col = about_box.column(align=True)
            about_col.label(text="About", icon='INFO_LARGE')
            about_col.separator(factor=0.3)
            about_col.label(text="Unlike Selection mode, Edge Mode aligns the view directly to a")
            about_col.label(text="single selected edge for precise geometric control. Particularly")
            about_col.label(text="suited for automotive and industrial design workflows where")
            about_col.label(text="exact edge alignment is critical.")

            # Settings
            box = layout.box()
            box.prop(self, "pref_force_viewpoint_edge")
            if self.pref_force_viewpoint_edge:
                warn_row = box.row()
                warn_row.separator(factor=2.0)
                warn_box = warn_row.box()
                col = warn_box.column(align=True)
                col.alert = True
                col.label(text="Relies on the object's origin being correctly set.", icon='ERROR')
                row_ignore = box.row()
                row_ignore.separator(factor=2.0)
                row_ignore.prop(self, "pref_ignore_depth_edge")
            else:
                row_ignore = box.row()
                row_ignore.separator(factor=2.0)
                row_ignore.enabled = False
                row_ignore.prop(self, "pref_ignore_depth_edge")
            box.prop(self, "pref_offer_edge_mode_when_one_edge")

        elif tab == 'UI':
            # Pie menu
            box = layout.box()
            box.label(text="Pie Menu", icon='COLLAPSEMENU')
            row = box.row()
            split = row.split(factor=1)
            split.label(text="Default mode for Primary pie menu:")
            row.prop(self, "pref_default_pie_mode", text="")
            box.prop(self, "pref_enable_relative_position_after_align")

            # Overlays
            box = layout.box()
            box.label(text="Overlays", icon='OVERLAY')
            box.prop(self, "pref_show_overlay")
            if self.pref_show_overlay:
                sub = box.box()
                row = sub.row()
                row.prop(self, "pref_overlay_text_size")
                row.prop(self, "pref_overlay_text_color")
                row = sub.row()
                row.prop(self, "pref_overlay_vertical_position")
                row.prop(self, "pref_overlay_horizontal_position")

        elif tab == 'KEYMAPS':
            box = layout.box()
            self._draw_keymap(context, box)

    def _draw_keymap(self, context, layout):
        wm = context.window_manager
        kc = wm.keyconfigs.user
        kc_addon = wm.keyconfigs.addon

        # Align 2 Custom Pie Menus (user keyconfig)
        km = kc.keymaps.get(ui.KEYMAP_INFO['km_name']) if kc else None
        if km:
            for kmi in km.keymap_items:
                if (kmi.idname == ui.KEYMAP_INFO['operator_idname']
                        and kmi.properties.get('name') == ui.KEYMAP_INFO['menu_name']):
                    rna_keymap_ui.draw_kmi([], kc, km, kmi, layout, 0)
                    break

        # Addon keymaps (operator_idname, optional prop_filter dict)
        keymap_items = (
            ('view3d.a2c_leave_aligned_view', None),
            ('view3d.a2c_pivot_view_drag', None),
            ('view3d.a2c_snap_orbit', None),
        )
        if kc_addon:
            for item in keymap_items:
                operator_idname = item[0]
                prop_filter = item[1]
                drawn = False
                for km in kc_addon.keymaps:
                    if drawn:
                        break
                    for kmi in km.keymap_items:
                        if kmi.idname != operator_idname:
                            continue
                        if prop_filter is not None:
                            if not all(kmi.properties.get(k) == v for k, v in prop_filter.items()):
                                continue
                        rna_keymap_ui.draw_kmi([], kc_addon, km, kmi, layout, 0)
                        drawn = True
                        break

        # View Roll shortcuts: vanilla operator keymaps live in user keyconfig, not addon
        if kc:
            km_3d = kc.keymaps.get('3D View')
            if km_3d:
                for kmi in km_3d.keymap_items:
                    if kmi.idname != 'view3d.view_roll':
                        continue
                    if not (kmi.shift and kmi.alt):
                        continue
                    if kmi.type == 'WHEELUPMOUSE':
                        rna_keymap_ui.draw_kmi([], kc, km_3d, kmi, layout, 0)
                    elif kmi.type == 'WHEELDOWNMOUSE':
                        rna_keymap_ui.draw_kmi([], kc, km_3d, kmi, layout, 0)


# ## Registration ##############################################################

def register():
    bpy.utils.register_class(A2C_Preferences)


def unregister():
    bpy.utils.unregister_class(A2C_Preferences)
