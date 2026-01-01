#!/usr/bin/env python3
"""
Generate sample STL files for testing the 3D CAD Viewer.
"""

import struct
import math
import os


def write_binary_stl(filename, triangles):
    """Write triangles to a binary STL file."""
    with open(filename, "wb") as f:
        # Header (80 bytes)
        header = b"Binary STL generated for 3D CAD Viewer testing" + b"\0" * 34
        f.write(header[:80])

        # Number of triangles
        f.write(struct.pack("<I", len(triangles)))

        # Write each triangle
        for normal, v1, v2, v3 in triangles:
            # Normal vector
            f.write(struct.pack("<fff", *normal))
            # Vertices
            f.write(struct.pack("<fff", *v1))
            f.write(struct.pack("<fff", *v2))
            f.write(struct.pack("<fff", *v3))
            # Attribute byte count
            f.write(struct.pack("<H", 0))


def create_cube(size=50, offset=(0, 0, 0)):
    """Create a cube geometry."""
    triangles = []
    s = size / 2
    ox, oy, oz = offset

    # Define cube vertices
    vertices = [
        (-s + ox, -s + oy, -s + oz),  # 0
        (s + ox, -s + oy, -s + oz),  # 1
        (s + ox, s + oy, -s + oz),  # 2
        (-s + ox, s + oy, -s + oz),  # 3
        (-s + ox, -s + oy, s + oz),  # 4
        (s + ox, -s + oy, s + oz),  # 5
        (s + ox, s + oy, s + oz),  # 6
        (-s + ox, s + oy, s + oz),  # 7
    ]

    # Define faces (each face has 2 triangles)
    faces = [
        # Front face
        ((0, 0, -1), [0, 1, 2], [0, 2, 3]),
        # Back face
        ((0, 0, 1), [4, 6, 5], [4, 7, 6]),
        # Top face
        ((0, 1, 0), [3, 2, 6], [3, 6, 7]),
        # Bottom face
        ((0, -1, 0), [0, 5, 1], [0, 4, 5]),
        # Right face
        ((1, 0, 0), [1, 5, 6], [1, 6, 2]),
        # Left face
        ((-1, 0, 0), [0, 3, 7], [0, 7, 4]),
    ]

    for normal, tri1, tri2 in faces:
        triangles.append(
            (normal, vertices[tri1[0]], vertices[tri1[1]], vertices[tri1[2]])
        )
        triangles.append(
            (normal, vertices[tri2[0]], vertices[tri2[1]], vertices[tri2[2]])
        )

    return triangles


def create_sphere(radius=30, resolution=16, offset=(0, 0, 0)):
    """Create a sphere geometry using icosphere subdivision."""
    triangles = []
    ox, oy, oz = offset

    # Create UV sphere
    for i in range(resolution):
        lat0 = math.pi * (-0.5 + float(i) / resolution)
        lat1 = math.pi * (-0.5 + float(i + 1) / resolution)
        z0 = math.sin(lat0) * radius
        z1 = math.sin(lat1) * radius
        r0 = math.cos(lat0) * radius
        r1 = math.cos(lat1) * radius

        for j in range(resolution * 2):
            lon0 = 2 * math.pi * float(j) / (resolution * 2)
            lon1 = 2 * math.pi * float(j + 1) / (resolution * 2)

            x00 = math.cos(lon0) * r0 + ox
            y00 = math.sin(lon0) * r0 + oy
            x01 = math.cos(lon1) * r0 + ox
            y01 = math.sin(lon1) * r0 + oy
            x10 = math.cos(lon0) * r1 + ox
            y10 = math.sin(lon0) * r1 + oy
            x11 = math.cos(lon1) * r1 + ox
            y11 = math.sin(lon1) * r1 + oy

            v0 = (x00, y00, z0 + oz)
            v1 = (x01, y01, z0 + oz)
            v2 = (x10, y10, z1 + oz)
            v3 = (x11, y11, z1 + oz)

            # Calculate normals (pointing outward)
            def normalize(v):
                length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
                if length > 0:
                    return (v[0] / length, v[1] / length, v[2] / length)
                return (0, 0, 1)

            n0 = normalize((v0[0] - ox, v0[1] - oy, v0[2] - oz))
            n1 = normalize((v1[0] - ox, v1[1] - oy, v1[2] - oz))
            n2 = normalize((v2[0] - ox, v2[1] - oy, v2[2] - oz))
            n3 = normalize((v3[0] - ox, v3[1] - oy, v3[2] - oz))

            # Average normal for face
            def avg_normal(n1, n2, n3):
                return normalize(
                    (
                        (n1[0] + n2[0] + n3[0]) / 3,
                        (n1[1] + n2[1] + n3[1]) / 3,
                        (n1[2] + n2[2] + n3[2]) / 3,
                    )
                )

            if i != 0:
                triangles.append((avg_normal(n0, n1, n2), v0, v1, v2))
            if i != resolution - 1:
                triangles.append((avg_normal(n1, n3, n2), v1, v3, v2))

    return triangles


