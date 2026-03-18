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
Align2Custom module implementation
"""


import math
import mathutils as mu
import threading as thd
import time
import bpy
import blf
import bmesh


# ## Global data ##############################################################
GL_TOKEN_LOCK = thd.Event()  # Set while a smooth rotation is in progress
_A2C_STOP_EVENT = thd.Event()  # Set during unregister to abort any running rotation thread
# Storage for original perspective mode and rotation state for each area
# Also stores pre-alignment view (rotation, location, distance) for "Leave aligned view"
GL_VIEWPORT_STATE = {}      # Format: {area_ptr: {'original_perspective': str, 'aligned_rotation': quat, 'is_aligned': bool, 'view_rotation_before': quat, 'view_location_before': Vector, 'view_distance_before': float}}
GL_DRAW_HANDLER = None      # Draw handler for monitoring viewport changes
_A2C_OVERLAY_HANDLER = None # Draw handler for the persistent aligned-view overlay text
# Captured once when the first viewport enters aligned view; restored when the last one leaves.
# Prevents the "last leaver restores wrong value" bug when multiple viewports are aligned.
_A2C_USE_AUTO_PERSPECTIVE_BEFORE_ANY = None


# ## Constants ################################################################

# Rotation dot product threshold: below this value (~2.5°) the view is
# considered rotated away from the aligned position.
A2C_ROTATION_DOT_THRESHOLD = 0.999

# Viewpoint enum items shared by all operators that accept a viewpoint argument.
A2C_VIEWPOINT_ITEMS = (
    ("TOP",     "Top view",     "", 1),
    ("BOTTOM",  "Bottom view",  "", 2),
    ("FRONT",   "Front view",   "", 3),
    ("BACK",    "Back view",    "", 4),
    ("RIGHT",   "Right view",   "", 5),
    ("LEFT",    "Left view",    "", 6),
    ("NEAREST", "Nearest view", "", 7),
)

# Pie / align mode enum items shared by ui.a2c_pie_mode and preferences.pref_default_pie_mode.
A2C_PIE_MODE_ITEMS = (
    ('CUSTOM',    'Custom',    'Align to custom transform orientation', 'OBJECT_ORIGIN',       0),
    ('CURSOR',    'Cursor',    'Align to 3D cursor orientation',        'PIVOT_CURSOR',        1),
    ('SELECTION', 'Selection', 'Align to selection orientation. For reliable alignments, ensure the origin is correctly set up', 'RESTRICT_SELECT_OFF', 2),
    ('EDGE',      'Edge',      'Align to selected edge (Edit Mode, only one edge must be selected)', 'MOD_EDGESPLIT',   3),
)

# Roll angles (degrees) tested when minimizing viewport roll.
A2C_ROLL_ANGLES = (0, 90, 180, 270)
# Precomputed Z-rotation matrices for roll angles (avoids repeated allocation in hot paths).
A2C_ROLL_MATRICES = tuple(mu.Matrix.Rotation(math.radians(a), 3, 'Z') for a in A2C_ROLL_ANGLES)

# Viewpoint rotation matrices built once at load time.
A2C_VIEWPOINT_MATRICES = {
    "TOP":    mu.Matrix.Identity(3),
    "BOTTOM": mu.Matrix.Rotation(math.radians(180.0), 3, 'X'),
    "FRONT":  mu.Matrix.Rotation(math.radians(90.0), 3, 'X'),
    "BACK":   mu.Matrix.Rotation(math.radians(90.0), 3, 'X') @ mu.Matrix.Rotation(math.radians(180.0), 3, 'Y'),
    "RIGHT":  mu.Matrix.Rotation(math.radians(90.0), 3, 'X') @ mu.Matrix.Rotation(math.radians(90.0), 3, 'Y'),
    "LEFT":   mu.Matrix.Rotation(math.radians(90.0), 3, 'X') @ mu.Matrix.Rotation(math.radians(-90.0), 3, 'Y'),
}


# ## Viewport monitoring system ###############################################
def get_prefs(context):
    """Return addon preferences or None if not available."""
    try:
        return context.preferences.addons[__package__].preferences
    except Exception:
        return None


def get_area_pointer(area):
    """Get a unique pointer identifier for a 3D viewport area"""
    if area and area.type == 'VIEW_3D':
        return area.as_pointer()
    return None


def _capture_auto_perspective_if_first(context):
    """
    If no viewport is currently in aligned view, capture the current global
    auto-perspective preference so it can be restored when the last aligned
    viewport leaves. Safe to call even when Force Ortho is off.
    """
    global _A2C_USE_AUTO_PERSPECTIVE_BEFORE_ANY
    if any(st.get('is_aligned') for st in GL_VIEWPORT_STATE.values()):
        return
    try:
        _A2C_USE_AUTO_PERSPECTIVE_BEFORE_ANY = context.preferences.inputs.use_auto_perspective
    except Exception:
        pass


def _restore_auto_perspective_if_last(context):
    """
    If no viewport is still in aligned view, restore the global auto-perspective
    preference that was captured before any viewport entered aligned view.
    """
    global _A2C_USE_AUTO_PERSPECTIVE_BEFORE_ANY
    if any(st.get('is_aligned') for st in GL_VIEWPORT_STATE.values()):
        return
    if _A2C_USE_AUTO_PERSPECTIVE_BEFORE_ANY is not None:
        try:
            context.preferences.inputs.use_auto_perspective = _A2C_USE_AUTO_PERSPECTIVE_BEFORE_ANY
        except Exception:
            pass
        _A2C_USE_AUTO_PERSPECTIVE_BEFORE_ANY = None


def store_viewport_state(area, original_perspective, aligned_rotation,
                        view_rotation_before=None, view_location_before=None, view_distance_before=None,
                        transform_orientation_before=None, object_align_before=None,
                        use_auto_perspective_before=None, base_matrix=None):
    """Store the original viewport state before alignment (for restore on leave)"""
    area_ptr = get_area_pointer(area)
    if area_ptr:
        global GL_VIEWPORT_STATE
        state = {
            'original_perspective': original_perspective,
            'aligned_rotation': aligned_rotation,
            'aligned_rotation_base': aligned_rotation.copy(),  # Never updated by roll/pivot; used for "from original"
            'is_aligned': True
        }
        if view_rotation_before is not None:
            state['view_rotation_before'] = view_rotation_before.copy()
        if view_location_before is not None:
            state['view_location_before'] = view_location_before.copy()
        if view_distance_before is not None:
            state['view_distance_before'] = float(view_distance_before)
        if transform_orientation_before is not None:
            state['transform_orientation_before'] = str(transform_orientation_before)
        if object_align_before is not None:
            state['object_align_before'] = str(object_align_before)
        if use_auto_perspective_before is not None:
            state['use_auto_perspective_before'] = bool(use_auto_perspective_before)
        if base_matrix is not None:
            state['base_matrix'] = base_matrix.copy()
        GL_VIEWPORT_STATE[area_ptr] = state


def _restore_aligned_state_settings(window, state):
    """
    Restore transform orientation and object align from the stored state dict.
    Auto-perspective is intentionally NOT restored here; use
    _restore_auto_perspective_if_last() after marking the viewport as unaligned
    so the preference is only restored when the last aligned viewport leaves.
    Swallows errors.
    """
    if 'transform_orientation_before' in state:
        try:
            window.scene.transform_orientation_slots[0].type = state['transform_orientation_before']
        except Exception:
            pass
    if 'object_align_before' in state:
        try:
            bpy.context.preferences.edit.object_align = state['object_align_before']
            if 'a2c_object_align_before' in window.scene:
                del window.scene['a2c_object_align_before']
        except Exception:
            pass


def check_and_restore_perspective():
    """Check if user has rotated away from aligned view and restore original perspective if so"""
    if GL_TOKEN_LOCK.is_set() or not GL_VIEWPORT_STATE:
        return

    try:
        prefs = get_prefs(bpy.context)
    except Exception:
        prefs = None

    live_ptrs = set()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            area_ptr = get_area_pointer(area)
            if area_ptr:
                live_ptrs.add(area_ptr)
            if area_ptr and area_ptr in GL_VIEWPORT_STATE:
                state = GL_VIEWPORT_STATE[area_ptr]
                if state['is_aligned']:
                    space = area.spaces[0]
                    current_rotation = space.region_3d.view_rotation
                    aligned_rotation = state['aligned_rotation']

                    if prefs and prefs.pref_force_ortho_in_aligned_view:
                        if space.region_3d.view_perspective != 'ORTHO':
                            dot_product = abs(current_rotation.dot(aligned_rotation))
                            # View rotation still matches aligned → user toggled perspective (e.g. numpad 5)
                            if dot_product >= A2C_ROTATION_DOT_THRESHOLD:
                                space.region_3d.view_perspective = state['original_perspective']
                                state['is_aligned'] = False
                                _restore_aligned_state_settings(window, state)
                                _restore_auto_perspective_if_last(bpy.context)
                            else:
                                # Orbiting / auto-perspective switched view; force ortho back
                                space.region_3d.view_perspective = 'ORTHO'
                    else:
                        dot_product = abs(current_rotation.dot(aligned_rotation))
                        if dot_product < A2C_ROTATION_DOT_THRESHOLD:
                            space.region_3d.view_perspective = state['original_perspective']
                            state['is_aligned'] = False
                            _restore_aligned_state_settings(window, state)
                            _restore_auto_perspective_if_last(bpy.context)

    # Prune entries for viewports that no longer exist and are no longer aligned
    stale = [p for p, s in GL_VIEWPORT_STATE.items()
             if p not in live_ptrs and not s.get('is_aligned')]
    for p in stale:
        del GL_VIEWPORT_STATE[p]


def viewport_draw_handler():
    """Draw handler to monitor viewport rotation changes"""
    try:
        check_and_restore_perspective()
    except Exception:
        # Silently handle any errors to avoid disrupting the viewport
        pass


def _overlay_draw_callback():
    """Draw a persistent 'Aligned View' text label whenever the active viewport is in aligned state."""
    try:
        context = bpy.context
        if not context or not context.area or context.area.type != 'VIEW_3D':
            return
        prefs = get_prefs(context)
        if prefs is None or not getattr(prefs, 'pref_show_overlay', True):
            return
        if not is_viewport_aligned(context):
            return
        region = context.region
        if not region:
            return
        text = "Aligned View"
        font_id = 0
        size = getattr(prefs, 'pref_overlay_text_size', 16)
        color = tuple(getattr(prefs, 'pref_overlay_text_color', (1.0, 1.0, 1.0, 0.8)))
        v_pct = getattr(prefs, 'pref_overlay_vertical_position', 90.0)
        h_pct = getattr(prefs, 'pref_overlay_horizontal_position', 50.0)
        blf.size(font_id, size)
        text_w, _ = blf.dimensions(font_id, text)
        x = int(region.width * h_pct / 100.0) - int(text_w / 2)
        y = int(region.height * v_pct / 100.0)
        blf.position(font_id, x, y, 0)
        blf.color(font_id, *color)
        blf.draw(font_id, text)
    except Exception:
        pass


def restore_object_align_from_scene():
    """
    Restore object_align from persistent scene storage if the addon changed it
    in a previous session and never restored it (e.g. after a Blender restart).
    """
    try:
        for window in bpy.context.window_manager.windows:
            scene = window.scene
            if 'a2c_object_align_before' in scene:
                bpy.context.preferences.edit.object_align = scene['a2c_object_align_before']
                del scene['a2c_object_align_before']
                break
    except Exception:
        pass



def is_viewport_aligned(context):
    """
    Return True if the current 3D viewport is in an aligned state
    (i.e. was aligned by this addon and not rotated away since).
    When the view is maximized/unmaximized the area pointer can change;
    we detect that by matching the current view rotation to any stored state
    and migrate the state to the current area.
    """
    if not context.area or context.area.type != 'VIEW_3D':
        return False
    area_ptr = get_area_pointer(context.area)
    if not area_ptr:
        return False
    if area_ptr in GL_VIEWPORT_STATE:
        return GL_VIEWPORT_STATE[area_ptr].get('is_aligned', False)
    # Area not in state (e.g. recreated after maximize) – check if current
    # view rotation matches any stored aligned view and migrate state
    try:
        space = context.space_data
        if not space:
            return False
        current_rotation = space.region_3d.view_rotation
        for ptr, state in list(GL_VIEWPORT_STATE.items()):
            if not state.get('is_aligned'):
                continue
            if abs(current_rotation.dot(state['aligned_rotation'])) >= A2C_ROTATION_DOT_THRESHOLD:
                GL_VIEWPORT_STATE[area_ptr] = dict(state)
                del GL_VIEWPORT_STATE[ptr]
                return True
    except Exception:
        pass
    return False


def is_viewport_drifted(context):
    """
    Return True if the viewport is in aligned state but the current view rotation
    has drifted from the stored aligned_rotation (e.g. user orbited manually).
    Used to show pie menu suffix and to choose operator base (original vs current).
    """
    if not context.area or context.area.type != 'VIEW_3D':
        return False
    area_ptr = get_area_pointer(context.area)
    if not area_ptr or area_ptr not in GL_VIEWPORT_STATE:
        return False
    state = GL_VIEWPORT_STATE[area_ptr]
    if not state.get('is_aligned'):
        return False
    try:
        space = context.space_data
        if not space:
            return False
        current = space.region_3d.view_rotation
        aligned = state['aligned_rotation']
        return abs(current.dot(aligned)) < A2C_ROTATION_DOT_THRESHOLD
    except Exception:
        return False


def find_nearest_canonical_quat(current_quat, state):
    """
    Given a current view quaternion, return the nearest canonical aligned viewpoint
    quaternion from the 24 candidates (6 viewpoints × 4 roll angles) relative to
    the base orientation stored when entering aligned view.
    Returns None if base_matrix is not stored in state.
    """
    base_matrix = state.get('base_matrix')
    if base_matrix is None:
        return None
    best_quat = None
    best_dot = -1.0
    for vp_matrix in A2C_VIEWPOINT_MATRICES.values():
        for roll_mat in A2C_ROLL_MATRICES:
            candidate_quat = (base_matrix @ vp_matrix @ roll_mat).to_quaternion()
            dot = abs(current_quat.dot(candidate_quat))
            if dot > best_dot:
                best_dot = dot
                best_quat = candidate_quat
    return best_quat


def has_single_edge_selected(context):
    """Return True if in Edit Mesh mode with exactly one edge selected."""
    if context.mode != 'EDIT_MESH':
        return False
    obj = context.edit_object
    if not obj or obj.type != 'MESH':
        return False
    return obj.data.total_edge_sel == 1


def should_offer_switch_to_edge(context, align_mode):
    """Return True when in Selection mode with exactly one edge selected (offer Edge Align instead)."""
    return align_mode == 'SELECTION' and has_single_edge_selected(context)


def get_viewpoint_matrix_for_nearest(base_matrix, current_view_direction):
    """
    Return the viewpoint rotation matrix (TOP, FRONT, etc.) that best matches
    the given view direction when combined with base_matrix. Used for NEAREST.
    """
    max_dot = -float('inf')
    best_viewpoint = "TOP"
    for viewpoint_name, viewpoint_rot in A2C_VIEWPOINT_MATRICES.items():
        target_view_direction = -(base_matrix @ viewpoint_rot).col[2]
        dot = current_view_direction.dot(target_view_direction)
        if dot > max_dot:
            max_dot = dot
            best_viewpoint = viewpoint_name
    return A2C_VIEWPOINT_MATRICES[best_viewpoint]


# ## Math functions section ###################################################
def s_curve(x):
    """
    Map a linear value in [0, 1] through an S-curve (sinusoidal ease in/out).
    Input is clamped to [0, 1] to stay numerically safe even with float drift.
    """
    x = max(0.0, min(1.0, x))
    return (1.0 + math.sin((x - 0.5) * math.pi)) / 2.0


def find_best_roll_orientation(current_quat, target_base_matrix, viewpoint_matrix):
    """
    Find the best roll orientation by preserving the visual "up" direction after cursor alignment.
    
    Simple approach:
    1. Capture the current visual "up" direction in world space
    2. Do proper cursor alignment 
    3. Apply 90-degree rotation to restore the visual "up" direction as closely as possible
    
    Parameters:
     - current_quat: Current view rotation quaternion
     - target_base_matrix: Base matrix (cursor or custom orientation)
     - viewpoint_matrix: Viewpoint rotation matrix (TOP, FRONT, etc.)
    
    Returns: Final orientation matrix with cursor alignment and preserved visual orientation
    """
    
    # Step 1: Capture the current visual "up" direction in world space
    current_matrix = current_quat.to_matrix()
    
    # The current "up" direction is what appears to go upward in the viewport
    # This is the Y-axis (column) of the current view matrix
    # Note: matrix[1] gets the ROW, matrix.col[1] gets the COLUMN (Y-axis)
    visual_up_direction = current_matrix.col[1]  # Y-axis column (up direction in viewport)
    
    # Step 2: Do the standard cursor alignment
    aligned_matrix = target_base_matrix @ viewpoint_matrix
    
    # Step 3: Test 90-degree rotations to find the one that best preserves visual "up"
    best_idx = 0
    best_score = -1

    for idx, roll_mat in enumerate(A2C_ROLL_MATRICES):
        test_matrix = aligned_matrix @ roll_mat

        # Get the new "up" direction after this rotation
        new_up_direction = test_matrix.col[1]  # Y-axis column of the rotated matrix

        # Score based on how closely the new "up" matches the original visual "up"
        # Use dot product - closer to 1.0 means better alignment
        alignment_score = visual_up_direction.dot(new_up_direction)

        # We want the highest dot product (closest to 1.0)
        if alignment_score > best_score:
            best_score = alignment_score
            best_idx = idx

    # Step 4: Apply the best rotation
    final_rotation_matrix = A2C_ROLL_MATRICES[best_idx]
    final_matrix = aligned_matrix @ final_rotation_matrix
    
    return final_matrix


# ## Smooth rotation ##########################################################

_SMOOTH_ROT_STEP = 0.02
_SMOOTH_ROT_DURATION = 0.24


def smooth_rotate(space, quat_begin, quat_end, on_complete=None):
    """
    Rotate the 3D view smoothly between 'quat_begin' and 'quat_end' on a
    background thread. Calls on_complete(space) when done, if provided.
    Clears GL_TOKEN_LOCK when finished.
    Exits early if _A2C_STOP_EVENT is set (e.g. during addon unregister / Blender shutdown).
    """
    if space:
        diff_quat = quat_end.rotation_difference(quat_begin)
        _, angle = diff_quat.to_axis_angle()
        duration = abs(_SMOOTH_ROT_DURATION * angle / math.pi)

        start_time = time.time()
        current_time = start_time

        while current_time <= start_time + duration and not _A2C_STOP_EVENT.is_set():
            if duration == 0.0:
                factor = 1.0
            else:
                factor = s_curve((current_time - start_time) / duration)
            space.region_3d.view_rotation = quat_begin.slerp(quat_end, factor)
            time.sleep(_SMOOTH_ROT_STEP)
            current_time = time.time()

        if not _A2C_STOP_EVENT.is_set():
            space.region_3d.view_rotation = quat_end
            space.region_3d.view_perspective = 'ORTHO'
            if on_complete:
                on_complete(space)

    GL_TOKEN_LOCK.clear()


def _start_rotation_thread(target, args=()):
    """
    Start a smooth-rotation background thread as a daemon.
    Daemon threads are abandoned (not waited for) during Python shutdown,
    preventing the crash that occurs when Blender closes mid-rotation.
    """
    t = thd.Thread(target=target, args=args, daemon=True)
    t.start()
    return t


# ## Preferences section ######################################################
# ## Operator section #########################################################


class VIEW3D_OT_a2c_pivot_view(bpy.types.Operator):
    """
    Pivot the 3D view by 90 degrees in the given direction (up, down, left, right).
    Works in the current view's local frame, regardless of how the view was aligned.
    """
    bl_idname = "view3d.a2c_pivot_view"
    bl_label = "Pivot View 90°"
    bl_options = {'REGISTER'}

    direction: bpy.props.EnumProperty(
        items=[
            ("TOP",    "Top",    "Pivot view 90° toward top",    1),
            ("BOTTOM", "Bottom", "Pivot view 90° toward bottom", 2),
            ("LEFT",   "Left",   "Pivot view 90° toward left",   3),
            ("RIGHT",  "Right",  "Pivot view 90° toward right",   4),
        ],
        name="Direction",
        default="TOP",
    )
    from_canonical: bpy.props.BoolProperty(
        name="From canonical aligned angle",
        description="Use the stored aligned angle as base instead of current view (e.g. when view has drifted)",
        default=False,
    )

    def execute(self, context):
        space = context.space_data
        if not space or space.type != 'VIEW_3D':
            return {'CANCELLED'}
        rv3d = space.region_3d
        area_ptr = get_area_pointer(context.area)
        if self.from_canonical and area_ptr and area_ptr in GL_VIEWPORT_STATE:
            state = GL_VIEWPORT_STATE[area_ptr]
            if state.get('is_aligned') and 'aligned_rotation' in state:
                view_quat = state['aligned_rotation'].copy()
            else:
                view_quat = rv3d.view_rotation.copy()
        else:
            view_quat = rv3d.view_rotation.copy()
        # Rotate in the view's local frame so roll is preserved:
        # local X = right, local Y = up, local Z = forward (view direction)
        if self.direction == 'LEFT':
            # Orbit left: rotate around local Y (up) by -90°
            rot_quat = mu.Quaternion((0, 1, 0), math.radians(-90))
        elif self.direction == 'RIGHT':
            rot_quat = mu.Quaternion((0, 1, 0), math.radians(90))
        elif self.direction == 'TOP':
            # Tilt up: rotate around local X (right) by -90°
            rot_quat = mu.Quaternion((1, 0, 0), math.radians(-90))
        else:  # BOTTOM
            rot_quat = mu.Quaternion((1, 0, 0), math.radians(90))
        # view_quat @ rot_quat = apply view then rotate in its local frame
        new_quat = (view_quat @ rot_quat).normalized()

        prefs = context.preferences.addons[__package__].preferences

        if prefs.pref_smooth:
            GL_TOKEN_LOCK.set()
            _start_rotation_thread(smooth_rotate, (space, view_quat, new_quat))
        else:
            rv3d.view_rotation = new_quat

        # Keep viewport in "aligned" state so relative pie layout stays available
        if area_ptr and area_ptr in GL_VIEWPORT_STATE:
            GL_VIEWPORT_STATE[area_ptr]['aligned_rotation'] = new_quat
            GL_VIEWPORT_STATE[area_ptr]['is_aligned'] = True
        return {'FINISHED'}


class VIEW3D_OT_a2c_snap_orbit(bpy.types.Operator):
    """
    Snap to nearest canonical aligned viewpoint.
    While in aligned view, press Left Alt to snap the current view to the nearest
    of the 24 canonical viewpoints (6 faces × 4 roll angles) of the original
    alignment orientation. Orbit freely first, then press Alt to snap.
    Most useful together with 'Force ortho view in aligned view'.
    """
    bl_idname = "view3d.a2c_snap_orbit"
    bl_label = "Snap Orbit (Aligned View)"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        # Only run when in aligned view; enable/disable via keymap checkbox
        if not is_viewport_aligned(context):
            return {'PASS_THROUGH'}
        return self.execute(context)

    def execute(self, context):
        area_ptr = get_area_pointer(context.area)
        if not area_ptr or area_ptr not in GL_VIEWPORT_STATE:
            return {'CANCELLED'}
        state = GL_VIEWPORT_STATE[area_ptr]
        if not state.get('is_aligned'):
            return {'CANCELLED'}
        space = context.space_data
        if not space or space.type != 'VIEW_3D':
            return {'CANCELLED'}
        rv3d = space.region_3d
        current_quat = rv3d.view_rotation.copy()
        target_quat = find_nearest_canonical_quat(current_quat, state)
        if target_quat is None:
            return {'CANCELLED'}
        # Nothing to do if already at the nearest canonical position
        if abs(current_quat.dot(target_quat)) >= A2C_ROTATION_DOT_THRESHOLD:
            return {'FINISHED'}
        try:
            prefs = context.preferences.addons[__package__].preferences
        except Exception:
            return {'CANCELLED'}
        if prefs.pref_smooth:
            GL_TOKEN_LOCK.set()
            _start_rotation_thread(smooth_rotate, (space, current_quat, target_quat))
        else:
            rv3d.view_rotation = target_quat
        rv3d.view_perspective = 'ORTHO'
        state['aligned_rotation'] = target_quat
        state['is_aligned'] = True
        return {'FINISHED'}


# Minimum drag distance (pixels) to trigger pivot direction
PIVOT_DRAG_THRESHOLD = 15


class VIEW3D_OT_a2c_pivot_view_drag(bpy.types.Operator):
    """
    Pivot the aligned view by 90° based on Alt+MMB drag direction.
    Only works when the viewport is in aligned state (similar to view3d.view_axis).
    """
    bl_idname = "view3d.a2c_pivot_view_drag"
    bl_label = "Pivot View by Drag (Aligned)"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        if not is_viewport_aligned(context):
            return {'PASS_THROUGH'}
        self.start_x = event.mouse_x
        self.start_y = event.mouse_y
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MIDDLEMOUSE' and event.value == 'RELEASE':
            dx = event.mouse_x - self.start_x
            dy = event.mouse_y - self.start_y
            if abs(dx) < PIVOT_DRAG_THRESHOLD and abs(dy) < PIVOT_DRAG_THRESHOLD:
                return {'CANCELLED'}
            if abs(dx) >= abs(dy):
                # Drag right (dx > 0) = pivot LEFT; drag left = pivot RIGHT
                direction = 'LEFT' if dx > 0 else 'RIGHT'
            else:
                # Drag up (dy > 0) = pivot BOTTOM; drag down = pivot TOP (inverted from widget)
                direction = 'BOTTOM' if dy > 0 else 'TOP'
            bpy.ops.view3d.a2c_pivot_view(direction=direction)
            return {'FINISHED'}
        if event.type in ('ESC', 'RIGHTMOUSE'):
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class VIEW3D_OT_a2c_confirm_and_exit(bpy.types.Operator):
    """Exit Aligned View keeping the current camera angle.
