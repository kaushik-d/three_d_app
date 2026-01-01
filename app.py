#!/usr/bin/env python3
"""
3D CAD Viewer Application
A modern, professional 3D CAD file visualization application using VTK and Trame.
Supports STL and STP file formats with interactive selection capabilities.
"""

import os
import sys

# Set VTK to use off-screen rendering before importing
os.environ.setdefault("VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN", "1")
os.environ.setdefault("DISPLAY", ":0")

import base64
import time
from pathlib import Path

from trame.app import get_server
from trame.app.file_upload import ClientFile
from trame.ui.vuetify3 import SinglePageWithDrawerLayout
from trame.widgets import vuetify3 as vuetify, vtk as vtk_widgets, html

# Try to import VTK with fallback for headless systems
try:
    import vtk
except ImportError as e:
    print(f"VTK import error: {e}")
    print("\nFor headless systems, you may need to install X11 libraries:")
    print("  sudo apt-get install libxrender1 libxtst6 libxi6")
    print("\nOr use VTK with OSMesa/EGL support")
    sys.exit(1)

import numpy as np

# Create server
server = get_server(client_type="vue3")
state, ctrl = server.state, server.controller

# Application state
state.trame__title = "3D CAD Viewer"
state.drawer_open = True
state.loaded_files = []
state.selected_file = None
state.selected_cell_id = -1
state.is_loading = False
state.error_message = ""
state.show_error = False
state.status_message = "Ready - Open STL or STP files to begin"
state.file_upload_key = 0
state.tooltip_text = ""
state.show_help = False
state.selected_files = []

# Color constants
HIGHLIGHT_COLOR = (0.2, 0.9, 0.4)  # Bright green for selection
DEFAULT_COLOR = (0.7, 0.75, 0.8)  # Light gray-blue
HOVER_COLOR = (0.5, 0.7, 0.9)  # Light blue for hover


