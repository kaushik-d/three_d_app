#!/bin/bash
# Setup script for 3D CAD Viewer

set -e

echo "=============================================="
echo "  3D CAD Viewer - Setup Script"
echo "=============================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "Python version: $PYTHON_VERSION"

# Function to install using pip in user space (no venv)
install_user_space() {
    echo ""
    echo "Installing dependencies in user space..."

    # Check if pip is available, if not install it
    if ! python3 -m pip --version &> /dev/null; then
        echo "pip not found, installing pip..."
        curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
        python3 /tmp/get-pip.py --user
        rm /tmp/get-pip.py
        export PATH="$HOME/.local/bin:$PATH"
    fi

    echo "Installing dependencies..."
    python3 -m pip install --user --upgrade pip
    python3 -m pip install --user -r requirements.txt

    echo ""
    echo "=============================================="
    echo "  Setup Complete!"
    echo "=============================================="
    echo ""
    echo "To run the application:"
    echo "  1. Make sure ~/.local/bin is in your PATH:"
    echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "  2. Run the application:"
    echo "     python3 app.py"
    echo ""
    echo "  3. Open your browser at:"
    echo "     http://localhost:8080"
    echo ""
}

# Function to install using virtual environment
install_venv() {
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv

    # Activate virtual environment
    echo "Activating virtual environment..."
    source venv/bin/activate

    # Install dependencies
    echo ""
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt

    echo ""
    echo "=============================================="
    echo "  Setup Complete!"
    echo "=============================================="
    echo ""
    echo "To run the application:"
    echo "  1. Activate the virtual environment:"
    echo "     source venv/bin/activate"
    echo ""
    echo "  2. Run the application:"
    echo "     python app.py"
    echo ""
    echo "  3. Open your browser at:"
    echo "     http://localhost:8080"
    echo ""
}

# Check if venv exists and is valid
if [ -d "venv" ]; then
    if [ -f "venv/bin/activate" ]; then
        echo "Virtual environment already exists."
        echo "Activating and updating dependencies..."
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt

        echo ""
        echo "=============================================="
        echo "  Setup Complete!"
        echo "=============================================="
        echo ""
        echo "To run the application:"
        echo "  1. Activate the virtual environment:"
        echo "     source venv/bin/activate"
        echo ""
        echo "  2. Run the application:"
        echo "     python app.py"
        echo ""
        echo "  3. Open your browser at:"
        echo "     http://localhost:8080"
        echo ""
    else
        echo "Found incomplete venv directory. Removing and recreating..."
        rm -rf venv
        # Test if venv module is available
        if python3 -c "import venv" 2>/dev/null; then
            install_venv
        else
            echo ""
            echo "Warning: python3-venv is not installed."
            echo "To install it, run: sudo apt-get install python3-venv"
            echo ""
            echo "Falling back to user space installation..."
            install_user_space
        fi
    fi
else
    # Test if venv module is available
    if python3 -c "import venv" 2>/dev/null; then
        install_venv
    else
        echo ""
        echo "Warning: python3-venv is not installed."
        echo "To install it, run: sudo apt-get install python3-venv"
        echo ""
        echo "Falling back to user space installation..."
        install_user_space
    fi
fi
