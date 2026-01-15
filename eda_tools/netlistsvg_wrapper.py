"""
netlistsvg Integration Wrapper
Interface to netlistsvg tool for generating SVG schematics from KiCad netlists
"""
import subprocess
import json
import os
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path


class NetlistSVGGenerator:
    """Wrapper for netlistsvg command-line tool"""

    def __init__(self, netlistsvg_path: str = None):
        """
        Initialize netlistsvg wrapper

        Args:
            netlistsvg_path: Path to netlistsvg executable (default: auto-detect)
        """
        if netlistsvg_path is None:
            # Try to auto-detect from npm global installation
            import os
            npm_path = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'npm', 'netlistsvg.cmd')
            if os.path.exists(npm_path):
                netlistsvg_path = npm_path
            else:
                netlistsvg_path = 'netlistsvg'  # Fall back to PATH

        self.netlistsvg_path = netlistsvg_path
        self.verify_installation()

    def verify_installation(self) -> bool:
        """Check if netlistsvg is installed and accessible"""
        try:
            result = subprocess.run(
                [self.netlistsvg_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Exit code 1 with usage message means it's installed
            return 'usage' in result.stderr.lower() or 'input_json_file' in result.stderr.lower()
        except FileNotFoundError:
            raise RuntimeError(
                "netlistsvg not found! Install it with: npm install -g netlistsvg\n"
                "Also ensure Node.js is in your system PATH."
            )
        except Exception as e:
            print(f"Warning: Could not verify netlistsvg: {e}")
            return False

    def generate(
        self,
        kicad_netlist: Dict[str, Any],
        output_file: Optional[str] = None,
        skin_file: Optional[str] = None
    ) -> str:
        """
        Generate SVG schematic from KiCad netlist

        Args:
            kicad_netlist: KiCad netlist as dictionary
            output_file: Optional output SVG file path
            skin_file: Optional custom skin file for styling

        Returns:
            SVG string
        """
        # Create temporary files for netlistsvg
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as netlist_file:
            json.dump(kicad_netlist, netlist_file, indent=2)
            netlist_path = netlist_file.name

        try:
            # Prepare output file path
            if output_file is None:
                output_file = tempfile.mktemp(suffix='.svg')

            # Build command
            cmd = [self.netlistsvg_path, netlist_path, '-o', output_file]

            # Add skin if provided
            if skin_file:
                cmd.extend(['--skin', skin_file])

            # Run netlistsvg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise RuntimeError(
                    f"netlistsvg failed:\n{error_msg}\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"Netlist saved to: {netlist_path}"
                )

            # Read generated SVG
            with open(output_file, 'r', encoding='utf-8') as f:
                svg_content = f.read()

            return svg_content

        finally:
            # Clean up temporary files
            try:
                os.unlink(netlist_path)
            except:
                pass

            if output_file and output_file.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(output_file)
                except:
                    pass

    def generate_from_spice(
        self,
        spice_data: Dict[str, Any],
        output_file: Optional[str] = None
    ) -> str:
        """
        Convenience method: generate SVG directly from SPICE data

        Args:
            spice_data: Parsed SPICE data from SPICEParser
            output_file: Optional output SVG file path

        Returns:
            SVG string
        """
        from eda_tools.kicad_netlist import KiCadNetlistConverter

        # Convert SPICE to KiCad netlist
        converter = KiCadNetlistConverter()
        kicad_netlist = converter.convert(spice_data)

        # Generate SVG
        return self.generate(kicad_netlist, output_file)

    def save_svg(
        self,
        kicad_netlist: Dict[str, Any],
        filename: str,
        skin_file: Optional[str] = None
    ):
        """
        Generate and save SVG to file

        Args:
            kicad_netlist: KiCad netlist dictionary
            filename: Output SVG file path
            skin_file: Optional custom skin file
        """
        svg = self.generate(kicad_netlist, filename, skin_file)
        print(f"SVG saved to: {filename}")
        return svg


def generate_schematic_svg(spice_data: Dict[str, Any]) -> str:
    """
    Convenience function to generate SVG schematic from SPICE data

    Args:
        spice_data: Parsed SPICE data

    Returns:
        SVG string
    """
    generator = NetlistSVGGenerator()
    return generator.generate_from_spice(spice_data)


# For testing
if __name__ == '__main__':
    # Test with 555 timer circuit
    test_netlist = """* 555 Timer LED Blinker
V1 VCC 0 DC 9
R1 VCC 7 1k
R2 7 6 71.5k
C1 6 0 10u
C2 5 0 10n
R3 3 700 220
D1 700 0 LED
XU1 1 2 3 4 8 7 6 5 NE555
"""

    from eda_tools.spice_parser import SPICEParser

    parser = SPICEParser()
    spice_data = parser.parse(test_netlist)

    generator = NetlistSVGGenerator()
    svg = generator.generate_from_spice(spice_data, 'test_schematic.svg')

    print(f"Generated SVG: {len(svg)} bytes")
    print(f"SVG contains 'NE555': {'NE555' in svg}")
    print(f"SVG contains '<rect': {'<rect' in svg}")