class CADViewerApp:
    """Main CAD Viewer Application class."""

    def __init__(self):
        self.actors = {}
        self.mappers = {}
        self.polydata = {}
        self.file_info = {}
        self.selection = {
            "file_id": None,
            "cell_id": -1,
            "original_color": None,
        }

        # VTK Renderer setup
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.12, 0.12, 0.15)
        self.renderer.SetBackground2(0.22, 0.22, 0.28)
        self.renderer.GradientBackgroundOn()

        # Add subtle ambient lighting
        self.renderer.SetAmbient(0.3, 0.3, 0.3)

        # Create light
        light = vtk.vtkLight()
        light.SetPosition(1, 1, 1)
        light.SetFocalPoint(0, 0, 0)
        light.SetColor(1, 1, 1)
        light.SetIntensity(0.8)
        self.renderer.AddLight(light)

        light2 = vtk.vtkLight()
        light2.SetPosition(-1, -0.5, 0.5)
        light2.SetFocalPoint(0, 0, 0)
        light2.SetColor(0.8, 0.85, 1.0)
        light2.SetIntensity(0.4)
        self.renderer.AddLight(light2)

        self.render_window = vtk.vtkRenderWindow()
        self.render_window.AddRenderer(self.renderer)
        self.render_window.SetOffScreenRendering(1)
        self.render_window.SetSize(1200, 800)

        self.interactor = vtk.vtkRenderWindowInteractor()
        self.interactor.SetRenderWindow(self.render_window)

        # Use trackball camera style for intuitive controls
        style = vtk.vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(style)

        # Cell picker for selection
        self.picker = vtk.vtkCellPicker()
        self.picker.SetTolerance(0.005)

    def generate_file_id(self):
        """Generate a unique file ID."""
        return f"file_{int(time.time() * 1000)}"

    def load_stl_file(self, file_content):
        """Load an STL file from bytes content."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            reader = vtk.vtkSTLReader()
            reader.SetFileName(tmp_path)
            reader.Update()

            polydata = vtk.vtkPolyData()
            polydata.DeepCopy(reader.GetOutput())
            return polydata, "STL"
        finally:
            os.unlink(tmp_path)

    def load_stp_file(self, file_content, filename):
        """
        Load a STEP file. Creates tessellated geometry.
        Note: Full STEP support requires OpenCASCADE integration.
        This implementation provides a placeholder for STEP files.
        """
        import tempfile

        # Try to use VTK's OCCT reader if available
        try:
            if hasattr(vtk, "vtkOCCTReader"):
                with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as tmp:
                    tmp.write(file_content)
                    tmp_path = tmp.name
                try:
                    reader = vtk.vtkOCCTReader()
                    reader.SetFileName(tmp_path)
                    reader.Update()
                    output = reader.GetOutput()
                    if output and output.GetNumberOfCells() > 0:
                        polydata = vtk.vtkPolyData()
                        polydata.DeepCopy(output)
                        return polydata, "STP"
                finally:
                    os.unlink(tmp_path)
        except Exception:
            pass

        # Fallback: Create a sample geometry for demonstration
        # In production, integrate with pythonOCC or FreeCAD for full STEP support
        source = vtk.vtkCylinderSource()
        source.SetRadius(25)
        source.SetHeight(50)
        source.SetResolution(36)
        source.Update()

        triangulator = vtk.vtkTriangleFilter()
        triangulator.SetInputConnection(source.GetOutputPort())
        triangulator.Update()

        polydata = vtk.vtkPolyData()
        polydata.DeepCopy(triangulator.GetOutput())

        state.status_message = (
            "Note: STEP shown as placeholder. Full STEP support requires OpenCASCADE."
        )
        return polydata, "STP"

    def setup_cell_colors(self, polydata):
        """Initialize cell colors array for the polydata."""
        num_cells = polydata.GetNumberOfCells()

        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(3)
        colors.SetNumberOfTuples(num_cells)
        colors.SetName("CellColors")

        default_rgb = [int(c * 255) for c in DEFAULT_COLOR]
        for i in range(num_cells):
            colors.SetTuple(i, default_rgb)

        polydata.GetCellData().SetScalars(colors)
        return colors

    def add_file(self, polydata, filename, file_type):
        """Add a file's geometry to the scene."""
        file_id = self.generate_file_id()

        # Setup cell colors
        self.setup_cell_colors(polydata)

        # Create mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        mapper.ScalarVisibilityOn()
        mapper.SetScalarModeToUseCellData()
        mapper.SelectColorArray("CellColors")

        # Create actor
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetSpecular(0.4)
        actor.GetProperty().SetSpecularPower(30)
        actor.GetProperty().SetAmbient(0.2)
        actor.GetProperty().SetDiffuse(0.8)
        actor.GetProperty().SetInterpolationToPhong()

        # Store references
        self.actors[file_id] = actor
        self.mappers[file_id] = mapper
        self.polydata[file_id] = polydata
        self.file_info[file_id] = {
            "filename": filename,
            "type": file_type,
            "num_cells": polydata.GetNumberOfCells(),
            "num_points": polydata.GetNumberOfPoints(),
        }

        # Add to renderer
        self.renderer.AddActor(actor)

        return file_id

    def remove_file(self, file_id):
        """Remove a file from the scene."""
        if file_id not in self.actors:
            return False

        # Clear selection if this file was selected
        if self.selection["file_id"] == file_id:
            self.clear_selection()

        # Remove actor from renderer
        self.renderer.RemoveActor(self.actors[file_id])

        # Clean up references
        del self.actors[file_id]
        del self.mappers[file_id]
        del self.polydata[file_id]
        del self.file_info[file_id]

        return True

    def highlight_cell(self, file_id, cell_id):
        """Highlight a specific cell."""
        # Clear previous selection
        self.clear_selection()

        polydata = self.polydata.get(file_id)
        if not polydata:
            return False

        colors = polydata.GetCellData().GetScalars("CellColors")
        if not colors or cell_id < 0 or cell_id >= colors.GetNumberOfTuples():
            return False

        # Store original color and selection info
        self.selection["file_id"] = file_id
        self.selection["cell_id"] = cell_id
        self.selection["original_color"] = list(colors.GetTuple(cell_id))

        # Set highlight color
        highlight_rgb = [int(c * 255) for c in HIGHLIGHT_COLOR]
        colors.SetTuple(cell_id, highlight_rgb)
        polydata.Modified()

        return True

    def clear_selection(self):
        """Clear the current selection."""
        if self.selection["file_id"] and self.selection["cell_id"] >= 0:
            polydata = self.polydata.get(self.selection["file_id"])
            if polydata and self.selection["original_color"]:
                colors = polydata.GetCellData().GetScalars("CellColors")
                if colors:
                    colors.SetTuple(
                        self.selection["cell_id"], self.selection["original_color"]
                    )
                    polydata.Modified()

        self.selection["file_id"] = None
        self.selection["cell_id"] = -1
        self.selection["original_color"] = None

    def pick_cell(self, x, y):
        """Perform cell picking at screen coordinates."""
        self.picker.Pick(x, y, 0, self.renderer)
        cell_id = self.picker.GetCellId()
        actor = self.picker.GetActor()

        if cell_id >= 0 and actor:
            # Find which file this actor belongs to
            for file_id, stored_actor in self.actors.items():
                if stored_actor is actor:
                    return file_id, cell_id

        return None, -1

    def set_file_highlight(self, file_id, highlight=True):
        """Toggle edge highlighting for a file."""
        actor = self.actors.get(file_id)
        if actor:
            if highlight:
                actor.GetProperty().SetEdgeVisibility(1)
                actor.GetProperty().SetEdgeColor(0.3, 0.6, 1.0)
                actor.GetProperty().SetLineWidth(1.5)
            else:
                actor.GetProperty().SetEdgeVisibility(0)

    def toggle_wireframe(self, file_id):
        """Toggle wireframe display for a file."""
        actor = self.actors.get(file_id)
        if actor:
            current = actor.GetProperty().GetRepresentation()
            if current == vtk.VTK_SURFACE:
                actor.GetProperty().SetRepresentationToWireframe()
                return True
            else:
                actor.GetProperty().SetRepresentationToSurface()
                return False
        return None

    def reset_camera(self):
        """Reset camera to fit all geometry."""
        self.renderer.ResetCamera()
        camera = self.renderer.GetActiveCamera()
        camera.Zoom(0.9)