The current view becomes the new starting point for the next alignment — no revert.
Alt+Click the Exit/Leave button in the pie menu to trigger this"""
    bl_idname = "view3d.a2c_confirm_and_exit"
    bl_label = "Confirm and Exit Aligned View"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not context.area or context.area.type != 'VIEW_3D':
            return {'CANCELLED'}
        area_ptr = get_area_pointer(context.area)
        if not area_ptr or area_ptr not in GL_VIEWPORT_STATE:
            return {'CANCELLED'}
        state = GL_VIEWPORT_STATE[area_ptr]
        if not state.get('is_aligned'):
            return {'CANCELLED'}
        # Restore transform orientation and object align without touching the camera transform
        _restore_aligned_state_settings(context.window, state)
        state['is_aligned'] = False
        _restore_auto_perspective_if_last(context)
        self.report({'INFO'}, "Aligned View: Confirmed (camera angle kept)")
        return {'FINISHED'}


class VIEW3D_OT_a2c_reset_state(bpy.types.Operator):
    """Reset Auto Perspective and Align Methods to defaults.
Use this as a last resort when Auto Perspective or Align to World are no longer working correctly.
Alt+Click the Smart button in the pie menu (non-aligned mode) to trigger this"""
    bl_idname = "view3d.a2c_reset_state"
    bl_label = "Reset Auto Perspective and Align Methods"
    bl_options = {'REGISTER'}

    def execute(self, context):
        global _A2C_USE_AUTO_PERSPECTIVE_BEFORE_ANY
        try:
            context.preferences.inputs.use_auto_perspective = True
        except Exception:
            pass
        try:
            context.preferences.edit.object_align = 'WORLD'
        except Exception:
            pass
        for window in context.window_manager.windows:
            scene = window.scene
            # Reset transform orientation if stuck on VIEW (set by the addon on align)
            try:
                if scene.transform_orientation_slots[0].type == 'VIEW':
                    scene.transform_orientation_slots[0].type = 'GLOBAL'
            except Exception:
                pass
            if 'a2c_object_align_before' in scene:
                try:
                    del scene['a2c_object_align_before']
                except Exception:
                    pass
        for state in GL_VIEWPORT_STATE.values():
            state['is_aligned'] = False
        _A2C_USE_AUTO_PERSPECTIVE_BEFORE_ANY = None
        self.report({'INFO'}, "Align2Custom: Auto Perspective, Transform Orientation and New Objects Align reset to defaults")
        return {'FINISHED'}


class VIEW3D_OT_a2c_leave_aligned_view(bpy.types.Operator):
    """
    Restore the view to its state from before the last alignment.
    Only available when the viewport is in aligned state.
    """
    bl_idname = "view3d.a2c_leave_aligned_view"
    bl_label = "Leave Aligned View"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not context.area or context.area.type != 'VIEW_3D':
            return {'CANCELLED'}
        area_ptr = get_area_pointer(context.area)
        if not area_ptr or area_ptr not in GL_VIEWPORT_STATE:
            return {'CANCELLED'}
        state = GL_VIEWPORT_STATE[area_ptr]
        if not state.get('is_aligned'):
            return {'CANCELLED'}
        if 'view_rotation_before' not in state or 'view_location_before' not in state:
            return {'CANCELLED'}
        space = context.space_data
        rv3d = space.region_3d
        current_quat = rv3d.view_rotation.copy()
        target_quat = state['view_rotation_before'].copy()

        # Restore transform orientation and object align immediately (auto-perspective deferred)
        _restore_aligned_state_settings(context.window, state)

        prefs = context.preferences.addons[__package__].preferences
        if prefs.pref_smooth:
            GL_TOKEN_LOCK.set()

            def on_leave_complete(space):
                space.region_3d.view_location = state['view_location_before'].copy()
                space.region_3d.view_distance = state['view_distance_before']
                space.region_3d.view_perspective = state['original_perspective']
                state['is_aligned'] = False
                _restore_auto_perspective_if_last(bpy.context)

            _start_rotation_thread(smooth_rotate, (space, current_quat, target_quat, on_leave_complete))
        else:
            rv3d.view_rotation = target_quat
            rv3d.view_location = state['view_location_before'].copy()
            rv3d.view_distance = state['view_distance_before']
            rv3d.view_perspective = state['original_perspective']
            state['is_aligned'] = False
            _restore_auto_perspective_if_last(context)
        self.report({'INFO'}, "Aligned View: Disabled")
        return {'FINISHED'}


class VIEW3D_OT_a2c_roll_view(bpy.types.Operator):
    """
    Roll the 3D view by an angle (radians), enforce orthographic view,
    and update the aligned state so the addon still considers the view aligned.
    """
    bl_idname = "view3d.a2c_roll_view"
    bl_label = "Roll View (Aligned)"
    bl_options = {'REGISTER'}

    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Roll angle in radians",
        default=0.0,
        unit='ROTATION',
    )
    from_canonical: bpy.props.BoolProperty(
        name="From canonical aligned angle",
        description="Use the stored aligned angle as base instead of current view (e.g. when view has drifted)",
        default=False,
    )

    def execute(self, context):
        space = context.space_data
        if not space or space.type != 'VIEW_3D':
            return {'CANCELLED'}
        rv3d = space.region_3d
        area_ptr = get_area_pointer(context.area)
        if self.from_canonical and area_ptr and area_ptr in GL_VIEWPORT_STATE:
            state = GL_VIEWPORT_STATE[area_ptr]
            if state.get('is_aligned') and 'aligned_rotation' in state:
                view_quat = state['aligned_rotation'].copy()
            else:
                view_quat = rv3d.view_rotation.copy()
        else:
            view_quat = rv3d.view_rotation.copy()
        # Roll: rotate around view's forward axis (local Z)
        new_quat = (view_quat @ mu.Quaternion((0, 0, 1), self.angle)).normalized()

        prefs = context.preferences.addons[__package__].preferences

        if prefs.pref_smooth:
            GL_TOKEN_LOCK.set()
            _start_rotation_thread(smooth_rotate, (space, view_quat, new_quat))
        else:
            rv3d.view_rotation = new_quat

        rv3d.view_perspective = 'ORTHO'
        if area_ptr and area_ptr in GL_VIEWPORT_STATE:
            GL_VIEWPORT_STATE[area_ptr]['aligned_rotation'] = new_quat
            GL_VIEWPORT_STATE[area_ptr]['is_aligned'] = True
        return {'FINISHED'}


class VIEW3D_OT_a2c(bpy.types.Operator):
    """
    Align 3D View to a chosen orientation (custom, cursor, or selection) and viewpoint (top, front, nearest, etc.)
    """

    bl_idname = "view3d.a2c"
    bl_label = "Align View to orientation"
    bl_options = {'REGISTER'}

    ALIGN_MODE_ITEMS = [
        ("CUSTOM", "Align to custom orientation", "", 1),
        ("CURSOR", "Align to cursor orientation", "", 2),
        ("SELECTION", "Align to selection orientation", "", 3),
    ]

    prop_align_mode: bpy.props.EnumProperty(items=ALIGN_MODE_ITEMS,
                                            name="Align mode",
                                            default="CUSTOM")
    prop_viewpoint: bpy.props.EnumProperty(items=A2C_VIEWPOINT_ITEMS,
                                           name="Point of view",
                                           default="TOP")

    def invoke(self, context, event):
        """Offer to switch to Edge Align when in Selection mode with one edge selected."""
        if should_offer_switch_to_edge(context, self.prop_align_mode):
            try:
                prefs = context.preferences.addons[__package__].preferences
                if getattr(prefs, "pref_offer_edge_mode_when_one_edge", True):
                    wm = context.window_manager
                    wm.a2c_pending_edge_viewpoint = self.prop_viewpoint
                    bpy.ops.wm.call_menu(name='VIEW3D_MT_a2c_confirm_one_edge')
                    return {'FINISHED'}
            except Exception:
                pass
        return self.execute(context)

    def execute(self, context):
        """
        Set the orientation of the 3D View in which the operator is called,
        as a combination of the 3D cursor matrix or the active custom transform
        orientation matrix, and the rotation matrix passed in argument.

        The rotation transition depends on the parameter selected in the addon
        preferences UI. The transition can be instantaneous or smooth.
        """

        # Get the addon preferences
        prefs = context.preferences.addons[__package__].preferences

        scene = context.window.scene
        space = context.space_data

        # Handle SELECTION mode: create temporary orientation from selection
        temp_orientation_created = False
        if self.prop_align_mode == 'SELECTION':
            try:
                # Create temporary custom orientation from selection
                bpy.ops.transform.create_orientation(
                    name="Temp",
                    use=True,
                    overwrite=True
                )
                temp_orientation_created = True
            except RuntimeError:
                # No valid selection to create orientation from
                self.report({'WARNING'}, "Cannot create orientation from current selection")
                return {'CANCELLED'}

        co = scene.transform_orientation_slots[0].custom_orientation
        can_proceed = (self.prop_align_mode == 'CURSOR') or \
                      (self.prop_align_mode == 'SELECTION' and temp_orientation_created) or \
                      (self.prop_align_mode == 'CUSTOM' and co)
        
        if (not GL_TOKEN_LOCK.is_set()) and (space.type == 'VIEW_3D') and can_proceed:

            # Store original perspective and full view state before alignment (for "Leave aligned view")
            rv3d = space.region_3d
            original_perspective = rv3d.view_perspective
            view_rotation_before = rv3d.view_rotation.copy()
            view_location_before = rv3d.view_location.copy()
            view_distance_before = rv3d.view_distance

            # Determine the base matrix first (needed for NEAREST calculation)
            if self.prop_align_mode == 'CURSOR':
                base_matrix = scene.cursor.matrix.to_3x3()
            else:
                # Both CUSTOM and SELECTION modes use the custom orientation
                base_matrix = co.matrix.copy()

            # Compute the rotation matrix according to the desired viewpoint
            if self.prop_viewpoint == "NEAREST":
                current_quat = space.region_3d.view_rotation
                current_view_direction = -current_quat.to_matrix().col[2]
                rot_matrix = get_viewpoint_matrix_for_nearest(base_matrix, current_view_direction)
            elif self.prop_viewpoint in A2C_VIEWPOINT_MATRICES:
                rot_matrix = A2C_VIEWPOINT_MATRICES[self.prop_viewpoint]
            else:   # TOP (DEFAULT)
                rot_matrix = mu.Matrix.Identity(3)

            # Use minimize roll feature if enabled
            if prefs.pref_minimize_roll:
                current_quat = space.region_3d.view_rotation
                new_orientation = find_best_roll_orientation(current_quat, base_matrix, rot_matrix)
            else:
                new_orientation = base_matrix @ rot_matrix

            final_quat = new_orientation.to_quaternion()

            # Delete temporary orientation if we created one (SELECTION mode)
            if temp_orientation_created:
                try:
                    bpy.ops.transform.delete_orientation()
                except RuntimeError:
                    pass  # Orientation might already be deleted

            # Store viewport state before making changes
            transform_orientation_before = None
            object_align_before = None
            should_set_view_orientation = prefs.pref_set_orientation_to_view and (
                self.prop_align_mode != 'CUSTOM' or prefs.pref_set_orientation_to_view_for_custom
            )
            if should_set_view_orientation:
                transform_orientation_before = scene.transform_orientation_slots[0].type
            if prefs.pref_use_view_orientation_in_aligned_view:
                try:
                    object_align_before = context.preferences.edit.object_align
                except Exception:
                    pass
            use_auto_perspective_before = None
            if prefs.pref_force_ortho_in_aligned_view:
                # Must capture before store_viewport_state marks is_aligned=True,
                # otherwise the "any already aligned?" guard in the capture function
                # fires prematurely and the global value is never saved.
                _capture_auto_perspective_if_first(context)
                try:
                    use_auto_perspective_before = context.preferences.inputs.use_auto_perspective
                except Exception:
                    pass
            store_viewport_state(
                context.area, original_perspective, final_quat,
                view_rotation_before=view_rotation_before,
                view_location_before=view_location_before,
                view_distance_before=view_distance_before,
                transform_orientation_before=transform_orientation_before,
                object_align_before=object_align_before,
                use_auto_perspective_before=use_auto_perspective_before,
                base_matrix=base_matrix
            )

            space.region_3d.view_perspective = 'ORTHO'
            if prefs.pref_force_ortho_in_aligned_view:
                try:
                    context.preferences.inputs.use_auto_perspective = False
                except Exception:
                    pass

            self.report({'INFO'}, "Aligned View: Enabled ({})".format(
                self.prop_align_mode.capitalize()))

            if prefs.pref_smooth:
                initial_quat = space.region_3d.view_rotation
                GL_TOKEN_LOCK.set()
                _start_rotation_thread(smooth_rotate, (space, initial_quat, final_quat))
            else:
                space.region_3d.view_rotation = final_quat

            # Set transform orientation to View if preference is enabled (Transform Orientation dropdown only)
            if should_set_view_orientation:
                scene.transform_orientation_slots[0].type = 'VIEW'
            # Set "New Objects > Align to" to View if preference is enabled (affects newly added primitives only)
            if prefs.pref_use_view_orientation_in_aligned_view:
                try:
                    scene['a2c_object_align_before'] = context.preferences.edit.object_align
                    context.preferences.edit.object_align = 'VIEW'
                except Exception:
                    pass

        else:
            # If we couldn't proceed but created a temp orientation, clean it up
            if temp_orientation_created:
                try:
                    bpy.ops.transform.delete_orientation()
                except RuntimeError:
                    pass

        return {'FINISHED'}


# ## Edge alignment operator ##################################################

class VIEW3D_OT_a2c_align_to_edge(bpy.types.Operator):
    """Align the view so the selected edge appears perfectly horizontal or vertical.
