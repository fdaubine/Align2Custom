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
Align2Custom UI – pie menu, regular menus and menu registration
"""


import math
import bpy

from . import ops as align2custom
from .ops import A2C_VIEWPOINT_ITEMS, A2C_PIE_MODE_ITEMS, is_viewport_drifted, should_offer_switch_to_edge


# ## Global data ###############################################################

_pie_keymaps = []

# Keymap info exposed for preferences to draw the keymap editor
KEYMAP_INFO = {
    'km_name': '3D View',
    'space_type': 'VIEW_3D',
    'operator_idname': 'wm.call_menu_pie',
    'key': 'Q',
    'value': 'PRESS',
    'ctrl': True,
    'alt': True,
    'menu_name': 'VIEW3D_MT_a2c_pie',
}


def _invoke_align_to_edge(context, viewpoint):
    """Run view3d.a2c_align_to_edge with optional area override so it runs in the 3D view."""
    if context.area and context.area.type == 'VIEW_3D':
        with context.temp_override(area=context.area):
            return bpy.ops.view3d.a2c_align_to_edge(prop_viewpoint=viewpoint)
    return bpy.ops.view3d.a2c_align_to_edge(prop_viewpoint=viewpoint)


# ## Pie operator ##############################################################

class VIEW3D_OT_a2c_pie_viewpoint(bpy.types.Operator):
    """Enter Aligned View with the selected Method and this axis"""
    bl_idname = "view3d.a2c_pie_viewpoint"
    bl_label = "Align View (Pie)"
    bl_options = {'REGISTER'}

    prop_viewpoint: bpy.props.EnumProperty(
        items=A2C_VIEWPOINT_ITEMS,
        name="Point of view",
        default="TOP",
    )

    def execute(self, context):
        mode = context.window_manager.a2c_pie_mode
        if mode == 'SELECTION':
            try:
                prefs = context.preferences.addons[__package__].preferences
                if (getattr(prefs, "pref_offer_edge_mode_when_one_edge", True) and
                        should_offer_switch_to_edge(context, mode)):
                    wm = context.window_manager
                    wm.a2c_pending_edge_viewpoint = self.prop_viewpoint
                    bpy.ops.wm.call_menu(name='VIEW3D_MT_a2c_confirm_one_edge')
                    return {'FINISHED'}
            except Exception:
                pass
        if mode == 'EDGE':
            # Ensure the edge operator runs in the 3D view (e.g. when invoked from pie menu)
            result = _invoke_align_to_edge(context, self.prop_viewpoint)
            if result == {'FINISHED'}:
                self.report({'INFO'}, "Aligned View: Enabled (Edge)")
            return result
        result = bpy.ops.view3d.a2c(prop_align_mode=mode, prop_viewpoint=self.prop_viewpoint)
        if result == {'FINISHED'}:
            self.report({'INFO'}, "Aligned View: Enabled ({})".format(mode.capitalize()))
        return result


class VIEW3D_OT_a2c_pie_viewpoint_nearest(bpy.types.Operator):
    """Align view to the nearest axis of the current orientation (Smart).