# Create application instance
app = CADViewerApp()


def process_file_content(filename, content):
    """Process file content and add to scene."""
    ext = Path(filename).suffix.lower()

    try:
        if ext == ".stl":
            polydata, file_type = app.load_stl_file(content)
        elif ext in [".stp", ".step"]:
            polydata, file_type = app.load_stp_file(content, filename)
        else:
            state.error_message = f"Unsupported format: {ext}. Use .stl or .stp files."
            state.show_error = True
            return False

        if polydata.GetNumberOfCells() == 0:
            state.error_message = f"No geometry found in {filename}"
            state.show_error = True
            return False

        # Add to scene
        file_id = app.add_file(polydata, filename, file_type)

        # Update file list in state
        file_info = {
            "id": file_id,
            "name": filename,
            "type": file_type,
            "cells": polydata.GetNumberOfCells(),
            "points": polydata.GetNumberOfPoints(),
        }
        state.loaded_files = state.loaded_files + [file_info]
        return True

    except Exception as e:
        state.error_message = f"Error loading {filename}: {str(e)}"
        state.show_error = True
        return False


# File upload handler using trame's ClientFile - triggered by state change
@state.change("selected_files")
def on_selected_files_change(selected_files, **kwargs):
    """Handle file selection from VFileInput using trame's ClientFile."""
    if not selected_files:
        return

    try:
        state.is_loading = True
        loaded_count = 0

        files = selected_files if isinstance(selected_files, list) else [selected_files]

        for file in files:
            if not file:
                continue

            file_helper = ClientFile(file)
            filename = file_helper.name
            state.status_message = f"Loading {filename}..."
            ctrl.view_update()

            # Get file content as bytes
            content = file_helper.content

            if process_file_content(filename, content):
                loaded_count += 1

        if loaded_count > 0:
            app.reset_camera()
            state.status_message = f"Loaded {loaded_count} file(s) successfully"

        ctrl.view_update()

    except Exception as e:
        state.error_message = f"Error loading files: {str(e)}"
        state.show_error = True
    finally:
        state.is_loading = False
        state.selected_files = []  # Clear the selection


