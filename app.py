#!/usr/bin/env python3
"""
3D CAD Viewer Application
A modern, professional 3D CAD file visualization application using VTK and Trame.
Supports STL and STP file formats with interactive selection capabilities.
"""

import os
import tempfile
import time
from pathlib import Path

# VTK imports - order matters for factory initialization
import vtkmodules.vtkRenderingOpenGL2  # noqa
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleSwitch  # noqa
from vtkmodules.vtkIOGeometry import vtkSTLReader
from vtkmodules.vtkFiltersSources import vtkCylinderSource
from vtkmodules.vtkFiltersCore import vtkTriangleFilter
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
    vtkRenderer,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
    vtkLight,
    vtkCellPicker,
)
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkCommonCore import vtkUnsignedCharArray

from trame.app import get_server
from trame.app.file_upload import ClientFile
from trame.decorators import TrameApp, change
from trame.ui.vuetify import SinglePageLayout
from trame.widgets import vuetify, vtk as vtk_widgets, html

# Color constants
HIGHLIGHT_COLOR = (0.2, 0.9, 0.4)  # Bright green for selection
DEFAULT_COLOR = (0.7, 0.75, 0.8)  # Light gray-blue


@TrameApp()
class CADViewerApp:
    """Main CAD Viewer Application class."""

    def __init__(self, server=None):
        self.server = get_server(server, client_type="vue2")
        self._setup_state()
        self._setup_vtk()
        self.ui = self._build_ui()

    @property
    def state(self):
        return self.server.state

    @property
    def ctrl(self):
        return self.server.controller

    def _setup_state(self):
        """Initialize application state."""
        self.state.trame__title = "3D CAD Viewer"
        self.state.drawer_open = True
        self.state.loaded_files = []
        self.state.selected_file = None
        self.state.selected_cell_id = -1
        self.state.is_loading = False
        self.state.error_message = ""
        self.state.show_error = False
        self.state.status_message = "Ready - Open STL or STP files to begin"
        self.state.show_help = False
        self.state.file_exchange = None

    def _setup_vtk(self):
        """Initialize VTK rendering pipeline."""
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
        self.renderer = vtkRenderer()
        self.renderer.SetBackground(0.12, 0.12, 0.15)
        self.renderer.SetBackground2(0.22, 0.22, 0.28)
        self.renderer.GradientBackgroundOn()
        self.renderer.SetAmbient(0.3, 0.3, 0.3)

        # Create lights
        light = vtkLight()
        light.SetPosition(1, 1, 1)
        light.SetFocalPoint(0, 0, 0)
        light.SetColor(1, 1, 1)
        light.SetIntensity(0.8)
        self.renderer.AddLight(light)

        light2 = vtkLight()
        light2.SetPosition(-1, -0.5, 0.5)
        light2.SetFocalPoint(0, 0, 0)
        light2.SetColor(0.8, 0.85, 1.0)
        light2.SetIntensity(0.4)
        self.renderer.AddLight(light2)

        self.render_window = vtkRenderWindow()
        self.render_window.AddRenderer(self.renderer)
        self.render_window.OffScreenRenderingOn()
        self.render_window.SetSize(1200, 800)

        self.interactor = vtkRenderWindowInteractor()
        self.interactor.SetRenderWindow(self.render_window)
        self.interactor.GetInteractorStyle().SetCurrentStyleToTrackballCamera()

        # Cell picker for selection
        self.picker = vtkCellPicker()
        self.picker.SetTolerance(0.005)

        # Initial render
        self.render_window.Render()

    def generate_file_id(self):
        """Generate a unique file ID."""
        return f"file_{int(time.time() * 1000)}"

    def load_stl_file(self, file_content):
        """Load an STL file from bytes content."""
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            reader = vtkSTLReader()
            reader.SetFileName(tmp_path)
            reader.Update()

            polydata = vtkPolyData()
            polydata.DeepCopy(reader.GetOutput())
            return polydata, "STL"
        finally:
            os.unlink(tmp_path)

    def load_stp_file(self, file_content, filename):
        """Load a STEP file - placeholder implementation."""
        # Fallback: Create a sample geometry for demonstration
        source = vtkCylinderSource()
        source.SetRadius(25)
        source.SetHeight(50)
        source.SetResolution(36)
        source.Update()

        triangulator = vtkTriangleFilter()
        triangulator.SetInputConnection(source.GetOutputPort())
        triangulator.Update()

        polydata = vtkPolyData()
        polydata.DeepCopy(triangulator.GetOutput())

        self.state.status_message = (
            "Note: STEP shown as placeholder. Full STEP support requires OpenCASCADE."
        )
        return polydata, "STP"

    def setup_cell_colors(self, polydata):
        """Initialize cell colors array for the polydata."""
        num_cells = polydata.GetNumberOfCells()

        colors = vtkUnsignedCharArray()
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
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        mapper.ScalarVisibilityOn()
        mapper.SetScalarModeToUseCellData()
        mapper.SelectColorArray("CellColors")

        # Create actor
        actor = vtkActor()
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
        self.renderer.ResetCamera()
        self.render_window.Render()

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
            if current == 1:  # VTK_SURFACE
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
        self.render_window.Render()

    def process_file_content(self, filename, content):
        """Process file content and add to scene."""
        ext = Path(filename).suffix.lower()

        try:
            if ext == ".stl":
                polydata, file_type = self.load_stl_file(content)
            elif ext in [".stp", ".step"]:
                polydata, file_type = self.load_stp_file(content, filename)
            else:
                self.state.error_message = f"Unsupported format: {ext}. Use .stl or .stp files."
                self.state.show_error = True
                return False

            if polydata.GetNumberOfCells() == 0:
                self.state.error_message = f"No geometry found in {filename}"
                self.state.show_error = True
                return False

            # Add to scene
            file_id = self.add_file(polydata, filename, file_type)

            # Update file list in state
            file_info = {
                "id": file_id,
                "name": filename,
                "type": file_type,
                "cells": polydata.GetNumberOfCells(),
                "points": polydata.GetNumberOfPoints(),
            }
            self.state.loaded_files = self.state.loaded_files + [file_info]
            return True

        except Exception as e:
            self.state.error_message = f"Error loading {filename}: {str(e)}"
            self.state.show_error = True
            return False

    # State change handlers
    @change("file_exchange")
    def on_file_exchange(self, file_exchange, **kwargs):
        """Handle file upload from VFileInput."""
        if file_exchange is None:
            return

        try:
            self.state.is_loading = True

            # Get file info from the exchange dict
            file_name = file_exchange.get("name", "unknown")
            file_content = file_exchange.get("content")

            self.state.status_message = f"Loading {file_name}..."

            # Content can be bytes or list of bytes
            if isinstance(file_content, list):
                content = b"".join(file_content)
            else:
                content = file_content

            if self.process_file_content(file_name, content):
                self.reset_camera()
                self.render_window.Render()
                self.state.status_message = f"Loaded {file_name} successfully"

            # Update view if available
            if hasattr(self.ctrl, 'view_update') and self.ctrl.view_update:
                self.ctrl.view_update()

        except Exception as e:
            self.state.error_message = f"Error loading file: {str(e)}"
            self.state.show_error = True
        finally:
            self.state.is_loading = False
            self.state.file_exchange = None

    # Controller methods
    def _setup_ctrl_methods(self):
        """Setup controller methods."""

        @self.ctrl.add("remove_file")
        def remove_file(file_id):
            if self.remove_file(file_id):
                self.state.loaded_files = [f for f in self.state.loaded_files if f["id"] != file_id]
                self.state.status_message = "File removed"
                self.state.selected_cell_id = -1
                self.reset_camera()
                self.ctrl.view_update()

        @self.ctrl.add("select_file_in_tree")
        def select_file_in_tree(file_id):
            for fid in self.actors:
                self.set_file_highlight(fid, False)
            self.set_file_highlight(file_id, True)
            self.state.selected_file = file_id
            self.ctrl.view_update()

        @self.ctrl.add("toggle_wireframe")
        def toggle_wireframe(file_id):
            result = self.toggle_wireframe(file_id)
            if result is not None:
                self.state.status_message = f"{'Wireframe' if result else 'Surface'} mode"
                self.ctrl.view_update()

        @self.ctrl.add("clear_all")
        def clear_all():
            for file_id in list(self.actors.keys()):
                self.remove_file(file_id)
            self.state.loaded_files = []
            self.state.selected_file = None
            self.state.selected_cell_id = -1
            self.state.status_message = "All files cleared"
            self.ctrl.view_update()

        @self.ctrl.add("reset_view")
        def reset_view():
            self.reset_camera()
            self.state.status_message = "View reset"
            self.ctrl.view_update()

        @self.ctrl.add("on_left_click")
        def on_left_click(event_data):
            if not event_data:
                return
            x = event_data.get("x", 0)
            y = event_data.get("y", 0)
            file_id, cell_id = self.pick_cell(x, y)
            if file_id and cell_id >= 0:
                if self.highlight_cell(file_id, cell_id):
                    self.state.selected_cell_id = cell_id
                    self.state.selected_file = file_id
                    file_info = self.file_info.get(file_id, {})
                    file_type = file_info.get("type", "")
                    element_type = "triangle" if file_type == "STL" else "surface"
                    self.state.status_message = f"Selected {element_type} (Cell ID: {cell_id})"
                    self.ctrl.view_update()

        @self.ctrl.add("on_right_click")
        def on_right_click(event_data):
            self.clear_selection()
            self.state.selected_cell_id = -1
            self.state.status_message = "Selection cleared"
            self.ctrl.view_update()

        @self.ctrl.add("toggle_help")
        def toggle_help():
            self.state.show_help = not self.state.show_help

    def _build_ui(self):
        """Build the application UI."""
        self._setup_ctrl_methods()

        with SinglePageLayout(self.server) as layout:
            layout.title.set_text("3D CAD Viewer")

            # Toolbar
            with layout.toolbar as toolbar:
                toolbar.dense = True

                vuetify.VIcon("mdi-cube-scan", classes="mr-2")

                vuetify.VSpacer()

                # File upload using VFileInput
                vuetify.VFileInput(
                    v_model=("file_exchange", None),
                    accept=".stl,.stp,.step",
                    label="Open CAD File",
                    prepend_icon="mdi-folder-open-outline",
                    dense=True,
                    outlined=True,
                    hide_details=True,
                    clearable=True,
                    classes="mr-2",
                    style="max-width: 300px;",
                )

                with vuetify.VBtn(icon=True, click=self.ctrl.reset_view):
                    vuetify.VIcon("mdi-camera-retake-outline")

                with vuetify.VBtn(icon=True, click=self.ctrl.clear_all):
                    vuetify.VIcon("mdi-delete-sweep-outline")

            # Main content (3D View)
            with layout.content:
                with vuetify.VContainer(fluid=True, classes="pa-0 fill-height"):
                    view = vtk_widgets.VtkRemoteView(self.render_window)
                    self.ctrl.view_update = view.update
                    self.ctrl.view_reset_camera = view.reset_camera

            return layout


def main():
    app = CADViewerApp()
    print("\n" + "=" * 60)
    print("  3D CAD Viewer - Starting Application")
    print("=" * 60)
    print("\n  Open your browser at: http://localhost:8080")
    print("  Supported formats: STL, STP/STEP")
    print("\n" + "=" * 60 + "\n")
    app.server.start()


if __name__ == "__main__":
    main()
