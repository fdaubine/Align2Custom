# Align2Custom

Blender incorporates 3 operators to align the 3D view :
 - alignment to the global transform orientation
 - alignment to a local transform orientation
 - alignment to the camera orientation

Most of the time these methods become limited when working on a complicated mesh or a complicated scene.

This add-on bypasses these limits by offering 2 custom alignment features for the 3D view :
 - alignment to the 3D cursor orientation
 - alignment to a custom transform orientation

<br>

## Features

### Alignment to the 3D cursor orientation

This method is based on the ability of the 3D cursor to automatically align itself to the geometry of a face it is snapped to.

<br>

#### Prerequisites and limitations

Blender provides the following operators to snap the 3D cursor to one face of a mesh : <kbd>SHIFT</kbd> + <kbd>RMB</kbd> click (on the face), the _snap menu_ (<kbd>SHIFT</kbd> + <kbd>S</kbd>), or the _Cursor_ tool. Unfortunately the first two methods don't change the 3D cursor orientation ; they merely change the cursor position.
Therefore there is no choice but to use the 3D cursor tool. However it requires a bit of configuration to work as expected.

First, it's necessary to allow the 3D cursor to align automatically to the geometry of the targeted mesh :
 - select the _Cursor_ tool in the 3D viewport toolbar
 - open the 3D viewport properties panel (keyboard shortcut <kbd>N</kbd>) and select the `Tool` thumbnail
 - in the `Active tool` section, change the `Orientation` parameter to __*Geometry*__

<br>

![GIF showing how to configure the 3D cursor orientation parameter](./doc_img/cursor_orientation_cfg.gif "How to configure the 3D cursor orientation parameter")

<br>

__Important note__ : Each work mode has its own 3D cursor configuration. Therefore, you'll have to change the 3D cursor _Orientation_ parameter for each relevant mode (Object mode, Edit mode, Sculpt mode, ...).

Second, since you need to switch to the 3D cursor tool to snap the cursor to a face, I strongly recommend assigning a keyboard shortcut (let's say <kbd>Q</kbd> for instance) to the 3D cursor tool, so as to speed up the workflow.
<details>
<summary>Click here if you want to see how...</summary>

![GIF showing how to assign a keyboard shortcut to a tool](./doc_img/assign_kb_shortcut.gif "How to assign a keyboard shortcut to a tool")
</details>

Finally, I encourage you to save this configuration in the startup file, so that you don't have to do it again each time you start a new project.

<br>

#### Workflow

Once you have properly configured the 3D cursor tool, switch to it, snap the cursor to the desired face (it should be aligned to the face geometry), and switch back to the tool you were working on before.

Then, use one of the following keyboard shortcuts to align the 3D View to the 3D cursor orientation :
 - Top View    : <kbd>ALT</kbd> + <kbd>NUMPAD 8</kbd>
 - Bottom View : <kbd>ALT</kbd> + <kbd>CTRL</kbd> + <kbd>NUMPAD 8</kbd>
 - Front View  : <kbd>ALT</kbd> + <kbd>NUMPAD 5</kbd>
 - Back View   : <kbd>ALT</kbd> + <kbd>CTRL</kbd> + <kbd>NUMPAD 5</kbd>
 - Right View  : <kbd>ALT</kbd> + <kbd>NUMPAD 6</kbd>
 - Left View   : <kbd>ALT</kbd> + <kbd>CTRL</kbd> + <kbd>NUMPAD 6</kbd>

<br>

![GIF showing the workflow to align the 3D View to the cursor orientation](./doc_img/workflow_align_2_cursor.gif "Workflow to align the 3D View to the cursor orientation")

<br>

Those commands are also accessible in the `View` -> `Align View` -> `Align View to Cursor` top menu of the 3D View.

<br>

![Image showing the 'Align View to Cursor' menu](./doc_img/menu_align_2_cursor.png "'Align View to Cursor' menu")
	
<br>

### Alignment to a custom transform orientation

This method is based on the Blender feature that allows to define custom transform orientations.

<br>

#### Preparation

To align the 3D View to a custom transform orientation, it must have been created beforehand.

My method is based on the _Normal_ transform orientation of a face or plane to define a _Custom_ transform orientation :

<br>

![GIF showing how to define a custom transform orientation](./doc_img/define_custom_orientation.gif "How to define a custom transform orientation")

<br>

#### Workflow

When a _Custom_ transformation orientation is active, you can use one of the following keyboard shortcuts to align the 3D View to its axes :
 - Top View    : <kbd>ALT</kbd> + <kbd>NUMPAD 7</kbd>
 - Bottom View : <kbd>ALT</kbd> + <kbd>CTRL</kbd> + <kbd>NUMPAD 7</kbd>
 - Front View  : <kbd>ALT</kbd> + <kbd>NUMPAD 1</kbd>
 - Back View   : <kbd>ALT</kbd> + <kbd>CTRL</kbd> + <kbd>NUMPAD 1</kbd>
 - Right View  : <kbd>ALT</kbd> + <kbd>NUMPAD 3</kbd>
 - Left View   : <kbd>ALT</kbd> + <kbd>CTRL</kbd> + <kbd>NUMPAD 3</kbd>

__Note__ : these commands have no effect if no _Custom_ transform orientation is active.

<br>

![GIF showing the workflow to align the 3D View to a custom transform orientation](./doc_img/workflow_align_2_custom.gif "Workflow to align the 3D View to a custom transform orientation")

<br>

Those commands are also accessible in the `View` -> `Align View` -> `Align View to Custom` top menu of the 3D View.

<br>

![Image showing the 'Align View to Custom' menu](./doc_img/menu_align_2_custom.png "'Align View to Custom' menu")

<br>

## Installation

This addon can be installed in two differents ways.

### Installation from Github

This method is recommended for Blender versions prior to 4.2 :
 - Download ZIP file of [Align2Custom V2.1.0](https://github.com/fdaubine/Align2Custom/releases/tag/V2.1.0) from the release section
 - Open Blender, then drag and drop the ZIP file onto Blender UI to install the add-on
 - Check that the `Align 2 Custom` option appears in the list of add-ons (`Edit` -> `Preferences...` -> `Add-ons`)

### Installation from Blender Extensions platform

Since 4.2 version, Blender can connect to an online platform called __Blender Extensions__ to download and install tons of add-ons. This add-on is now available on this platform. To install it, follow these instructions :
- Look for __Align2Custom__ add-on on [Blender Extensions](https://extensions.blender.org/)
- Follow the [installation instructions](https://extensions.blender.org/about/)
- In Blender, check that the `Align 2 Custom` option appears in the list of add-ons (`Edit` -> `Preferences...` -> `Add-ons`)

This method is recommended for Blender 4.2 (and newer) because add-on update can be managed easily and directly from Blender UI whenever a new version of the add-on is published.

### add-on preferences

If you prefer hard transitions or if you're facing problems (odd behaviors, performance, ...), the add-on installation panel provides an option to disable the smooth transition during the 3D View alignment.

<br>

![GIF showing the difference between hard and smooth transition](./doc_img/hard_smooth_transitions.gif "Hard vs Smooth alignment transitions")


<br>

## Changelog

### V2.1.0

Packaging optimization for publication on __Blender Extensions__ platform.
No functional evolution nor bug fixing.
No need to update to this version if you run a Blender version prior to __4.2__.

### V2.0.1

Bug correction (Issue #3) for Blender 4.0 compatibility.

### V2.0.0

New feature : align the 3D view to the 3D cursor orientation.
Improvement : smooth alignment transitions.

### V1.0.0

First stable release.
Only feature : align the 3D view to a custom orientation.