@ctrl.add("remove_file")
def remove_file(file_id):
    """Remove a file from the scene."""
    if app.remove_file(file_id):
        state.loaded_files = [f for f in state.loaded_files if f["id"] != file_id]
        state.status_message = "File removed"
        state.selected_cell_id = -1
        app.reset_camera()
        ctrl.view_update()


@ctrl.add("select_file_in_tree")
def select_file_in_tree(file_id):
    """Handle file selection in the tree view."""
    # Clear previous highlights
    for fid in app.actors:
        app.set_file_highlight(fid, False)

    # Highlight selected file
    app.set_file_highlight(file_id, True)
    state.selected_file = file_id
    ctrl.view_update()


@ctrl.add("toggle_wireframe")
def toggle_wireframe(file_id):
    """Toggle wireframe mode for a file."""
    result = app.toggle_wireframe(file_id)
    if result is not None:
        state.status_message = f"{'Wireframe' if result else 'Surface'} mode"
        ctrl.view_update()


@ctrl.add("clear_all")
def clear_all():
    """Remove all files from the scene."""
    for file_id in list(app.actors.keys()):
        app.remove_file(file_id)

    state.loaded_files = []
    state.selected_file = None
    state.selected_cell_id = -1
    state.status_message = "All files cleared"
    ctrl.view_update()


@ctrl.add("reset_view")
def reset_view():
    """Reset the camera view."""
    app.reset_camera()
    state.status_message = "View reset"
    ctrl.view_update()


@ctrl.add("on_left_click")
def on_left_click(event_data):
    """Handle left mouse button click for selection."""
    if not event_data:
        return

    x = event_data.get("x", 0)
    y = event_data.get("y", 0)

    file_id, cell_id = app.pick_cell(x, y)

    if file_id and cell_id >= 0:
        if app.highlight_cell(file_id, cell_id):
            state.selected_cell_id = cell_id
            state.selected_file = file_id
            file_info = app.file_info.get(file_id, {})
            file_type = file_info.get("type", "")
            element_type = "triangle" if file_type == "STL" else "surface"
            state.status_message = f"Selected {element_type} (Cell ID: {cell_id})"
            ctrl.view_update()


@ctrl.add("on_right_click")
def on_right_click(event_data):
    """Handle right mouse button click for deselection."""
    app.clear_selection()
    state.selected_cell_id = -1
    state.status_message = "Selection cleared"
    ctrl.view_update()


@ctrl.add("toggle_help")
def toggle_help():
    """Toggle help dialog."""
    state.show_help = not state.show_help


