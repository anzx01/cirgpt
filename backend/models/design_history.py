from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base


class DesignHistory(Base):
    """Design history model for version tracking"""
    __tablename__ = "design_history"

    id = Column(Integer, primary_key=True, index=True)
    design_id = Column(Integer, ForeignKey("circuit_designs.id"), nullable=False)
    version = Column(Integer, nullable=False)

    # Snapshot of design at this version
    description = Column(Text, nullable=False)
    netlist = Column(Text, nullable=True)
    schematic_svg = Column(Text, nullable=True)
    simulation_results = Column(JSON, nullable=True)
    pcb_layout = Column(JSON, nullable=True)
    bom = Column(JSON, nullable=True)

    # Change metadata
    change_description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    design = relationship("CircuitDesign", back_populates="history")

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "design_id": self.design_id,
            "version": self.version,
            "description": self.description,
            "netlist": self.netlist,
            "schematic_svg": self.schematic_svg,
            "simulation_results": self.simulation_results,
            "pcb_layout": self.pcb_layout,
            "bom": self.bom,
            "change_description": self.change_description,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