Alt+Click: Reset Auto Perspective and Align to World (last-resort recovery)"""
    bl_idname = "view3d.a2c_pie_viewpoint_nearest"
    bl_label = "Align to Nearest View"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        if event.alt and not align2custom.is_viewport_aligned(context):
            return bpy.ops.view3d.a2c_reset_state('EXEC_DEFAULT')
        return self.execute(context)

    def execute(self, context):
        mode = context.window_manager.a2c_pie_mode
        if mode == 'SELECTION':
            try:
                prefs = context.preferences.addons[__package__].preferences
                if (getattr(prefs, "pref_offer_edge_mode_when_one_edge", True) and
                        should_offer_switch_to_edge(context, mode)):
                    wm = context.window_manager
                    wm.a2c_pending_edge_viewpoint = 'NEAREST'
                    bpy.ops.wm.call_menu(name='VIEW3D_MT_a2c_confirm_one_edge')
                    return {'FINISHED'}
            except Exception:
                pass
        if mode == 'EDGE':
            result = _invoke_align_to_edge(context, 'NEAREST')
            if result == {'FINISHED'}:
                self.report({'INFO'}, "Aligned View: Enabled (Edge)")
            return result
        result = bpy.ops.view3d.a2c(prop_align_mode=mode, prop_viewpoint='NEAREST')
        if result == {'FINISHED'}:
            self.report({'INFO'}, "Aligned View: Enabled ({})".format(mode.capitalize()))
        return result


class VIEW3D_OT_a2c_confirm_switch_to_edge(bpy.types.Operator):
    """Switch to Edge Align mode and align view to the selected edge"""
    bl_idname = "view3d.a2c_confirm_switch_to_edge"
    bl_label = "Yes – Switch to Edge Align"
    bl_options = {'REGISTER'}

    # When True, run execute directly (used when clicked from the confirm menu "Yes" button)
    direct_execute: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    def invoke(self, context, event):
        if self.direct_execute:
            return self.execute(context)
        return {'CANCELLED'}

    def execute(self, context):
        wm = context.window_manager
        viewpoint = getattr(wm, "a2c_pending_edge_viewpoint", "NEAREST")
        context.window_manager.a2c_pie_mode = 'EDGE'
        result = _invoke_align_to_edge(context, viewpoint)
        if result == {'FINISHED'}:
            self.report({'INFO'}, "Aligned View: Enabled (Edge)")
        return result


class VIEW3D_OT_a2c_run_selection_align(bpy.types.Operator):
    """Enter Aligned View in Selection mode (do not switch to Edge)"""
    bl_idname = "view3d.a2c_run_selection_align"
    bl_label = "No – Align in Selection mode"
    bl_options = {'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        viewpoint = getattr(wm, "a2c_pending_edge_viewpoint", "NEAREST")
        if context.area and context.area.type == 'VIEW_3D':
            with context.temp_override(area=context.area):
                result = bpy.ops.view3d.a2c('EXEC_DEFAULT', prop_align_mode='SELECTION', prop_viewpoint=viewpoint)
        else:
            result = bpy.ops.view3d.a2c('EXEC_DEFAULT', prop_align_mode='SELECTION', prop_viewpoint=viewpoint)
        if result == {'FINISHED'}:
            self.report({'INFO'}, "Aligned View: Enabled (Selection)")
        return result


class VIEW3D_MT_a2c_confirm_one_edge(bpy.types.Menu):
    """One edge selected: switch to Edge Align or stay in Selection mode"""
    bl_idname = "VIEW3D_MT_a2c_confirm_one_edge"
    bl_label = "One edge selected"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Do you want to switch to Edge Align mode instead?")
        layout.separator()
        row = layout.row(align=True)
        op_yes = row.operator("view3d.a2c_confirm_switch_to_edge", text="Yes", icon='CHECKMARK')
        op_yes.direct_execute = True
        row.operator("view3d.a2c_run_selection_align", text="No", icon='X')


# ## Exit-pie wrapper (handles ALT+Click → Confirm and Exit) ##################

class VIEW3D_OT_a2c_exit_pie(bpy.types.Operator):
    """Exit Aligned View, restoring the previous camera angle.