# Build the UI
with SinglePageWithDrawerLayout(server) as layout:
    layout.title.set_text("3D CAD Viewer")

    # Custom CSS for modern styling
    html.Style(
        """
        :root {
            --primary-dark: #1a1a2e;
            --secondary-dark: #16213e;
            --accent-blue: #0f4c75;
            --highlight-blue: #3282b8;
            --text-light: #e8e8e8;
        }

        .v-application {
            font-family: 'Inter', 'Roboto', 'Segoe UI', sans-serif;
        }

        .app-toolbar {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #1a1a2e 100%) !important;
            border-bottom: 1px solid rgba(50, 130, 184, 0.3);
        }

        .drawer-content {
            background: linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%) !important;
        }

        .file-tree-item {
            border-radius: 8px;
            margin: 4px 8px;
            transition: all 0.2s ease;
            border-left: 3px solid transparent;
        }

        .file-tree-item:hover {
            background-color: rgba(50, 130, 184, 0.15) !important;
        }

        .file-tree-item.selected {
            background-color: rgba(50, 130, 184, 0.25) !important;
            border-left: 3px solid #3282b8;
        }

        .vtk-container {
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(50, 130, 184, 0.2);
        }

        .status-bar {
            background: linear-gradient(90deg, #0f0f1a 0%, #1a1a2e 50%, #0f0f1a 100%) !important;
            border-top: 1px solid rgba(50, 130, 184, 0.3);
        }

        .info-chip {
            font-size: 10px !important;
            height: 20px !important;
        }

        .selection-panel {
            background: linear-gradient(135deg, rgba(50, 130, 184, 0.15) 0%, rgba(50, 130, 184, 0.05) 100%);
            border: 1px solid rgba(50, 130, 184, 0.3);
            border-radius: 12px;
        }

        .help-panel {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .upload-btn {
            background: linear-gradient(135deg, #3282b8 0%, #0f4c75 100%) !important;
        }

        .upload-btn:hover {
            background: linear-gradient(135deg, #4a9fd4 0%, #1a6a9e 100%) !important;
        }

        .action-btn:hover {
            background-color: rgba(50, 130, 184, 0.2) !important;
        }

        .empty-state {
            opacity: 0.6;
        }

        .empty-state-icon {
            font-size: 48px !important;
            opacity: 0.4;
        }
    """
    )

    # Toolbar
    with layout.toolbar as toolbar:
        toolbar.classes = "app-toolbar"

        with vuetify.VBtn(
            icon=True,
            click="drawer_open = !drawer_open",
            variant="text",
            classes="action-btn",
        ):
            vuetify.VIcon("mdi-menu")

        with html.Div(classes="d-flex align-center ml-3"):
            vuetify.VIcon("mdi-cube-scan", color="primary", classes="mr-2")
            vuetify.VToolbarTitle("3D CAD Viewer")

        vuetify.VSpacer()

        # File upload using VFileInput
        vuetify.VFileInput(
            v_model=("selected_files", []),
            accept=".stl,.stp,.step",
            multiple=True,
            label="Open CAD Files",
            prepend_icon="mdi-folder-open-outline",
            density="compact",
            variant="outlined",
            hide_details=True,
            clearable=True,
            classes="mr-2",
            style="max-width: 300px;",
        )

        vuetify.VDivider(vertical=True, classes="mx-2", style="opacity: 0.3;")

        with vuetify.VBtn(
            icon=True,
            click=ctrl.reset_view,
            variant="text",
            classes="action-btn",
            title="Reset Camera View",
        ):
            vuetify.VIcon("mdi-camera-retake-outline")

        with vuetify.VBtn(
            icon=True,
            click=ctrl.toggle_help,
            variant="text",
            classes="action-btn",
            title="Help",
        ):
            vuetify.VIcon("mdi-help-circle-outline")

        with vuetify.VBtn(
            icon=True,
            click=ctrl.clear_all,
            variant="text",
            classes="action-btn",
            title="Clear All Files",
            color="error",
        ):
            vuetify.VIcon("mdi-delete-sweep-outline")

    # Drawer (File Tree Sidebar)
    with layout.drawer as drawer:
        drawer.classes = "drawer-content"
        drawer.v_model = ("drawer_open",)
        drawer.width = 340

        with vuetify.VCard(flat=True, color="transparent", classes="ma-3"):
            with html.Div(classes="d-flex align-center pa-2"):
                vuetify.VIcon("mdi-file-tree-outline", color="primary", classes="mr-2")
                html.Span("Loaded Files", classes="text-subtitle-1 font-weight-medium")
                vuetify.VSpacer()
                vuetify.VChip(
                    "{{ loaded_files.length }}",
                    size="x-small",
                    color="primary",
                    variant="tonal",
                )

            vuetify.VDivider(classes="mt-2")

            # File list
            with vuetify.VList(
                density="compact",
                nav=True,
                bg_color="transparent",
                classes="mt-2",
            ):
                with vuetify.VListItem(
                    v_for="file in loaded_files",
                    key="file.id",
                    click=(ctrl.select_file_in_tree, "[file.id]"),
                    classes="file-tree-item",
                    v_bind="{class: {'selected': selected_file === file.id}}",
                ):
                    with vuetify.Template(v_slot_prepend=True):
                        vuetify.VIcon(
                            "{{ file.type === 'STL' ? 'mdi-triangle-outline' : 'mdi-shape-outline' }}",
                            color="primary",
                            size="small",
                        )

                    with vuetify.VListItemTitle(classes="font-weight-medium"):
                        html.Span("{{ file.name }}")

                    with vuetify.VListItemSubtitle(
                        classes="d-flex align-center mt-1 flex-wrap ga-1"
                    ):
                        vuetify.VChip(
                            "{{ file.type }}",
                            size="x-small",
                            color="info",
                            variant="outlined",
                            classes="info-chip",
                        )
                        vuetify.VChip(
                            "{{ file.cells.toLocaleString() }} cells",
                            size="x-small",
                            color="success",
                            variant="outlined",
                            classes="info-chip",
                        )
                        vuetify.VChip(
                            "{{ file.points.toLocaleString() }} pts",
                            size="x-small",
                            color="warning",
                            variant="outlined",
                            classes="info-chip",
                        )

                    with vuetify.Template(v_slot_append=True):
                        with html.Div(classes="d-flex"):
                            with vuetify.VBtn(
                                icon=True,
                                size="x-small",
                                variant="text",
                                click=(ctrl.toggle_wireframe, "[file.id]"),
                                click_stop=True,
                                title="Toggle Wireframe",
                            ):
                                vuetify.VIcon("mdi-grid", size="small")

                            with vuetify.VBtn(
                                icon=True,
                                size="x-small",
                                variant="text",
                                color="error",
                                click=(ctrl.remove_file, "[file.id]"),
                                click_stop=True,
                                title="Remove File",
                            ):
                                vuetify.VIcon("mdi-close", size="small")

                # Empty state
                with vuetify.VListItem(
                    v_if="loaded_files.length === 0",
                    classes="empty-state",
                ):
                    with html.Div(classes="text-center py-8 w-100"):
                        vuetify.VIcon(
                            "mdi-cube-off-outline",
                            classes="empty-state-icon mb-4",
                        )
                        html.Div("No files loaded", classes="text-subtitle-1 mb-1")
                        html.Div(
                            "Click 'Open Files' to load STL or STP files",
                            classes="text-caption",
                        )

        vuetify.VSpacer()

        # Selection info panel
        with vuetify.VCard(
            v_if="selected_cell_id >= 0",
            flat=True,
            classes="ma-3 pa-4 selection-panel",
        ):
            with html.Div(classes="d-flex align-center mb-3"):
                vuetify.VIcon(
                    "mdi-cursor-default-click",
                    color="success",
                    size="small",
                    classes="mr-2",
                )
                html.Span("Selection", classes="text-subtitle-2 font-weight-medium")

            with html.Div(classes="d-flex flex-column ga-2"):
                with html.Div(classes="d-flex justify-space-between"):
                    html.Span("Cell ID:", classes="text-caption text-grey")
                    html.Span(
                        "{{ selected_cell_id }}",
                        classes="font-weight-bold text-success",
                    )

        # Help panel
        with vuetify.VCard(
            flat=True,
            classes="ma-3 pa-3 help-panel",
        ):
            html.Div(
                "Mouse Controls",
                classes="text-caption font-weight-medium mb-2 text-grey-lighten-1",
            )

            with html.Div(classes="d-flex flex-column ga-1"):
                with html.Div(classes="d-flex align-center"):
                    vuetify.VIcon("mdi-mouse", size="x-small", classes="mr-2 text-grey")
                    html.Span(
                        "Left click: Select triangle/surface",
                        classes="text-caption text-grey",
                    )

                with html.Div(classes="d-flex align-center"):
                    vuetify.VIcon("mdi-mouse", size="x-small", classes="mr-2 text-grey")
                    html.Span(
                        "Right click: Clear selection", classes="text-caption text-grey"
                    )

                with html.Div(classes="d-flex align-center"):
                    vuetify.VIcon(
                        "mdi-rotate-3d-variant",
                        size="x-small",
                        classes="mr-2 text-grey",
                    )
                    html.Span(
                        "Left drag: Rotate view", classes="text-caption text-grey"
                    )

                with html.Div(classes="d-flex align-center"):
                    vuetify.VIcon(
                        "mdi-arrow-all", size="x-small", classes="mr-2 text-grey"
                    )
                    html.Span(
                        "Middle drag / Shift+drag: Pan",
                        classes="text-caption text-grey",
                    )

                with html.Div(classes="d-flex align-center"):
                    vuetify.VIcon(
                        "mdi-magnify", size="x-small", classes="mr-2 text-grey"
                    )
                    html.Span("Scroll: Zoom in/out", classes="text-caption text-grey")

    # Main content (3D View)
    with layout.content:
        with vuetify.VContainer(
            fluid=True, classes="fill-height pa-4", style="background: #0a0a0f;"
        ):
            with vuetify.VCard(
                classes="fill-height vtk-container",
                color="#1a1a2e",
                flat=True,
            ):
                # VTK View with picking support
                view = vtk_widgets.VtkRemoteView(
                    app.render_window,
                    interactive_ratio=1,
                    classes="fill-height",
                )
                ctrl.view_update = view.update
                ctrl.view_reset_camera = view.reset_camera

                # JavaScript for handling mouse clicks with picking
                html.Div(
                    style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; pointer-events: none;",
                    id="pick-overlay",
                )

    # Attach click handlers to the VTK view container
    layout.root.add_child(
        html.Script(
            """
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                // VTK container click handlers
                var vtkContainer = document.querySelector('.vtk-container');
                if (vtkContainer) {
                    vtkContainer.addEventListener('click', function(event) {
                        if (event.button === 0) {
                            var rect = vtkContainer.getBoundingClientRect();
                            var x = event.clientX - rect.left;
                            var y = rect.height - (event.clientY - rect.top);
                            if (window.trame) {
                                window.trame.trigger('on_left_click', {x: x, y: y});
                            }
                        }
                    });

                    vtkContainer.addEventListener('contextmenu', function(event) {
                        event.preventDefault();
                        var rect = vtkContainer.getBoundingClientRect();
                        var x = event.clientX - rect.left;
                        var y = rect.height - (event.clientY - rect.top);
                        if (window.trame) {
                            window.trame.trigger('on_right_click', {x: x, y: y});
                        }
                    });
                }
            }, 1000);
        });
    """
        )
    )

    # Status bar
    with layout.footer as footer:
        footer.classes = "status-bar px-4 py-2"
        footer.app = True
        footer.height = 40

        with vuetify.VRow(no_gutters=True, align="center", classes="fill-height"):
            with vuetify.VCol(cols="auto", classes="d-flex align-center"):
                vuetify.VIcon(
                    "mdi-check-circle",
                    color="success",
                    size="small",
                    classes="mr-2",
                    v_if="!is_loading && !show_error",
                )
                vuetify.VIcon(
                    "mdi-alert-circle",
                    color="error",
                    size="small",
                    classes="mr-2",
                    v_if="show_error",
                )
                vuetify.VProgressCircular(
                    indeterminate=True,
                    size=16,
                    width=2,
                    color="primary",
                    classes="mr-2",
                    v_if="is_loading",
                )
                html.Span("{{ status_message }}", classes="text-caption")

            vuetify.VSpacer()

            with vuetify.VCol(cols="auto", classes="d-flex align-center ga-2"):
                vuetify.VChip(
                    v_if="loaded_files.length > 0",
                    size="x-small",
                    variant="tonal",
                    color="primary",
                    children=["{{ loaded_files.length }} file(s)"],
                )

                vuetify.VChip(
                    v_if="selected_cell_id >= 0",
                    size="x-small",
                    variant="tonal",
                    color="success",
                    children=["Cell {{ selected_cell_id }}"],
                )

    # Error snackbar
    with vuetify.VSnackbar(
        v_model=("show_error",),
        color="error",
        timeout=5000,
        location="top",
    ):
        with html.Div(classes="d-flex align-center"):
            vuetify.VIcon("mdi-alert-circle-outline", classes="mr-2")
            html.Span("{{ error_message }}")

    # Help dialog
    with vuetify.VDialog(
        v_model=("show_help",),
        max_width=500,
    ):
        with vuetify.VCard(color="#1a1a2e"):
            with vuetify.VCardTitle(classes="d-flex align-center"):
                vuetify.VIcon("mdi-help-circle-outline", classes="mr-2")
                html.Span("Help - 3D CAD Viewer")
                vuetify.VSpacer()
                with vuetify.VBtn(
                    icon=True,
                    variant="text",
                    click="show_help = false",
                ):
                    vuetify.VIcon("mdi-close")

            vuetify.VDivider()

            with vuetify.VCardText():
                html.H4("Supported Formats", classes="mb-2")
                html.P("- STL (Stereolithography) files", classes="text-caption mb-1")
                html.P(
                    "- STP/STEP (Standard for Exchange of Product Data) files*",
                    classes="text-caption mb-3",
                )

                html.H4("File Operations", classes="mb-2")
                html.P(
                    "- Open Files: Load one or multiple CAD files",
                    classes="text-caption mb-1",
                )
                html.P(
                    "- Remove: Click the X button on a file to remove it",
                    classes="text-caption mb-1",
                )
                html.P(
                    "- Toggle Wireframe: Click the grid icon to switch views",
                    classes="text-caption mb-3",
                )

                html.H4("Selection", classes="mb-2")
                html.P(
                    "- Left Click: Select a triangle (STL) or surface (STP)",
                    classes="text-caption mb-1",
                )
                html.P(
                    "- Right Click: Clear the current selection",
                    classes="text-caption mb-3",
                )

                html.H4("Camera Controls", classes="mb-2")
                html.P(
                    "- Left Mouse Drag: Rotate the view", classes="text-caption mb-1"
                )
                html.P("- Middle Mouse Drag: Pan the view", classes="text-caption mb-1")
                html.P("- Mouse Wheel: Zoom in/out", classes="text-caption mb-1")
                html.P("- Shift + Left Drag: Pan the view", classes="text-caption mb-3")

                with vuetify.VAlert(
                    type="info",
                    variant="tonal",
                    density="compact",
                    classes="mt-4",
                ):
                    html.Span(
                        "* Full STEP support requires OpenCASCADE integration. "
                        "STEP files are currently shown as placeholder geometry.",
                        classes="text-caption",
                    )


# Main entry point
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  3D CAD Viewer - Starting Application")
    print("=" * 60)
    print("\n  Open your browser at: http://localhost:8080")
    print("  Supported formats: STL, STP/STEP")
    print("\n  Controls:")
    print("    - Left Click: Select triangle/surface")
    print("    - Right Click: Clear selection")
    print("    - Drag: Rotate view")
    print("    - Shift+Drag: Pan view")
    print("    - Scroll: Zoom")
    print("\n" + "=" * 60 + "\n")

    server.start()
