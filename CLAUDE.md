# CLAUDE.md - Project Guidelines for 3D CAD Viewer

## Project Overview
A 3D CAD file visualization application using VTK and Trame. Supports STL and STP file formats with interactive viewing capabilities.

## Key Learnings

### Trame Framework

#### Vue Version Compatibility
- **Use Vue2 with `trame.ui.vuetify`** - Vue3/Vuetify3 has different APIs and may have rendering issues
- Server setup: `get_server(server, client_type="vue2")`
- Import from: `from trame.ui.vuetify import SinglePageLayout`
- Widgets: `from trame.widgets import vuetify, vtk as vtk_widgets, html`

#### Class-Based Application Structure
Use the `@TrameApp()` decorator for proper trame applications:
```python
from trame.decorators import TrameApp, change

@TrameApp()
class MyApp:
    def __init__(self, server=None):
        self.server = get_server(server, client_type="vue2")
        # setup code...
        self.ui = self._build_ui()

    @property
    def state(self):
        return self.server.state

    @property
    def ctrl(self):
        return self.server.controller

    @change("state_variable")
    def on_state_change(self, state_variable, **kwargs):
        # Handle state changes
        pass
```

#### File Upload Pattern
Use `VFileInput` with `v_model` bound to a state variable:
```python
vuetify.VFileInput(
    v_model=("file_exchange", None),  # Use None as default, not []
    accept=".stl,.stp,.step",
    # ... other props
)

@change("file_exchange")
def on_file_exchange(self, file_exchange, **kwargs):
    if file_exchange is None:
        return
    file_name = file_exchange.get("name")
    file_content = file_exchange.get("content")  # bytes or list of bytes
    # Content may be list of bytes chunks
    if isinstance(file_content, list):
        content = b"".join(file_content)
    else:
        content = file_content
```

#### Vuetify2 vs Vuetify3 Property Differences
| Vuetify3 | Vuetify2 |
|----------|----------|
| `density="compact"` | `dense=True` |
| `variant="outlined"` | `outlined=True` |
| `variant="text"` | `text=True` |
| `size="x-small"` | `x_small=True` |

### VTK Integration

#### Required Imports (Order Matters!)
```python
import vtkmodules.vtkRenderingOpenGL2  # noqa - must be first
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleSwitch  # noqa - factory init
```

#### VTK Render Pipeline Setup
```python
renderer = vtkRenderer()
render_window = vtkRenderWindow()
render_window.AddRenderer(renderer)
render_window.OffScreenRenderingOn()  # Required for trame

interactor = vtkRenderWindowInteractor()
interactor.SetRenderWindow(render_window)
interactor.GetInteractorStyle().SetCurrentStyleToTrackballCamera()

# Initial render before UI
render_window.Render()
```

#### After Adding Actors
Always call these after modifying the scene:
```python
self.renderer.AddActor(actor)
self.renderer.ResetCamera()
self.render_window.Render()

# Then update the trame view
if hasattr(self.ctrl, 'view_update') and self.ctrl.view_update:
    self.ctrl.view_update()
```

#### VtkRemoteView Setup
```python
with layout.content:
    with vuetify.VContainer(fluid=True, classes="pa-0 fill-height"):
        view = vtk_widgets.VtkRemoteView(self.render_window)
        self.ctrl.view_update = view.update
        self.ctrl.view_reset_camera = view.reset_camera
```

## Common Issues and Solutions

### "Geometry not displaying"
1. Ensure `render_window.OffScreenRenderingOn()` is called
2. Call `render_window.Render()` after adding actors
3. Call `self.ctrl.view_update()` after scene changes
4. Check VTK import order (OpenGL2 first, then InteractionStyle)

### "JS Error: Cannot read properties of undefined"
- Avoid using `document.getElementById()` in click handlers
- Use trame's built-in event handling patterns
- Keep click methods in Python, not JavaScript

### "bytes-like object required" error in file upload
- File content from VFileInput can be `bytes` or `list` of bytes
- Always check: `if isinstance(content, list): content = b"".join(content)`

## File Structure
```
three_d_app/
├── app.py              # Main application
├── requirements.txt    # Python dependencies
├── setup.sh           # Environment setup script
├── samples/           # Sample STL files for testing
├── examples/          # Reference trame examples
│   ├── ClassRemoteRendering.py
│   └── upload.py
└── CLAUDE.md          # This file
```

## Running the Application
```bash
# Setup (first time)
./setup.sh

# Run
python3 app.py
# Open browser at http://localhost:8080
```

## Dependencies
- trame >= 3.0.0
- trame-vuetify >= 2.4.0
- trame-vtk >= 2.6.0
- vtk >= 9.2.0
- numpy >= 1.24.0