Alt+Click: Confirm current angle and exit — the view stays here and becomes the new starting point"""
    bl_idname = "view3d.a2c_exit_pie"
    bl_label = "Exit"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        if event.alt:
            return bpy.ops.view3d.a2c_confirm_and_exit('EXEC_DEFAULT')
        return self.execute(context)

    def execute(self, context):
        return bpy.ops.view3d.a2c_leave_aligned_view('EXEC_DEFAULT')


# ## Pie menu ##################################################################

class VIEW3D_MT_a2c_pie(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_a2c_pie"
    bl_label = "Align 2 Custom"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        wm = context.window_manager
        prefs = context.preferences.addons[__package__].preferences
        is_aligned = align2custom.is_viewport_aligned(context)
        use_relative = prefs.pref_enable_relative_position_after_align and is_aligned
        is_drifted = is_viewport_drifted(context) if is_aligned else False
        suffix = " *" if (use_relative and is_drifted) else ""

        # Blender pie slot fill order:
        # 1-West  2-East  3-South  4-North  5-NW  6-NE  7-SW  8-SE

        if use_relative:
            # Relative layout: pivot 90°, roll, leave
            # 1 – West: pivot left
            op = pie.operator("view3d.a2c_pivot_view", icon='TRIA_LEFT', text=suffix)
            op.direction = 'LEFT'
            op.from_canonical = is_drifted
            # 2 – East: pivot right
            op = pie.operator("view3d.a2c_pivot_view", icon='TRIA_RIGHT', text=suffix)
            op.direction = 'RIGHT'
            op.from_canonical = is_drifted
            # 3 – South: pivot down
            op = pie.operator("view3d.a2c_pivot_view", icon='TRIA_DOWN', text=suffix)
            op.direction = 'BOTTOM'
            op.from_canonical = is_drifted
            # 4 – North: pivot up
            op = pie.operator("view3d.a2c_pivot_view", icon='TRIA_UP', text=suffix)
            op.direction = 'TOP'
            op.from_canonical = is_drifted
            # 5
            op = pie.operator("view3d.a2c_roll_view", icon='LOOP_BACK', text="Roll -90°" + suffix)
            op.angle = math.radians(-90)
            op.from_canonical = is_drifted
            # 6
            op = pie.operator("view3d.a2c_roll_view", icon='LOOP_FORWARDS', text="Roll +90°" + suffix)
            op.angle = math.radians(90)
            op.from_canonical = is_drifted
            # 7
            pie.operator("view3d.a2c_exit_pie", icon='SCREEN_BACK', text="Exit")
            # 8
            op = pie.operator("view3d.a2c_roll_view", icon='DECORATE_OVERRIDE', text="Roll +180°" + suffix)
            op.angle = math.radians(180)
            op.from_canonical = is_drifted

        else:
            # Standard layout: alignment viewpoints
            # When mode is EDGE, viewpoint slots are enabled only if exactly one edge is selected
            edge_ok = align2custom.has_single_edge_selected(context)
            viewpoint_enabled = (wm.a2c_pie_mode != 'EDGE') or edge_ok

            # 1 – West: Y / Front
            col = pie.column()
            col.enabled = viewpoint_enabled
            col.operator("view3d.a2c_pie_viewpoint", text="Y").prop_viewpoint = 'FRONT'
            # 2 – East: -Y / Back
            col = pie.column()
            col.enabled = viewpoint_enabled
            col.operator("view3d.a2c_pie_viewpoint", text="-Y").prop_viewpoint = 'BACK'
            # 3 – South: Smart (Nearest)
            col = pie.column()
            col.enabled = viewpoint_enabled
            col.operator("view3d.a2c_pie_viewpoint_nearest", icon='SHADERFX', text="Smart")
            # 4 – North: mode selector (Custom, Cursor, Selection, Edge)
            box = pie.box()
            row = box.row(align=True)
            row.scale_x = 1.2
            row.scale_y = 1.2
            row.prop(wm, "a2c_pie_mode", expand=True, icon_only=True)
            # 5 – NW: Z / Top
            col = pie.column()
            col.enabled = viewpoint_enabled
            col.operator("view3d.a2c_pie_viewpoint", text="Z").prop_viewpoint = 'TOP'
            # 6 – NE: -X / Left
            col = pie.column()
            col.enabled = viewpoint_enabled
            col.operator("view3d.a2c_pie_viewpoint", text="-X").prop_viewpoint = 'LEFT'
            # 7 – SW: X / Right, and Leave only when aligned
            if is_aligned:
                box_sw = pie.box()
                row_sw = box_sw.row(align=True)
                sub = row_sw.row()
                sub.enabled = viewpoint_enabled
                sub.operator("view3d.a2c_pie_viewpoint", text="X").prop_viewpoint = 'RIGHT'
                row_sw.operator("view3d.a2c_exit_pie", icon='SCREEN_BACK', text="Exit")
            else:
                col = pie.column()
                col.enabled = viewpoint_enabled
                col.operator("view3d.a2c_pie_viewpoint", text="X").prop_viewpoint = 'RIGHT'
            # 8 – SE: -Z / Bottom
            col = pie.column()
            col.enabled = viewpoint_enabled
            col.operator("view3d.a2c_pie_viewpoint", text="-Z").prop_viewpoint = 'BOTTOM'


# ## Regular menus #############################################################

class VIEW3D_MT_a2c(bpy.types.Menu):
    """
    Submenu 'Align View ...' base class
    """

    bl_idname = "VIEW3D_MT_a2c"
    bl_label = "Align View base class"

    def draw(self, context):
        self.create_items(context)

    def create_items(self, context, align_mode='CUSTOM'):
        use_edge = (align_mode == 'EDGE')
        op_idname = "view3d.a2c_align_to_edge" if use_edge else "view3d.a2c"

        # (label, viewpoint, separator_before, icon or None)
        entries = (
            ("Top",     'TOP',     False, None),
            ("Bottom",  'BOTTOM',  False, None),
            ("Front",   'FRONT',   True,  None),
            ("Back",    'BACK',    False, None),
            ("Right",   'RIGHT',   True,  None),
            ("Left",    'LEFT',    False, None),
            ("Smart",   'NEAREST', True,  'SHADERFX'),
        )
        for label, viewpoint, sep, icon in entries:
            if sep:
                self.layout.separator()
            op = self.layout.operator(op_idname, text=label, icon=icon if icon else 'NONE')
            op.prop_viewpoint = viewpoint
            if not use_edge:
                op.prop_align_mode = align_mode


class VIEW3D_MT_align2custom(VIEW3D_MT_a2c):
    """
    Submenu 'Align View to Custom': align to the active custom transform orientation
    """

    bl_idname = "VIEW3D_MT_align2custom"
    bl_label = "Align View to Custom"

    def draw(self, context):
        self.create_items(context, 'CUSTOM')


class VIEW3D_MT_align2cursor(VIEW3D_MT_a2c):
    """
    Submenu 'Align View to Cursor': align to the 3D cursor orientation
    """

    bl_idname = "VIEW3D_MT_align2cursor"
    bl_label = "Align View to Cursor"

    def draw(self, context):
        self.create_items(context, 'CURSOR')


class VIEW3D_MT_align2selection(VIEW3D_MT_a2c):
    """
    Submenu 'Align View to Selection': create a temporary orientation from the
    selection, align the view to it, then delete the temporary orientation
    """

    bl_idname = "VIEW3D_MT_align2selection"
    bl_label = "Align View to Selection"

    def draw(self, context):
        self.create_items(context, 'SELECTION')


class VIEW3D_MT_align2edge(VIEW3D_MT_a2c):
    """
    Submenu 'Align View to Edge': align so the selected edge lies flat
    (Edit Mode, one edge selected). Same viewpoint choices as other align modes.
    """

    bl_idname = "VIEW3D_MT_align2edge"
    bl_label = "Align View to Edge"

    def draw(self, context):
        self.create_items(context, 'EDGE')


def a2c_menu_func(self, context):
    """
    Append the submenus to View3D > View > Align View
    """
    self.layout.separator()
    self.layout.menu(VIEW3D_MT_align2custom.bl_idname)
    self.layout.menu(VIEW3D_MT_align2cursor.bl_idname)
    self.layout.menu(VIEW3D_MT_align2selection.bl_idname)
    self.layout.menu(VIEW3D_MT_align2edge.bl_idname)


# ## Registration ##############################################################

_classes = (
    VIEW3D_OT_a2c_pie_viewpoint,
    VIEW3D_OT_a2c_pie_viewpoint_nearest,
    VIEW3D_OT_a2c_confirm_switch_to_edge,
    VIEW3D_OT_a2c_run_selection_align,
    VIEW3D_MT_a2c_confirm_one_edge,
    VIEW3D_OT_a2c_exit_pie,
    VIEW3D_MT_a2c_pie,
    VIEW3D_MT_a2c,
    VIEW3D_MT_align2custom,
    VIEW3D_MT_align2cursor,
    VIEW3D_MT_align2selection,
    VIEW3D_MT_align2edge,
)


def register():
    bpy.types.WindowManager.a2c_pie_mode = bpy.props.EnumProperty(
        items=A2C_PIE_MODE_ITEMS,
        name="Align Mode",
        default='SELECTION',
    )
    bpy.types.WindowManager.a2c_pending_edge_viewpoint = bpy.props.StringProperty(
        name="Pending Edge Viewpoint",
        default='NEAREST',
    )

    for cls in _classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_view_align.append(a2c_menu_func)

    # Apply default pie mode from preferences
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
        bpy.context.window_manager.a2c_pie_mode = prefs.pref_default_pie_mode
    except Exception:
        pass

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(
            name=KEYMAP_INFO['km_name'],
            space_type=KEYMAP_INFO['space_type'],
        )
        kmi = km.keymap_items.new(
            KEYMAP_INFO['operator_idname'],
            type=KEYMAP_INFO['key'],
            value=KEYMAP_INFO['value'],
            ctrl=KEYMAP_INFO['ctrl'],
            alt=KEYMAP_INFO['alt'],
        )
        kmi.properties.name = KEYMAP_INFO['menu_name']
        _pie_keymaps.append((km, kmi))


def unregister():
    bpy.types.VIEW3D_MT_view_align.remove(a2c_menu_func)

    for km, kmi in _pie_keymaps:
        km.keymap_items.remove(kmi)
    _pie_keymaps.clear()

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.WindowManager.a2c_pending_edge_viewpoint
    del bpy.types.WindowManager.a2c_pie_mode