def create_cylinder(radius=20, height=60, resolution=32, offset=(0, 0, 0)):
    """Create a cylinder geometry."""
    triangles = []
    ox, oy, oz = offset
    h2 = height / 2

    for i in range(resolution):
        a0 = 2 * math.pi * i / resolution
        a1 = 2 * math.pi * (i + 1) / resolution

        x0 = math.cos(a0) * radius + ox
        y0 = math.sin(a0) * radius + oy
        x1 = math.cos(a1) * radius + ox
        y1 = math.sin(a1) * radius + oy

        # Side faces
        v0 = (x0, y0, -h2 + oz)
        v1 = (x1, y1, -h2 + oz)
        v2 = (x0, y0, h2 + oz)
        v3 = (x1, y1, h2 + oz)

        n0 = (math.cos(a0), math.sin(a0), 0)
        n1 = (math.cos(a1), math.sin(a1), 0)
        nav = ((n0[0] + n1[0]) / 2, (n0[1] + n1[1]) / 2, 0)

        triangles.append((nav, v0, v1, v2))
        triangles.append((nav, v1, v3, v2))

        # Top cap
        triangles.append(((0, 0, 1), (ox, oy, h2 + oz), v2, v3))

        # Bottom cap
        triangles.append(((0, 0, -1), (ox, oy, -h2 + oz), v1, v0))

    return triangles


def create_pyramid(base=40, height=50, offset=(0, 0, 0)):
    """Create a pyramid geometry."""
    triangles = []
    ox, oy, oz = offset
    b = base / 2

    # Base vertices
    v0 = (-b + ox, -b + oy, oz)
    v1 = (b + ox, -b + oy, oz)
    v2 = (b + ox, b + oy, oz)
    v3 = (-b + ox, b + oy, oz)
    apex = (ox, oy, height + oz)

    # Base (2 triangles)
    triangles.append(((0, 0, -1), v0, v2, v1))
    triangles.append(((0, 0, -1), v0, v3, v2))

    # Side faces
    def calc_normal(v1, v2, v3):
        ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        vx, vy, vz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length > 0:
            return (nx / length, ny / length, nz / length)
        return (0, 0, 1)

    triangles.append((calc_normal(v0, v1, apex), v0, v1, apex))
    triangles.append((calc_normal(v1, v2, apex), v1, v2, apex))
    triangles.append((calc_normal(v2, v3, apex), v2, v3, apex))
    triangles.append((calc_normal(v3, v0, apex), v3, v0, apex))

    return triangles


def main():
    """Generate sample STL files."""
    samples_dir = os.path.dirname(os.path.abspath(__file__))
    samples_dir = os.path.join(samples_dir, "samples")
    os.makedirs(samples_dir, exist_ok=True)

    print("Generating sample STL files...")

    # Create individual files
    write_binary_stl(os.path.join(samples_dir, "cube.stl"), create_cube(50))
    print("  - Created cube.stl (12 triangles)")

    write_binary_stl(os.path.join(samples_dir, "sphere.stl"), create_sphere(30, 16))
    print("  - Created sphere.stl (sphere geometry)")

    write_binary_stl(
        os.path.join(samples_dir, "cylinder.stl"), create_cylinder(20, 60, 32)
    )
    print("  - Created cylinder.stl (cylinder geometry)")

    write_binary_stl(os.path.join(samples_dir, "pyramid.stl"), create_pyramid(40, 50))
    print("  - Created pyramid.stl (6 triangles)")

    # Create a combined assembly
    assembly = []
    assembly.extend(create_cube(30, (-50, 0, 0)))
    assembly.extend(create_sphere(20, 12, (50, 0, 0)))
    assembly.extend(create_cylinder(15, 40, 24, (0, 50, 0)))
    assembly.extend(create_pyramid(25, 35, (0, -50, 0)))

    write_binary_stl(os.path.join(samples_dir, "assembly.stl"), assembly)
    print("  - Created assembly.stl (combined geometry)")

    print(f"\nSample files created in: {samples_dir}")
    print("\nYou can now open these files in the 3D CAD Viewer!")


if __name__ == "__main__":
    main()
