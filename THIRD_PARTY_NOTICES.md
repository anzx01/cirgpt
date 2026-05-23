# Third-Party Notices

This repository is licensed under the ISC License. It depends on third-party
open-source packages and external EDA tools that remain under their own
licenses.

## Runtime Dependencies

Python dependencies are declared in:

- `backend/requirements.txt`
- `ai_service/requirements.txt`
- `eda_tools/requirements.txt`

Frontend dependencies are declared in:

- `frontend/package.json`
- `frontend/package-lock.json`

Before publishing a binary distribution or hosted service image, generate a
complete dependency license report from the lock files and installed packages.

## External Tools

The project integrates with tools such as ngspice, KiCad, SKiDL, PySpice, and
netlistsvg. These tools are not owned by this project and are not redistributed
from this repository. Install them from their official upstream sources and
review their licenses separately.

## SPICE Models And Vendor Files

Vendor SPICE models, simulator bundles, downloaded model weights, local
virtual environments, and generated runtime files must not be committed to this
repository unless their redistribution rights have been reviewed and documented.

The local `Spice64/` directory is intentionally ignored and removed from Git
tracking because it contains third-party ngspice examples and vendor model
files with separate copyright and license terms.