Temporarily moves the 3D Cursor to the edge midpoint and orients it
along the edge, aligns the view, then restores the cursor."""
    bl_idname = "view3d.a2c_align_to_edge"
    bl_label = "Align View to Edge"
    bl_options = {'REGISTER'}

    prop_viewpoint: bpy.props.EnumProperty(
        items=A2C_VIEWPOINT_ITEMS,
        name="Point of view",
        default="TOP",
    )

    @classmethod
    def poll(cls, context):
        if not context.space_data or context.space_data.type != 'VIEW_3D':
            return False
        if context.mode != 'EDIT_MESH':
            return False
        obj = context.edit_object
        if not obj or obj.type != 'MESH':
            return False
        return obj.data.total_edge_sel == 1

    def execute(self, context):
        scene = context.scene
        space = context.space_data
        obj = context.edit_object

        prefs = get_prefs(context)
        if prefs is None:
            addon = context.preferences.addons.get("align2custom")
            prefs = addon.preferences if addon else None
        if not prefs:
            self.report({'WARNING'}, "Addon preferences not found")
            return {'CANCELLED'}

        # When Force Viewpoint is on, we will change the view twice (object align, then edge).
        # Store the true original view now so "Leave Aligned View" restores it correctly.
        force_viewpoint = getattr(prefs, "pref_force_viewpoint_edge", False)
        saved_view_for_leave = None
        if force_viewpoint:
            rv3d = space.region_3d
            try:
                transform_before = scene.transform_orientation_slots[0].type
            except Exception:
                transform_before = None
            try:
                object_align_before = context.preferences.edit.object_align
            except Exception:
                object_align_before = None
            try:
                use_auto_perspective_before = context.preferences.inputs.use_auto_perspective
            except Exception:
                use_auto_perspective_before = None
            saved_view_for_leave = {
                "view_rotation_before": rv3d.view_rotation.copy(),
                "view_location_before": rv3d.view_location.copy(),
                "view_distance_before": float(rv3d.view_distance),
                "original_perspective": rv3d.view_perspective,
                "transform_orientation_before": transform_before,
                "object_align_before": object_align_before,
                "use_auto_perspective_before": use_auto_perspective_before,
            }

        # Force Viewpoint: pre-align the view to the object's world orientation before
        # building the edge matrix (so the result is relative to the object, not the
        # current arbitrary view). Uses obj.matrix_world directly — no mode switch needed.
        if force_viewpoint:
            base_matrix = obj.matrix_world.to_3x3()
            rv3d = space.region_3d
            current_quat = rv3d.view_rotation

            if self.prop_viewpoint == "NEAREST":
                current_view_direction = -(current_quat.to_matrix().col[2])
                rot_matrix = get_viewpoint_matrix_for_nearest(base_matrix, current_view_direction)
            elif self.prop_viewpoint in A2C_VIEWPOINT_MATRICES:
                rot_matrix = A2C_VIEWPOINT_MATRICES[self.prop_viewpoint]
            else:
                rot_matrix = mu.Matrix.Identity(3)

            if prefs.pref_minimize_roll:
                pre_orientation = find_best_roll_orientation(current_quat, base_matrix, rot_matrix)
            else:
                pre_orientation = base_matrix @ rot_matrix

            rv3d.view_rotation = pre_orientation.to_quaternion()
            rv3d.view_perspective = 'ORTHO'

        # Save full cursor state so we can restore it after aligning
        saved_location = scene.cursor.location.copy()
        saved_rotation_mode = scene.cursor.rotation_mode
        saved_rotation_quat = scene.cursor.rotation_quaternion.copy()
        saved_rotation_euler = scene.cursor.rotation_euler.copy()
        saved_rotation_axis_angle = list(scene.cursor.rotation_axis_angle)

        try:
            bm = bmesh.from_edit_mesh(obj.data)
            e = next((ed for ed in bm.edges if ed.select), None)
            if e is None:
                return {'CANCELLED'}

            # Edge midpoint in world space
            mid_world = obj.matrix_world @ ((e.verts[0].co + e.verts[1].co) / 2)

            # Edge direction in world space
            ed_vec = (obj.matrix_world.to_3x3() @ (e.verts[1].co - e.verts[0].co)).normalized()

            ignore_depth = force_viewpoint and getattr(prefs, "pref_ignore_depth_edge", False)
            if ignore_depth:
                # Keep view direction from Force Viewpoint (object axis); only roll so the edge
                # lies flat. This avoids the "shift" when the edge has an angle in the object's XY plane.
                vr = space.region_3d.view_rotation
                view_dir = (vr @ mu.Vector((0, 0, 1))).normalized()
                V = -view_dir  # from camera into scene
                col_2 = -V  # cursor -Z = view direction
                cross = V.cross(ed_vec)
                if cross.length < 1e-6:
                    self.report({'WARNING'}, "Edge is parallel to the view direction; cannot align")
                    return {'CANCELLED'}
                col_1 = cross.normalized()
                col_0 = col_1.cross(col_2).normalized()
                m = mu.Matrix([col_0, col_1, col_2]).transposed()
            else:
                # Build an orientation matrix so the edge is the local X axis and
                # lies flat (horizontal) when the view is snapped to TOP.
                # cam  = view Z axis in world space (points toward viewer)
                # ed   = edge direction in world space (becomes cursor local X)
                # perp = vector perpendicular to both edge and cam (cursor local Y)
                # cam2 = recomputed cam-like direction perpendicular to edge (cursor local Z)
                vr = space.region_3d.view_rotation
                cam = (vr @ mu.Vector((0, 0, 1))).normalized()
                # Guard against degenerate edge (zero length) or edge parallel to view
                perp = ed_vec.cross(cam)
                if perp.length < 1e-6:
                    self.report({'WARNING'}, "Edge is parallel to the view direction; cannot align")
                    return {'CANCELLED'}
                perp = perp.normalized()
                cam2 = ed_vec.cross(perp).normalized()
                m = mu.Matrix([ed_vec, perp, cam2]).transposed()

            # Temporarily place cursor at edge midpoint with computed orientation
            scene.cursor.location = mid_world
            scene.cursor.rotation_mode = 'QUATERNION'
            scene.cursor.rotation_quaternion = m.to_quaternion()

            # Align view: cursor + chosen viewpoint (TOP = edge horizontal)
            # With "Ignore depth" we built the cursor so view direction is already correct; use TOP.
            viewpoint = 'TOP' if ignore_depth else self.prop_viewpoint
            result = bpy.ops.view3d.a2c(prop_align_mode='CURSOR', prop_viewpoint=viewpoint)

            # If we had stored the true original view (Force Viewpoint path), patch the
            # state so "Leave Aligned View" restores to that instead of the view after pre-step.
            if (result and 'FINISHED' in result) and saved_view_for_leave is not None:
                area_ptr = get_area_pointer(context.area)
                if area_ptr and area_ptr in GL_VIEWPORT_STATE:
                    state = GL_VIEWPORT_STATE[area_ptr]
                    state["view_rotation_before"] = saved_view_for_leave["view_rotation_before"].copy()
                    state["view_location_before"] = saved_view_for_leave["view_location_before"].copy()
                    state["view_distance_before"] = saved_view_for_leave["view_distance_before"]
                    state["original_perspective"] = saved_view_for_leave["original_perspective"]
                    if saved_view_for_leave.get("transform_orientation_before") is not None:
                        state["transform_orientation_before"] = saved_view_for_leave["transform_orientation_before"]
                    if saved_view_for_leave.get("object_align_before") is not None:
                        state["object_align_before"] = saved_view_for_leave["object_align_before"]
                    if saved_view_for_leave.get("use_auto_perspective_before") is not None:
                        state["use_auto_perspective_before"] = saved_view_for_leave["use_auto_perspective_before"]

        finally:
            # Restore cursor to its original state regardless of what happened
            scene.cursor.rotation_mode = saved_rotation_mode
            if saved_rotation_mode == 'QUATERNION':
                scene.cursor.rotation_quaternion = saved_rotation_quat
            elif saved_rotation_mode == 'AXIS_ANGLE':
                scene.cursor.rotation_axis_angle = saved_rotation_axis_angle
            else:
                scene.cursor.rotation_euler = saved_rotation_euler
            scene.cursor.location = saved_location

        self.report({'INFO'}, "Aligned View: Enabled (Edge)")
        return {'FINISHED'}


# ## Blender registration section #############################################
def register():
    """
    Module register function called by the main package register function
    """
    global GL_DRAW_HANDLER, _A2C_OVERLAY_HANDLER

    # Clear the stop flag in case the addon was just reloaded after being disabled
    _A2C_STOP_EVENT.clear()

    # Restore object_align if the addon changed it in a previous session
    # (e.g. Blender was closed while in aligned view and the runtime state was lost)
    restore_object_align_from_scene()

    bpy.utils.register_class(VIEW3D_OT_a2c_snap_orbit)
    bpy.utils.register_class(VIEW3D_OT_a2c_pivot_view_drag)
    bpy.utils.register_class(VIEW3D_OT_a2c_confirm_and_exit)
    bpy.utils.register_class(VIEW3D_OT_a2c_reset_state)
    bpy.utils.register_class(VIEW3D_OT_a2c_leave_aligned_view)
    bpy.utils.register_class(VIEW3D_OT_a2c_roll_view)
    bpy.utils.register_class(VIEW3D_OT_a2c_pivot_view)
    bpy.utils.register_class(VIEW3D_OT_a2c)
    bpy.utils.register_class(VIEW3D_OT_a2c_align_to_edge)

    # Register the viewport draw handler (rotation monitoring)
    GL_DRAW_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
        viewport_draw_handler, (), 'WINDOW', 'POST_PIXEL'
    )
    # Register the aligned-view overlay text draw handler
    _A2C_OVERLAY_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
        _overlay_draw_callback, (), 'WINDOW', 'POST_PIXEL'
    )


def unregister():
    """
    Module unregister function called by the main package register function
    """
    global GL_VIEWPORT_STATE, GL_DRAW_HANDLER, _A2C_OVERLAY_HANDLER

    # Signal any running smooth-rotation thread to stop, then wait long enough
    # for it to notice the flag (one sleep step + margin).  This prevents the
    # EXCEPTION_ACCESS_VIOLATION crash that occurs when Blender closes while a
    # daemon rotation thread is still writing to region_3d.view_rotation.
    _A2C_STOP_EVENT.set()
    time.sleep(_SMOOTH_ROT_STEP * 3)
    GL_TOKEN_LOCK.clear()

    # Restore object_align if we changed it and the user is still in aligned view
    for state in GL_VIEWPORT_STATE.values():
        if state.get('is_aligned') and 'object_align_before' in state:
            try:
                bpy.context.preferences.edit.object_align = state['object_align_before']
            except Exception:
                pass
            break
    restore_object_align_from_scene()

    # Clean up global state
    GL_VIEWPORT_STATE.clear()

    # Remove the viewport draw handlers
    if GL_DRAW_HANDLER:
        bpy.types.SpaceView3D.draw_handler_remove(GL_DRAW_HANDLER, 'WINDOW')
        GL_DRAW_HANDLER = None
    if _A2C_OVERLAY_HANDLER:
        bpy.types.SpaceView3D.draw_handler_remove(_A2C_OVERLAY_HANDLER, 'WINDOW')
        _A2C_OVERLAY_HANDLER = None

    bpy.utils.unregister_class(VIEW3D_OT_a2c_align_to_edge)
    bpy.utils.unregister_class(VIEW3D_OT_a2c)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_roll_view)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_leave_aligned_view)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_reset_state)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_confirm_and_exit)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_snap_orbit)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_pivot_view_drag)
    bpy.utils.unregister_class(VIEW3D_OT_a2c_pivot_view)

