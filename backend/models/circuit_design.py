from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base


class CircuitDesign(Base):
    """Circuit design model"""
    __tablename__ = "circuit_designs"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text, nullable=False)  # Natural language description
    status = Column(String(50), default="pending")  # pending, processing, completed, failed

    # Design results
    parsed_requirements = Column(JSON, nullable=True)  # AI parsed requirements
    netlist = Column(Text, nullable=True)  # Generated netlist
    schematic_svg = Column(Text, nullable=True)  # Schematic in SVG format
    schematic_png = Column(Text, nullable=True)  # Base64 PNG image

    # Simulation results
    simulation_results = Column(JSON, nullable=True)  # Waveform data
    simulation_status = Column(String(50), nullable=True)  # success, failed

    # PCB layout
    pcb_layout = Column(JSON, nullable=True)  # PCB layout data
    pcb_gerber_files = Column(JSON, nullable=True)  # Paths to Gerber files
    pcb_image = Column(Text, nullable=True)  # Base64 PNG image

    # BOM
    bom = Column(JSON, nullable=True)  # Bill of materials
    estimated_cost = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)

    # Relationships
    history = relationship("DesignHistory", back_populates="design", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "parsed_requirements": self.parsed_requirements,
            "netlist": self.netlist,
            "schematic_svg": self.schematic_svg,
            "schematic_png": self.schematic_png,
            "simulation_results": self.simulation_results,
            "simulation_status": self.simulation_status,
            "pcb_layout": self.pcb_layout,
            "pcb_gerber_files": self.pcb_gerber_files,
            "pcb_image": self.pcb_image,
            "bom": self.bom,
            "estimated_cost": self.estimated_cost,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message
        }
