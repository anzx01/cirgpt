"""
CircuitBERT model loader and inference
"""
try:
    import torch
    from transformers import AutoTokenizer, AutoModel
except ImportError:  # Optional in the KiCad-first MVP.
    torch = None
    AutoTokenizer = None
    AutoModel = None
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class CircuitBERTModel:
    """CircuitBERT model for circuit design understanding"""

    def __init__(self, model_name: str = "microsoft/circuit-bert"):
        """
        Initialize CircuitBERT model

        Args:
            model_name: Hugging Face model name or local path
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        if torch is None:
            self.device = None
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")

    def load(self):
        """Load the model and tokenizer"""
        try:
            if torch is None or AutoTokenizer is None or AutoModel is None:
                raise RuntimeError("torch/transformers are not installed")
            logger.info(f"Loading CircuitBERT model: {self.model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info("✓ CircuitBERT model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load CircuitBERT model: {e}")
            logger.warning("Will use rule-based fallback instead")
            raise

    def encode_text(self, text: str):
        """
        Encode text using CircuitBERT

        Args:
            text: Input text

        Returns:
            Encoded tensor
        """
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model not loaded. Call load() first.")

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512
        )

        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        # Use [CLS] token representation
        return outputs.last_hidden_state[:, 0, :]

    def extract_components(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract electronic components from natural language description

        Args:
            text: Natural language description

        Returns:
            List of extracted components with attributes
        """
        # For MVP, use rule-based extraction combined with embeddings
        # This is a simplified approach - can be enhanced with fine-tuning

        components = []
        text_lower = text.lower()

        # Define component patterns
        component_patterns = {
            "resistor": ["resistor", "resistance", "ohm", "r"],
            "capacitor": ["capacitor", "cap", "farad", "uf", "pf"],
            "inductor": ["inductor", "inductance", "henry", "l"],
            "diode": ["diode", "led", "d"],
            "transistor": ["transistor", "bjt", "mosfet", "q"],
            "ic": ["555", "op-amp", "operational amplifier", "timer", "microcontroller"],
            "battery": ["battery", "power supply", "voltage source", "vcc"],
            "switch": ["switch", "button"],
            "sensor": ["sensor", "thermistor", "photodiode"]
        }

        # Extract components based on patterns
        for component_type, keywords in component_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                # Extract values using simple patterns
                component = {
                    "type": component_type,
                    "count": text_lower.count(component_type) if component_type in text_lower else 1
                }

                # Try to extract numeric values
                import re
                numbers = re.findall(r'\d+\.?\d*', text)
                if numbers:
                    component["values"] = [float(n) for n in numbers[:3]]  # Take first 3 numbers

                components.append(component)

        return components

    def extract_circuit_topology(self, text: str) -> Dict[str, Any]:
        """
        Extract circuit topology from description

        Args:
            text: Natural language description

        Returns:
            Dictionary with topology information
        """
        text_lower = text.lower()

        topology = {
            "type": "unknown",
            "configuration": "unknown",
            "features": []
        }

        # Detect circuit type
        circuit_types = {
            "amplifier": ["amplifier", "amplify", "gain"],
            "filter": ["filter", "low-pass", "high-pass", "band-pass"],
            "oscillator": ["oscillator", "astable", "multivibrator", "blinker"],
            "timer": ["timer", "delay", "pulse"],
            "power_supply": ["power supply", "voltage regulator", "rectifier"],
            "led_driver": ["led", "blink", "flash"]
        }

        for circuit_type, keywords in circuit_types.items():
            if any(keyword in text_lower for keyword in keywords):
                topology["type"] = circuit_type
                break

        # Detect configuration
        configurations = {
            "common_emitter": ["common emitter", "ce"],
            "common_collector": ["common collector", "emitter follower"],
            "inverting": ["inverting", "inverter"],
            "non-inverting": ["non-inverting", "buffer"],
            "differential": ["differential", "diff"],
            "series": ["series"],
            "parallel": ["parallel"]
        }

        for config, keywords in configurations.items():
            if any(keyword in text_lower for keyword in keywords):
                topology["configuration"] = config
                topology["features"].append(config)

        # Extract additional features
        features = {
            "feedback": ["feedback", "negative feedback", "positive feedback"],
            "gain_control": ["gain", "amplification"],
            "timing": ["timing", "frequency", "period", "duty cycle"],
            "pwm": ["pwm", "pulse width modulation"]
        }

        for feature, keywords in features.items():
            if any(keyword in text_lower for keyword in keywords):
                topology["features"].append(feature)

        return topology

    def parse_requirements(self, text: str) -> Dict[str, Any]:
        """
        Parse natural language circuit requirements

        Args:
            text: Natural language description

        Returns:
            Parsed requirements dictionary
        """
        logger.info(f"Parsing requirements: {text[:100]}...")

        # Extract components and topology
        components = self.extract_components(text)
        topology = self.extract_circuit_topology(text)

        # Extract specifications
        import re
        specs = {}

        # Extract voltage
        voltages = re.findall(r'(\d+\.?\d*)\s*v', text.lower())
        if voltages:
            specs["voltage"] = float(voltages[0])

        # Extract current
        currents = re.findall(r'(\d+\.?\d*)\s*(ma|a)', text.lower())
        if currents:
            value, unit = currents[0]
            specs["current"] = float(value) * (0.001 if unit == "ma" else 1)

        # Extract frequency
        frequencies = re.findall(r'(\d+\.?\d*)\s*(hz|khz|mhz)', text.lower())
        if frequencies:
            value, unit = frequencies[0]
            multipliers = {"hz": 1, "khz": 1000, "mhz": 1000000}
            specs["frequency"] = float(value) * multipliers[unit]

        # Extract resistance values
        resistances = re.findall(r'(\d+\.?\d*)\s*(k?|m?)\s*ohm', text.lower())
        if resistances:
            values = []
            for r in resistances:
                value, prefix = r[0], r[1] if len(r) > 1 else ""
                multipliers = {"k": 1000, "m": 1000000, "": 1}
                values.append(float(value) * multipliers[prefix])
            specs["resistances"] = values

        return {
            "description": text,
            "components": components,
            "topology": topology,
            "specifications": specs
        }


# Global model instance
_model_instance = None


def get_model() -> CircuitBERTModel:
    """Get or create global model instance"""
    global _model_instance
    if _model_instance is None:
        _model_instance = CircuitBERTModel()
        try:
            _model_instance.load()
        except Exception as e:
            logger.warning(f"Failed to load CircuitBERT, will use fallback: {e}")
    return _model_instance
